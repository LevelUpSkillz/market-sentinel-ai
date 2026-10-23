"""Narrow Kraken spot REST adapter; authorization and durable state live above it.

No retries, withdrawals, margin, arbitrary hosts, or credential logging. An IOC
order can fill partly; a transport failure after submission is an unknown result,
never permission to resend. All tests use httpx.MockTransport.

Contracts checked against Kraken's current official documentation:
https://docs.kraken.com/exchange/guides/rest/authentication
https://docs.kraken.com/api-reference/trading/add-order
https://docs.kraken.com/api-reference/account-data/get-extended-balance
https://docs.kraken.com/api-reference/account-data/query-orders-info
"""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import hmac
import inspect
import json
import re
from urllib.parse import urlencode
from uuid import UUID

import httpx

ORIGIN = 'https://api.kraken.com'
_PRIVATE = frozenset({'GetApiKeyInfo','BalanceEx','OpenOrders','ClosedOrders','OpenPositions','TradeVolume','AddOrder'})
_PAIR = re.compile(r'[A-Za-z0-9_.]{2,40}\Z')
_NUMBER = re.compile(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')
_ORDER_KEYS = frozenset({'status','opentm','closetm','starttm','expiretm','reason','vol','vol_exec','cost','fee','price','stopprice','limitprice','misc','oflags','trades','cl_ord_id'})


class KrakenError(ValueError):
    """Safe to expose; no provider body, credentials, request, or error chain."""
    def __init__(self, code, message, *, uncertain=False):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


def _error(code, *, uncertain=False):
    messages = {
        'credentials':'Kraken credentials are unavailable or invalid.',
        'nonce':'Kraken request nonce is unavailable or invalid.',
        'input':'Kraken order or request fields are invalid.',
        'authentication':'Kraken rejected account authorization. Review the linked key permissions.',
        'rate_limit':'Kraken rate limit reached. Retry a read later.',
        'rejected':'Kraken rejected the request. Refresh account and market checks.',
        'unavailable':'Kraken is unavailable. No account data or order result is substituted.',
        'response':'Kraken returned an incomplete or invalid response.',
        'submission_unknown':'Kraken submission outcome is unknown. Reconcile the client order ID; do not submit it again.',
    }
    return KrakenError(code,messages[code],uncertain=uncertain)


def signature(path, nonce, encoded_payload, secret):
    """Sign the exact bytes sent, using Kraken's published signing algorithm."""
    try:
        decoded = base64.b64decode(secret,validate=True)
        if not decoded:
            raise ValueError()
        body = encoded_payload.encode('ascii') if isinstance(encoded_payload,str) else encoded_payload
        digest = hashlib.sha256(str(nonce).encode('ascii')+body).digest()
        return base64.b64encode(hmac.new(decoded,path.encode('ascii')+digest,hashlib.sha512).digest()).decode('ascii')
    except (ValueError,TypeError,UnicodeError):
        raise _error('credentials') from None


def _decimal(value):
    try:
        # Never turn a binary float, non-finite value or boolean into account money.
        if isinstance(value,(float,bool)) or value is None:
            raise ValueError()
        result = Decimal(value)
        if not result.is_finite() or len(result.as_tuple().digits)>80 or abs(result.adjusted())>80:
            raise ValueError()
        return result
    except (InvalidOperation,ValueError,TypeError):
        raise _error('response') from None


def _strings(value):
    if isinstance(value,Decimal):
        return format(_decimal(value),'f')
    if isinstance(value,dict):
        return {key:_strings(item) for key,item in value.items()}
    if isinstance(value,list):
        return [_strings(item) for item in value]
    return value


def _pair(value):
    if not isinstance(value,str) or not _PAIR.fullmatch(value):
        raise _error('input')
    return value


def _client_id(value):
    try:
        if not isinstance(value,str) or len(value)!=36 or str(UUID(value))!=value.lower():
            raise ValueError()
    except (ValueError,AttributeError):
        raise _error('input') from None
    return value


@dataclass(frozen=True,slots=True)
class LimitOrder:
    """Immutable spot IOC instruction, approved by the caller before submission."""
    pair: str
    side: str
    volume: str
    price: str
    cl_ord_id: str
    deadline: str

    def __post_init__(self):
        _pair(self.pair)
        _client_id(self.cl_ord_id)
        if self.side not in ('buy','sell'):
            raise _error('input')
        for value in (self.volume,self.price):
            if not isinstance(value,str) or len(value)>80 or not _NUMBER.fullmatch(value) or Decimal(value)<=0:
                raise _error('input')
        try:
            if not isinstance(self.deadline,str) or not self.deadline.endswith('Z'):
                raise ValueError()
            at = datetime.fromisoformat(self.deadline[:-1]+'+00:00')
            if at.tzinfo!=timezone.utc:
                raise ValueError()
        except (ValueError,TypeError):
            raise _error('input') from None

    def payload(self):
        return {'ordertype':'limit','pair':self.pair,'type':self.side,'volume':self.volume,
                'price':self.price,'cl_ord_id':self.cl_ord_id,'deadline':self.deadline,
                'timeinforce':'IOC','oflags':'fciq'}


class KrakenClient:
    def __init__(self, api_key, api_secret, nonce_factory, client=None):
        # Validate before creating headers. Credentials remain private attributes.
        if (not isinstance(api_key,str) or not 1<=len(api_key)<=512 or
                any(ord(char)<33 or ord(char)>126 for char in api_key) or
                not isinstance(api_secret,str) or len(api_secret)>1024 or not callable(nonce_factory)):
            raise _error('credentials')
        signature('/0/private/GetApiKeyInfo','1','nonce=1',api_secret)
        self._api_key,self._api_secret,self._nonce_factory = api_key,api_secret,nonce_factory
        self._client = client

    def __repr__(self):
        return '<KrakenClient credentials=redacted>'

    async def _private(self, method, fields=None, *, submission=False):
        if method not in _PRIVATE:
            raise _error('input')
        # The callback must reserve an increasing nonce in a committed durable
        # transaction shared by all requests for this key, including after restart.
        try:
            nonce = self._nonce_factory()
            if inspect.isawaitable(nonce):
                nonce = await nonce
            if isinstance(nonce,bool) or not isinstance(nonce,(str,int)) or not str(nonce).isdigit() or not 0<int(nonce)<2**64:
                raise ValueError()
            nonce = str(nonce)
        except Exception:
            raise _error('nonce') from None
        payload = {'nonce':nonce,**(fields or {})}
        path = '/0/private/'+method
        encoded = urlencode(payload)
        headers = {'API-Key':self._api_key,'API-Sign':signature(path,nonce,encoded,self._api_secret),
                   'Content-Type':'application/x-www-form-urlencoded'}
        return await self._request('POST',path,content=encoded,headers=headers,submission=submission)

    async def _request(self, method, path, *, submission=False, **kwargs):
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10,follow_redirects=False)
        try:
            try:
                response = await client.request(method,ORIGIN+path,follow_redirects=False,timeout=10,**kwargs)
            except httpx.HTTPError:
                raise _error('submission_unknown' if submission else 'unavailable',uncertain=submission) from None
            # A gateway/redirect/malformed response after AddOrder cannot prove
            # that matching-engine submission failed. Never follow or retry it.
            if response.status_code!=200:
                code = 'rate_limit' if response.status_code==429 else 'authentication' if response.status_code in (401,403) else 'unavailable'
                if submission:
                    raise _error('submission_unknown',uncertain=True)
                raise _error(code)
            if len(response.content)>1024*1024:
                raise _error('submission_unknown' if submission else 'response',uncertain=submission)
            try:
                row = json.loads(response.text,parse_float=Decimal)
            except (ValueError,UnicodeError):
                raise _error('submission_unknown' if submission else 'response',uncertain=submission) from None
            if not isinstance(row,dict) or not isinstance(row.get('error'),list):
                raise _error('submission_unknown' if submission else 'response',uncertain=submission)
            errors = row['error']
            if errors:
                # Use fixed messages only; provider errors can contain user text.
                values = [item for item in errors if isinstance(item,str)]
                definite = ('EAPI:Invalid key','EAPI:Invalid signature','EAPI:Invalid nonce',
                            'EGeneral:Permission denied','EGeneral:Invalid arguments',
                            'EOrder:Insufficient funds','EOrder:Order minimum not met',
                            'EOrder:Cost minimum not met','EOrder:Tick size check failed',
                            'EOrder:Invalid price','EOrder:Invalid volume')
                if submission and (len(values)!=len(errors) or not all(item.startswith(definite) for item in values)):
                    # Deadline elapsed, duplicate client IDs, internal/unknown
                    # errors can coexist with an accepted order. Reconcile only.
                    raise _error('submission_unknown',uncertain=True)
                code = 'authentication' if any(item.startswith(('EAPI:Invalid key','EAPI:Invalid signature','EGeneral:Permission denied')) for item in values) else 'rate_limit' if any('Rate limit' in item or 'Throttled' in item for item in values) else 'nonce' if any(item.startswith('EAPI:Invalid nonce') for item in values) else 'rejected'
                raise _error(code)
            if not isinstance(row.get('result'),dict):
                raise _error('submission_unknown' if submission else 'response',uncertain=submission)
            return row['result']
        finally:
            if owns_client:
                await client.aclose()

    async def key_info(self):
        row = await self._private('GetApiKeyInfo')
        permissions = row.get('permissions')
        if not isinstance(permissions,list) or not all(isinstance(item,str) for item in permissions):
            raise _error('response')
        result = {'permissions':permissions}
        for field in ('validUntil','queryFrom','queryTo'):
            value = row.get(field,'0')
            if not isinstance(value,(str,int)) or not str(value).isdigit():
                raise _error('response')
            result[field] = str(value)
        result['ip_allowlist_configured'] = bool(row.get('ipAllowlist'))
        return result

    async def balances(self):
        row = await self._private('BalanceEx')
        result = {}
        for asset,values in row.items():
            if not isinstance(values,dict) or 'balance' not in values or 'hold_trade' not in values:
                raise _error('response')
            balance,credit,used,held = (_decimal(values.get(field,'0')) for field in ('balance','credit','credit_used','hold_trade'))
            if credit<0 or used<0 or held<0:
                raise _error('response')
            with localcontext() as context:
                context.prec = 180
                available = balance+credit-used-held
                spot_available = max(Decimal(0),min(balance-held,available))
            result[asset] = {key:format(value,'f') for key,value in {
                'balance':balance,'credit':credit,'credit_used':used,'hold_trade':held,
                'available':available,'spot_available':spot_available}.items()}
        return result

    @staticmethod
    def _orders(values):
        if not isinstance(values,dict):
            raise _error('response')
        orders = {}
        for txid,row in values.items():
            if not isinstance(row,dict):
                raise _error('response')
            order = {key:_strings(value) for key,value in row.items() if key in _ORDER_KEYS}
            if isinstance(row.get('descr'),dict):
                order['descr'] = {key:_strings(value) for key,value in row['descr'].items() if key in {'pair','type','ordertype','price','price2','leverage'}}
            orders[txid] = order
        return orders

    async def open_orders(self):
        row = await self._private('OpenOrders',{'trades':'true'})
        return self._orders(row.get('open'))

    async def open_positions(self):
        row = await self._private('OpenPositions',{'docalcs':'true'})
        if not all(isinstance(value,dict) for value in row.values()):
            raise _error('response')
        # Position records are returned for the caller's margin exclusion check;
        # no margin-capable order method exists in this adapter.
        allowed = {'ordertxid','posstatus','pair','time','type','ordertype','cost','fee',
                   'vol','vol_closed','margin','value','net','leverage','rollovertm'}
        return {txid:{key:_strings(value) for key,value in position.items() if key in allowed}
                for txid,position in row.items()}

    async def fees(self,pair):
        row = await self._private('TradeVolume',{'pair':_pair(pair)})
        fees = row.get('fees')
        if not isinstance(fees,dict) or not fees:
            raise _error('response')
        result = {}
        for name,values in fees.items():
            if not isinstance(values,dict) or 'fee' not in values:
                raise _error('response')
            rate = _decimal(values['fee'])
            if not Decimal(0)<=rate<=Decimal(100):
                raise _error('response')
            result[name] = {'fee':format(rate,'f')}
        return {'fees':result,'fee_units':'percent'}

    async def asset_pairs(self,pair,country_code=None):
        params = {'pair':_pair(pair)}
        if country_code is not None:
            if not isinstance(country_code,str) or not re.fullmatch(r'[A-Z]{2}',country_code):
                raise _error('input')
            params['country_code'] = country_code
        row = await self._request('GET','/0/public/AssetPairs',params=params)
        if not row or not all(isinstance(value,dict) for value in row.values()):
            raise _error('response')
        return _strings(row)

    async def validate_limit_order(self,order):
        if not isinstance(order,LimitOrder):
            raise _error('input')
        row = await self._private('AddOrder',{**order.payload(),'validate':'true'})
        # Kraken validation has no transaction ID and never creates an order.
        if row.get('txid'):
            raise _error('response')
        return {'validated':True,'submitted':False,'cl_ord_id':order.cl_ord_id}

    async def submit_limit_order(self,order):
        if not isinstance(order,LimitOrder):
            raise _error('input')
        row = await self._private('AddOrder',{**order.payload(),'validate':'false'},submission=True)
        txids = row.get('txid')
        if not isinstance(txids,list) or len(txids)!=1 or not isinstance(txids[0],str) or not re.fullmatch(r'[A-Z0-9-]{5,64}',txids[0]):
            raise _error('submission_unknown',uncertain=True)
        return {'validated':False,'submitted':True,'cl_ord_id':order.cl_ord_id,'txid':txids}

    async def orders_by_client_id(self,cl_ord_id,submitted_at):
        """Read-only reconciliation. An empty result NEVER permits resubmission.

        QueryOrders needs a known Kraken txid. For an unknown AddOrder outcome,
        inspect both open and closed orders by client ID, including closed pages.
        """
        _client_id(cl_ord_id)
        try:
            start = max(0,int(submitted_at)-60)
        except (ValueError,TypeError,OverflowError):
            raise _error('input') from None
        opened = await self._private('OpenOrders',{'trades':'true','cl_ord_id':cl_ord_id})
        all_orders = self._orders(opened.get('open'))
        cursor = None
        seen = set()
        complete = False
        for _ in range(20):
            fields = {'trades':'true','cl_ord_id':cl_ord_id,'start':str(start),'closetime':'open','with_cursor':'true'}
            if cursor:
                fields['cursor'] = cursor
            closed = await self._private('ClosedOrders',fields)
            all_orders.update(self._orders(closed.get('closed')))
            pagination = closed.get('cursor') or {}
            if not isinstance(pagination,dict):
                raise _error('response')
            cursor = pagination.get('next')
            if not cursor:
                complete = True
                break
            if not isinstance(cursor,str) or len(cursor)>2048 or cursor in seen:
                raise _error('response')
            seen.add(cursor)
        # Provider-side filtering is not sufficient: match the exact ID locally.
        matches = {txid:row for txid,row in all_orders.items() if row.get('cl_ord_id')==cl_ord_id}
        return {'orders':matches,'complete':complete,'absence_proves_failure':False}

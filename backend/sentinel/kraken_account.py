"""Private-owner Kraken spot execution. No scheduler can approve an order.

Credentials are encrypted with a separately provisioned server key. Durable intent
is committed before AddOrder; an ambiguous response is never blindly retried.
"""
import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal as D
from cryptography.fernet import Fernet, InvalidToken
from .capital import get_profile
from .models import decimal
from .kraken import KrakenClient, KrakenError, LimitOrder

CONNECTION_KEY = 'connection:kraken'
ALLOWED_PERMISSIONS = {'query-funds','query-open-trades','query-closed-trades','modify-trades','close-trades'}
READ_PERMISSIONS = {'query-funds','query-open-trades','query-closed-trades'}
TRADE_PERMISSIONS = READ_PERMISSIONS | {'modify-trades','close-trades'}
PAIRS = {'BTC-USD':('XBTUSD','XXBT','ZUSD'),'ETH-USD':('ETHUSD','XETH','ZUSD'),'SOL-USD':('SOLUSD','SOL','ZUSD')}
ASSETS = {'XXBT':'BTC-USD','XBT':'BTC-USD','BTC':'BTC-USD','XETH':'ETH-USD','ETH':'ETH-USD','SOL':'SOL-USD'}
DISCLOSURES = [
    'This is your own manual spot order, not a recommendation or a validated profitable strategy.',
    'Immediate-or-cancel limit orders may fill partly or not at all. Submission is not a fill.',
    'No stop-loss is placed. For a buy, the full purchase and fee reserve count against your declared risk budget.',
    'Daily P&L and total trading capital are owner declarations, not independently verified account performance.',
    'No withdrawals, borrowing, leverage or autonomous trading. Render Free can sleep; inspect orders and fills directly in Kraken.',
]


class AccountError(ValueError):
    pass


class SerializedClient:
    """Serialize signed requests locally and across overlapping Render instances."""
    def __init__(self,client,store,lock,key):
        self.client,self.store,self.lock=client,store,lock
        self.lock_id=int.from_bytes(hashlib.sha256(('kraken:'+key).encode()).digest()[:8],'big',signed=True)

    def __getattr__(self,name):
        method=getattr(self.client,name)
        async def call(*args,**kwargs):
            async with self.lock:
                acquired=False
                if self.store.postgres:
                    with self.store.lock:
                        acquired=bool(self.store.execute('SELECT pg_try_advisory_lock(?) AS acquired',(self.lock_id,)).fetchone()['acquired'])
                    if not acquired:raise AccountError('Another account request is active. Wait and refresh; no order was sent.')
                try:return await method(*args,**kwargs)
                finally:
                    if acquired:
                        with self.store.lock:self.store.execute('SELECT pg_advisory_unlock(?)',(self.lock_id,))
        return call


def amount(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,12}(?:\.\d{1,12})?',value):
        raise AccountError('Enter a positive decimal amount using at most twelve decimal places.')
    out=decimal(value)
    if out<=0:raise AccountError('Order amounts must be positive.')
    return out


def text(value):
    return format(value,'f')


class KrakenAccount:
    def __init__(self,store,settings,books,client_factory=KrakenClient):
        self.store,self.settings,self.books,self.client_factory=store,settings,books,client_factory
        self.request_lock=asyncio.Lock()

    def _new_client(self,key,secret):
        return SerializedClient(self.client_factory(key,secret,lambda:self._nonce(key)),self.store,self.request_lock,key)

    @property
    def vault_ready(self):
        try:Fernet(self.settings.kraken_vault_key.encode());return True
        except (ValueError,TypeError,AttributeError):return False

    @property
    def enabled(self):
        return self.vault_ready and self.settings.kraken_live_enabled

    def status(self):
        saved=self.store.get_state(CONNECTION_KEY)
        connected=bool(saved and saved.get('cipher') and self.vault_ready)
        connection=None if not saved else {k:saved[k] for k in ('id','verified_at','permissions','can_trade')}
        active=self.store.get_state('kraken_live_active')
        active_doc=self.store.get('real_order',active) if active else None
        return {'credential_entry_enabled':self.vault_ready,'live_order_submission_enabled':self.enabled,
            'order_submission_enabled':bool(self.enabled and connected and saved['can_trade']),
            'connected':connected,'connection':connection,
            'active_order':dict(self._result(active_doc),**{k:active_doc.get(k) for k in ('symbol','side','quantity','limit_price','expires_at','estimated_notional','fee_reserve','risk_disclosure')}) if active_doc else None,
            'markets':[{'symbol':symbol,'ready':book.fresh() and book.integrity=='crc32_verified'} for (provider,symbol),book in self.books.items() if provider=='kraken' and book.instrument=='spot' and book.quote=='USD'],
            'withdrawals_enabled':False,'autonomous_trading':False,'individual_order_approval_required':True,
            'status':'connected' if connected else 'secure_setup_required'}

    def _nonce(self,key):
        fingerprint=hashlib.sha256(key.encode()).hexdigest()
        state_key='kraken_nonce:'+fingerprint
        with self.store.transaction():
            self.store.set_default(state_key,{'value':0})
            row=self.store.execute('SELECT data FROM state WHERE key=?'+(' FOR UPDATE' if self.store.postgres else ''),(state_key,)).fetchone()
            value=max(time.time_ns()//1000,int(json.loads(row['data'])['value'])+1)
            self.store.set_state(state_key,{'value':value})
        return value

    def _client(self):
        if not self.vault_ready:raise AccountError('Secure server-side credential storage is not configured.')
        saved=self.store.get_state(CONNECTION_KEY)
        if not saved or not saved.get('cipher'):raise AccountError('Connect your own Kraken account first.')
        try:credentials=json.loads(Fernet(self.settings.kraken_vault_key.encode()).decrypt(saved['cipher'].encode()))
        except (InvalidToken,ValueError,KeyError,TypeError):raise AccountError('Stored credentials are unavailable. Reconnect using the secure form.') from None
        client=self._new_client(credentials['api_key'],credentials['api_secret'])
        return saved,credentials,client

    @staticmethod
    def _permissions(info):
        permissions=set(info.get('permissions',[]))
        if permissions-ALLOWED_PERMISSIONS or not READ_PERMISSIONS<=permissions:
            raise AccountError('Use a dedicated key with funds, open-order and closed-order query permissions only; add modify/close trades for trading. All other permissions, including funding and withdrawals, must be off.')
        if any(str(info.get(field,'0'))!='0' for field in ('queryFrom','queryTo')):
            raise AccountError('Remove key history-date restrictions so uncertain orders can be reconciled.')
        expires=info.get('validUntil','0')
        if expires and float(expires)>0 and float(expires)<=time.time()+120:
            raise AccountError('The Kraken key is expired or too close to expiry.')
        return sorted(permissions)

    async def connect(self,api_key,api_secret,country_code,region,eligibility_confirmed,dedicated_key_confirmed):
        if not self.vault_ready:raise AccountError('Secure server-side credential storage is not configured.')
        if eligibility_confirmed is not True or dedicated_key_confirmed is not True:
            raise AccountError('Confirm regional/account eligibility and use a dedicated API key.')
        if not re.fullmatch('[A-Z]{2}',country_code) or not region.strip() or len(region)>100:
            raise AccountError('Provide your country code and state/province or region.')
        if not isinstance(api_key,str) or not isinstance(api_secret,str) or not 8<=len(api_key)<=512 or not 8<=len(api_secret)<=4096:
            raise AccountError('Invalid Kraken API credentials. Use the secure form.')
        client=self._new_client(api_key,api_secret)
        info=await client.key_info()
        permissions=self._permissions(info)
        # A successful key-info request alone does not verify funds/order access.
        await client.balances()
        await client.open_orders()
        await client.open_positions()
        payload={'api_key':api_key,'api_secret':api_secret,'country_code':country_code,'region':region.strip()}
        now=time.time()
        fingerprint=hashlib.sha256(api_key.encode()).hexdigest()
        doc={'id':str(uuid.uuid4()),'fingerprint':fingerprint,'cipher':Fernet(self.settings.kraken_vault_key.encode()).encrypt(json.dumps(payload).encode()).decode(),
            'verified_at':now,'permissions':permissions,'can_trade':TRADE_PERMISSIONS<=set(permissions)}
        with self.store.transaction():
            self._active_lock()
            previous=self.store.get_state(CONNECTION_KEY)
            if self.store.get_state('kraken_live_active'):
                if not previous or previous.get('fingerprint')!=fingerprint:
                    raise AccountError('Reconnect the original dedicated key to reconcile the prior order before replacing this connection.')
                doc['id']=previous['id']
            self.store.set_state(CONNECTION_KEY,doc)
            self.store.put('audit',{'action':'kraken.connect','connection_id':doc['id'],'permissions':permissions,'actor':'owner'})
        return self.status()

    def disconnect(self):
        with self.store.transaction():
            self._active_lock()
            previous=self.store.get_state(CONNECTION_KEY)
            if previous:
                previous['cipher']=None
                self.store.set_state(CONNECTION_KEY,previous)
            self.store.put('audit',{'action':'kraken.disconnect','actor':'owner'})
        return dict(self.status(),message='Credentials removed. This does not cancel orders or reverse fills at Kraken. Inspect Kraken directly.')

    def _active_lock(self):
        self.store.set_default('kraken_live_active',None)
        if self.store.postgres:self.store.execute('SELECT data FROM state WHERE key=? FOR UPDATE',('kraken_live_active',)).fetchone()

    async def _verified(self):
        saved,credentials,client=self._client()
        permissions=self._permissions(await client.key_info())
        if permissions!=saved['permissions']:
            raise AccountError('Key permissions changed. Disconnect and reconnect before proceeding.')
        balances=await client.balances()
        orders=await client.open_orders()
        positions=await client.open_positions()
        return saved,credentials,client,balances,orders,positions

    async def account(self):
        saved,_,_,balances,orders,_=await self._verified()
        rows=[]
        for oid,order in orders.items():
            description=order.get('descr',{})
            rows.append({'id':oid,'pair':description.get('pair'),'side':description.get('type'),
                'quantity':order.get('vol'),'executed':order.get('vol_exec'),'status':order.get('status'),
                'limit_price':description.get('price')})
        return {'verified_at':time.time(),'connection_id':saved['id'],
            'balances':[{'asset':asset,'balance':value['balance'],'available':value['spot_available']} for asset,value in balances.items()],
            'open_orders':rows,'fees_note':'Pair-specific account fees are queried for every preview. Available amounts exclude held funds and borrowing.'}

    def _book(self,symbol,now):
        book=self.books.get(('kraken',symbol))
        if book is None or not book.fresh(now) or book.instrument!='spot' or book.quote!='USD' or book.integrity!='crc32_verified':
            raise AccountError('A fresh CRC-verified Kraken USD spot book is required. Wait for the collector to recover.')
        return book

    def _risk(self,symbol,side,quantity,price,fee_rate,balances,orders,positions,now,asset_symbols=None):
        if self.store.get_state('control',{}).get('stopped'):raise AccountError('Emergency stop is active.')
        if orders or positions:raise AccountError('Resolve existing open orders or margin positions directly in Kraken before placing an app order.')
        profile=get_profile(self.store,now)
        if not profile or profile['stale']:raise AccountError('Confirm your real-capital profile and today’s realized P&L in Settings first.')
        capital=decimal(profile['capital_usd'])
        if decimal(profile['daily_realized_pnl_usd'])<=-capital*decimal(profile['daily_loss_limit_pct'])/100:
            raise AccountError('Your declared daily loss limit is reached.')
        book=self._book(symbol,now)
        vwap=book.fill(side,quantity)
        if (side=='buy' and vwap>price) or (side=='sell' and vwap<price):
            raise AccountError('The limit does not cover the current visible execution depth. Refresh the quote and review again.')
        midpoint=(min(book.asks)+max(book.bids))/2
        if abs(price/midpoint-1)>D('.01'):raise AccountError('The limit must be within 1% of the current verified midpoint.')
        notional=quantity*price
        fee=notional*fee_rate
        if notional>D(500):raise AccountError('The initial live order limit is 500 USD per order.')
        holdings={};usd=D(0)
        for asset,value in balances.items():
            if decimal(value.get('credit','0')) or decimal(value.get('credit_used','0')):
                raise AccountError('Borrowed or credit balances are unsupported. This app places own-cash spot orders only.')
            balance=decimal(value['balance'])
            if balance<0:raise AccountError('Negative balances are unsupported.')
            if asset in ('ZUSD','USD'):usd+=decimal(value['spot_available']);continue
            if not balance:continue
            holding_symbol=(asset_symbols or {}).get(asset) or ASSETS.get(asset)
            if not holding_symbol:raise AccountError('Cannot verify total crypto exposure for every held asset yet. Use Kraken directly for this portfolio.')
            current=self._book(holding_symbol,now)
            holdings[holding_symbol]=holdings.get(holding_symbol,D(0))+balance*(max(current.bids)+min(current.asks))/2
        available=sum((decimal(v['spot_available']) for a,v in balances.items() if ((asset_symbols or {}).get(a) or ASSETS.get(a))==symbol),D(0))
        if side=='buy':
            if notional+fee>min(usd,decimal(profile['available_cash_usd'])):raise AccountError('Verified available USD or your declared cash budget is insufficient, including fees.')
            if holdings.get(symbol,D(0))+notional>min(D(500),capital*decimal(profile['max_position_pct'])/100):
                raise AccountError('This would exceed the actual asset position limit.')
            exposure=max(sum(holdings.values(),D(0)),decimal(profile['existing_crypto_exposure_usd']))
            if exposure+notional>min(D(2500),capital*decimal(profile['max_crypto_exposure_pct'])/100):
                raise AccountError('This would exceed your crypto exposure limit.')
            if notional+fee>capital*decimal(profile['risk_per_trade_pct'])/100:
                raise AccountError('Without an attached stop, the full purchase plus fees must fit your declared per-trade risk budget.')
            remaining=capital*decimal(profile['daily_loss_limit_pct'])/100+min(D(0),decimal(profile['daily_realized_pnl_usd']))
            if notional+fee>remaining:raise AccountError('The full purchase plus fees exceeds your remaining declared daily loss budget.')
        elif quantity>available:raise AccountError('Verified unheld spot quantity is insufficient. Borrowing is disabled.')
        return notional,fee

    @staticmethod
    def _pair_name(symbol):
        if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z0-9.]{1,20}-USD',symbol):raise AccountError('Select an eligible Kraken USD spot market.')
        return symbol[:-4].replace('BTC','XBT')+'USD'

    @staticmethod
    def _symbol(metadata):
        wsname=metadata.get('wsname','')
        if not isinstance(wsname,str) or not wsname.endswith('/USD'):raise AccountError('Kraken USD spot identity is unavailable.')
        base=wsname[:-4]
        base={'XBT':'BTC','XDG':'DOGE'}.get(base,base)
        return base+'-USD'

    async def _rules(self,client,pair,symbol,quantity,price,country):
        pairs=await client.asset_pairs(pair,country_code=country)
        if len(pairs)!=1:raise AccountError('The Kraken pair is unavailable for the declared country.')
        pair_id,metadata=next(iter(pairs.items()))
        base=metadata.get('base')
        if not isinstance(base,str) or (base in ASSETS and ASSETS[base]!=symbol) or self._symbol(metadata)!=symbol or metadata.get('status')!='online' or metadata.get('quote') not in ('ZUSD','USD'):
            raise AccountError('The selected Kraken USD spot market is not fully online or its identity does not match.')
        try:
            p,l=int(metadata['pair_decimals']),int(metadata['lot_decimals'])
            if not 0<=p<=12 or not 0<=l<=12:raise ValueError()
            tick=decimal(metadata.get('tick_size',D(10)**-p));lot=D(10)**-l
            minimum=decimal(metadata['ordermin']);costmin=decimal(metadata['costmin'])
            if tick<=0 or minimum<=0 or costmin<=0 or tick>D('1000000000000'):raise ValueError()
        except (ValueError,KeyError,TypeError,ArithmeticError):raise AccountError('Kraken trading rules are incomplete or unsupported.') from None
        if quantity%lot or price%tick:raise AccountError('Quantity or price does not match Kraken’s actual lot/tick increments.')
        if quantity<minimum or quantity*price<costmin:raise AccountError('The order is below Kraken’s actual minimum quantity or cost.')
        return pair_id,metadata

    async def _asset_symbols(self,client,balances,country,metadata,symbol):
        mapping=dict(ASSETS);mapping[metadata['base']]=symbol
        for asset,value in balances.items():
            if asset in ('ZUSD','USD') or asset in mapping or decimal(value['balance'])==0:continue
            if not re.fullmatch(r'[A-Z0-9.]{1,20}',asset):raise AccountError('Unsupported account asset identity.')
            pairs=await client.asset_pairs(asset+'ZUSD',country_code=country)
            if len(pairs)!=1:raise AccountError('Cannot verify USD exposure for every held asset yet.')
            row=next(iter(pairs.values()))
            if row.get('base')!=asset or row.get('quote') not in ('ZUSD','USD'):raise AccountError('Account asset identity does not match Kraken trading metadata.')
            mapping[asset]=self._symbol(row)
        return mapping

    async def preview(self,symbol,side,quantity,limit_price):
        if not self.enabled:raise AccountError('Real order submission is disabled by the server.')
        if side not in ('buy','sell'):raise AccountError('Only Kraken USD spot buy/sell limit orders are supported.')
        pair=self._pair_name(symbol)
        self._book(symbol,time.time())
        quantity,price=amount(quantity),amount(limit_price)
        saved,credentials,client,balances,orders,positions=await self._verified()
        if not saved['can_trade']:raise AccountError('This connection is read-only. Use a dedicated key with modify/close trades permissions to trade.')
        pair_id,metadata=await self._rules(client,pair,symbol,quantity,price,credentials['country_code'])
        asset_symbols=await self._asset_symbols(client,balances,credentials['country_code'],metadata,symbol)
        fee_info=await client.fees(pair)
        fee_rows=fee_info.get('fees',{})
        fee_row=fee_rows.get(pair_id)
        if not fee_row:raise AccountError('The account’s actual taker fee for this pair is unavailable.')
        fee_rate=decimal(fee_row['fee'])/100
        if not 0<=fee_rate<=D('.1'):raise AccountError('The provider fee is outside the supported range.')
        now=time.time()
        notional,fee=self._risk(symbol,side,quantity,price,fee_rate,balances,orders,positions,now,asset_symbols)
        oid=str(uuid.uuid4());deadline=datetime.fromtimestamp(now+60,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        order=LimitOrder(pair=pair,side=side,volume=text(quantity),price=text(price),cl_ord_id=oid,deadline=deadline)
        await client.validate_limit_order(order)
        checked=time.time()
        if checked>=now+30:raise AccountError('Provider validation took too long. Build a new preview.')
        doc={'connection_id':saved['id'],'status':'validated','expires_at':now+30,'symbol':symbol,'side':side,
            'quantity':text(quantity),'limit_price':text(price),'pair':pair,'deadline':deadline,'cl_ord_id':oid,
            'estimated_notional':text(notional),'fee_reserve':text(fee),'fee_rate':text(fee_rate),'quote_currency':'USD',
            'provider_validation':True,'risk_disclosure':DISCLOSURES,'profile_confirmed_at':get_profile(self.store,checked)['confirmed_at']}
        with self.store.transaction():
            if self.store.get_state(CONNECTION_KEY,{}).get('id')!=saved['id']:raise AccountError('Connection changed during validation.')
            self.store.put('real_order',doc,id=oid,at=checked)
        return dict(doc,id=oid)

    def _result(self,doc):
        return {'id':doc['id'],'status':doc['status'],'order_ids':doc.get('order_ids',[]),
            'message':doc.get('message','Order intent recorded. Inspect execution status and any fills directly in Kraken.')}

    async def approve(self,preview_id,confirmation):
        if confirmation!='PLACE THIS REAL ORDER':raise AccountError('Type PLACE THIS REAL ORDER to approve these exact details.')
        doc=self.store.get('real_order',preview_id)
        if not doc:raise AccountError('Order preview not found.')
        if doc.get('restored_execution_disabled') or doc.get('execution_enabled') is False:raise AccountError('Restored order evidence can never be submitted. Build a new preview after fresh account verification.')
        if doc['status']!='validated':return self._result(doc)
        if not self.enabled:raise AccountError('Real order submission is disabled by the server.')
        if time.time()>=doc['expires_at']:raise AccountError('This preview expired. Build and review a new one.')
        saved,credentials,client,balances,orders,positions=await self._verified()
        if saved['id']!=doc['connection_id'] or not saved['can_trade']:raise AccountError('The connection changed or no longer permits trading.')
        now=time.time()
        profile=get_profile(self.store,now)
        if not profile or profile['stale'] or profile['confirmed_at']!=doc['profile_confirmed_at']:raise AccountError('Your risk profile changed or expired. Build a new preview.')
        pair_id,metadata=await self._rules(client,doc['pair'],doc['symbol'],amount(doc['quantity']),amount(doc['limit_price']),credentials['country_code'])
        asset_symbols=await self._asset_symbols(client,balances,credentials['country_code'],metadata,doc['symbol'])
        fees=await client.fees(doc['pair'])
        fee_row=fees.get('fees',{}).get(pair_id)
        if not fee_row or decimal(fee_row['fee'])/100>decimal(doc['fee_rate']):raise AccountError('The account fee changed or is unavailable. Build a new preview.')
        self._risk(doc['symbol'],doc['side'],amount(doc['quantity']),amount(doc['limit_price']),decimal(doc['fee_rate']),balances,orders,positions,time.time(),asset_symbols)
        order=LimitOrder(pair=doc['pair'],side=doc['side'],volume=doc['quantity'],price=doc['limit_price'],cl_ord_id=doc['cl_ord_id'],deadline=doc['deadline'])
        # Database lock across overlapping deployments serializes approval; only
        # the winner may send. Committed submitting intent survives a crash.
        with self.store.transaction():
            self._active_lock()
            current=self.store.get('real_order',preview_id)
            if current['status']!='validated':return self._result(current)
            if self.store.get_state('kraken_live_active'):raise AccountError('A prior order is submitting or unresolved. Reconcile it before another order.')
            if time.time()>=current['expires_at']:raise AccountError('This preview expired before submission.')
            if self.store.get_state(CONNECTION_KEY,{}).get('id')!=saved['id'] or self.store.get_state('control',{}).get('stopped'):
                raise AccountError('The connection or emergency control changed. No order was sent.')
            doc.update(status='submitting',submitted_at=time.time(),message='Submission intent saved; do not retry this order.')
            self.store.replace(preview_id,doc);self.store.set_state('kraken_live_active',preview_id)
            self.store.put('audit',{'action':'kraken.order_approved','order_id':preview_id,'actor':'owner','mode':'real_manual_ioc'})
        try:
            result=await client.submit_limit_order(order)
            ids=result.get('txid')
            if not isinstance(ids,list) or not ids or not all(isinstance(x,str) for x in ids):
                raise KrakenError('ambiguous_response','Kraken returned no confirmed order ID.',uncertain=True)
            doc.update(status='submitted',order_ids=ids,message='Kraken acknowledged the order. An IOC may fill partly or not at all; reconcile before another order.')
        except KrakenError as error:
            doc.update(status='unknown' if error.uncertain else 'rejected',message='Submission outcome is uncertain. Inspect Kraken and reconcile; this order will not be sent again.' if error.uncertain else 'Kraken rejected the order. No automatic retry will occur.')
        except Exception:
            doc.update(status='unknown',message='Submission outcome is uncertain. Inspect Kraken and reconcile; this order will not be sent again.')
        with self.store.transaction():
            self.store.replace(preview_id,doc)
            if doc['status']=='rejected':self.store.set_state('kraken_live_active',None)
        return self._result(doc)

    async def reconcile(self,order_id):
        doc=self.store.get('real_order',order_id)
        if not doc:raise AccountError('Order not found.')
        saved,_,client=self._client()
        if saved['id']!=doc['connection_id']:raise AccountError('The original account connection is unavailable. Inspect Kraken directly.')
        if doc['status'] not in ('submitting','submitted','unknown'):return self._result(doc)
        result=await client.orders_by_client_id(doc['cl_ord_id'],doc['submitted_at'])
        orders=result.get('orders',{})
        if orders:
            terminal=result.get('complete') is True and len(orders)==1 and all(value.get('status') in ('closed','canceled','expired') for value in orders.values())
            doc.update(status='resolved' if terminal else 'submitted',order_ids=list(orders),
                message='Kraken order records found. Review actual fills and fees in Kraken; no new order was sent.',provider_orders=orders)
            with self.store.transaction():
                self.store.replace(order_id,doc)
                if terminal and self.store.get_state('kraken_live_active')==order_id:self.store.set_state('kraken_live_active',None)
        return self._result(doc)

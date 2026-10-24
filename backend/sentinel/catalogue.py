"""Owner-only research catalogue. Indicative prices never become execution books.

Native provider IDs stay distinct: a ticker symbol is not a token identity.
CoinPaprika Free is used only for this private, noncommercial research workspace.
"""
import asyncio
import json
import logging
import re
import time
from decimal import Decimal as D
import httpx
from .models import decimal, timestamp

log = logging.getLogger('sentinel')
COIN_ROOT = 'https://api.coinpaprika.com/v1'
HL_INFO = 'https://api.hyperliquid.xyz/info'
BASES = ('BTC','ETH','SOL')
EXTRA_BOOK_LIMIT = 6
FIAT = {'USD','EUR','GBP','CAD','AUD','CHF','JPY','AED','ARS','BRL','MXN','TRY','ZAR'}
NATIVE = re.compile(r'^[A-Za-z0-9_.-]{1,40}$')


def numeric(value, positive=False):
    if value is None:return None
    try:
        out = decimal(value)
        return str(out) if (out>0 if positive else out>=0) else None
    except ValueError:return None


def signed(value):
    if value is None:return None
    try:return str(decimal(value))
    except ValueError:return None


async def fetch_json(client, url, payload=None):
    # Fixed upstream URLs only, no redirects, bounded decoded response size.
    async with client.stream('GET' if payload is None else 'POST',url,json=payload) as response:
        response.raise_for_status()
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data)>32*1024*1024:raise ValueError('Catalogue response exceeds size limit')
    return json.loads(data,parse_float=D)


class Catalogue:
    def __init__(self,store,providers=()):
        self.store,self.providers = store,set(providers)
        self.assets = store.get_state('catalogue:coins',{'items':{},'at':0})
        self.global_quotes = store.get_state('catalogue:quotes',{'items':{},'at':0})
        self.venues = store.get_state('catalogue:venues',{'kraken':{},'hyperliquid':{}})
        self.quotes = {}  # Socket quotes must be observed again after a restart.
        self.sessions = {p:{'state':'waiting' if p in providers else 'disabled','received_at':None} for p in ('kraken','hyperliquid')}
        self.errors = {}
        self.hl_at = 0

    def set_coins(self,rows,now):
        if not isinstance(rows,list) or not rows:raise ValueError('Empty or invalid coin catalogue')
        items = {}
        for row in rows:
            if not isinstance(row,dict):continue
            key = row.get('id')
            if not isinstance(key,str) or len(key)>200:continue
            items[key] = {'id':'coinpaprika:'+key,'provider_id':key,'source':'coinpaprika',
                'name':str(row.get('name',''))[:200],'symbol':str(row.get('symbol',''))[:60],
                'rank':row.get('rank') if isinstance(row.get('rank'),int) else 0,
                'active':row.get('is_active') is True,'kind':str(row.get('type','token'))[:40],
                'quote_currency':'USD','instrument':'aggregate','watch_symbol':None}
        if not items:raise ValueError('No valid coin identities')
        value = {'items':items,'at':now}
        self.store.set_state('catalogue:coins',value)
        self.assets = value
        self.errors.pop('coinpaprika:coins',None)

    def set_global_quotes(self,rows,now):
        if not isinstance(rows,list) or not rows:raise ValueError('Empty or invalid global quotes')
        items = {}
        for row in rows:
            try:
                quote = row.get('quotes',{}).get('USD',{})
                price = numeric(quote.get('price'),positive=True)
                at = timestamp(row.get('last_updated'))
                if not price or not at or at>now+60:continue
                items[row['id']] = {'price':price,'source_at':at,'received_at':now,
                    'volume_24h':numeric(quote.get('volume_24h')),'market_cap':numeric(quote.get('market_cap')),
                    'change_24h_pct':signed(quote.get('percent_change_24h')),'price_kind':'aggregate USD price',
                    'transport':'rest','timestamp_basis':'provider_event','valid':True}
            except (TypeError,KeyError,ValueError,AttributeError):continue
        if not items:raise ValueError('No valid global prices')
        value = {'items':items,'at':now}
        self.store.set_state('catalogue:quotes',value)
        self.global_quotes = value
        self.errors.pop('coinpaprika:quotes',None)

    def kraken_instruments(self,data,now,snapshot=False):
        items = {} if snapshot else dict(self.venues.get('kraken',{}))
        for row in data.get('pairs',[]):
            base,quote,pair = row.get('base',''),row.get('quote',''),row.get('symbol','')
            if base in FIAT or not NATIVE.fullmatch(base) or not NATIVE.fullmatch(quote) or pair!=base+'/'+quote:continue
            key = 'kraken:'+pair
            items[key] = {'id':key,'provider_id':pair,'source':'kraken','name':pair,'symbol':base,
                'rank':0,'active':row.get('status')=='online','kind':'spot pair','quote_currency':quote,
                'instrument':'spot','watch_symbol':base+'-USD' if quote=='USD' else None,'metadata_at':now}
        self.venues['kraken'] = items
        if snapshot:self.persist_venues()
        return {v['provider_id'] for v in items.values() if v['active']}

    def kraken_tick(self,row,now,*,event_trigger='trades'):
        key = 'kraken:'+str(row.get('symbol',''))
        if key not in self.venues['kraken']:return
        bid,ask = numeric(row.get('bid'),True),numeric(row.get('ask'),True)
        at = timestamp(row.get('timestamp'))
        # Display the current top-of-book midpoint, not an arbitrarily old last trade.
        price = str((D(bid)+D(ask))/2) if bid and ask and D(bid)<D(ask) else None
        if not price or not at or at>now+1:return
        volume,vwap = numeric(row.get('volume')),numeric(row.get('vwap'),True)
        self.quotes[key] = {'price':price,'bid':bid,'ask':ask,'source_at':at,'received_at':now,
            'volume_24h':str(D(volume)*D(vwap)) if volume and vwap else None,'market_cap':None,
            'change_24h_pct':signed(row.get('change_pct')),'price_kind':'best bid/ask midpoint',
            'transport':'websocket','timestamp_basis':'provider_event','event_trigger':event_trigger,'valid':True}

    def hyperliquid_metadata(self,data,now):
        if not isinstance(data,list) or len(data)!=2:raise ValueError('Invalid Hyperliquid metadata')
        universe,contexts = data[0]['universe'],data[1]
        if not universe or len(universe)!=len(contexts):raise ValueError('Mismatched native market context')
        items = {}
        for row,ctx in zip(universe,contexts):
            coin = row.get('name','')
            if not NATIVE.fullmatch(coin):continue  # HIP-3 namespaces/spot IDs need separate explicit support.
            key = 'hyperliquid:'+coin
            items[key] = {'id':key,'provider_id':coin,'source':'hyperliquid','name':coin+' perpetual',
                'symbol':coin,'rank':0,'active':not row.get('isDelisted',False),'kind':'perpetual',
                'quote_currency':'USDC','instrument':'perpetual','watch_symbol':coin+'-USDC-PERP','metadata_at':now,
                'volume_24h':numeric(ctx.get('dayNtlVlm')),'funding':signed(ctx.get('funding'))}
        if not items:raise ValueError('No native perpetual instruments')
        self.venues['hyperliquid'] = items
        self.hl_at = now
        self.persist_venues()
        self.errors.pop('hyperliquid:metadata',None)

    def hyperliquid_mids(self,mids,now):
        for coin,value in mids.items():
            key = 'hyperliquid:'+coin
            price = numeric(value,True)
            if key not in self.venues['hyperliquid'] or not price:continue
            self.quotes[key] = {'price':price,'source_at':None,'received_at':now,'volume_24h':None,
                'market_cap':None,'change_24h_pct':None,'price_kind':'perpetual midpoint',
                'transport':'websocket','timestamp_basis':'receipt_only','valid':True}

    def persist_venues(self):
        self.store.set_state('catalogue:venues',self.venues)

    def disconnected(self,provider,error):
        self.sessions[provider] = {'state':'reconnecting','received_at':time.time(),'error':error}
        for key,row in self.quotes.items():
            if key.startswith(provider+':'):row['valid'] = False

    def quote_view(self,row,now):
        source = row['source']
        quote = self.global_quotes['items'].get(row['provider_id']) if source=='coinpaprika' else self.quotes.get(row['id'])
        if not quote:return {'price':None,'status':'unavailable','source_at':None,'received_at':None,'executable':False}
        result = dict(quote,executable=False)
        age = now-(quote['source_at'] if quote['source_at'] is not None else quote['received_at'])
        receipt_age = now-quote['received_at']
        if source=='coinpaprika':
            result['status'] = 'delayed' if 0<=age<=1200 and 0<=receipt_age<=1200 else 'stale'
        else:
            connected = self.sessions[source]['state']=='connected' and quote['valid']
            recent = -1<=age<=30 and 0<=receipt_age<=30
            result['status'] = ('live' if source=='kraken' else 'streaming') if connected and recent else 'stale'
            if source=='hyperliquid':
                result['volume_24h'] = row.get('volume_24h') if now-row['metadata_at']<=300 else None
                result['context_received_at'] = row['metadata_at']
        result['age_seconds'] = max(0,age)
        return result

    def all_rows(self):
        return [*self.assets['items'].values(),*(v for p,items in self.venues.items() if p in self.providers for v in items.values())]

    def search(self,q='',source='live',page=1,limit=25,active='active',now=None):
        now = time.time() if now is None else now
        q = q[:100].strip().casefold()
        rows = self.all_rows()
        counts = {'catalogue':len(self.assets['items']),'global_prices':len(self.global_quotes['items']),
            'venue_markets':sum(len(v) for p,v in self.venues.items() if p in self.providers),
            'streaming_quotes':sum(1 for r in rows if r['source']!='coinpaprika' and self.quote_view(r,now)['status'] in ('live','streaming'))}
        filtered = [r for r in rows if (source=='all' or (source=='live' and r['source']!='coinpaprika') or r['source']==source)
            and (active=='all' or r['active']==(active=='active'))
            and (not q or q in ' '.join((r['name'],r['symbol'],r['provider_id'])).casefold())]
        filtered.sort(key=lambda r:(0 if q and r['symbol'].casefold()==q else 1,
            r['rank'] if r['rank']>0 else 999999,r['symbol'].casefold(),r['id']))
        page,limit = max(1,page),min(100,max(1,limit))
        return {'items':[dict(r,quote=self.quote_view(r,now)) for r in filtered[(page-1)*limit:page*limit]],
            'page':page,'limit':limit,'total':len(filtered),'counts':counts,'as_of':now,
            'sessions':self.sessions,'errors':self.errors,'catalogue_received_at':self.assets['at'] or None,
            'global_quotes_received_at':self.global_quotes['at'] or None,
            'coverage':'Kraken crypto spot pairs and native Hyperliquid perpetuals; CoinPaprika supplies a broader research catalogue. No source covers every token on every chain.',
            'attribution':{'label':'Powered by CoinPaprika','url':'https://coinpaprika.com','license':'Free API: private personal/noncommercial research only; up to 2,000 aggregate USD prices. No paid fallback.'}}

    def validate_watch(self,market_id,now=None):
        now = time.time() if now is None else now
        for provider,items in self.venues.items():
            row = items.get(market_id)
            if row and provider in self.providers and row['active'] and row['watch_symbol']:
                session = self.sessions[provider]
                connected = session['state']=='connected' and now-(session.get('received_at') or 0)<=30
                if now-row['metadata_at']>24*3600 and not connected:raise ValueError('Market metadata is stale; retry after the provider recovers')
                return {'id':market_id,'provider':provider,'symbol':row['watch_symbol']}
        raise ValueError('Choose an active Kraken USD spot pair or native Hyperliquid perpetual from the live directory')

    async def refresh(self,client,now=None):
        now = time.time() if now is None else now
        jobs = []
        if now-self.assets['at']>=6*3600:
            jobs.append(('coinpaprika:coins',COIN_ROOT+'/coins',None,self.set_coins))
        if now-self.global_quotes['at']>=600:
            jobs.append(('coinpaprika:quotes',COIN_ROOT+'/tickers?quotes=USD',None,self.set_global_quotes))
        if 'hyperliquid' in self.providers and now-self.hl_at>=120:
            jobs.append(('hyperliquid:metadata',HL_INFO,{'type':'metaAndAssetCtxs'},self.hyperliquid_metadata))
        for key,url,payload,apply in jobs:
            prior = self.errors.get(key,{})
            if now<prior.get('retry_at',0):continue
            try:
                data = await fetch_json(client,url,payload)
                apply(data,time.time())
                log.info('catalogue_refreshed source=%s',key)
            except asyncio.CancelledError:raise
            except Exception as error:
                status = error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None
                delay = 3600 if status in (402,403,429) else 120
                self.errors[key] = {'error':type(error).__name__,'http_status':status,'at':now,'retry_at':now+delay,
                    'policy':'Retain last verified data; no paid upgrade or substituted price.'}
                log.warning('catalogue_unavailable source=%s error=%s http_status=%s',key,type(error).__name__,status)

    async def run(self):
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            while True:
                await self.refresh(client)
                await asyncio.sleep(30)

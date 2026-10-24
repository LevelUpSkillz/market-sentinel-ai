"""Public historical candles for display only; never execution or strategy input.

Kraken OHLC always includes an unfinished last candle; explicitly label it.
Verified contract: https://docs.kraken.com/api-reference/market-data/get-ohlc-data
"""
import asyncio
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
import re
import time
import httpx

ROOT = 'https://api.kraken.com/0/public/OHLC'
HL_ROOT = 'https://api.hyperliquid.xyz/info'
SYMBOL = re.compile(r'^[A-Z0-9.]{1,40}-USD$')


def parse_candles(payload, symbol, interval, now):
    if not isinstance(payload,dict) or payload.get('error') != []:
        raise ValueError('Provider rejected historical data')
    result = payload.get('result',{})
    series = [v for k,v in result.items() if k!='last'] if isinstance(result,dict) else []
    if len(series)!=1 or not isinstance(series[0],list) or len(series[0])>720:
        raise ValueError('Invalid historical series')
    candles=[]
    last=0
    for row in series[0]:
        if not isinstance(row,list) or len(row)!=8:raise ValueError('Invalid candle shape')
        at=int(row[0])
        if isinstance(row[0],bool) or float(row[0])!=at or at<=last or at%(interval*60) or at>now+1:
            raise ValueError('Invalid candle timestamp')
        try: o,h,l,c,v=(Decimal(str(row[i])) for i in (1,2,3,4,6))
        except (InvalidOperation,ValueError):raise ValueError('Invalid candle number') from None
        if not all(x.is_finite() for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
            raise ValueError('Invalid candle range')
        candles.append({'at':at,'open':str(o),'high':str(h),'low':str(l),'close':str(c),
            'volume':str(v),'closed':at+interval*60<=now})
        last=at
    if len(candles)<2:raise ValueError('Not enough historical candles')
    return {'provider':'kraken','symbol':symbol,'interval_minutes':interval,'received_at':now,
        'source_at':candles[-1]['at'],'source':ROOT,'price_kind':'exchange trade candles',
        'executable':False,'candles':candles[-180:]}


class PriceHistory:
    def __init__(self):
        self.cache=OrderedDict()
        self.failures={}
        self.lock=asyncio.Lock()

    async def get(self,symbol,interval=1,provider='kraken'):
        valid=SYMBOL.fullmatch(symbol) if provider=='kraken' else re.fullmatch(r'[A-Z0-9.]{1,40}-USDC-PERP',symbol) if provider=='hyperliquid' else None
        if not valid or interval not in (1,5,15):raise ValueError('Unsupported chart market')
        key=(provider,symbol,interval)
        async with self.lock:
            now=time.time()
            prior=self.cache.get(key)
            if prior and now-prior['received_at']<20:
                self.cache.move_to_end(key)
                return dict(prior,cached=True)
            if now-self.failures.get(key,0)<20:raise ValueError('Historical provider is temporarily unavailable')
            pair=symbol[:-4]
            if pair=='BTC':pair='XBT'
            if provider=='hyperliquid':pair=symbol.removesuffix('-USDC-PERP')
            try:
                async with httpx.AsyncClient(timeout=8,follow_redirects=False) as client:
                    async with client.stream('GET' if provider=='kraken' else 'POST',ROOT if provider=='kraken' else HL_ROOT,
                        params={'pair':pair+'USD','interval':interval} if provider=='kraken' else None,
                        json={'type':'candleSnapshot','req':{'coin':pair,'interval':str(interval)+'m',
                            'startTime':int((now-180*interval*60)*1000),'endTime':int(now*1000)}} if provider=='hyperliquid' else None) as response:
                        response.raise_for_status()
                        chunks=[]; size=0
                        async for chunk in response.aiter_bytes():
                            size+=len(chunk)
                            if size>1024*1024:raise ValueError('Oversized historical response')
                            chunks.append(chunk)
                import json
                payload=json.loads(b''.join(chunks))
                if provider=='hyperliquid':
                    if not isinstance(payload,list) or len(payload)>720:raise ValueError('Invalid historical series')
                    rows=[]
                    for row in payload:
                        if row.get('s')!=pair or row.get('i')!=str(interval)+'m' or int(row['t'])%1000:
                            raise ValueError('Mismatched historical instrument')
                        rows.append([int(row['t'])//1000,row['o'],row['h'],row['l'],row['c'],'0',row['v'],row['n']])
                    payload={'error':[],'result':{pair:rows}}
                value=parse_candles(payload,symbol,interval,time.time())
                value.update(provider=provider,source=ROOT if provider=='kraken' else HL_ROOT)
            except (httpx.HTTPError,ValueError,TypeError,KeyError,OverflowError,AttributeError):
                self.failures[key]=now
                self.failures={k:v for k,v in self.failures.items() if now-v<20}
                raise ValueError('Historical provider is temporarily unavailable') from None
            self.failures.pop(key,None)
            self.cache[key]=value
            while len(self.cache)>40:self.cache.popitem(last=False)
            return dict(value,cached=False)

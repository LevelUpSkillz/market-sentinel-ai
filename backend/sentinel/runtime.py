import asyncio
from collections import deque
from decimal import Decimal as D
import json
import logging
import random
import time
import httpx
from websockets.asyncio.client import connect
from .models import Book
from .providers import ADAPTERS
from .engine import investigate, anomaly_facts
from .traders import poll_trader

log = logging.getLogger('sentinel')

def reconnect_delay(attempt, random_value=None):
    return min(60,2**min(attempt,6))+(random.random() if random_value is None else random_value)

class Runtime:
    def __init__(self,store,settings):
        self.store,self.settings = store,settings
        self.books = {}
        self.trades = deque(maxlen=2000)
        self.tickers,self.funding = {},{}
        self.tasks = []
        self.status = {p:{'state':'disabled','reason':'Provider terms/use approval not configured.','reconnects':0} for p in ADAPTERS}
        self.last_persist = None
        self.last_error = None

    async def start(self):
        if not self.settings.collect:
            return
        self.store.acquire_collector()
        for provider in self.settings.providers:
            self.tasks.append(asyncio.create_task(self.stream(provider)))
        self.tasks.append(asyncio.create_task(self.journal()))
        if 'hyperliquid' in self.settings.providers:
            self.tasks.append(asyncio.create_task(self.track_traders()))
        self.tasks.append(asyncio.create_task(self.alert_delivery()))

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)

    async def stream(self,provider):
        attempt = 0
        while True:
            adapter = ADAPTERS[provider]()
            status = self.status[provider]
            status.update(state='connecting',reason=None)
            connected_at = time.time()
            try:
                async with connect(adapter.url,open_timeout=15,ping_interval=20,ping_timeout=20,max_size=8*1024*1024,max_queue=32) as ws:
                    for subscription in adapter.subscriptions():
                        await ws.send(json.dumps(subscription))
                    while True:
                        raw = await asyncio.wait_for(ws.recv(),timeout=40)
                        now = time.time()
                        message = json.loads(raw,parse_float=D)
                        for kind,event in adapter.consume(message,now):
                            if kind=='book':
                                self.books[(provider,event.symbol)] = event
                                status.update(state='connected',last_book_at=now)
                            elif kind=='trade':
                                self.trades.append(event)
                            elif kind=='funding':
                                self.funding[event['symbol']] = event
                            elif kind=='ticker':
                                self.tickers[(provider,event['symbol'])] = event
                        status['last_message_at'] = now
                        if now-connected_at > 60:
                            attempt = 0
            except asyncio.CancelledError:
                adapter.invalidate()
                raise
            except Exception as e:
                adapter.invalidate()
                # Invalidate published books, including a previous connection's data.
                for (p,_),book in self.books.items():
                    if p==provider:
                        book.valid = False
                        book.integrity = 'disconnected'
                status.update(state='reconnecting',reason=type(e).__name__,reconnects=status['reconnects']+1)
                log.warning('provider_reconnect provider=%s error=%s',provider,type(e).__name__)
                await asyncio.sleep(reconnect_delay(attempt))
                attempt += 1

    def market_view(self):
        now = time.time()
        views = [b.view(now) for b in self.books.values()]
        expected = [(p,s) for p in ADAPTERS for s in (['BTC-USDC-PERP','ETH-USDC-PERP'] if p=='hyperliquid' else ['BTC-USD','ETH-USD'])]
        for p,s in expected:
            if (p,s) not in self.books:
                views.append(Book(p,s,'perpetual' if p=='hyperliquid' else 'spot','USDC' if p=='hyperliquid' else 'USD').view(now))
        return views

    def current_signals(self):
        signals = []
        stopped = self.store.get_state('control')['stopped']
        for symbol in ['BTC-USD','ETH-USD']:
            for buy,sell in [('kraken','coinbase'),('coinbase','kraken')]:
                a,b = self.books.get((buy,symbol)),self.books.get((sell,symbol))
                signals.append(investigate(a or Book(buy,symbol),b or Book(sell,symbol),stopped=stopped))
        return signals

    async def journal(self):
        previous = {}
        tick = 0
        while True:
            try:
                for view in self.market_view():
                    if not view['received_at']:
                        continue
                    key = (view['provider'],view['symbol'])
                    if tick%6==0:
                        self.store.put('market_snapshot',view)
                    facts = anomaly_facts(view,previous.get(key))
                    if facts:
                        self.store.put('forensic',{'facts':facts,'snapshot':view,'prior_snapshot':previous.get(key),
                            'hypotheses':['Liquidity repricing, cancellations, or normal market response may explain these observations.'],
                            'unknowns':['Intent, trader identity, hidden liquidity and causal mechanism.'],
                            'conclusion':'Observed anomaly; evidence does not establish manipulation.'})
                    previous[key] = view
                if tick%30==0:
                    for signal in self.current_signals():
                        # Persist actual paired observations, including cost-based rejections.
                        if all(s['received_at'] for s in signal['snapshots']):
                            opportunity = self.store.put('opportunity',signal)
                            if signal['decision']=='WAIT':
                                self.store.put('alert',{'title':'Research candidate requires review','opportunity_id':opportunity['id'],
                                    'decision':'WAIT','status':'inbox_only','mode':'research_only',
                                    'note':'Mobile delivery is reserved for eligible GO signals; none are auto-approved.'})
                self.resolve_outcomes()
                self.last_persist = time.time()
                self.last_error = None
                tick += 1
            except Exception as e:
                self.last_error = type(e).__name__
                log.exception('journal_failed')
            await asyncio.sleep(10)

    def resolve_outcomes(self):
        now = time.time()
        for opportunity in self.store.list('opportunity',500):
            if opportunity.get('outcome') or now-opportunity['detected_at'] < 300:
                continue
            b = self.books.get((opportunity['buy_provider'],opportunity['symbol']))
            s = self.books.get((opportunity['sell_provider'],opportunity['symbol']))
            followup = investigate(b,s) if b and s else None
            observed = followup and followup['net_bps'] is not None
            opportunity['outcome'] = {'measured_at':now,'horizon_seconds':now-opportunity['detected_at'],
                'status':'observed' if observed else 'unavailable','later_net_bps':followup['net_bps'] if observed else None,
                'later_snapshots':followup['snapshots'] if followup else [],
                'interpretation':'Paired-book edge persistence measurement, not a realized return or proof of profitability.',
                'autopsy':('Edge remained above costs.' if D(followup['net_bps'])>0 else 'Later costs/quotes erased the apparent edge.') if observed else 'A fresh comparable pair was unavailable. Outcome cannot be inferred.'}
            self.store.replace(opportunity['id'],opportunity)

    async def track_traders(self):
        while True:
            for trader in self.store.list('watchlist',10):
                try:
                    await poll_trader(self.store,trader,self.books)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.store.set_state('trader_error:'+trader['address'],{'error':type(e).__name__,'at':time.time()})
                await asyncio.sleep(2)
            await asyncio.sleep(60)

    async def alert_delivery(self):
        # Explicit topic/token setup and per-message queueing are required; never send to arbitrary URLs.
        while True:
            if self.settings.ntfy_topic and not self.store.get_state('control')['stopped']:
                for alert in self.store.list('alert',100):
                    if alert['status']!='queued' or alert.get('retry_at',0)>time.time():
                        continue
                    try:
                        headers = {'Title':'Market Sentinel AI','Priority':'default'}
                        if self.settings.ntfy_token:
                            headers['Authorization'] = 'Bearer '+self.settings.ntfy_token
                        async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
                            r = await client.post('https://ntfy.sh/'+self.settings.ntfy_topic,content=alert['title'].encode(),headers=headers)
                            r.raise_for_status()
                        alert.update(status='delivered',delivered_at=time.time())
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        attempts = alert.get('attempts',0)+1
                        alert.update(attempts=attempts,last_error=type(e).__name__,retry_at=time.time()+min(3600,2**min(attempts,12)))
                        if attempts>=8:
                            alert['status']='failed'
                    self.store.replace(alert['id'],alert)
            await asyncio.sleep(10)

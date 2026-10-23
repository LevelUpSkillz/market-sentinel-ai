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
from .flow import FlowDetector

log = logging.getLogger('sentinel')
BOOK_STALL_SECONDS = 90

def reconnect_delay(attempt, random_value=None):
    return min(60,2**min(attempt,6))+(random.random() if random_value is None else random_value)

class Runtime:
    def __init__(self,store,settings):
        self.store,self.settings = store,settings
        self.books = {}
        self.trades = deque(maxlen=2000)
        self.tickers,self.funding = {},{}
        self.tasks = []
        self.flow=FlowDetector()
        self.status = {p:{'state':'disabled','reason':'Provider terms/use approval not configured.','reconnects':0} for p in ADAPTERS}
        self.last_persist = None
        self.last_error = None
        self.collector_state = 'disabled'
        self.coordinator_heartbeat = None
        self.job_status = {}

    async def start(self):
        if not self.settings.collect:
            return
        self.collector_state = 'starting'
        self.tasks.append(asyncio.create_task(self.coordinate(),name='collector-coordinator'))

    async def supervise(self,name,factory):
        attempt = 0
        while True:
            self.job_status[name] = {'state':'running','at':time.time()}
            try:
                await factory()
                raise RuntimeError('Continuous background task exited unexpectedly')
            except asyncio.CancelledError:
                self.job_status[name] = {'state':'stopped','at':time.time()}
                raise
            except Exception as error:
                self.job_status[name] = {'state':'restarting','at':time.time(),'error':type(error).__name__}
                log.exception('background_task_failed task=%s',name)
                await asyncio.sleep(reconnect_delay(attempt))
                attempt += 1

    async def coordinate(self):
        # A new Render instance must become ready before the old instance drains.
        # Stand by until its PostgreSQL session lock is released, then collect.
        acquired = False
        jobs = []
        try:
            while True:
                self.coordinator_heartbeat = time.monotonic()
                if not acquired:
                    try:
                        acquired = self.store.try_acquire_collector()
                        self.collector_state = 'active' if acquired else 'standby'
                    except Exception:
                        self.collector_state = 'recovering'
                        log.exception('collector_lock_failed')
                    if acquired:
                        factories = [('stream:'+p,lambda p=p:self.stream(p)) for p in self.settings.providers]
                        factories += [('journal',self.journal),('alerts',self.alert_delivery)]
                        if 'hyperliquid' in self.settings.providers:
                            factories.append(('traders',self.track_traders))
                        jobs = [asyncio.create_task(self.supervise(name,factory),name=name) for name,factory in factories]
                if any(task.done() for task in jobs):
                    self.collector_state = 'failed'
                    return  # Readiness fails; Render restarts the service.
                await asyncio.sleep(2)
        finally:
            for task in jobs:
                task.cancel()
            await asyncio.gather(*jobs,return_exceptions=True)
            for book in self.books.values():
                book.valid = False
                book.integrity = 'collector_stopped'
            if acquired:
                try:self.store.release_collector()
                except Exception:log.exception('collector_unlock_failed')
            if self.collector_state!='failed':self.collector_state = 'stopped'

    def healthy(self):
        if not self.settings.collect:return True
        if self.coordinator_heartbeat is None or time.monotonic()-self.coordinator_heartbeat>15:return False
        if any(task.done() for task in self.tasks):return False
        if self.collector_state=='standby':return True
        return (self.collector_state=='active' and self.last_persist is not None and
                time.time()-self.last_persist<60 and self.last_error is None)

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)

    async def stream(self,provider):
        attempt = 0
        while True:
            adapter = ADAPTERS[provider]()
            self.flow.reset(provider)
            status = self.status[provider]
            status.update(state='connecting',reason=None)
            connected_at = time.time()
            expected = ['BTC-USDC-PERP','ETH-USDC-PERP'] if provider=='hyperliquid' else ['BTC-USD','ETH-USD']
            progress = {symbol:time.monotonic() for symbol in expected}
            logged_fresh = set()
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
                                progress[event.symbol] = time.monotonic()
                                status.update(state='connected',last_book_at=now)
                                if event.fresh(now) and event.symbol not in logged_fresh:
                                    logged_fresh.add(event.symbol)
                                    log.info('provider_book_observed provider=%s symbol=%s source_at=%s received_at=%s integrity=%s',provider,event.symbol,event.source_at,event.received_at,event.integrity)
                            elif kind=='trade':
                                self.trades.append(event)
                                self.flow.observe(event)
                            elif kind=='funding':
                                self.funding[event['symbol']] = event
                            elif kind=='ticker':
                                self.tickers[(provider,event['symbol'])] = event
                        status['last_message_at'] = now
                        if any(time.monotonic()-last>BOOK_STALL_SECONDS for last in progress.values()):
                            raise TimeoutError('Provider book updates stalled')
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
                        log.info('market_snapshot_persisted provider=%s symbol=%s status=%s source_at=%s received_at=%s',view['provider'],view['symbol'],view['status'],view['source_at'],view['received_at'])
                    facts = anomaly_facts(view,previous.get(key))
                    if facts:
                        self.store.put('forensic',{'facts':facts,'snapshot':view,'prior_snapshot':previous.get(key),
                            'hypotheses':['Liquidity repricing, cancellations, or normal market response may explain these observations.'],
                            'unknowns':['Intent, trader identity, hidden liquidity and causal mechanism.'],
                            'conclusion':'Observed anomaly; evidence does not establish manipulation.'})
                    previous[key] = view
                for flow in self.flow.anomalies(time.time()):
                    self.store.put('forensic',{'facts':flow['facts'],'flow':flow,'snapshot':next((v for v in self.market_view() if v['provider']==flow['provider'] and v['symbol']==flow['symbol']),None),
                        'hypotheses':['Changing participation or liquidity could explain these observations.'],
                        'unknowns':['Complete off-venue flow, trader intent and causal mechanism.'],
                        'conclusion':'Observed flow anomaly; no directional profitability or manipulation conclusion.'})
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

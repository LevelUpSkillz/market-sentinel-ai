"""Causal conditional-entry hypotheses from actual observed Kraken USD quotes.

This fixed, unvalidated research rule is not a predictor of profit. GO means only
that a short-lived simulated experiment currently passes deterministic controls.
Directory quotes build an observed range; only a fresh detailed book can pass GO.
No exchange order or owner paper trade is placed by this module.
"""
from collections import deque
from copy import deepcopy
from decimal import Decimal as D
import hashlib
import time
from .models import decimal
from .engine import FEES, POLICY, evaluate_paper_plan

VERSION = 'observed-breakout-v1'
BIN_SECONDS = 30
BASELINE_BINS = 10
MAX_SOURCE_GAP = 15
SETUP_SECONDS = 180
ENTRY_SECONDS = 30
COOLDOWN_SECONDS = 300
MAX_SETUPS = 12
MAX_SERIES = 2000
TRIGGER_BPS = D('5')
MAX_CHASE_BPS = D('20')
MIN_MOMENTUM_BPS = D('25')
MIN_RANGE_BPS = D('20')
NEAR_HIGH_BPS = D('30')


class Radar:
    def __init__(self,store):
        self.store = store
        self.series = {}
        self.setups = {}
        self.last_created = {}
        self.recent_created = deque(maxlen=12)
        self.coverage = {'universe':0,'observed':0,'warming_up':0,'ready':0,'candidates':0}
        self.last_tick = None
        # Persisted historical records remain searchable. They are never restored
        # as active setups or used to invent uninterrupted observations on restart.

    def _risk(self,now):
        rows = self.store.list('paper',10000)
        exposure = sum((decimal(p['entry_notional']) for p in rows if p['status']=='open'),D(0))
        daily = sum((decimal(p.get('net_pnl',0)) for p in rows if p.get('closed_at',0)>=now-now%86400),D(0))
        return {'exposure':exposure,'cash':decimal(self.store.get_state('account')['cash']),
            'daily_pnl':daily,'stopped':bool(self.store.get_state('control')['stopped'])}

    def _observe(self,key,quote,now):
        if not quote or quote.get('transport')!='websocket' or quote.get('timestamp_basis')!='provider_event' or not quote.get('valid'):
            return None
        at,received = quote.get('source_at'),quote.get('received_at')
        if at is None or received is None or not 0<=now-at<=5 or not 0<=now-received<=5:return None
        try:price = decimal(quote.get('price'))
        except ValueError:return None
        if price<=0:return None
        prior = self.series.get(key)
        if prior and at<=prior['last_at']:
            # Receiving the same event again neither completes a bin nor warms up.
            return prior if at==prior['last_at'] else None
        if prior is None or at-prior['last_at']>MAX_SOURCE_GAP:
            prior = {'bins':{},'last_at':at,'last_received_at':received,'last_price':price,'previous_at':None,'previous_price':None,'first_at':at}
            self.series[key] = prior
        else:
            prior['previous_at'],prior['previous_price'] = prior['last_at'],prior['last_price']
            prior['last_at'],prior['last_received_at'],prior['last_price'] = at,received,price
        index = int(at//BIN_SECONDS)
        bar = prior['bins'].setdefault(index,{'open':price,'high':price,'low':price,'close':price,'first_at':at,'last_at':at,'points':0})
        bar.update(high=max(bar['high'],price),low=min(bar['low'],price),close=price,last_at=at,points=bar['points']+1)
        for old in list(prior['bins']):
            if old<index-BASELINE_BINS-2:del prior['bins'][old]
        return prior

    def _baseline(self,series,now):
        index = int(series['last_at']//BIN_SECONDS)
        bins = [series['bins'].get(i) for i in range(index-BASELINE_BINS,index)]
        if any(b is None or b['points']<2 for b in bins):return None
        if now-series['last_at']>5:return None
        if series['last_at']-bins[0]['first_at']<295:return None
        return bins,index*BIN_SECONDS

    def _create(self,row,series,bins,baseline_end,now):
        high = max(b['high'] for b in bins)
        low = min(b['low'] for b in bins)
        price = series['last_price']
        momentum = (price/bins[0]['open']-1)*10000
        span = (high/low-1)*10000
        trigger = high*(1+TRIGGER_BPS/10000)
        limit = trigger*(1+MAX_CHASE_BPS/10000)
        if momentum<MIN_MOMENTUM_BPS or span<MIN_RANGE_BPS or price<high*(1-NEAR_HIGH_BPS/10000) or price>limit:return None
        stop = low*(1-TRIGGER_BPS/10000)
        fee = FEES['kraken']/10000
        exit_factor = (1-POLICY.latency_bps/10000)*(1-fee)
        # Solve at the worst permitted modeled entry so an entry anywhere in the
        # band has >=2 net reward/risk. 2.01 avoids decimal-rounding edge failures.
        entry_cost_per_unit = limit*(1+fee)
        loss_per_unit = entry_cost_per_unit-stop*exit_factor
        target = (entry_cost_per_unit+D('2.01')*loss_per_unit)/exit_factor
        identity = hashlib.sha256((VERSION+'|'+row['id']+'|'+str(baseline_end)).encode()).hexdigest()[:32]
        result = {'id':identity,'market_id':row['id'],'provider':'kraken','symbol':row['watch_symbol'],
            'strategy_version':VERSION,'mode':'paper_only','side':'long','decision':'WAIT','state':'waiting_for_trigger',
            'next_action':'Wait for the entry trigger; do not buy early.','created_at':now,'expires_at':now+SETUP_SECONDS,
            'triggered_at':None,'entry_deadline':None,'entry_trigger':str(trigger),'entry_limit':str(limit),
            'entry_vwap':None,'stop':str(stop),'target':str(target),'notional_usd':str(POLICY.notional_usd),
            'estimated_round_trip_cost_bps':str(FEES['kraken']*2+POLICY.latency_bps*2),
            'cost_model':'Before detailed depth: estimated fees and latency only. Entry depth and current exit liquidity are checked separately; future exit liquidity remains unknown.',
            'risk_reward':None,'maximum_modeled_loss':None,'success_probability_pct':None,'validation_status':'unvalidated',
            'source_at':series['last_at'],'received_at':series['last_received_at'],'reasons':[],
            'facts':[f'Observed five-minute price change: {momentum:.2f} bps; sampled range: {span:.2f} bps.',
                'Trigger is five bps above the high of ten previously completed 30-second observed-price bins.',
                'Stop is five bps below that observed low. Target is a cost-based 2:1 risk/reward hypothesis, not a forecast.'],
            'baseline':{'end_at':baseline_end,'high':str(high),'low':str(low),'momentum_bps':str(momentum),'range_bps':str(span),
                'bins':[{'start_at':(baseline_end-(BASELINE_BINS-i)*BIN_SECONDS),'open':str(b['open']),
                    'high':str(b['high']),'low':str(b['low']),'close':str(b['close']),'points':b['points'],
                    'first_at':b['first_at'],'last_at':b['last_at']} for i,b in enumerate(bins)]},
            'transitions':[]}
        self._advance(result,series,now)
        return result

    def _advance(self,setup,series,now):
        if setup.get('invalidated_at') or now>=setup['expires_at']:return
        price = series['last_price']
        at = series['last_at']
        setup['source_at'],setup['received_at'] = at,series['last_received_at']
        if series['first_at']>setup['created_at']:
            setup.update(invalidated_at=at,invalidation_reason='A data gap reset the observed range. Reject the old setup and rebuild five minutes of fresh observations.')
            return
        if price<=decimal(setup['stop']):
            setup.update(invalidated_at=at,invalidation_reason='The observed price breached the stop hypothesis before a new entry.')
            return
        if price>=decimal(setup['target']):
            setup.update(invalidated_at=at,invalidation_reason='The target was observed before a recorded owner entry; do not chase the completed move.')
            return
        if setup['triggered_at'] is None:
            previous = series.get('previous_price')
            previous_at = series.get('previous_at')
            if previous is not None and previous_at is not None and 0<at-previous_at<=MAX_SOURCE_GAP and previous<decimal(setup['entry_trigger'])<=price:
                setup['triggered_at'] = at
                setup['entry_deadline'] = min(setup['expires_at'],at+ENTRY_SECONDS)

    def _evaluate(self,setup,books,risk,now):
        result = deepcopy(setup)
        result.update(decision='WAIT',state='waiting_for_trigger',next_action='Wait for the entry trigger; do not buy early.',entry_vwap=None,risk_reward=None,maximum_modeled_loss=None)
        result['risk_inputs'] = {key:(value if isinstance(value,bool) else str(value)) for key,value in risk.items()}
        reasons = ['This fixed research hypothesis has no validated predictive edge or success probability.']
        book = books.get(('kraken',setup['symbol']))
        if setup.get('invalidated_at'):
            result.update(decision='NO-GO',state='invalidated',next_action='Reject this setup.')
            reasons.append(setup['invalidation_reason'])
        elif now>=setup['expires_at'] or (setup['entry_deadline'] is not None and now>=setup['entry_deadline']):
            result.update(decision='NO-GO',state='expired',next_action='Entry window expired; wait for a new setup.')
            reasons.append('The original expiry or first-trigger entry deadline passed; it is never extended by repeated observations.')
        elif risk['stopped']:
            result.update(decision='NO-GO',state='rejected',next_action='Emergency stop is active.')
            reasons.append('Emergency stop prevents new paper entries.')
        elif now-setup['source_at']>5 or now-setup['received_at']>5 or setup['source_at']>now:
            result.update(decision='NO-GO',state='stale',next_action='Wait for fresh provider observations.')
            reasons.append('The latest observed directory quote is stale or future-dated.')
        elif book is None:
            result.update(state='needs_depth',next_action='Inspect the live detailed book before considering a paper entry.')
            reasons.append('Indicative directory prices cannot establish executable depth. A detailed book is required.')
        elif book.provider!='kraken' or book.symbol!=setup['symbol'] or book.quote!='USD' or book.instrument!='spot' or not book.fresh(now):
            result.update(decision='NO-GO',state='stale',next_action='Wait for a fresh matching USD spot book.')
            reasons.append('Matching timestamp-verified USD spot depth is stale, invalid or unavailable.')
        else:
            result['snapshot'] = book.view(now)
            result['source_at'],result['received_at'] = book.source_at,book.received_at
            plan = evaluate_paper_plan(book,setup['notional_usd'],setup['stop'],setup['target'],now=now,**risk)
            result['risk_plan'] = plan
            plan['stages']['finder']['facts'] = ['Radar-generated long-entry hypothesis from actual past observed quotes; no historical edge is inferred.']
            for key in ('entry_vwap','risk_reward','maximum_modeled_loss'):
                result[key] = plan.get(key)
            # Ticker receipts cannot green-light or refresh an execution book.
            current_mid = (max(book.bids)+min(book.asks))/2
            entry = decimal(plan['entry_vwap']) if plan.get('entry_vwap') else None
            exit_liquidity = True
            if plan.get('quantity') and plan.get('entry_cost'):
                try:
                    qty = decimal(plan['quantity'])
                    exit_now = book.fill('sell',qty)*(1-POLICY.latency_bps/10000)*qty*(1-FEES['kraken']/10000)
                    cost_now = decimal(plan['entry_cost'])
                    result['estimated_round_trip_cost_bps'] = str((cost_now-exit_now)/cost_now*10000)
                    result['cost_model'] = 'Current visible-depth round trip, including spread, both fees and adverse latency; this is not a forecast of future exit liquidity.'
                except ValueError:exit_liquidity = False
            if not exit_liquidity:
                result.update(decision='NO-GO',state='rejected',next_action='Reject the entry; current visible exit liquidity is insufficient.')
                reasons.append('The current detailed bid book cannot support an exit of the modeled quantity.')
            elif current_mid<=decimal(setup['stop']) or current_mid>=decimal(setup['target']):
                result.update(decision='NO-GO',state='invalidated',next_action='The setup price levels have already been invalidated.')
                reasons.append('Current detailed depth is beyond the stop or target level.')
            elif entry is not None and entry>decimal(setup['entry_limit']):
                result.update(decision='NO-GO',state='rejected',next_action='Do not chase; current modeled entry exceeds the limit.')
                reasons.append('Current visible-depth entry plus latency exceeds the trigger-plus-20-bps entry cap.')
            elif plan['decision']!='GO':
                result.update(decision='NO-GO',state='rejected',next_action='Reject this paper entry under the current risk limits.')
                reasons.extend(plan['stages']['skeptic']['objections'])
            elif setup['triggered_at'] is None or current_mid<decimal(setup['entry_trigger']):
                reasons.append('A fresh observed crossing and a current midpoint at or above the trigger are required.')
            else:
                result.update(decision='GO',state='paper_ready',next_action='A paper entry is eligible now within the displayed entry limit and deadline.')
                reasons.append('An observed trigger, fresh executable depth, entry cap and deterministic paper risk checks currently pass.')
                reasons.append('GO is for a simulated experiment only. It is not approval to risk real money.')
        result['reasons'] = reasons
        result['stages'] = {'finder':{'facts':result['facts']},'skeptic':{'objections':reasons},
            'risk':{'rules':['$250 modeled notional; existing portfolio, cash and daily-loss limits apply.',
                'A fresh matching book is required; directory prices are not executable.',
                'Maximum entry deterioration: 20 bps; first-trigger entry window: 30 seconds.']},
            'decision':{'result':result['decision'],'reason':result['next_action']}}
        return result

    def _persist(self,setup,evaluation,now,created=False):
        signature = (evaluation['decision'],evaluation['state'],tuple(evaluation['reasons']))
        if not created and setup.get('_last_signature')==signature:return
        setup['_last_signature'] = signature
        if evaluation['decision']=='GO' and 'first_paper_ready' not in setup:
            setup['first_paper_ready'] = {'at':now,'mode':'paper_only','entry_vwap':evaluation['entry_vwap'],
                'source_at':evaluation['source_at'],'received_at':evaluation['received_at'],
                'snapshot':deepcopy(evaluation.get('snapshot')),'risk_plan':deepcopy(evaluation.get('risk_plan')),
                'risk_inputs':deepcopy(evaluation['risk_inputs']),
                'note':'First eligible paper hypothesis, not an account fill or real trade.'}
        setup['transitions'] = [*setup['transitions'][-19:],{'at':now,'decision':evaluation['decision'],'state':evaluation['state'],
            'source_at':evaluation['source_at'],'received_at':evaluation['received_at'],'reasons':evaluation['reasons']}]
        record = dict(evaluation,transitions=deepcopy(setup['transitions']))
        if 'first_paper_ready' in setup:record['first_paper_ready'] = deepcopy(setup['first_paper_ready'])
        record.pop('_last_signature',None)
        if created:self.store.put('radar_signal',record,id=setup['id'],at=now)
        else:self.store.replace(setup['id'],record)

    def tick(self,catalogue,books,*,now=None):
        now = time.time() if now is None else now
        risk = self._risk(now)
        universe = {key:row for key,row in catalogue.venues.get('kraken',{}).items() if 'kraken' in catalogue.providers
            and row.get('active') and row.get('quote_currency')=='USD' and row.get('instrument')=='spot' and row.get('watch_symbol')}
        observed = ready = 0
        new_candidates = []
        connected = catalogue.sessions.get('kraken',{}).get('state')=='connected'
        for key,row in list(universe.items())[:MAX_SERIES]:
            quote = catalogue.quotes.get(key) if connected else None
            series = self._observe(key,quote,now)
            if series is None:continue
            observed += 1
            existing = self.setups.get(key)
            if existing:self._advance(existing,series,now)
            baseline = self._baseline(series,now)
            if baseline is None:continue
            ready += 1
            if existing and now<existing['expires_at']:continue
            if now-self.last_created.get(key,-COOLDOWN_SECONDS)<COOLDOWN_SECONDS:continue
            candidate = self._create(row,series,*baseline,now)
            if candidate:new_candidates.append(candidate)
        for key,series in list(self.series.items()):
            if key not in universe or now-series['last_at']>600:self.series.pop(key,None)
        for key,setup in list(self.setups.items()):
            if key not in universe or now>setup['expires_at']+SETUP_SECONDS:self.setups.pop(key,None)
        while self.recent_created and now-self.recent_created[0]>=60:self.recent_created.popleft()
        new_candidates.sort(key=lambda r:decimal(r['baseline']['momentum_bps']),reverse=True)
        for setup in new_candidates:
            if len(self.setups)>=MAX_SETUPS and setup['market_id'] not in self.setups:
                old = next((key for key,value in self.setups.items() if now>=value['expires_at']),None)
                if old:self.setups.pop(old)
            if (len(self.setups)>=MAX_SETUPS and setup['market_id'] not in self.setups) or len(self.recent_created)>=6:break
            self.setups[setup['market_id']] = setup
            self.last_created[setup['market_id']] = now
            self.recent_created.append(now)
            self._persist(setup,self._evaluate(setup,books,risk,now),now,True)
        # Prune cooldown metadata for removed/stale markets as well as sampled bins.
        for key,at in list(self.last_created.items()):
            if key not in universe and now-at>600:self.last_created.pop(key,None)
        for setup in self.setups.values():self._persist(setup,self._evaluate(setup,books,risk,now),now)
        self.coverage = {'universe':len(universe),'observed':observed,'warming_up':max(0,observed-ready),'ready':ready,'candidates':len(self.setups)}
        self.last_tick = now
        return self.snapshot(books,now=now)

    def snapshot(self,books,*,now=None):
        now = time.time() if now is None else now
        risk = self._risk(now)
        setups = [self._evaluate(setup,books,risk,now) for setup in self.setups.values()]
        setups.sort(key=lambda r:({'GO':0,'WAIT':1,'NO-GO':2}[r['decision']],-r['created_at'],r['symbol']))
        for setup in setups:setup.pop('_last_signature',None)
        fresh = self.last_tick is not None and 0<=now-self.last_tick<=10
        if not fresh:
            for setup in setups:
                if setup['decision']=='GO':
                    setup.update(decision='NO-GO',state='stale',next_action='Wait for the radar collector to resume.')
                    setup['reasons'].append('The independent radar scan is stale.')
        return {'as_of':self.last_tick if self.last_tick is not None else now,'last_scan_at':self.last_tick,'strategy_version':VERSION,'mode':'paper_only',
            'status':'stopped' if risk['stopped'] else 'collecting' if fresh else 'waiting_for_collector',
            'coverage':dict(self.coverage),'setups':setups[:MAX_SETUPS],
            'limitations':['GO means current paper-risk eligibility, not a validated profitable edge or real-money instruction.',
                'Five-minute observed-price baselines must warm up after a restart or data gap; no missing prices are filled.',
                'This fixed breakout hypothesis has no out-of-sample validation or estimated success odds yet.',
                'Stop and target are calculated hypothesis levels; gaps and unknown future liquidity can exceed modeled loss.',
                'The radar scans approved Kraken USD spot quotes. Other venue quotes and catalogue prices remain separate research data.',
                'Free hosting can sleep. A future profitable entry time cannot be guaranteed.']}

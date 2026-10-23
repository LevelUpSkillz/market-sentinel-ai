"""Deterministic calculations. No LLM, order routing, or credentials for exchanges."""
from dataclasses import dataclass, asdict
from decimal import Decimal as D
import time
from .models import Book, decimal

VERSION = 'spot-cross-v1.0.0'
# Conservative estimates, not claimed account-specific fees. Configure via reviewed code version.
FEES = {'kraken':D('40'),'coinbase':D('60'),'hyperliquid':D('5')}

@dataclass(frozen=True)
class Policy:
    notional_usd: D = D('250')
    latency_bps: D = D('5')
    minimum_net_bps: D = D('10')
    max_age: int = 5
    max_snapshot_skew: float = 2
    max_position: D = D('500')
    max_total_exposure: D = D('2500')
    max_daily_loss: D = D('200')

POLICY = Policy()

def investigate(buy: Book, sell: Book, *, now=None, stopped=False):
    now = time.time() if now is None else now
    facts, objections, limits = [], [], []
    result = {'strategy_version':VERSION,'kind':'cross_exchange','symbol':buy.symbol,
              'buy_provider':buy.provider,'sell_provider':sell.provider,'detected_at':now,
              'mode':'research_only','notional_usd':str(POLICY.notional_usd),
              'snapshots':[buy.view(now),sell.view(now)],'net_bps':None,'gross_bps':None,
              'fees_bps':str(FEES[buy.provider]+FEES[sell.provider]),'latency_bps':str(POLICY.latency_bps),
              'inventory_verified':False,'decision':'NO-GO'}
    if buy.symbol != sell.symbol or buy.instrument != 'spot' or sell.instrument != 'spot' or buy.quote != sell.quote:
        objections.append('Incompatible instruments or quote currencies; no synthetic USD/USDC equivalence.')
    if buy.provider == sell.provider:
        objections.append('A cross-exchange signal requires independent venues.')
    if not buy.fresh(now) or not sell.fresh(now):
        objections.append('Book is stale, invalid, future-dated, or lacks a source timestamp.')
    if buy.source_at is not None and sell.source_at is not None and abs(buy.source_at-sell.source_at) > POLICY.max_snapshot_skew:
        objections.append('Source snapshots are more than two seconds apart.')
    if stopped:
        limits.append('Emergency stop is active.')
    if not objections:
        quantity = POLICY.notional_usd / min(buy.asks)
        try:
            entry, exit = buy.fill('buy',quantity), sell.fill('sell',quantity)
            gross = (exit-entry)/entry*10000
            net = gross-FEES[buy.provider]-FEES[sell.provider]-POLICY.latency_bps
            result.update(quantity=str(quantity),entry_vwap=str(entry),exit_vwap=str(exit),gross_bps=str(gross),net_bps=str(net),estimated_net_usd=str(entry*quantity*net/10000))
            facts.append(f'Visible book VWAP edge is {gross:.2f} bps for {quantity:.8f} units.')
            facts.append('Fees on both legs, visible depth slippage and a 5 bps latency reserve are included.')
            if net < POLICY.minimum_net_bps:
                objections.append('Net edge does not clear the 10 bps safety margin after estimated costs.')
        except ValueError as e:
            objections.append(str(e))
    # Read-only feeds cannot verify prefunded balances, inventory or simultaneous leg execution.
    limits.append('Prefunded sell-side inventory and buy-side cash are unverified; transfers are not instantaneous.')
    if not objections and not stopped:
        result['decision'] = 'WAIT'
    result['stages'] = {'finder':{'facts':facts},'skeptic':{'objections':objections},'risk':{'limits':limits},
                        'decision':{'result':result['decision'],'reason':'Research candidate only; no live execution path exists.'}}
    return result

def copy_decision(event, book: Book | None, exposure=D(0), stopped=False, now=None):
    """Observed wallet success is never sufficient evidence for an entry."""
    now = time.time() if now is None else now
    reasons = ['A public position does not reveal the trader’s hedges, risk budget or complete track record.']
    result = {'decision':'NO-GO','strategy_version':'copy-v1.0.0','observed_event':dict(event),'reasons':reasons,'mode':'paper_only'}
    if stopped:
        reasons.append('Emergency stop is active.')
    if book is None or not book.fresh(now):
        reasons.append('A fresh executable book is unavailable.')
        return result
    if now-float(event.get('observed_at',0)) > 60 or event.get('baseline',True):
        reasons.append('Observation is old or an initial baseline; it is not a new entry.')
        return result
    entry = decimal(event.get('entry_price',0))
    if entry <= 0:
        reasons.append('Original entry price is unavailable.')
        return result
    current = min(book.asks) if event.get('side') == 'long' else max(book.bids)
    drift = (current-entry)/entry*10000*(1 if event.get('side')=='long' else -1)
    result['entry_drift_bps'] = str(drift)
    if drift > 20:
        reasons.append('Follower entry deteriorated by more than 20 bps.')
    if exposure >= POLICY.max_total_exposure:
        reasons.append('Total correlated crypto exposure exceeds policy.')
    reasons.append('Stop, target, fee tier, funding horizon and out-of-sample trader evidence are unverified.')
    return result

def anomaly_facts(current, previous):
    """Observations are not allegations of manipulation or directional trade recommendations."""
    facts = []
    if not previous or current['status'] != 'live' or previous['status'] != 'live' or not 0 <= current['received_at']-previous['received_at'] <= 20:
        return facts
    depth, old_depth = decimal(current['visible_depth_usd']), decimal(previous['visible_depth_usd'])
    spread, old_spread = decimal(current['spread_bps']), decimal(previous['spread_bps'])
    if old_depth > 0 and depth < old_depth*D('.5'):
        facts.append('Visible top-10 depth fell by more than 50% since the preceding saved snapshot.')
    if spread > max(D(10),old_spread*3):
        facts.append('Spread exceeds 10 bps and is more than three times the preceding spread.')
    if abs(decimal(current['imbalance'])) > D('.8'):
        facts.append('Absolute top-10 notional book imbalance exceeds 0.8.')
    return facts

def paper_open(store, book, notional, idempotency_key, now=None):
    now = time.time() if now is None else now
    amount = decimal(notional)
    if not D(10) <= amount <= POLICY.max_position:
        raise ValueError('Paper position must be between $10 and $500')
    with store.transaction():
        prior = store.get('paper',idempotency_key)
        if prior:
            return prior
        if store.get_state('control')['stopped']:
            raise ValueError('Emergency stop is active')
        if not book.fresh(now) or book.instrument != 'spot' or book.quote != 'USD':
            raise ValueError('Paper entries require a fresh USD spot book')
        account = store.get_state('account')
        positions = [p for p in store.list('paper',10000) if p['status']=='open']
        exposure = sum((decimal(p['entry_notional']) for p in positions),D(0))
        if exposure+amount*(1+POLICY.latency_bps/10000) > POLICY.max_total_exposure:
            raise ValueError('Correlated crypto exposure limit reached')
        day_pnl = sum((decimal(p.get('net_pnl',0)) for p in store.list('paper',10000) if p.get('closed_at',0) >= now-now%86400),D(0))
        if day_pnl <= -POLICY.max_daily_loss:
            raise ValueError('Daily realized loss limit reached')
        quantity = amount/min(book.asks)
        price = book.fill('buy',quantity)*(1+POLICY.latency_bps/10000)
        cost = price*quantity
        fee = cost*FEES[book.provider]/10000
        if decimal(account['cash']) < cost+fee:
            raise ValueError('Insufficient paper cash')
        account['cash'] = str(decimal(account['cash'])-cost-fee)
        store.set_state('account',account)
        position = store.put('paper',{'status':'open','mode':'SIMULATED PAPER TRADE','provider':book.provider,
            'symbol':book.symbol,'quantity':str(quantity),'entry_price':str(price),'entry_notional':str(cost),
            'entry_fee':str(fee),'opened_at':now,'snapshot':book.view(now),'strategy_version':'manual-paper-v1',
            'execution_model':'Visible depth VWAP + 5 bps adverse latency on each leg; no actual fill.'},id=idempotency_key)
        store.put('audit',{'action':'paper.open','position':position['id'],'actor':'owner'})
        return position

def paper_close(store, position_id, book, now=None):
    now = time.time() if now is None else now
    with store.transaction():
        p = store.get('paper',position_id)
        if not p:
            raise ValueError('Unknown paper position')
        if p['status']=='closed':
            return p
        if book.provider != p['provider'] or book.symbol != p['symbol'] or not book.fresh(now):
            raise ValueError('Fresh original venue and symbol book required to close')
        quantity = decimal(p['quantity'])
        price = book.fill('sell',quantity)*(1-POLICY.latency_bps/10000)
        proceeds = quantity*price
        fee = proceeds*FEES[book.provider]/10000
        pnl = proceeds-fee-decimal(p['entry_notional'])-decimal(p['entry_fee'])
        account = store.get_state('account')
        account['cash'] = str(decimal(account['cash'])+proceeds-fee)
        account['realized_pnl'] = str(decimal(account['realized_pnl'])+pnl)
        store.set_state('account',account)
        p.update(status='closed',closed_at=now,exit_price=str(price),exit_fee=str(fee),net_pnl=str(pnl),exit_snapshot=book.view(now))
        store.replace(position_id,p)
        store.put('audit',{'action':'paper.close','position':position_id,'actor':'owner'})
        return p

def evaluate_paper_plan(book, notional, stop, target, *, exposure=D(0), cash=D('10000'), daily_pnl=D(0), stopped=False, now=None):
    """GO only means eligible for a simulated experiment, never an assertion of edge."""
    now=time.time() if now is None else now
    amount,stop,target=decimal(notional),decimal(stop),decimal(target)
    result={'kind':'paper_entry_plan','strategy_version':'paper-risk-v1','mode':'SIMULATED PAPER EXPERIMENT',
            'decision':'NO-GO','symbol':book.symbol,'provider':book.provider,'detected_at':now,
            'notional_usd':str(amount),'stop':str(stop),'target':str(target),'snapshot':book.view(now),
            'risk_reward':None,'maximum_modeled_loss':None,'hypothesis_validated':False}
    reasons=[]
    if stopped:reasons.append('Emergency stop is active.')
    if not book.fresh(now) or book.instrument!='spot' or book.quote!='USD':
        reasons.append('A fresh USD spot book is required.')
    if not D(10)<=amount<=POLICY.max_position:reasons.append('Notional violates the $10–$500 paper limit.')
    if daily_pnl<=-POLICY.max_daily_loss:reasons.append('Daily realized paper loss limit has been reached.')
    if not reasons:
        try:
            qty=amount/min(book.asks)
            entry=book.fill('buy',qty)*(1+POLICY.latency_bps/10000)
            entry_cost=entry*qty*(1+FEES[book.provider]/10000)
            stop_proceeds=stop*qty*(1-POLICY.latency_bps/10000)*(1-FEES[book.provider]/10000)
            target_proceeds=target*qty*(1-POLICY.latency_bps/10000)*(1-FEES[book.provider]/10000)
            loss,reward=entry_cost-stop_proceeds,target_proceeds-entry_cost
            result.update(entry_vwap=str(entry),quantity=str(qty),maximum_modeled_loss=str(loss),
                target_net_profit=str(reward),entry_cost=str(entry_cost),risk_reward=str(reward/loss) if loss>0 else None)
            if entry_cost>cash:reasons.append('Available paper cash cannot fund the entry including fees.')
            if exposure+entry*qty>POLICY.max_total_exposure:reasons.append('Correlated crypto exposure limit would be exceeded.')
            if not 0<stop<entry<target:reasons.append('A long plan requires a positive stop below entry and target above entry.')
            if loss<=0 or loss>D(100):reasons.append('Modeled risk must be positive and at most $100 per experiment.')
            if loss>0 and reward/loss<D(2):reasons.append('Net reward/risk must be at least 2 after both-leg costs.')
            if not reasons:result['decision']='GO'
        except ValueError as error:reasons.append(str(error))
    result['stages']={'finder':{'facts':['Owner-specified long-entry hypothesis; no historical edge is inferred.']},
        'skeptic':{'objections':reasons,'unknowns':['Stop orders are not guaranteed; gaps can exceed modeled loss.','Probability of reaching the target is unvalidated.']},
        'risk':{'rules':['No leverage or shorting.','$500 requested notional; $2,500 correlated crypto exposure; $100 modeled risk cap.','2:1 net modeled reward/risk minimum.']},
        'decision':{'result':result['decision'],'meaning':'GO means eligible for a paper experiment. It does not mean profitable or approved for live execution.'}}
    return result

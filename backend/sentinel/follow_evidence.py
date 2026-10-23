"""Versioned, prospective shadow-follow study; never changes the paper account."""
from decimal import Decimal as D
from math import sqrt
import time
from .models import decimal

VERSION = 'follow-shadow-v1'
HORIZON = 3600
MIN_SAMPLE = 100
FEE = D('0.0005')
LATENCY = D('0.0005')


def wilson(wins,count):
    if not count:return None
    p,z = wins/count,1.959963984540054
    scale = 1+z*z/count
    center = (p+z*z/(2*count))/scale
    radius = z*sqrt(p*(1-p)/count+z*z/(4*count*count))/scale
    return [max(0,(center-radius)*100),min(100,(center+radius)*100)]


def evidence(rows,symbol,side,as_of=None):
    now = time.time() if as_of is None else as_of
    cohort = [r for r in rows if r.get('version')==VERSION and r.get('symbol')==symbol and r.get('side')==side and r.get('entered_at',now+1)<=now]
    closed = sorted([r for r in cohort if r.get('status')=='closed' and r.get('closed_at',now+1)<=now],key=lambda r:r['closed_at'])
    missing = sum(r.get('status')=='unavailable' and r.get('resolved_at',now+1)<=now for r in cohort)
    count = len(closed)
    wins = sum(decimal(r['net_pnl_usdc'])>0 for r in closed)
    interval = wilson(wins,count)
    scored = [r for r in closed if r.get('predicted_at_entry') is not None]
    brier = sum((r['predicted_at_entry']-(1 if decimal(r['net_pnl_usdc'])>0 else 0))**2 for r in scored)/len(scored) if scored else None
    calibration = abs(sum(r['predicted_at_entry'] for r in scored)/len(scored)-sum(decimal(r['net_pnl_usdc'])>0 for r in scored)/len(scored)) if scored else None
    coverage = count/(count+missing) if count+missing else None
    span = (closed[-1]['closed_at']-closed[0]['entered_at'])/86400 if closed else 0
    reasons = []
    if count<MIN_SAMPLE:reasons.append(f'Need at least {MIN_SAMPLE} non-overlapping completed observations for this asset/direction; have {count}.')
    if span<7:reasons.append('Need at least seven days of observations.')
    if coverage is None or coverage<.9:reasons.append('At least 90% outcome availability is required; outage gaps are excluded, not assumed losses.')
    if len(scored)<30:reasons.append('Need at least 30 chronologically held-out predictions made before their outcomes.')
    if brier is None or brier>=.25:reasons.append('Prospective probability forecasts have not beaten a constant 50% Brier-score benchmark.')
    if calibration is None or calibration>.1:reasons.append('Prospective calibration error must be at most ten percentage points.')
    if interval is None or interval[1]-interval[0]>25:reasons.append('The 95% interval is too wide or unavailable.')
    return {'symbol':symbol,'side':side,'version':VERSION,'horizon_minutes':60,'completed':count,'wins':wins,
        'missing':missing,'pending':sum(r.get('status')=='pending' for r in cohort),'minimum_sample':MIN_SAMPLE,
        'historical_success_pct':100*wins/count if count else None,'interval_95_pct':interval,
        'estimated_success_pct':100*(wins+1)/(count+2) if not reasons else None,
        'status':'prospectively_validated_estimate' if not reasons else 'insufficient_validated_evidence',
        'brier_score':brier,'held_out_predictions':len(scored),'coverage_pct':100*coverage if coverage is not None else None,
        'reasons':reasons,'meaning':'Positive modeled net USDC P&L one hour after an observed opening/increase; not the trader’s lifetime win rate.',
        'limitations':['Selected public-wallet cohort; hidden hedges, regime shifts and residual cross-market correlation remain.',
            'One observation per asset per hour across all wallets limits duplicate and overlapping exposure.',
            'The 95% Wilson interval assumes independent outcomes; residual dependence can make it too narrow.',
            'A modeled funding reserve is not an observed funding bill. Estimates are not guarantees or live-order approval.']}


def begin_sample(store,event,book,now=None):
    now = time.time() if now is None else now
    if event.get('action') not in ['opened','increased','reversal'] or event.get('baseline',True):return None
    if event.get('side') not in ['long','short'] or book is None or not book.fresh(now) or book.provider!='hyperliquid':return None
    if store.get_state('control')['stopped']:return None
    key = 'follow-last:'+book.symbol
    with store.transaction():
        if now-store.get_state(key,{'at':0})['at']<HORIZON:return None
        side = event['side']
        buy = side=='long'
        top = min(book.asks) if buy else max(book.bids)
        quantity = D(250)/top
        try:price = book.fill('buy' if buy else 'sell',quantity)*(1+LATENCY if buy else 1-LATENCY)
        except ValueError:return None
        previous = evidence(store.list('follow_sample',10000),book.symbol,side,now)
        predicted = (previous['wins']+1)/(previous['completed']+2) if previous['completed']>=30 else None
        doc = {'version':VERSION,'symbol':book.symbol,'side':side,'address':event['address'],
            'entered_at':now,'due_at':now+HORIZON,'status':'pending','quantity':str(quantity),'entry_price':str(price),
            'entry_fee':str(price*quantity*FEE),'entry_snapshot':book.view(now),'predicted_at_entry':predicted,
            'funding_reserve_bps':'20','mode':'shadow_research_not_account_trade','source':'Prospective observed position change + Hyperliquid live book'}
        result = store.put('follow_sample',doc)
        store.set_state(key,{'at':now})
        return result


def resolve_samples(store,books,now=None):
    now = time.time() if now is None else now
    for sample in store.list('follow_sample',10000):
        if sample['status']!='pending' or now<sample['due_at']:continue
        book = books.get(('hyperliquid',sample['symbol']))
        if now-sample['due_at']>60:
            sample.update(status='unavailable',resolved_at=now,reason='No fresh executable exit was recorded within 60 seconds of the fixed horizon.')
        elif book is None or not book.fresh(now):continue
        else:
            buy = sample['side']=='long'
            quantity,entry = D(sample['quantity']),D(sample['entry_price'])
            try:exit_price = book.fill('sell' if buy else 'buy',quantity)*(1-LATENCY if buy else 1+LATENCY)
            except ValueError:continue
            reserve = entry*quantity*D(sample['funding_reserve_bps'])/10000
            pnl = (exit_price-entry)*quantity*(1 if buy else -1)-D(sample['entry_fee'])-exit_price*quantity*FEE-reserve
            sample.update(status='closed',closed_at=now,exit_price=str(exit_price),exit_snapshot=book.view(now),
                funding_reserve_usdc=str(reserve),net_pnl_usdc=str(pnl),success=pnl>0)
        store.replace(sample['id'],sample)

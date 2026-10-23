"""Observed complete position cycles, never a follower win-probability shortcut."""
from decimal import Decimal as D
import hashlib
import json
from statistics import median
import time
import httpx
from .models import decimal
from .traders import ADDRESS, INFO_URL
from .catalogue import NATIVE

HISTORY_VERSION = 'public-cycles-v2'


def analyze_fills(rows, as_of=None):
    as_of = time.time() if as_of is None else as_of
    active,completed,seen = {},[],set()
    rejected = incomplete = gaps = 0
    accepted = []
    for raw in sorted(rows,key=lambda r:r.get('time',0)):
        coin = raw.get('coin')
        if not isinstance(coin,str) or not NATIVE.fullmatch(coin):continue
        try:
            at = int(raw['time'])/1000
            if at>as_of:continue
            identity = (coin,int(raw['time']),str(raw['tid']))
            if identity in seen:continue
            seen.add(identity)
            start,size,price,fee,pnl = [decimal(raw[k]) for k in ['startPosition','sz','px','fee','closedPnl']]
            if at<=0 or size<=0 or price<=0 or raw['side'] not in ['A','B'] or raw.get('feeToken','').strip()!='USDC':
                raise ValueError('Invalid or incomparable fill')
        except (KeyError,ValueError,TypeError):
            active.pop(coin,None)
            rejected += 1
            continue
        accepted.append(raw)
        change = size if raw['side']=='B' else -size
        end = start+change
        cycle = active.get(coin)
        if cycle and cycle['size']!=start:
            active.pop(coin)
            cycle = None
            gaps += 1
        if start==0:
            cycle = {'coin':coin,'side':'long' if change>0 else 'short','opened_at':at,'size':D(0),'gross':D(0),'fees':D(0),'entry_notional':D(0),'fills':0}
            active[coin] = cycle
        reversal = start*end<0
        close_fraction = abs(start)/size if reversal else D(1)
        if cycle:
            cycle['gross'] += pnl
            cycle['fees'] += fee*close_fraction
            cycle['fills'] += 1
            if start==0 or start*change>0:cycle['entry_notional'] += size*price
            cycle['size'] = end
            if end==0 or reversal:
                net = cycle['gross']-cycle['fees']
                completed.append({'coin':coin,'side':cycle['side'],'opened_at':cycle['opened_at'],'closed_at':at,
                    'holding_seconds':at-cycle['opened_at'],'gross_closed_pnl_usdc':str(cycle['gross']),
                    'trading_fees_usdc':str(cycle['fees']),'net_before_funding_usdc':str(net),
                    'entry_notional_usdc':str(cycle['entry_notional']),'fills':cycle['fills']})
                active.pop(coin,None)
        else:incomplete += 1
        if reversal:
            # A reversal closes the old cycle and opens a new, fully observed one.
            active[coin] = {'coin':coin,'side':'long' if end>0 else 'short','opened_at':at,'size':end,
                'gross':D(0),'fees':fee*(1-close_fraction),'entry_notional':abs(end)*price,'fills':1}
    completed.sort(key=lambda r:r['closed_at'])
    pnls = [D(c['net_before_funding_usdc']) for c in completed]
    wins = sum(p>0 for p in pnls)
    gains = sum((p for p in pnls if p>0),D(0))
    losses = -sum((p for p in pnls if p<0),D(0))
    curve = peak = drawdown = D(0)
    for pnl in pnls:
        curve += pnl
        peak = max(peak,curve)
        drawdown = max(drawdown,peak-curve)
    return {'version':HISTORY_VERSION,'as_of':as_of,'fills_analyzed':len(accepted),'complete_cycles':len(completed),
        'historical_win_rate_pct':100*wins/len(pnls) if pnls else None,'winning_cycles':wins,
        'net_before_funding_usdc':str(sum(pnls,D(0))) if pnls else None,'profit_factor':str(gains/losses) if losses else None,
        'realized_pnl_drawdown_usdc':str(drawdown) if pnls else None,'median_holding_seconds':median([c['holding_seconds'] for c in completed]) if completed else None,
        'unclosed_cycles':len(active),'incomplete_initial_fills':incomplete,'position_gaps':gaps,'rejected_fills':rejected,
        'first_fill_at':min((r['time']/1000 for r in accepted),default=None),
        'last_fill_at':max((r['time']/1000 for r in accepted),default=None),'cycles':completed[-30:],
        'recent_fills':[{'coin':r['coin'],'side':r['side'],'action':r.get('dir','provider execution'),
            'price':str(r['px']),'quantity':str(r['sz']),'source_at':r['time']/1000,
            'closed_pnl_before_fees_usdc':str(r['closedPnl']),'trading_fee_usdc':str(r['fee'])} for r in accepted[-20:]],
        'follower_success_probability_pct':None,'account_drawdown_pct':None,
        'limitations':['Historical rate counts complete flat-to-flat position cycles, not individual partial fills.',
            'Trading fees include provider builder fees exactly once. Funding, deposits, withdrawals and outside hedges are not reconstructed.',
            'Net P&L is before funding. Realized P&L drawdown is not account-equity drawdown.',
            'Large-trade-selected wallets have selection bias; these figures do not estimate a follower’s odds.',
            'Only the provider-available requested history is observed; absence of returned fills does not prove a complete history.']}


async def fetch_history(store,address,client=None):
    if not ADDRESS.fullmatch(address):raise ValueError('Invalid public address')
    now = time.time()
    owns = client is None
    client = client or httpx.AsyncClient(timeout=20,follow_redirects=False)
    try:
        response = await client.post(INFO_URL,json={'type':'userFillsByTime','user':address,
            'startTime':int((now-30*86400)*1000),'endTime':int(now*1000),'aggregateByTime':False})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows,list) or len(rows)>2000:raise ValueError('Unexpected fill-history response')
        summary = analyze_fills(rows,now)
        summary.update(address=address,source='Hyperliquid public info/userFillsByTime',received_at=now,
            requested_lookback_days=30,provider_limit_reached=len(rows)==2000,
            input_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        store.set_state('trader_history:'+address,dict(summary,raw_fills=rows))
        store.set_state('trader_history_error:'+address,None)
        return summary
    finally:
        if owns:await client.aclose()

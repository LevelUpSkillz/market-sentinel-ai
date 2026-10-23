"""Discover public participants from large prints; size is not proof of skill."""
from decimal import Decimal as D
import time
from .models import decimal
from .traders import ADDRESS
from .follow_evidence import evidence
from .catalogue import NATIVE

THRESHOLD = D('100000')
AUTO_LIMIT = 5


def discover(store,trade,now=None):
    now = time.time() if now is None else now
    if trade.get('provider')!='hyperliquid' or trade.get('source_at') is None or not -1<=now-trade['source_at']<=10:return []
    notional = decimal(trade['price'])*decimal(trade['quantity'])
    if notional<THRESHOLD:return []
    existing = store.list('watchlist',10)
    slots = min(10-len(existing),AUTO_LIMIT-sum(t.get('origin')=='auto_large_trade' for t in existing))
    added = []
    for role,address in zip(['buyer','seller'],trade.get('public_participants',[])):
        if slots<=0:break
        if not isinstance(address,str) or not ADDRESS.fullmatch(address) or int(address,16)==0:continue
        address = address.lower()
        if store.get('watchlist',address):continue
        doc = {'address':address,'label':'Large-trade participant '+address[:8]+'…','origin':'auto_large_trade',
            'added_at':now,'discovery':{'source':'Hyperliquid public WebSocket trades/users','symbol':trade['symbol'],
                'trade_id':trade['trade_id'],'source_at':trade['source_at'],'received_at':trade['received_at'],
                'observed_notional_usdc':str(notional),'role_in_print':role},
            'selection_note':'Observed in a print of at least 100,000 USDC; size does not establish identity, account wealth or profitability.'}
        store.put('watchlist',doc,id=address)
        store.put('audit',{'action':'watchlist.auto_discovered','address':address,'actor':'read_only_collector','source':doc['discovery']})
        added.append(address)
        slots -= 1
    return added


def intelligence(store,books,now=None):
    now = time.time() if now is None else now
    rows = store.list('follow_sample',10000)
    stopped = store.get_state('control')['stopped']
    actions = []
    for trader in store.list('watchlist',10):
        snapshot = store.get_state('trader:'+trader['address'])
        if not snapshot:continue
        history = store.get_state('trader_history:'+trader['address'])
        for position in snapshot['positions']:
            if not NATIVE.fullmatch(position['coin']) or decimal(position['szi'])==0:continue
            side = 'long' if decimal(position['szi'])>0 else 'short'
            symbol = position['coin']+'-USDC-PERP'
            book = books.get(('hyperliquid',symbol))
            confidence = evidence(rows,symbol,side,now)
            reasons = []
            reject = stopped or now-snapshot['received_at']>90 or not book or not book.fresh(now)
            if stopped:reasons.append('Emergency stop is active.')
            if now-snapshot['received_at']>90:reasons.append('The public position snapshot is stale.')
            if not book or not book.fresh(now):reasons.append('A fresh matching perpetual order book is unavailable.')
            drift = None
            entry = decimal(position.get('entryPx') or 0)
            if book and book.fresh(now) and entry>0:
                executable = min(book.asks) if side=='long' else max(book.bids)
                drift = (executable-entry)/entry*10000*(1 if side=='long' else -1)
                if drift>20:
                    reject = True
                    reasons.append('The follower price is more than 20 bps worse than the observed average entry.')
                liq = decimal(position.get('liquidationPx') or 0)
                if liq>0 and abs(executable-liq)/executable<D('.02'):
                    reject = True
                    reasons.append('Observed liquidation price is within 2% of the current quote.')
            if history and history['complete_cycles']>=5 and D(history['net_before_funding_usdc'])<0:
                reject = True
                reasons.append('Observed complete historical cycles have negative P&L after trading fees, before funding.')
            if confidence['estimated_success_pct'] is None:reasons.append('Follower odds have insufficient validated evidence; the trader’s historical win rate is not a substitute.')
            reasons.append('Define an independent stop, target and exposure budget in the paper risk planner before considering any entry.')
            actions.append({'address':trader['address'],'label':trader['label'],'symbol':symbol,'side':side,
                'decision':'NO-GO' if reject else 'WAIT','next_action':'Avoid chasing this entry' if reject else 'Investigate with a paper risk plan',
                'entry_drift_bps':str(drift) if drift is not None else None,'reasons':reasons,'follow_evidence':confidence,
                'source':snapshot['source'],'source_at':snapshot.get('source_at'),'received_at':snapshot['received_at'],
                'history_received_at':history.get('received_at') if history else None})
    return {'as_of':now,'actions':actions,'discovery_threshold_usdc':str(THRESHOLD),'auto_wallet_limit':AUTO_LIMIT,
        'poll_interval_seconds':30,'historical_scope':'Up to 2,000 provider-available native perpetual fills in a requested 30-day window; complete cycles only. Namespaced HIP-3 and spot IDs are excluded.',
        'probability_policy':'A percentage for future follower success requires prospective non-overlapping observations, coverage, held-out calibration and uncertainty checks.',
        'source':'Hyperliquid public trades, clearinghouseState and userFillsByTime; selected cohort, not the whole market.'}

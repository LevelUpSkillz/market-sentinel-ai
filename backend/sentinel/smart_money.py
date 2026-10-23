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
            stale_position = now-snapshot['received_at']>90
            unavailable_book = not book or not book.fresh(now)
            adverse_entry = nearby_liquidation = negative_history = False
            reject = stopped or stale_position or unavailable_book
            if stopped:reasons.append('Emergency stop is active.')
            if stale_position:reasons.append('The public position snapshot is stale.')
            if unavailable_book:reasons.append('A fresh matching perpetual order book is unavailable.')
            drift = None
            entry = decimal(position.get('entryPx') or 0)
            executable = (min(book.asks) if side=='long' else max(book.bids)) if book and book.fresh(now) else None
            if book and book.fresh(now) and entry>0:
                drift = (executable-entry)/entry*10000*(1 if side=='long' else -1)
                if drift>20:
                    adverse_entry = True
                    reject = True
                    reasons.append('The follower price is more than 20 bps worse than the observed average entry.')
                liq = decimal(position.get('liquidationPx') or 0)
                if liq>0 and abs(executable-liq)/executable<D('.02'):
                    nearby_liquidation = True
                    reject = True
                    reasons.append('Observed liquidation price is within 2% of the current quote.')
            if history and history['complete_cycles']>=5 and D(history['net_before_funding_usdc'])<0:
                negative_history = True
                reject = True
                reasons.append('Observed complete historical cycles have negative P&L after trading fees, before funding.')
            if confidence['estimated_success_pct'] is None:reasons.append('Follower odds have insufficient validated evidence; the trader’s historical win rate is not a substitute.')
            reasons.append('Define an independent stop, target and exposure budget in the paper risk planner before considering any entry.')
            # The headline must explain the actual blocking evidence. A favorable
            # entry comparison can still fail liquidation/history checks; calling
            # every NO-GO "chasing" incorrectly describes such observations.
            if stopped:
                cause,next_action = 'emergency_stop','Research entries are paused'
            elif stale_position:
                cause,next_action = 'stale_position','Wait for a fresh public position snapshot'
            elif unavailable_book:
                cause,next_action = 'unavailable_market','Wait for a fresh matching market book'
            elif nearby_liquidation:
                cause,next_action = 'nearby_liquidation','Review nearby liquidation risk before copying'
            elif adverse_entry:
                cause,next_action = 'adverse_entry','Avoid chasing this entry'
            elif negative_history:
                cause,next_action = 'negative_history','Review the trader’s historical losses before copying'
            elif reject:
                cause,next_action = 'risk_checks','Do not enter while risk checks fail'
            else:
                cause,next_action = 'independent_plan_required','Investigate with a paper risk plan'
            actions.append({'address':trader['address'],'label':trader['label'],'symbol':symbol,'side':side,
                'decision':'NO-GO' if reject else 'WAIT','next_action':next_action,'decision_cause':cause,
                'asset':position['coin'],'instrument':'perpetual','quote_currency':'USDC',
                'reported_average_entry_price':str(entry) if entry>0 else None,
                'current_executable_price':str(executable) if executable is not None else None,
                'position_size_native_units':str(decimal(position['szi'])),
                'observation_kind':'current_public_position',
                'timing_note':'Current public position snapshot; an opening or exact execution time is not established.',
                'market_source_at':book.source_at if executable is not None else None,
                'market_received_at':book.received_at if executable is not None else None,
                'entry_drift_bps':str(drift) if drift is not None else None,'reasons':reasons,'follow_evidence':confidence,
                'source':snapshot['source'],'source_at':snapshot.get('source_at'),'received_at':snapshot['received_at'],
                'history_received_at':history.get('received_at') if history else None})
    return {'as_of':now,'actions':actions,'discovery_threshold_usdc':str(THRESHOLD),'auto_wallet_limit':AUTO_LIMIT,
        'poll_interval_seconds':30,'historical_scope':'Up to 2,000 provider-available native perpetual fills in a requested 30-day window; complete cycles only. Namespaced HIP-3 and spot IDs are excluded.',
        'probability_policy':'A percentage for future follower success requires prospective non-overlapping observations, coverage, held-out calibration and uncertainty checks.',
        'source':'Hyperliquid public trades, clearinghouseState and userFillsByTime; selected cohort, not the whole market.'}

"""Public-address observation; never deanonymizes wallets or infers hidden hedges."""
from decimal import Decimal as D
import re
import time
import httpx
from .models import decimal
from .engine import copy_decision

ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')
INFO_URL = 'https://api.hyperliquid.xyz/info'

def position_changes(previous, current, observed_at):
    old = {p['coin']:p for p in previous}
    new = {p['coin']:p for p in current}
    events = []
    for coin in sorted(old.keys()|new.keys()):
        a,b = old.get(coin),new.get(coin)
        size_a,size_b = decimal(a['szi']) if a else D(0),decimal(b['szi']) if b else D(0)
        if size_a==size_b:
            continue
        if size_a*size_b < 0:
            action = 'reversal'
        elif size_a==0:
            action = 'opened'
        elif size_b==0:
            action = 'closed'
        elif abs(size_b)>abs(size_a):
            action = 'increased'
        else:
            action = 'reduced'
        events.append({'coin':coin,'action':action,'before_size':str(size_a),'after_size':str(size_b),
            'entry_price':b.get('entryPx') if b else None,'side':'long' if size_b>0 else 'short' if size_b<0 else None,
            'observed_at':observed_at,'baseline':False,
            'confidence':'public_snapshot_difference','timing':'Change occurred between polls; exact entry time is unknown.'})
    return events

def ranking_evidence(samples):
    # Polls of account equity are not returns: deposits, withdrawals and transfers confound them.
    return {'rank':None,'status':'INSUFFICIENT EVIDENCE','observations':len(samples),
            'risk_adjusted_return':None,'max_drawdown':None,'copyability':None,
            'reasons':['Cash-flow-adjusted returns, complete history and out-of-sample evidence are required.',
                       'Watchlist membership is user-selected and subject to selection/survivorship bias.',
                       'Public fills may be truncated and do not establish portfolio-wide performance.']}

async def poll_trader(store, trader, books, client=None):
    address = trader['address']
    if not ADDRESS.fullmatch(address):
        raise ValueError('Invalid public EVM address')
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=15)
    try:
        response = await client.post(INFO_URL,json={'type':'clearinghouseState','user':address})
        response.raise_for_status()
        state = response.json()
        positions = [r['position'] for r in state['assetPositions']]
        # Validate before persisting any provider payload as financial evidence.
        for p in positions:
            decimal(p['szi'])
            if p.get('entryPx') is not None:
                decimal(p['entryPx'])
        now = time.time()
        key = 'trader:'+address
        prior = store.get_state(key)
        doc = {'address':address,'positions':positions,'source':'Hyperliquid public info/clearinghouseState',
               'source_at':state.get('time',0)/1000 or None,'received_at':now,'observed_at':now,
               'account_value':str(decimal(state['marginSummary']['accountValue'])),
               'data_completeness':'Current account snapshot only; external hedges and complete returns unknown.',
               'baseline':prior is None,'ranking':ranking_evidence([])}
        events = position_changes(prior['positions'],positions,now) if prior else []
        for event in events:
            event.update(address=address,source=doc['source'])
            book = books.get(('hyperliquid',event['coin']+'-USDC-PERP'))
            event['analysis'] = copy_decision(event,book,stopped=store.get_state('control')['stopped'])
            store.put('trader_event',event)
            from .follow_evidence import begin_sample
            begin_sample(store,event,book,now)
        store.set_state(key,doc)
        store.set_state('trader_error:'+address,None)
        store.put('trader_snapshot',doc)
        return doc
    finally:
        if owns_client:
            await client.aclose()

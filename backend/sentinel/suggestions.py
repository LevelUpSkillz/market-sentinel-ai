"""Explain current research choices. Public positions never approve a spot order.

No learned strategy, invented prices, inferred identity or synthetic odds.
"""
from decimal import Decimal, InvalidOperation
import time


def recent(at,now,seconds):
    return isinstance(at,(int,float)) and not isinstance(at,bool) and -1<=now-at<=seconds


def profile_for(action,store,now):
    history=store.get_state('trader_history:'+action['address'])
    history=history if history and recent(history.get('received_at'),now,7*3600) else None
    recent_fills=history.get('recent_fills',[]) if history else []
    last_fill=recent_fills[-1] if recent_fills else None
    return {'last_action':{'action':last_fill.get('action'),'coin':last_fill.get('coin'),'source_at':last_fill.get('source_at')} if last_fill else None,
        'address':action['address'],'direction':action['side'],
        'symbol':action['symbol'],'position_received_at':action['received_at'],
        'position_recent':recent(action['received_at'],now,90),
        'decision':action['decision'],'reason':action['next_action'],
        'history_received_at':history.get('received_at') if history else None,
        'completed_positions':history.get('complete_cycles') if history else None,
        'historical_win_rate_pct':history.get('historical_win_rate_pct') if history else None,
        'net_before_funding_usdc':history.get('net_before_funding_usdc') if history else None,
        'truncated':history.get('provider_limit_reached') if history else None,
        'source':action['source'],
        'note':'Public perpetual position; not a Kraken spot trade. Past results exclude funding and may be incomplete.'}


def review_profiles(profiles):
    notes=[]
    for profile in profiles:
        if not profile['position_recent']:
            notes.append('A matching wallet position is old; do not use it to time an entry.')
        elif profile['direction']=='short':
            notes.append('A matching wallet is positioned for a price fall. It does not support this long-only spot idea.')
        count=profile['completed_positions']
        if count is None or count<20:
            notes.append('Available trader history is missing or small. It cannot establish a reliable trading edge.')
        net=profile['net_before_funding_usdc']
        if net is not None:
            try:
                if Decimal(str(net)).is_finite() and Decimal(str(net))<0:
                    notes.append('A matching trader has net trading losses after fees, before funding. A high win rate would not change that loss.')
            except InvalidOperation:pass
        if profile['truncated']:
            notes.append('A matching trader has truncated history; missing trades can change the performance picture.')
    return list(dict.fromkeys(notes))


def suggestions(radar,intel,store,*,now=None,stopped=False):
    now=time.time() if now is None else now
    actions=intel.get('actions',[])
    cards=[]
    for setup in radar.get('setups',[])[:8]:
        symbol=setup['symbol']; asset=symbol.removesuffix('-USD')
        fresh=all(recent(setup.get(k),now,5) for k in ('source_at','received_at')) and recent(radar.get('as_of'),now,5)
        active=fresh and isinstance(setup.get('expires_at'),(int,float)) and setup['expires_at']>now
        if setup.get('entry_deadline') is not None:active=active and setup['entry_deadline']>now
        decision=setup.get('decision') if active and not stopped else 'NO-GO'
        if decision not in ('GO','WAIT','NO-GO'):decision='NO-GO'
        profiles=[profile_for(a,store,now) for a in actions if a.get('asset',a['symbol'].removesuffix('-USDC-PERP'))==asset][:4]
        state='practice_ready' if decision=='GO' else 'watch' if decision=='WAIT' else 'skip'
        cards.append({'id':setup['id'],'symbol':symbol,'provider':'kraken','decision':decision,'state':state,
            'title':('Try this idea with practice money' if decision=='GO' else 'Watch '+asset+' for a possible entry' if decision=='WAIT' else 'Skip this entry for now'),
            'reason':('New app trades are paused.' if stopped else 'Prices are old or the entry window has ended.' if not active else setup['next_action']),
            'levels':{k:setup.get(k) if active else None for k in ('entry_trigger','entry_limit','stop','target')},
            'cost_bps':setup.get('estimated_round_trip_cost_bps') if active else None,
            'facts':setup.get('facts',[])[:4],'checks':setup.get('reasons',[])[:5],
            'source_at':setup.get('source_at'),'received_at':setup.get('received_at'),
            'expires_at':setup.get('entry_deadline') or setup.get('expires_at'),'profiles':profiles,'trader_review':review_profiles(profiles),
            'success_probability_pct':None,'odds_note':'Not validated. Trader win rates are not your odds.',
            'execution':'Practice review only. No real order is authorized.'})
    # Real observation cards keep the section useful during honest baseline warmup.
    seen={c['symbol'] for c in cards}
    for row in radar.get('watchlist',[]):
        if len(cards)>=5:break
        if row['symbol'] in seen:continue
        fresh=recent(row.get('source_at'),now,5) and recent(row.get('received_at'),now,5)
        if not fresh:continue
        symbol=row['symbol']; asset=symbol.removesuffix('-USD');seen.add(symbol)
        profiles=[profile_for(a,store,now) for a in actions if a.get('asset',a['symbol'].removesuffix('-USDC-PERP'))==asset][:4]
        cards.append({'id':'watch:'+symbol,'symbol':symbol,'provider':'kraken','decision':'WAIT','state':'watch',
            'title':'Watch '+asset+' — no entry yet',
            'reason':('Enough price history is available, but no entry has passed the strategy checks.' if row.get('baseline_ready') else 'Still collecting the five-minute price history needed to judge this idea.'),
            'levels':{},'cost_bps':None,'facts':['Observed Kraken midpoint: '+row['price']+' USD. This is not an execution price.'],
            'checks':[],'source_at':row['source_at'],'received_at':row['received_at'],'expires_at':None,'profiles':profiles,'trader_review':review_profiles(profiles),
            'success_probability_pct':None,'odds_note':'Not validated. No success percentage is available.',
            'execution':'Watch only; no practice entry or real order is approved.'})
    # Wallet evidence for tokens not currently in radar remains explicitly a
    # different instrument and cannot turn an incomplete spot idea into GO.
    for action in actions:
        if len(cards)>=7:break
        if any(p['address']==action['address'] and p['symbol']==action['symbol'] for c in cards for p in c['profiles']):continue
        if not recent(action.get('received_at'),now,90):continue
        asset=action.get('asset',action['symbol'].removesuffix('-USDC-PERP'))
        cards.append({'id':'wallet:'+action['address']+action['symbol'],'symbol':action['symbol'],'provider':'hyperliquid',
            'decision':'NO-GO' if action['decision']=='NO-GO' or stopped else 'WAIT','state':'skip' if action['decision']=='NO-GO' or stopped else 'watch',
            'title':'Do not copy this position yet','reason':action['next_action'],
            'levels':{},'cost_bps':None,'facts':['Public wallet reports a '+action['side']+' '+asset+' perpetual position.'],
            'checks':action.get('reasons',[])[:3],'source_at':action.get('source_at'),'received_at':action['received_at'],
            'expires_at':None,'profiles':[profile_for(action,store,now)],'trader_review':review_profiles([profile_for(action,store,now)]),'success_probability_pct':None,
            'odds_note':'Not validated. A public trader’s win rate is not your odds.',
            'execution':'Public trader research only; not a Kraken spot order.'})
    return {'as_of':now,'cards':cards,'strategy_version':radar.get('strategy_version'),
        'scope':'deterministic_research_only','source':'Kraken public quotes and radar; Hyperliquid public positions and available fills',
        'limitations':['Wallet evidence is a selected sample, not a ranking of the world’s best traders.',
            'Different people can hedge elsewhere. Matching tokens do not make spot and perpetuals equivalent.',
            'No suggestion places an order. GO means practice checks passed, not that profit is likely.']}

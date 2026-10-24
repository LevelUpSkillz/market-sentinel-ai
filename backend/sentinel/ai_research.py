"""Bounded public evidence packets for an unprivileged Cloudflare explainer.

No account/vault/order access. The AI cannot set a price, risk limit or decision.
"""
import time
from .suggestions import suggestions
from .smart_money import intelligence


def evidence_packet(runtime,store,mode,card_id=None):
    if not store.rate('cloudflare_ai:minute',4,60) or not store.rate('cloudflare_ai:day',30,86400):
        raise ValueError('The free research allowance is used up. Try again later.')
    data=suggestions(runtime.radar.snapshot(runtime.books),intelligence(store,runtime.books),store,
        stopped=store.get_state('control')['stopped'])
    cards=data['cards']
    if card_id:
        cards=[c for c in cards if c['id']==card_id]
        if not cards:raise LookupError('This idea has changed or expired. Refresh the trade ideas.')
    cards=cards[:1] if mode!='search' else cards[:7]
    evidence=[]
    for card in cards:
        # Strict allowlist, not recursive forwarding of internal state. Public
        # wallet addresses and custom labels are deliberately absent.
        facts=[card['symbol']+' / '+card['provider']+' / '+card['decision'],card['reason']]
        facts.extend(card.get('facts',[])[:2]);facts.extend(card.get('checks',[])[:2])
        facts.extend(card.get('trader_review',[])[:2])
        evidence.append({'id':'E'+str(len(evidence)+1),'card_id':card['id'],'symbol':card['symbol'],
            'decision':card['decision'],'source':card['provider']+' public market data',
            'source_at':card['source_at'],'received_at':card['received_at'],'expires_at':card['expires_at'],
            'text':' '.join(str(f)[:400] for f in facts)[:1800]})
    store.put('audit',{'action':'ai.public_research_reserved','actor':'owner','mode':mode,
        'evidence_count':len(evidence),'financial_action':False})
    return {'as_of':time.time(),'evidence':evidence,'mode':mode,'daily_limit':30,
        'authority':'explanation_only','financial_action':False,'success_probability_pct':None}

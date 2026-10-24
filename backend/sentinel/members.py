"""Exact-email research invitations. No invitation ever grants owner authority."""
from copy import deepcopy
import hashlib
import json
import re
import time

MAX_MEMBERS=10
PREFIX='auth:member:'  # Excluded from logical backups; restoration never revives access.
VIEWER_GET=frozenset({'/api/session','/api/dashboard','/api/assets','/api/radar','/api/intelligence',
    '/api/traders','/api/trader-directory','/api/records/market_snapshot','/api/records/trader_event','/api/records/trader_cohort'})


def email_address(value):
    if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}',value):
        raise ValueError('Enter a valid exact email address.')
    return value.lower()


def member_key(email):return PREFIX+hashlib.sha256(email.encode()).hexdigest()


def active_member(store,email,now=None):
    try:email=email_address(email)
    except ValueError:return False
    member=store.get_state(member_key(email))
    now=time.time() if now is None else now
    return bool(member and member.get('email')==email and member.get('role')=='viewer' and member.get('revoked') is False and isinstance(member.get('expires_at'),(float,int)) and now<member['expires_at'])


def members(store):
    with store.lock:
        return [json.loads(row['data']) for row in store.execute('SELECT data FROM state WHERE key LIKE ? ORDER BY key',(PREFIX+'%',)).fetchall()]


def invite(store,email,owner,now=None):
    email=email_address(email)
    if email==owner.lower():raise ValueError('The owner already has separate access.')
    now=time.time() if now is None else now
    with store.transaction():
        store.set_default('auth:member_lock',None)
        if store.postgres:store.execute('SELECT data FROM state WHERE key=? FOR UPDATE',('auth:member_lock',)).fetchone()
        existing=store.get_state(member_key(email))
        active=[row for row in members(store) if row.get('revoked') is False and row.get('expires_at',0)>now]
        if not existing and len(members(store))>=MAX_MEMBERS:raise ValueError('This private workspace supports ten invited email addresses. Reuse an existing invitation or review capacity separately.')
        if not active_member(store,email,now) and len(active)>=MAX_MEMBERS:raise ValueError('The private research member limit is reached.')
        doc={'email':email,'role':'viewer','created_at':now,'expires_at':now+30*86400,'revoked':False}
        store.set_state(member_key(email),doc)
        store.put('audit',{'action':'research.invited','actor':'owner','member_id':member_key(email)[len(PREFIX):],'role':'viewer','expires_at':doc['expires_at']})
    return doc


def revoke(store,email):
    email=email_address(email)
    with store.transaction():
        doc=store.get_state(member_key(email))
        if not doc:raise ValueError('Research invitation not found.')
        doc['revoked']=True;doc['revoked_at']=time.time();store.set_state(member_key(email),doc)
        store.put('audit',{'action':'research.revoked','actor':'owner','member_id':member_key(email)[len(PREFIX):]})
    return doc


def shared_research(value):
    """Remove owner's paper-risk inputs and custom labels from shared public data."""
    private={'risk_inputs','risk_plan','account','paper','control','connection','real_capital_profile','actor','cipher','api_key','api_secret'}
    if isinstance(value,list):return [shared_research(item) for item in value]
    if isinstance(value,dict):
        return {key:('Public wallet' if key=='label' else shared_research(item)) for key,item in value.items() if key not in private}
    return deepcopy(value)

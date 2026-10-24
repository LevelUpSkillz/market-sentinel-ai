"""Supabase Auth only: single-use PKCE and separate research-only app sessions.

Never queries Supabase database/storage or reads its service-role/provider secrets.
No OAuth access/refresh token reaches browser storage or the research journal.
"""
import base64
import hashlib
import hmac
import json
import math
import secrets
import time
from urllib.parse import urlencode,urlparse
from cryptography.fernet import Fernet,InvalidToken
import httpx
from .members import active_member,email_address

FLOW_COOKIE='market_google_flow'
SESSION_COOKIE='market_research_session'
TTL=3600


def sign_session(secret,email,subject,environment,now=None,role='viewer'):
    if role not in {'viewer','owner'}:raise ValueError('Invalid Google session role')
    now=time.time() if now is None else now
    payload={'email':email,'sub':subject,'role':role,'aud':'market-sentinel-google-owner' if role=='owner' else 'market-sentinel-research','env':environment,'iat':now,'exp':now+TTL}
    raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode().rstrip('=')
    return raw+'.'+hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()


def research_session(token,secret,environment,now=None):
    now=time.time() if now is None else now
    if not secret or not isinstance(token,str) or len(token)>4096:return None
    try:
        raw,signature=token.split('.')
        if not hmac.compare_digest(signature,hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()):return None
        doc=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
        if doc.get('role') not in {'viewer','owner'} or doc.get('aud')!=('market-sentinel-google-owner' if doc.get('role')=='owner' else 'market-sentinel-research') or doc.get('env')!=environment or not isinstance(doc.get('sub'),str) or not doc['sub']:return None
        if type(doc.get('iat')) not in (int,float) or type(doc.get('exp')) not in (int,float) or not math.isfinite(doc['iat']) or not math.isfinite(doc['exp']) or not 0<=now-doc['iat']<=TTL or not now<doc['exp']<=now+TTL:return None
        doc['email']=email_address(doc['email']);return doc
    except (ValueError,TypeError,KeyError):return None


class GoogleAuth:
    def __init__(self,store,settings,client=None):self.store,self.settings,self.client=store,settings,client

    @property
    def ready(self):
        value=getattr(self.settings,'supabase_auth_url','')
        p=urlparse(value)
        return bool(p.scheme=='https' and p.hostname and p.hostname.endswith('.supabase.co') and not p.username and not p.password and not p.port and not p.path and not p.query and not p.fragment and getattr(self.settings,'supabase_publishable_key','') and getattr(self.settings,'research_origin','') and len(self.settings.session_secret)>=32)

    def _vault(self):return Fernet(base64.urlsafe_b64encode(hashlib.sha256(self.settings.session_secret.encode()).digest()))

    def start(self):
        if not self.ready:raise ValueError('Google sign-in is not configured for this app yet.')
        now=time.time()
        if not self.store.rate('oauth:global',100,600):raise ValueError('Sign-in is busy. Try again later.')
        nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
        key='auth:oauth:'+hashlib.sha256(nonce.encode()).hexdigest()
        with self.store.transaction():
            rows=self.store.execute('SELECT key,data FROM state WHERE key LIKE ?',('auth:oauth:%',)).fetchall()
            for row in rows:
                if json.loads(row['data']).get('expires_at',0)<=now:self.store.execute('DELETE FROM state WHERE key=?',(row['key'],))
            self.store.set_state(key,{'expires_at':now+300,'cipher':self._vault().encrypt(verifier.encode()).decode()})
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        params={'provider':'google','redirect_to':self.settings.research_origin+'/api/auth/google/callback','code_challenge':challenge,'code_challenge_method':'s256','flow_type':'pkce'}
        return self.settings.supabase_auth_url+'/auth/v1/authorize?'+urlencode(params),nonce

    async def finish(self,code,nonce):
        if not self.ready or not isinstance(code,str) or not 1<=len(code)<=4096 or not isinstance(nonce,str) or not 32<=len(nonce)<=128:raise ValueError('Restart Google sign-in from the same browser.')
        key='auth:oauth:'+hashlib.sha256(nonce.encode()).hexdigest()
        with self.store.transaction():
            row=self.store.execute('SELECT data FROM state WHERE key=?'+(' FOR UPDATE' if self.store.postgres else ''),(key,)).fetchone()
            if not row:raise ValueError('Google sign-in expired or was already used. Start again.')
            doc=json.loads(row['data']);self.store.execute('DELETE FROM state WHERE key=?',(key,))
        if doc.get('expires_at',0)<=time.time():raise ValueError('Google sign-in expired. Start again.')
        try:verifier=self._vault().decrypt(doc['cipher'].encode()).decode()
        except (InvalidToken,KeyError,ValueError,TypeError,AttributeError,UnicodeError):raise ValueError('Restart Google sign-in.') from None
        owns=self.client is None;client=self.client or httpx.AsyncClient(timeout=12,follow_redirects=False)
        try:
            headers={'apikey':self.settings.supabase_publishable_key}
            response=await client.post(self.settings.supabase_auth_url+'/auth/v1/token?grant_type=pkce',headers=headers,json={'auth_code':code,'code_verifier':verifier})
            if response.status_code!=200 or len(response.content)>131072:raise ValueError()
            token=response.json().get('access_token')
            if not isinstance(token,str) or not 1<=len(token)<=16384:raise ValueError()
            user_response=await client.get(self.settings.supabase_auth_url+'/auth/v1/user',headers={**headers,'Authorization':'Bearer '+token})
            if user_response.status_code!=200 or len(user_response.content)>131072:raise ValueError()
            user=user_response.json();email=email_address(user.get('email'))
            if not user.get('email_confirmed_at') or not isinstance(user.get('id'),str) or not user['id'] or not any(isinstance(item,dict) and item.get('provider')=='google' for item in user.get('identities',[])):raise ValueError()
        except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError):raise ValueError('Google identity verification failed. Start sign-in again.') from None
        finally:
            if owns:await client.aclose()
        if email!=self.settings.owner_email.lower() and not active_member(self.store,email):raise ValueError('An active Market Sentinel invitation is required for this Google account.')
        role='owner' if getattr(self.settings,'google_owner_enabled',False) and email==self.settings.owner_email.lower() else 'viewer'
        if role=='owner':
            verified=any(isinstance(item,dict) and item.get('provider')=='google' and isinstance(item.get('identity_data'),dict) and item['identity_data'].get('email','').lower()==email and item['identity_data'].get('email_verified') is True for item in user.get('identities',[]))
            if not verified:raise ValueError('Your verified owner Google email is required.')
        self.store.put('audit',{'action':'google.login','actor':role,'member_id':hashlib.sha256(email.encode()).hexdigest()})
        return sign_session(self.settings.session_secret,email,user['id'],self.settings.environment,role=role)

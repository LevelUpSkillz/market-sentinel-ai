"""Cloudflare Access origin verification, independent of untrusted identity headers."""
import asyncio
import time
from urllib.parse import urlparse
import httpx
import jwt

class AccessVerifier:
    def __init__(self,team,audience,owner):
        self.team,self.audience,self.owner=team.rstrip('/'),audience,owner.lower()
        self.keys={}
        self.loaded_at=0
        self.last_attempt=0
        self.lock=asyncio.Lock()

    async def verify(self,token,client=None):
        if not token or len(token)>16384 or not self.team or not self.audience or not self.owner:
            return False
        parsed=urlparse(self.team)
        if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.cloudflareaccess.com') or parsed.path or parsed.username or parsed.password or parsed.port:
            return False
        try:
            header=jwt.get_unverified_header(token)
            if header.get('alg')!='RS256' or not isinstance(header.get('kid'),str) or len(header['kid'])>128:
                return False
            kid=header['kid']
            now=time.time()
            if kid not in self.keys or now-self.loaded_at>3600:
                async with self.lock:
                    if now-self.last_attempt<30:
                        return False
                    self.last_attempt=now
                    owns_client=client is None
                    source=client or httpx.AsyncClient(timeout=5,follow_redirects=False)
                    try:
                        response=await source.get(self.team+'/cdn-cgi/access/certs')
                        response.raise_for_status()
                        rows=response.json()['keys']
                        self.keys={row['kid']:jwt.PyJWK.from_dict(row).key for row in rows if row.get('kty')=='RSA' and row.get('alg','RS256')=='RS256'}
                        self.loaded_at=now
                    finally:
                        if owns_client:await source.aclose()
            key=self.keys.get(kid)
            if key is None:return False
            claims=jwt.decode(token,key=key,algorithms=['RS256'],issuer=self.team,audience=self.audience,
                leeway=5,options={'require':['exp','iat','iss','aud','sub']})
            return claims.get('email','').lower()==self.owner and claims.get('type','app')=='app'
        except (jwt.PyJWTError,httpx.HTTPError,ValueError,KeyError,TypeError):
            return False

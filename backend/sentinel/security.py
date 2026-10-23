import base64
import hashlib
import hmac
import json
import secrets
import time

SESSION_TTL = 8*60*60

def password_hash(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
    return 'scrypt$'+salt+'$'+value

def verify_password(password,encoded):
    try:
        algorithm,salt,expected = encoded.split('$')
        if algorithm!='scrypt':
            return False
        value = hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
        return hmac.compare_digest(value,expected)
    except (ValueError,AttributeError):
        return False

def session_token(secret,environment,now=None):
    now = time.time() if now is None else now
    raw = base64.urlsafe_b64encode(json.dumps({'sub':'owner','scope':'paper','env':environment,'exp':now+SESSION_TTL,'nonce':secrets.token_hex(16)},separators=(',',':')).encode()).decode().rstrip('=')
    return raw+'.'+hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()

def verify_session(token,secret,environment,now=None):
    if not secret or not token or len(token)>2048:
        return False
    now = time.time() if now is None else now
    try:
        raw,signature = token.split('.')
        expected = hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):
            return False
        claims = json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
        return claims['sub']=='owner' and claims['scope']=='paper' and claims['env']==environment and now<claims['exp']<=now+SESSION_TTL+5
    except (ValueError,KeyError,TypeError):
        return False

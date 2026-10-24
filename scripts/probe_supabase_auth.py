"""Public Supabase Auth readiness only; no user login, database query or provider secret."""
import json
import httpx
URL='https://scftnhmrdxrysvnofcyd.supabase.co'
PUBLIC_KEY='sb_publishable_Cnia9Z5Iw0mn1ywN5D6Zrg_eN3dR7yk'
with httpx.Client(timeout=15,follow_redirects=False) as client:
    response=client.get(URL+'/auth/v1/settings',headers={'apikey':PUBLIC_KEY})
    response.raise_for_status()
    value=response.json()
    print('SUPABASE_AUTH_PUBLIC_PROBE '+json.dumps({'provider':'Supabase Auth only','google_enabled':value.get('external',{}).get('google') is True,'database_queries':0,'user_logins':0,'production_mutations':0}))
    if value.get('external',{}).get('google') is not True:raise SystemExit('Existing Google provider is unavailable; do not enable the login button.')

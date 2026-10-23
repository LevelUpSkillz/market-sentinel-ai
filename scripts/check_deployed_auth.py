"""Bounded read-only production acceptance. Never submit orders or change state."""
import httpx

origin = 'https://market-sentinel-ai-api.onrender.com'
with httpx.Client(timeout=25,follow_redirects=False) as client:
    response = client.get('https://market.getlevelupskillz.com/')
    if response.status_code not in (301,302,303,307,308,401,403):
        raise SystemExit('Custom hostname did not deny/redirect anonymous access: '+str(response.status_code))
    print('PRODUCTION_ACCEPTANCE custom_domain_anonymous HTTP '+str(response.status_code))

    for path in ['/health/live','/health/ready']:
        response = client.get(origin+path)
        response.raise_for_status()
        data = response.json()
        if response.status_code!=200 or data.get('live_trading') is not False:
            raise SystemExit('Production health/mode check failed: '+path)
        print('PRODUCTION_ACCEPTANCE '+path+' HTTP 200 live_trading=false')

    for url,headers in [
        (origin+'/api/dashboard',{}),
        ('https://market-sentinel-ai.pages.dev/api/dashboard',{}),
        (origin+'/api/dashboard',{'Cf-Access-Authenticated-User-Email':'levelupskillz.store@gmail.com','Cf-Access-Jwt-Assertion':'invalid-test-token'}),
    ]:
        response = client.get(url,headers=headers)
        if response.status_code!=401:
            raise SystemExit('Production must reject anonymous/forged identity: '+url+' HTTP '+str(response.status_code))
        print('PRODUCTION_ACCEPTANCE protected_api HTTP 401 url='+url+' forged_identity='+str(bool(headers)))

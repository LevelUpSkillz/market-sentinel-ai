"""Bounded read-only production acceptance. Never submit orders or change state."""
import httpx
import time


def get(client,url,**kwargs):
    # Render Free can need a cold start. Retry bounded transient failures without
    # accepting an unhealthy response or turning this into a keep-alive loop.
    for attempt in range(4):
        try:
            response = client.get(url,**kwargs)
            if response.status_code not in (502,503,504) or attempt==3:return response
        except httpx.TransportError:
            if attempt==3:raise
        print('PRODUCTION_ACCEPTANCE transient_retry attempt='+str(attempt+1)+' url='+url,flush=True)
        time.sleep(2)

origin = 'https://market-sentinel-ai-api.onrender.com'
with httpx.Client(timeout=25,follow_redirects=False) as client:
    response = get(client,'https://market.getlevelupskillz.com/')
    if response.status_code not in (301,302,303,307,308,401,403):
        raise SystemExit('Custom hostname did not deny/redirect anonymous access: '+str(response.status_code))
    print('PRODUCTION_ACCEPTANCE custom_domain_anonymous HTTP '+str(response.status_code))

    for path in ['/health/live','/health/ready']:
        response = get(client,origin+path)
        response.raise_for_status()
        data = response.json()
        if response.status_code!=200 or not isinstance(data.get('live_trading'),bool):
            raise SystemExit('Production health/mode check failed: '+path)
        if data.get('live_trading') and (data.get('individual_order_approval_required') is not True or data.get('autonomous_trading') is not False or data.get('withdrawals_enabled') is not False):
            raise SystemExit('Manual execution boundaries failed: '+path)
        print('PRODUCTION_ACCEPTANCE '+path+' HTTP 200 live_trading='+str(data.get('live_trading'))+' app_version='+str(data.get('app_version','not_in_ready_response')))

    for url,headers in [
        (origin+'/api/dashboard',{}),
        ('https://market-sentinel-ai.pages.dev/api/dashboard',{}),
        (origin+'/api/dashboard',{'Cf-Access-Authenticated-User-Email':'levelupskillz.store@gmail.com','Cf-Access-Jwt-Assertion':'invalid-test-token'}),
    ]:
        response = get(client,url,headers=headers)
        if response.status_code!=401:
            raise SystemExit('Production must reject anonymous/forged identity: '+url+' HTTP '+str(response.status_code))
        print('PRODUCTION_ACCEPTANCE protected_api HTTP 401 url='+url+' forged_identity='+str(bool(headers)))

"""Read-only checks of the deployed hostname; no credentials or market requests."""
import httpx
url='https://market.getlevelupskillz.com/'
response=httpx.get(url,follow_redirects=False,timeout=20)
if response.status_code not in (301,302,303,307,308,401,403):
    raise SystemExit('Custom hostname did not deny/redirect unauthenticated access: '+str(response.status_code))
print('Deployed custom hostname rejects/redirects unauthenticated access: HTTP '+str(response.status_code))
try:
    api=httpx.get('https://market-sentinel-ai.pages.dev/api/dashboard',follow_redirects=False,timeout=25)
    print('Deployed API proxy response before backend acceptance: HTTP '+str(api.status_code))
except httpx.HTTPError as error:
    print('Backend acceptance pending: '+type(error).__name__)

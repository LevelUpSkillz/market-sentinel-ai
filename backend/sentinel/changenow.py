"""Read-only ChangeNOW swap estimates. No swap-creation or fund-transfer methods."""
from decimal import Decimal as D
import json
import time
import httpx
from .models import decimal

ESTIMATE_URL = 'https://api.changenow.io/v2/exchange/estimated-amount'
ASSETS = {'btc':'btc','eth':'eth','usdc':'eth'}

async def estimate(settings,source,destination,amount,client=None):
    if not settings.changenow_key:
        raise ValueError('ChangeNOW public business API key is not configured in backend secrets')
    if not settings.changenow_approved:
        raise ValueError('ChangeNOW research-use permission has not been confirmed in deployment configuration')
    if source not in ASSETS or destination not in ASSETS or source==destination:
        raise ValueError('Choose distinct supported assets: btc, eth, usdc (Ethereum)')
    amount = decimal(amount)
    if not D('0.00000001')<=amount<=D('1000000'):
        raise ValueError('Quote amount is out of range')
    params={'fromCurrency':source,'toCurrency':destination,'fromNetwork':ASSETS[source],
            'toNetwork':ASSETS[destination],'fromAmount':str(amount),'flow':'standard','type':'direct'}
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10,follow_redirects=False)
    started = time.time()
    try:
        response = await client.get(ESTIMATE_URL,params=params,headers={'x-changenow-api-key':settings.changenow_key})
        if response.status_code==429:
            raise ValueError('ChangeNOW rate limit reached; retry later')
        if response.status_code in [401,403]:
            raise ValueError('ChangeNOW API key or provider permissions were rejected')
        if response.status_code!=200:
            raise ValueError('ChangeNOW quote service is unavailable; no fallback estimate is substituted')
        row = json.loads(response.text,parse_float=D)
        if not isinstance(row,dict) or row.get('error'):
            raise ValueError('ChangeNOW returned an unavailable route')
        output = decimal(row.get('toAmount'))
        if output<=0:
            raise ValueError('ChangeNOW did not provide a positive output estimate')
        if row.get('fromAmount') is not None and decimal(row['fromAmount'])!=amount:
            raise ValueError('ChangeNOW response input amount differs from the requested amount')
        for field,expected in [('fromCurrency',source),('toCurrency',destination),('fromNetwork',ASSETS[source]),('toNetwork',ASSETS[destination])]:
            if row.get(field) and row[field].lower()!=expected:
                raise ValueError('ChangeNOW response asset or network differs from the requested route')
        now=time.time()
        return {'provider':'changenow','kind':'indicative_swap_estimate','from_currency':source,'to_currency':destination,
                'from_network':ASSETS[source],'to_network':ASSETS[destination],'from_amount':str(amount),'to_amount':str(output),
                'output_per_input':str(output/amount),'source_at':None,'received_at':now,'requested_at':started,
                'response_latency_ms':round((now-started)*1000),'flow':'standard','executable':False,
                'provider_expiry':None,'decision':'WAIT','data_label':'REAL PROVIDER ESTIMATE — NOT AN ORDER-BOOK PRICE',
                'fee_policy':'Provider estimate includes its applicable costs; no extra invented service fee is deducted.',
                'unknowns':['Guaranteed fill price and validity window are not established for standard estimates.',
                    'Wallet send costs, confirmation time, network changes and total settlement latency remain unverified.',
                    'Fee breakdown is not assumed from absent fields. No cross-venue profit is calculated.'],
                'source_url':ESTIMATE_URL,'integration_status':'Contract implemented; requires a credentialed live acceptance check.'}
    except (httpx.HTTPError,json.JSONDecodeError) as exc:
        raise ValueError('ChangeNOW request failed ('+type(exc).__name__+'); no quote is fabricated') from None
    finally:
        if owns_client:
            await client.aclose()

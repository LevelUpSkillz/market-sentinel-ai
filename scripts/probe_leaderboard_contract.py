"""Bounded real public contract probe. No addresses, labels or production writes."""
import asyncio
import json
import re
import time
import httpx

URL='https://stats-data.hyperliquid.xyz/Mainnet/leaderboard'


async def main():
    report={'context':'Real public frontend contract probe; no production writes',
        'checked_at':time.time(),'source':URL,'source_at':None}
    try:
        async with asyncio.timeout(35):
            async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
                async with client.stream('GET',URL) as response:
                    response.raise_for_status()
                    report.update(http_status=response.status_code,content_type=response.headers.get('content-type'))
                    buffer=''
                    decoder=json.JSONDecoder()
                    rows=[]
                    started=False
                    async for chunk in response.aiter_text(chunk_size=16384):
                        buffer+=chunk
                        if len(buffer)>1024*1024:raise ValueError('Probe response exceeded its 1 MiB sample bound')
                        if not started:
                            match=re.search(r'"leaderboardRows"\s*:\s*\[',buffer)
                            if not match:continue
                            buffer=buffer[match.end():];started=True
                        while len(rows)<3:
                            buffer=buffer.lstrip(' \r\n\t,')
                            if not buffer or buffer.startswith(']'):break
                            try:row,end=decoder.raw_decode(buffer)
                            except json.JSONDecodeError:break
                            if not isinstance(row,dict):raise ValueError('Expected object rows')
                            rows.append(row);buffer=buffer[end:]
                        if len(rows)>=3:break
                    if not rows:raise ValueError('No expected rows observed')
                    sample=rows[0]
                    windows=sample.get('windowPerformances')
                    report.update(status='actual_frontend_sample_observed',rows_sampled=len(rows),
                        row_keys=sorted(sample.keys()),
                        address_shape_valid=bool(re.fullmatch(r'0x[0-9a-fA-F]{40}',str(sample.get('ethAddress','')))),
                        account_value_type=type(sample.get('accountValue')).__name__,
                        windows=[{'window':w[0],'keys':sorted(w[1].keys()),
                                  'metric_types':{k:type(v).__name__ for k,v in w[1].items()}}
                                 for w in windows if isinstance(w,list) and len(w)==2 and isinstance(w[1],dict)] if isinstance(windows,list) else None,
                        interpretation='Observed schema only; ROI units, publication time and redistribution rights remain unverified.')
    except Exception as error:
        report.update(status='unavailable',error=type(error).__name__)
    print('PUBLIC_LEADERBOARD_CONTRACT '+json.dumps(report),flush=True)


if __name__=='__main__':asyncio.run(main())

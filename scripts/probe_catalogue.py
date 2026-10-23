"""Real public coverage probe in Cloudflare's build runner; no production writes."""
import asyncio
import json
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sentinel.catalogue import Catalogue
from sentinel.market_directory import directory_stream
from sentinel.storage import Store


async def main():
    store = Store('sqlite:///:memory:')
    catalogue = Catalogue(store,('kraken','hyperliquid'))
    tasks = []
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            await catalogue.refresh(client)
        tasks = [asyncio.create_task(directory_stream(catalogue,p)) for p in ('kraken','hyperliquid')]
        deadline = time.monotonic()+35
        while time.monotonic()<deadline:
            await asyncio.sleep(1)
            if all(task.done() for task in tasks):break
            # Wait for broad subscriptions, not only the initial BTC quote.
            if len(catalogue.quotes)>=100 and time.monotonic()>deadline-15:break
        result = catalogue.search(source='live')
        errors = {p:type(t.exception()).__name__ for p,t in zip(('kraken','hyperliquid'),tasks) if t.done() and not t.cancelled() and t.exception()}
        print('PUBLIC_CATALOGUE_PROBE '+json.dumps({'checked_at':time.time(),'context':'Actual public APIs from Cloudflare build runner; does not prove Render production collection',
            'counts':result['counts'],'sessions':result['sessions'],'http_errors':result['errors'],'socket_errors':errors,
            'per_venue':{p:{'markets':len(catalogue.venues[p]),'quotes_observed':sum(k.startswith(p+':') for k in catalogue.quotes)} for p in ('kraken','hyperliquid')},
            'prices_used_for_paper_fills':False,'paid_services_created':False}))
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        store.close()


if __name__=='__main__':asyncio.run(main())

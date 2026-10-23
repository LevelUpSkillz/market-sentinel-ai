"""Bounded public connectivity checks. No credentials, orders or production writes."""
import asyncio
from decimal import Decimal
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from websockets.asyncio.client import connect
from sentinel.providers import ADAPTERS


async def probe(provider):
    adapter = ADAPTERS[provider]()
    expected = {'BTC-USDC-PERP','ETH-USDC-PERP'} if provider=='hyperliquid' else {'BTC-USD','ETH-USD'}
    observed = {}
    try:
        async with asyncio.timeout(25):
            async with connect(adapter.url,open_timeout=10,ping_interval=10,ping_timeout=10,max_size=8*1024*1024) as socket:
                for subscription in adapter.subscriptions():await socket.send(json.dumps(subscription))
                while set(observed)!=expected:
                    raw = await socket.recv()
                    now = time.time()
                    for kind,event in adapter.consume(json.loads(raw,parse_float=Decimal),now):
                        if kind=='book' and event.symbol in expected and event.fresh(now):
                            observed[event.symbol] = {'source_at':event.source_at,'received_at':event.received_at,'integrity':event.integrity}
        return {'provider':provider,'status':'observed_public_live_books','observations':observed}
    except Exception as error:
        return {'provider':provider,'status':'unavailable_or_adapter_failed','error':type(error).__name__,'observations':observed}


async def main():
    rows = await asyncio.gather(*(probe(p) for p in ['kraken','hyperliquid']))
    print('PUBLIC_PROVIDER_PROBE '+json.dumps({'checked_at':time.time(),'context':'Cloudflare build runner; does not verify deployed Render collectors','results':rows}))


if __name__=='__main__':asyncio.run(main())

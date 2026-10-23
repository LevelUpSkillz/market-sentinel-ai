"""Read actual public trader history without touching production data or accounts."""
import asyncio
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import httpx
from websockets.asyncio.client import connect
from sentinel.providers import Hyperliquid
from sentinel.smart_money import THRESHOLD
from sentinel.traders import ADDRESS,INFO_URL
from sentinel.trader_history import fetch_history
from sentinel.storage import Store


async def main():
    report={'context':'Real public-data probe in Cloudflare build runner, not a production write','checked_at':time.time()}
    address = None
    adapter = Hyperliquid()
    try:
        async with asyncio.timeout(20):
            async with connect(adapter.url,open_timeout=10,ping_interval=10,ping_timeout=10,max_size=8*1024*1024) as socket:
                for coin in ['BTC','ETH','SOL']:
                    await socket.send(json.dumps({'method':'subscribe','subscription':{'type':'trades','coin':coin}}))
                while address is None:
                    message=json.loads(await socket.recv(),parse_float=Decimal)
                    for kind,trade in adapter.consume(message,time.time()):
                        if kind!='trade' or time.time()-trade['source_at']>10:continue
                        notional=Decimal(trade['price'])*Decimal(trade['quantity'])
                        for candidate in trade.get('public_participants',[]):
                            if isinstance(candidate,str) and ADDRESS.fullmatch(candidate) and int(candidate,16)!=0:
                                address=candidate.lower()
                                report.update(symbol=trade['symbol'],observed_print_notional_usdc=str(notional),qualifies_as_large_print=notional>=THRESHOLD,public_participant_observed=True)
                                break
        store=Store('sqlite:///:memory:')
        try:
            async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
                positions,history=await asyncio.gather(client.post(INFO_URL,json={'type':'clearinghouseState','user':address}),fetch_history(store,address,client))
                positions.raise_for_status()
                state=positions.json()
                if not isinstance(state.get('assetPositions'),list):raise ValueError('Unexpected public position schema')
                report.update(status='actual_public_positions_and_history_observed',positions=len(state['assetPositions']),
                    fills_analyzed=history['fills_analyzed'],complete_cycles=history['complete_cycles'],
                    historical_win_rate_pct=history['historical_win_rate_pct'],follower_odds=None,
                    note='Historical cycles are before funding and do not estimate follower odds; wallet addresses are omitted from CI logs.')
        finally:store.close()
    except TimeoutError:report.update(status='public_participant_or_request_not_observed_within_probe_window')
    except Exception as error:report.update(status='provider_probe_unavailable',error=type(error).__name__)
    print('PUBLIC_TRADER_PROBE '+json.dumps(report))


if __name__=='__main__':asyncio.run(main())

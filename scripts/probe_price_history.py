"""Bounded public display-chart probe. No credentials or production writes."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sentinel.chart import PriceHistory
async def main():
    history=PriceHistory();rows=[]
    for provider,symbol in [('kraken','BTC-USD'),('hyperliquid','BTC-USDC-PERP')]:
        value=await history.get(symbol,1,provider)
        rows.append({'provider':provider,'symbol':symbol,'candles':len(value['candles']),
            'source_at':value['source_at'],'received_at':value['received_at'],'executable':value['executable']})
    print('PUBLIC_PRICE_HISTORY_PROBE '+json.dumps(rows))
if __name__=='__main__':asyncio.run(main())

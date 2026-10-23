"""Bounded real public frontend contract probe; no wallet identities in logs."""
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sentinel.leaderboard import TraderDirectory
from sentinel.storage import Store


async def main():
    store = Store('sqlite:///:memory:')
    try:
        directory = TraderDirectory(store)
        result = await directory.refresh()
        cache = directory.cache or {}
        metrics = {key:cache.get(key) for key in ('rows_scanned','eligible_rows','rejected_rows','duplicate_selected_rows','download_bytes','peak_buffer_bytes','candidate_limit')}
        print('PUBLIC_TRADER_DIRECTORY_PROBE '+json.dumps({'checked_at':time.time(),
            'context':'Actual experimental public frontend feed from build runner, not production account verification',
            'status':result['status'],'source_at':None,'received_at':result['received_at'],
            'candidates':len(cache.get('traders',[])),'metrics':metrics,'error':result['error'],
            'independent_rank':None,'success_probability':None,'roi_units_verified':False,
            'raw_response_retained':False,'production_writes':False}))
    finally:store.close()


if __name__=='__main__':asyncio.run(main())

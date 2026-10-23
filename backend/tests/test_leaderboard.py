"""SYNTHETIC upstream rows/chunks; no real identities, performance or network."""
import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
from sentinel.leaderboard import TraderDirectory, LeaderboardDecoder, read_candidates, CACHE_KEY, ERROR_KEY, CACHE_SECONDS
from sentinel.storage import Store

NOW = 1800000000


def row(index=1,*,windows=4,pnl='10',label='SYNTHETIC PUBLIC LABEL'):
    return {'ethAddress':'0x'+format(index,'040x'),'accountValue':'100', 'displayName':label,
        'windowPerformances':[[name,{'pnl':pnl,'roi':'0.125','vlm':'1000'}]
            for name in ('day','week','month','allTime')[:windows]]}


class Chunks(httpx.AsyncByteStream):
    def __init__(self,data,size=19):self.data,self.size = data,size
    async def __aiter__(self):
        for i in range(0,len(self.data),self.size):yield self.data[i:i+self.size]


def response(rows,*,size=19):
    return httpx.Response(200,stream=Chunks(json.dumps({'leaderboardRows':rows},ensure_ascii=False).encode(),size))


class DecoderTests(unittest.TestCase):
    def test_arbitrary_character_chunks_allow_root_metadata_without_numeric_prefix_loss(self):
        raw=json.dumps({'version':12345,'leaderboardRows':[row()],'extra':{'ignored':True}})
        parser=LeaderboardDecoder()
        actual=[]
        for c in raw:actual.extend(parser.feed(c))
        parser.finish()
        self.assertEqual(actual,[row()])
        self.assertLess(parser.peak_buffer_bytes,1024)

    def test_malformed_truncated_wrong_root_and_duplicate_arrays_rejected(self):
        for raw in ['[]','{}','{"leaderboardRows":{}}','{"leaderboardRows":[1]}',
                    '{"leaderboardRows":[{}', '{"leaderboardRows":[{},]}',
                    '{"leaderboardRows":[],}', '{"leaderboardRows":[],"leaderboardRows":[]}',
                    '{"leaderboardRows":[]} garbage', '{"leaderboardRows":[{"pnl":NaN}]}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                parser=LeaderboardDecoder();list(parser.feed(raw));parser.finish()

    def test_pending_large_row_cannot_grow_without_bound(self):
        parser=LeaderboardDecoder(max_buffer=200)
        list(parser.feed('{"leaderboardRows":[{"label":"'))
        with self.assertRaisesRegex(ValueError,'memory bound'):list(parser.feed('x'*201))


class LeaderboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):self.store=Store('sqlite:///:memory:')
    def tearDown(self):self.store.close()

    async def test_streamed_utf8_chunks_validate_schema_and_do_not_claim_identity_units_or_odds(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:response([row(label='SYNTHETIC Étiquette 🚀')],size=1))) as client:
            directory=TraderDirectory(self.store)
            data=await directory.refresh(client,now=NOW)
        self.assertEqual(data['status'],'cached_reported_metrics')
        candidate=data['traders'][0]
        self.assertEqual(candidate['label'],'SYNTHETIC Étiquette 🚀')
        self.assertFalse(candidate['identity_verified'])
        self.assertIsNone(candidate['independent_rank'])
        self.assertIsNone(candidate['success_probability'])
        self.assertEqual(candidate['currency'],'provider account units')
        self.assertEqual(candidate['windows']['month']['roi_raw'],'0.125')
        self.assertIsNone(candidate['windows']['month']['roi_pct'])
        self.assertIsNone(data['source_at'])
        self.assertEqual(data['received_at'],NOW)
        self.assertNotIn('raw_response',directory.cache)
        cohort=self.store.list('trader_cohort')[0]
        self.assertEqual(cohort['candidates'][0]['windows'],candidate['windows'])
        self.assertEqual(cohort['addresses'],[candidate['address']])

    async def test_top100_candidates_are_unique_bounded_and_prefer_window_coverage_over_recent_profit(self):
        rows=[row(i,pnl=str(i)) for i in range(1,121)]
        rows += [row(120,pnl='999'),row(121,windows=2,pnl='999999999')]
        parsed=await read_candidates(response(rows,size=43))
        self.assertEqual(len(parsed['traders']),100)
        self.assertEqual(len({r['address'] for r in parsed['traders']}),100)
        self.assertEqual(parsed['traders'][0]['address'],row(120)['ethAddress'])
        self.assertNotIn(row(121)['ethAddress'],[r['address'] for r in parsed['traders']])
        self.assertEqual(parsed['rows_scanned'],122)
        self.assertGreater(parsed['duplicate_selected_rows'],0)
        self.assertLess(parsed['peak_buffer_bytes'],1024*1024)

    async def test_reported_raw_roi_preserves_more_than_28_significant_digits(self):
        raw_roi='0.123456789012345678901234567890123456789'
        candidate=row()
        for _,metrics in candidate['windowPerformances']:metrics['roi']=raw_roi
        directory=TraderDirectory(self.store)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:response([candidate],size=7))) as client:
            data=await directory.refresh(client,now=NOW)
        self.assertEqual(data['status'],'cached_reported_metrics')
        reported=data['traders'][0]['windows']['month']
        self.assertEqual(reported['roi_raw'],raw_roi)
        self.assertIsNone(reported['roi_pct'])
        cached=self.store.get_state(CACHE_KEY)
        self.assertEqual(cached['traders'][0]['windows']['month']['roi_raw'],raw_roi)

    async def test_bad_addresses_nonfinite_metrics_and_duplicate_windows_never_become_candidates(self):
        invalid=[dict(row(2),ethAddress='not-a-wallet'),dict(row(3),ethAddress='0x'+'0'*40),
                 dict(row(4),accountValue='Infinity'),row(5,windows=1),row(6,pnl='NaN'),
                 dict(row(7),accountValue='1e99999999')]
        duplicate=row(8);duplicate['windowPerformances'].append(duplicate['windowPerformances'][0]);invalid.append(duplicate)
        parsed=await read_candidates(response([*invalid,row(1)]))
        self.assertEqual([r['address'] for r in parsed['traders']],[row(1)['ethAddress']])
        self.assertEqual(parsed['rejected_rows'],len(invalid))

    async def test_download_and_row_bounds_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'byte limit'):
            await read_candidates(response([row()]),max_download=20)
        with patch('sentinel.leaderboard.MAX_ROWS',1):
            with self.assertRaisesRegex(ValueError,'row limit'):
                await read_candidates(response([row(1),row(2)]))
        compressed=httpx.Response(200,headers={'Content-Encoding':'gzip'},stream=Chunks(b'not-read'))
        with self.assertRaisesRegex(ValueError,'compressed'):await read_candidates(compressed)

    async def test_cache_and_search_are_local_paginated_and_disabled_provider_hides_cached_data(self):
        calls=[]
        def handler(request):calls.append(request);return response([row(1,label='SYNTHETIC ALPHA'),row(2,label='SYNTHETIC BETA')])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            directory=TraderDirectory(self.store)
            await directory.refresh(client,now=NOW)
            await directory.refresh(client,now=NOW+10)
        self.assertEqual(len(calls),1)
        self.assertEqual(directory.directory('alpha',now=NOW)['total'],1)
        self.assertEqual(len(directory.directory(page=2,limit=1,now=NOW)['traders']),1)
        self.assertEqual(directory.directory(now=NOW+CACHE_SECONDS)['status'],'stale')
        disabled=TraderDirectory(self.store,enabled=False).directory(now=NOW)
        self.assertEqual(disabled['status'],'disabled')
        self.assertEqual(disabled['traders'],[])
        self.assertIsNone(disabled['received_at'])

    async def test_failure_keeps_original_metrics_and_receipt_then_rate_limit_backs_off(self):
        responses=iter([response([row()]),httpx.Response(429),response([row(2)])])
        calls=[]
        def handler(request):calls.append(request);return next(responses)
        directory=TraderDirectory(self.store)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await directory.refresh(client,now=NOW)
            failed=await directory.refresh(client,now=NOW+CACHE_SECONDS+1)
            self.assertEqual(failed['status'],'stale')
            self.assertEqual(failed['received_at'],NOW)
            self.assertEqual(failed['traders'][0]['address'],row()['ethAddress'])
            self.assertEqual(failed['error']['http_status'],429)
            await directory.refresh(client,now=NOW+CACHE_SECONDS+2)
            self.assertEqual(len(calls),2)
            recovered=await directory.refresh(client,now=NOW+CACHE_SECONDS+3602)
        self.assertEqual(recovered['status'],'cached_reported_metrics')
        self.assertEqual(recovered['traders'][0]['address'],row(2)['ethAddress'])
        self.assertIsNone(self.store.get_state(ERROR_KEY))
        self.assertEqual(len(self.store.list('trader_cohort')),2)

    async def test_malformed_response_keeps_last_good_cache_and_exponential_retry(self):
        directory=TraderDirectory(self.store)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:response([row()]))) as client:
            await directory.refresh(client,now=NOW)
        original=self.store.get_state(CACHE_KEY)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=Chunks(b'{"leaderboardRows":[')))) as client:
            first=await directory.refresh(client,now=NOW+CACHE_SECONDS+1)
            second=await directory.refresh(client,now=NOW+CACHE_SECONDS+122)
        self.assertEqual(self.store.get_state(CACHE_KEY),original)
        self.assertEqual(first['error']['retry_at']-first['error']['at'],120)
        self.assertEqual(second['error']['retry_at']-second['error']['at'],240)

    async def test_receipt_time_is_end_of_download_without_injected_test_clock(self):
        directory=TraderDirectory(self.store)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:response([row()]))) as client:
            ticks=iter([NOW,NOW+5,NOW+5])
            with patch('sentinel.leaderboard.time',SimpleNamespace(time=lambda:next(ticks))):
                data=await directory.refresh(client)
        self.assertEqual(data['received_at'],NOW+5)
        self.assertEqual(data['status'],'cached_reported_metrics')

    async def test_large_stream_yields_to_collectors_during_processing(self):
        ticks=[]
        async def sibling():
            for _ in range(3):ticks.append(True);await asyncio.sleep(0)
        task=asyncio.create_task(sibling())
        parsed=await read_candidates(response([row(i) for i in range(1,601)],size=16384))
        self.assertGreaterEqual(len(ticks),2)
        self.assertEqual(parsed['rows_scanned'],600)
        await task

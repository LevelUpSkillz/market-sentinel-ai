"""SYNTHETIC owner-only public-trader discovery API checks; no provider traffic."""
from copy import deepcopy
from dataclasses import replace
import json
import time
import unittest
from unittest.mock import patch
import httpx
from sentinel.app import create_app
from sentinel.config import Settings
from sentinel.security import session_token
from sentinel.storage import Store


def address(index):
    return '0x'+format(index,'040x')


class SyntheticLeaderboardStream(httpx.AsyncByteStream):
    """Exercise the real bounded parser over an unconsumed chunked response."""
    def __init__(self,payload):
        self.payload = payload

    async def __aiter__(self):
        for start in range(0,len(self.payload),37):
            yield self.payload[start:start+37]


class TraderDirectoryApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = Store('sqlite:///:memory:')
        self.settings = Settings(environment='test',database_url='sqlite:///:memory:',
            session_secret='SYNTHETIC_TRADER_DIRECTORY_TEST_SECRET'*3,
            origin='https://testserver',collect=False,providers=('hyperliquid',))
        self.app = create_app(self.settings,self.store)
        self.runtime = self.app.state.runtime
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
            base_url=self.settings.origin)
        self.headers = {'Origin':self.settings.origin}

    async def asyncTearDown(self):
        await self.client.aclose()
        self.store.close()

    def authenticate(self):
        self.client.cookies.set('sentinel_session',session_token(self.settings.session_secret,'test'))

    async def cache_synthetic_candidates(self):
        rows = []
        for index,name in [(1,'ALPHA'),(2,'BETA'),(3,'GAMMA')]:
            windows = [[window,{'pnl':str(index*1000),'roi':'0.123','vlm':'15000000'}]
                for window in ['day','week','month','allTime']]
            rows.append({'ethAddress':address(index),'accountValue':'100000',
                'displayName':'SYNTHETIC '+name,'windowPerformances':windows,'prize':0})
        calls = []
        def provider(request):
            calls.append(str(request.url))
            self.assertEqual(request.method,'GET')
            self.assertEqual(request.url.host,'stats-data.hyperliquid.xyz')
            self.assertEqual(request.url.path,'/Mainnet/leaderboard')
            payload = json.dumps({'leaderboardRows':rows}).encode()
            return httpx.Response(200,stream=SyntheticLeaderboardStream(payload),
                headers={'Content-Type':'application/json'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            await self.runtime.trader_directory.refresh(client=client,now=time.time())
        self.assertEqual(len(calls),1)
        cached = self.store.get_state('public_leaderboard')
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached['traders']),3)
        return cached

    async def test_directory_and_tracking_require_owner_authentication(self):
        self.assertEqual((await self.client.get('/api/trader-directory')).status_code,401)
        result = await self.client.post('/api/traders',json={
            'address':address(1),'label':'SYNTHETIC DIRECTORY CANDIDATE'},headers=self.headers)
        self.assertEqual(result.status_code,401)
        self.assertEqual(self.store.list('watchlist'),[])
        self.assertEqual(self.store.list('trader_event'),[])

    async def test_search_and_pagination_are_bounded_on_the_authenticated_server(self):
        self.authenticate()
        for query in ['q='+('x'*101),'page=0','page=101','limit=0','limit=51','page=abc']:
            with self.subTest(query=query):
                response = await self.client.get('/api/trader-directory?'+query)
                self.assertEqual(response.status_code,422)
        self.assertEqual(self.store.list('watchlist'),[])

    async def test_cached_directory_preserves_provenance_and_never_invents_rank_or_odds(self):
        cached = await self.cache_synthetic_candidates()
        self.authenticate()
        response = await self.client.get('/api/trader-directory')
        self.assertEqual(response.status_code,200)
        data = response.json()
        self.assertEqual(data['status'],'cached_reported_metrics')
        self.assertEqual(data['total'],3)
        self.assertEqual(data['received_at'],cached['received_at'])
        self.assertIsNone(data['source_at'])
        self.assertIn('Hyperliquid',data['source'])
        self.assertEqual(data['source_url'],'https://stats-data.hyperliquid.xyz/Mainnet/leaderboard')
        self.assertTrue(data['experimental'])
        self.assertTrue(data['limitations'])
        self.assertIsNone(data['independent_rank'])
        self.assertIsNone(data['success_probability'])
        for candidate in data['traders']:
            self.assertTrue(candidate['label'].startswith('SYNTHETIC '))
            self.assertFalse(candidate['label_verified'])
            self.assertFalse(candidate['identity_verified'])
            self.assertIsNone(candidate['independent_rank'])
            self.assertIsNone(candidate['success_probability'])
            self.assertIsNone(candidate['success_probability_pct'])
            self.assertIsNone(candidate['source_at'])
            self.assertEqual(candidate['currency'],'provider account units')
            for window in candidate['windows'].values():
                self.assertEqual(window['roi_raw'],'0.123')
                self.assertIsNone(window['roi_pct'])
                self.assertIsInstance(window['pnl'],str)
                self.assertIsInstance(window['volume'],str)
            self.assertNotIn('positions',candidate)
        self.assertEqual(self.store.list('watchlist'),[])
        self.assertEqual(self.store.list('trader_event'),[])

    async def test_search_and_pagination_read_cache_without_provider_download_or_following(self):
        cached = deepcopy(await self.cache_synthetic_candidates())
        initial_account = deepcopy(self.store.get_state('account'))
        initial_cohorts = deepcopy(self.store.list('trader_cohort'))
        self.authenticate()
        with patch.object(self.runtime.trader_directory,'refresh',side_effect=AssertionError('GET must not refresh')) as refresh:
            with patch('sentinel.leaderboard.httpx.AsyncClient',side_effect=AssertionError('GET must not open a provider client')):
                search = await self.client.get('/api/trader-directory',params={'q':'synthetic beta'})
                first = await self.client.get('/api/trader-directory',params={'page':1,'limit':1})
                second = await self.client.get('/api/trader-directory',params={'page':2,'limit':1})
                last = await self.client.get('/api/trader-directory',params={'page':4,'limit':1})
            refresh.assert_not_called()
        self.assertEqual(search.status_code,200)
        self.assertEqual(search.json()['total'],1)
        self.assertEqual(search.json()['traders'][0]['address'],address(2))
        self.assertEqual(first.status_code,200)
        self.assertEqual(second.status_code,200)
        self.assertEqual(first.json()['total'],3)
        self.assertEqual(first.json()['limit'],1)
        self.assertEqual(second.json()['page'],2)
        self.assertNotEqual(first.json()['traders'][0]['address'],second.json()['traders'][0]['address'])
        self.assertEqual(last.json()['traders'],[])
        self.assertEqual(last.json()['total'],3)
        self.assertEqual(self.store.get_state('public_leaderboard'),cached)
        self.assertEqual(self.store.list('trader_cohort'),initial_cohorts)
        self.assertEqual(self.store.get_state('account'),initial_account)
        self.assertEqual(self.store.list('watchlist'),[])
        self.assertEqual(self.store.list('paper'),[])

    async def test_unavailable_directory_does_not_download_on_first_get(self):
        self.authenticate()
        with patch('sentinel.leaderboard.httpx.AsyncClient',side_effect=AssertionError('GET must not download')):
            response = await self.client.get('/api/trader-directory')
        self.assertEqual(response.status_code,200)
        data = response.json()
        self.assertEqual(data['status'],'unavailable')
        self.assertEqual(data['traders'],[])
        self.assertEqual(data['total'],0)
        self.assertIsNone(data['received_at'])
        self.assertIsNone(self.store.get_state('public_leaderboard'))

    async def test_provider_approval_gate_hides_previously_cached_candidates(self):
        cached = deepcopy(await self.cache_synthetic_candidates())
        disabled_settings = replace(self.settings,providers=('kraken',))
        disabled_app = create_app(disabled_settings,self.store)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=disabled_app),
                                    base_url=self.settings.origin) as client:
            client.cookies.set('sentinel_session',session_token(self.settings.session_secret,'test'))
            with patch('sentinel.leaderboard.httpx.AsyncClient',side_effect=AssertionError('Unapproved provider must not be opened')):
                response = await client.get('/api/trader-directory')
        self.assertEqual(response.status_code,200)
        data = response.json()
        self.assertEqual(data['status'],'disabled')
        self.assertEqual(data['traders'],[])
        self.assertEqual(data['total'],0)
        self.assertIsNone(data['received_at'])
        self.assertIsNone(data['rows_scanned'])
        self.assertIsNone(data['success_probability'])
        self.assertEqual(self.store.get_state('public_leaderboard'),cached)
        self.assertEqual(self.store.list('watchlist'),[])

    async def test_tracking_a_public_candidate_requires_origin_and_preserves_simulated_cash(self):
        await self.cache_synthetic_candidates()
        self.authenticate()
        initial_account = deepcopy(self.store.get_state('account'))
        candidate = (await self.client.get('/api/trader-directory',params={'q':address(1)})).json()['traders'][0]
        body = {'address':candidate['address'],'label':candidate['label']}
        self.assertEqual((await self.client.post('/api/traders',json=body)).status_code,403)
        result = await self.client.post('/api/traders',json=body,headers=self.headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['address'],address(1))
        self.assertEqual(self.store.get('watchlist',address(1))['label'],body['label'])
        self.assertEqual(self.store.get_state('account'),initial_account)
        self.assertEqual(self.store.list('paper'),[])
        self.assertEqual(self.store.list('trader_event'),[])
        self.assertIsNone(self.store.get_state('trader:'+address(1)))

    async def test_discovery_tracking_cannot_exceed_the_existing_ten_wallet_limit(self):
        self.authenticate()
        for index in range(1,11):
            response = await self.client.post('/api/traders',json={
                'address':address(index),'label':'SYNTHETIC CANDIDATE '+str(index)},headers=self.headers)
            self.assertEqual(response.status_code,200)
        response = await self.client.post('/api/traders',json={
            'address':address(11),'label':'SYNTHETIC ELEVENTH CANDIDATE'},headers=self.headers)
        self.assertEqual(response.status_code,422)
        self.assertIn('10',response.json()['detail'])
        self.assertEqual(len(self.store.list('watchlist')),10)
        self.assertIsNone(self.store.get('watchlist',address(11)))
        repeated = await self.client.post('/api/traders',json={
            'address':address(1),'label':'SYNTHETIC CANDIDATE 1'},headers=self.headers)
        self.assertEqual(repeated.status_code,200)
        self.assertEqual(len(self.store.list('watchlist')),10)

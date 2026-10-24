"""Synthetic evidence only. No exchange credentials, orders or real profitability."""
from copy import deepcopy
import time
import unittest
from unittest.mock import AsyncMock,patch
import httpx
from sentinel.chart import PriceHistory,parse_candles
from sentinel.suggestions import suggestions
from sentinel.app import create_app
from sentinel.config import Settings
from sentinel.security import session_token
from sentinel.storage import Store
from sentinel.models import Book

NOW=1800000000
ADDRESS='0x'+'a'*40

def candles():
    return {'error':[],'result':{'XXBTZUSD':[[NOW-120,'100','103','99','102','101','2',3],
        [NOW-60,'102','104','101','103','102','1',2],[NOW,'103','105','102','104','103','1',1]],'last':NOW}}

def setup():
    return {'id':'SYNTHETIC','symbol':'BTC-USD','decision':'GO','next_action':'SYNTHETIC ready for practice review',
        'source_at':NOW,'received_at':NOW,'expires_at':NOW+30,'entry_deadline':NOW+20,
        'entry_trigger':'101','entry_limit':'102','stop':'99','target':'110','facts':['SYNTHETIC observed crossing'],
        'reasons':[],'estimated_round_trip_cost_bps':'85'}

class ChartTests(unittest.TestCase):
    def test_source_candles_preserve_range_and_mark_unfinished_candle(self):
        value=parse_candles(candles(),'BTC-USD',1,NOW+10)
        self.assertEqual([r['closed'] for r in value['candles']],[True,True,False])
        self.assertEqual(value['candles'][-1]['close'],'104')
        self.assertFalse(value['executable'])
        self.assertEqual(value['source_at'],NOW)

    def test_bounded_provider_history_can_include_a_current_candle_beyond_the_committed_window(self):
        rows=[[NOW-(720-i)*60,'100','103','99','102','101','2',3] for i in range(721)]
        value=parse_candles({'error':[],'result':{'XXBTZUSD':rows,'last':NOW}},'BTC-USD',1,NOW)
        self.assertEqual(len(value['candles']),180)
        self.assertFalse(value['candles'][-1]['closed'])
        with self.assertRaises(ValueError):
            parse_candles({'error':[],'result':{'XXBTZUSD':rows*2,'last':NOW}},'BTC-USD',1,NOW)

    def test_invalid_ranges_order_duplicates_future_or_nonfinite_are_rejected(self):
        for column,value in [(0,NOW+120),(0,NOW-60),(1,'NaN'),(2,'100'),(3,'110'),(6,'-1')]:
            data=candles();data['result']['XXBTZUSD'][-1][column]=value
            with self.subTest(column=column,value=value),self.assertRaises(ValueError):
                parse_candles(data,'BTC-USD',1,NOW)
        data=candles();data['error']=['EGeneral:Temporary lockout']
        with self.assertRaises(ValueError):parse_candles(data,'BTC-USD',1,NOW)

class SuggestionsTests(unittest.TestCase):
    def setUp(self):self.store=Store('sqlite:///:memory:')
    def tearDown(self):self.store.close()
    def radar(self):return {'as_of':NOW,'setups':[setup()],'strategy_version':'SYNTHETIC','watchlist':[]}
    def action(self):return {'address':ADDRESS,'symbol':'BTC-USDC-PERP','asset':'BTC','side':'short','received_at':NOW,
        'source_at':None,'source':'SYNTHETIC public positions','decision':'WAIT','next_action':'Independent plan required','reasons':[]}

    def test_profiles_do_not_turn_wait_into_go_or_invent_follower_probability(self):
        self.store.set_state('trader_history:'+ADDRESS,{'received_at':NOW,'complete_cycles':12,
            'historical_win_rate_pct':80,'net_before_funding_usdc':'-100','provider_limit_reached':True})
        radar=self.radar();radar['setups'][0]['decision']='WAIT'
        result=suggestions(radar,{'actions':[self.action()]},self.store,now=NOW)
        card=result['cards'][0]
        self.assertEqual(card['decision'],'WAIT');self.assertIsNone(card['success_probability_pct'])
        self.assertEqual(card['profiles'][0]['direction'],'short')
        self.assertEqual(card['profiles'][0]['historical_win_rate_pct'],80)
        self.assertIn('not a Kraken spot',card['profiles'][0]['note'])
        self.assertTrue(any('net trading losses' in note for note in card['trader_review']))
        self.assertTrue(any('price fall' in note for note in card['trader_review']))

    def test_stale_expired_stopped_and_unknown_states_cannot_authorize_entry(self):
        for field,value in [('source_at',NOW-6),('received_at',NOW-6),('expires_at',NOW),('entry_deadline',NOW),('decision','BUY_NOW')]:
            radar=self.radar();radar['setups'][0][field]=value
            card=suggestions(radar,{'actions':[]},self.store,now=NOW)['cards'][0]
            self.assertEqual(card['decision'],'NO-GO')
        card=suggestions(self.radar(),{'actions':[]},self.store,now=NOW,stopped=True)['cards'][0]
        self.assertEqual(card['decision'],'NO-GO');self.assertIn('paused',card['reason'])

    def test_old_profiles_and_different_tokens_do_not_become_supporting_evidence(self):
        self.store.set_state('trader_history:'+ADDRESS,{'received_at':NOW-8*3600,'complete_cycles':100,'historical_win_rate_pct':99})
        a=self.action();card=suggestions(self.radar(),{'actions':[a]},self.store,now=NOW)['cards'][0]
        self.assertIsNone(card['profiles'][0]['completed_positions'])
        a.update(asset='ETH',symbol='ETH-USDC-PERP')
        card=suggestions(self.radar(),{'actions':[a]},self.store,now=NOW)['cards'][0]
        self.assertEqual(card['profiles'],[])

class ChartApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store('sqlite:///:memory:')
        self.settings=Settings(environment='test',database_url='sqlite:///:memory:',collect=False,
            providers=('kraken','hyperliquid'),origin='https://testserver',session_secret='SYNTHETIC_TEST_ONLY'*4)
        self.app=create_app(self.settings,self.store)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=self.settings.origin)
        self.app.state.runtime.books[('kraken','BTC-USD')]=Book('kraken','BTC-USD')
    async def asyncTearDown(self):await self.client.aclose();self.store.close()
    def login(self):self.client.cookies.set('sentinel_session',session_token(self.settings.session_secret,'test'))
    async def test_chart_and_suggestions_require_auth_and_restrict_provider_instruments(self):
        for url in ['/api/price-history?symbol=BTC-USD','/api/suggestions']:
            self.assertEqual((await self.client.get(url)).status_code,401)
        self.login()
        self.assertEqual((await self.client.get('/api/price-history?symbol=FAKE-USD')).status_code,404)
        self.assertEqual((await self.client.get('/api/price-history?symbol=BTC-USD&provider=arbitrary')).status_code,422)
        with patch.object(PriceHistory,'get',new_callable=AsyncMock) as get:
            get.return_value=parse_candles(candles(),'BTC-USD',1,NOW+10)
            result=await self.client.get('/api/price-history?symbol=BTC-USD')
            self.assertEqual(result.status_code,200);self.assertFalse(result.json()['executable'])
            get.assert_awaited_once_with('BTC-USD',1,'kraken')
        self.assertEqual((await self.client.get('/api/suggestions')).status_code,200)

    async def test_provider_failure_is_not_a_fake_chart_or_execution(self):
        self.login()
        with patch.object(PriceHistory,'get',side_effect=ValueError('Historical provider is temporarily unavailable')):
            result=await self.client.get('/api/price-history?symbol=BTC-USD')
        self.assertEqual(result.status_code,503)
        self.assertEqual(self.store.list('paper',10),[])
        self.assertEqual(self.store.list('kraken_order',10),[])

class PublicHistoryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_failure_cooldown_and_recovery_use_only_bounded_public_reads(self):
        requests=[];failing=[False];clock=[NOW]
        def handler(request):
            requests.append(request)
            self.assertEqual(request.method,'GET');self.assertEqual(request.url.path,'/0/public/OHLC')
            self.assertEqual(request.url.params['pair'],'XBTUSD')
            self.assertNotIn('api-key',request.headers)
            return httpx.Response(503 if failing[0] else 200,json={} if failing[0] else candles())
        original=httpx.AsyncClient
        def factory(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
        history=PriceHistory()
        with patch('sentinel.chart.httpx.AsyncClient',side_effect=factory),patch('sentinel.chart.time.time',side_effect=lambda:clock[0]):
            first=await history.get('BTC-USD');second=await history.get('BTC-USD')
            self.assertFalse(first['cached']);self.assertTrue(second['cached']);self.assertEqual(len(requests),1)
            clock[0]+=21;failing[0]=True
            for _ in range(2):
                with self.assertRaises(ValueError):await history.get('BTC-USD')
            self.assertEqual(len(requests),2)
            clock[0]+=21;failing[0]=False
            self.assertFalse((await history.get('BTC-USD'))['cached']);self.assertEqual(len(requests),3)

    async def test_hyperliquid_candles_keep_native_instrument_and_reject_mismatches(self):
        import json
        mismatch=[False]
        def handler(request):
            body=json.loads(request.content);self.assertEqual(body['type'],'candleSnapshot')
            self.assertEqual(body['req']['coin'],'ETH');self.assertEqual(body['req']['interval'],'1m')
            return httpx.Response(200,json=[{'s':'BTC' if mismatch[0] else 'ETH','i':'1m','t':at*1000,
                'o':'100','h':'102','l':'99','c':'101','v':'1','n':2} for at in [NOW-60,NOW]])
        original=httpx.AsyncClient
        def factory(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
        with patch('sentinel.chart.httpx.AsyncClient',side_effect=factory),patch('sentinel.chart.time.time',return_value=NOW):
            result=await PriceHistory().get('ETH-USDC-PERP',1,'hyperliquid')
            self.assertEqual(result['provider'],'hyperliquid');self.assertFalse(result['candles'][-1]['closed'])
            mismatch[0]=True
            with self.assertRaises(ValueError):await PriceHistory().get('ETH-USDC-PERP',1,'hyperliquid')

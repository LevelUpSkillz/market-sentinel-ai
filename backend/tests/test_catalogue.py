"""Synthetic contract, isolation, limits and failure recovery tests; no real prices."""
import asyncio
import json
import time
import unittest
from unittest.mock import patch
import httpx
from sentinel.app import create_app
from sentinel.catalogue import Catalogue,EXTRA_BOOK_LIMIT
from sentinel.config import Settings
from sentinel.market_directory import directory_stream,ticker_subscriptions
from sentinel.models import Book
from sentinel.providers import Kraken,Hyperliquid
from sentinel.runtime import Runtime
from sentinel.security import session_token
from sentinel.storage import Store
from sentinel.trader_history import analyze_fills

NOW = 1800000000

def instruments(*coins):
    return {'pairs':[{'base':c,'quote':'USD','symbol':c+'/USD','status':'online'} for c in coins]}


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.store = Store('sqlite:///:memory:')
        self.cat = Catalogue(self.store,('kraken','hyperliquid'))
    def tearDown(self):self.store.close()

    def test_same_symbol_does_not_merge_different_token_ids(self):
        self.cat.set_coins([{'id':'synthetic-a','symbol':'SAME','name':'SYNTHETIC A','rank':2,'is_active':True},
            {'id':'synthetic-b','symbol':'SAME','name':'SYNTHETIC B','rank':1,'is_active':True}],NOW)
        result = self.cat.search(q='same',source='all',limit=1,now=NOW)
        self.assertEqual(result['total'],2)
        self.assertEqual(result['items'][0]['id'],'coinpaprika:synthetic-b')
        self.assertEqual(self.cat.search(q='same',source='all',page=2,limit=1,now=NOW)['items'][0]['id'],'coinpaprika:synthetic-a')
        self.assertIsNone(result['items'][0]['quote']['price'])

    def test_aggregate_price_is_delayed_not_executable_and_goes_stale(self):
        self.cat.set_coins([{'id':'synthetic-a','symbol':'TEST','is_active':True}],NOW)
        self.cat.set_global_quotes([{'id':'synthetic-a','last_updated':NOW-60,'quotes':{'USD':{'price':'.001','market_cap':'4','volume_24h':'3'}}}],NOW)
        row = self.cat.search(source='coinpaprika',now=NOW)['items'][0]
        self.assertEqual(row['quote']['status'],'delayed')
        self.assertFalse(row['quote']['executable'])
        self.assertEqual(self.cat.quote_view(row,NOW+1201)['status'],'stale')
        self.assertEqual(self.cat.quote_view(row,NOW+1201)['source_at'],NOW-60)

    def test_invalid_new_snapshot_does_not_erase_last_good_prices(self):
        self.cat.set_global_quotes([{'id':'test','last_updated':NOW,'quotes':{'USD':{'price':'1'}}}],NOW)
        for value in ['NaN','Infinity','0','-1']:
            with self.assertRaises(ValueError):self.cat.set_global_quotes([{'id':'test','last_updated':NOW,'quotes':{'USD':{'price':value}}}],NOW+1)
        self.assertEqual(self.cat.global_quotes['items']['test']['price'],'1')

    def test_inactive_filters_and_quote_currencies_stay_distinct(self):
        data = instruments('XRP')
        data['pairs'] += [{'base':'XRP','quote':'BTC','symbol':'XRP/BTC','status':'online'},
            {'base':'OLD','quote':'USD','symbol':'OLD/USD','status':'delisted'},
            {'base':'EUR','quote':'USD','symbol':'EUR/USD','status':'online'}]
        desired = self.cat.kraken_instruments(data,NOW,True)
        self.assertEqual(desired,{'XRP/USD','XRP/BTC'})
        self.assertEqual(self.cat.search(now=NOW)['total'],2)
        self.assertEqual(self.cat.search(active='inactive',now=NOW)['items'][0]['symbol'],'OLD')
        with self.assertRaises(ValueError):self.cat.validate_watch('kraken:XRP/BTC',NOW)

    def test_ticker_timestamp_and_disconnect_invalidate_without_rewriting_time(self):
        self.cat.kraken_instruments(instruments('XRP'),NOW,True)
        self.cat.kraken_tick({'symbol':'XRP/USD','bid':'1','ask':'1.2','timestamp':NOW,'volume':'10','vwap':'1.1'},NOW)
        self.cat.sessions['kraken']['state']='connected'
        row = self.cat.search(now=NOW)['items'][0]
        self.assertEqual(row['quote']['price'],'1.1')
        self.assertEqual(row['quote']['status'],'live')
        self.assertFalse(row['quote']['executable'])
        self.assertEqual(self.cat.quote_view(row,NOW+31)['status'],'stale')
        self.cat.disconnected('kraken','SYNTHETIC outage')
        stale = self.cat.search(now=NOW)['items'][0]['quote']
        self.assertEqual(stale['status'],'stale')
        self.assertEqual(stale['source_at'],NOW)
        restarted = Catalogue(self.store,('kraken',))
        self.assertEqual(restarted.search(now=NOW)['items'][0]['quote']['status'],'unavailable')

    def test_hyperliquid_native_multiplier_and_receipt_only_time_preserved(self):
        self.cat.hyperliquid_metadata([{'universe':[{'name':'kPEPE'},{'name':'xyz:STOCK'}]},[{'dayNtlVlm':'12'},{}]],NOW)
        self.cat.hyperliquid_mids({'kPEPE':'.123','PEPE':'999','xyz:STOCK':'100'},NOW)
        self.cat.sessions['hyperliquid']['state']='connected'
        row = self.cat.search(source='hyperliquid',now=NOW)['items'][0]
        self.assertEqual(row['symbol'],'kPEPE')
        self.assertEqual(row['quote_currency'],'USDC')
        self.assertEqual(row['quote']['price'],'0.123')
        self.assertIsNone(row['quote']['source_at'])
        self.assertEqual(row['quote']['status'],'streaming')
        self.assertEqual(row['quote']['timestamp_basis'],'receipt_only')

    def test_watch_limits_survive_restart_and_global_price_cannot_fill(self):
        runtime = Runtime(self.store,Settings(providers=('kraken',)))
        runtime.catalogue.kraken_instruments(instruments(*(f'TEST{i}' for i in range(7))),time.time(),True)
        for i in range(EXTRA_BOOK_LIMIT):runtime.set_market_watch('kraken:TEST'+str(i)+'/USD',True)
        self.assertEqual(len(runtime.live_watch),6)
        with self.assertRaisesRegex(ValueError,'six'):runtime.set_market_watch('kraken:TEST6/USD',True)
        self.assertEqual(Runtime(self.store,Settings(providers=('kraken',))).desired_symbols('kraken'),runtime.desired_symbols('kraken'))
        with self.assertRaises(ValueError):runtime.set_market_watch('coinpaprika:synthetic',True)
        self.assertNotIn(('kraken','TEST0-USD'),runtime.books)
        runtime.set_market_watch('kraken:TEST0/USD',False)
        self.assertNotIn('TEST0-USD',runtime.desired_symbols('kraken'))

    def test_cannot_remove_book_needed_to_exit_an_open_paper_position(self):
        runtime = Runtime(self.store,Settings(providers=('kraken',)))
        runtime.catalogue.kraken_instruments(instruments('XRP'),time.time(),True)
        runtime.set_market_watch('kraken:XRP/USD',True)
        self.store.put('paper',{'status':'open','provider':'kraken','symbol':'XRP-USD'})
        with self.assertRaisesRegex(ValueError,'Close'):runtime.set_market_watch('kraken:XRP/USD',False)
        self.assertIn('XRP-USD',runtime.desired_symbols('kraken'))

    def test_subscription_batches_cover_all_instruments_without_truncation(self):
        symbols = {f'TEST{i}/USD' for i in range(1001)}
        requests = ticker_subscriptions(symbols)
        self.assertEqual({s for r in requests for s in r['params']['symbol']},symbols)
        self.assertTrue(all(len(r['params']['symbol'])<=50 for r in requests))
        self.assertEqual(Kraken(['XRP-USD']).subscriptions()[0]['params']['symbol'],['XRP/USD'])
        self.assertEqual(Hyperliquid(['kPEPE-USDC-PERP']).subscriptions()[0]['subscription']['coin'],'kPEPE')

    def test_non_core_historical_cycles_use_native_units_and_exclude_spot_ids(self):
        rows = [{'coin':coin,'time':NOW*1000+i,'tid':i,'startPosition':start,'sz':'1','px':'1','fee':'0','closedPnl':pnl,'side':side,'feeToken':'USDC'}
            for coin in ('XRP','@123') for i,start,pnl,side in [(0,'0','0','B'),(1,'1','2','A')]]
        result = analyze_fills(rows,NOW+1)
        self.assertEqual(result['complete_cycles'],1)
        self.assertEqual(result['cycles'][0]['coin'],'XRP')


class CatalogueAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_free_limit_response_retains_data_and_backs_off(self):
        store = Store('sqlite:///:memory:')
        try:
            catalogue = Catalogue(store)
            catalogue.set_coins([{'id':'synthetic','symbol':'TEST','is_active':True}],NOW)
            catalogue.set_global_quotes([{'id':'synthetic','last_updated':NOW,'quotes':{'USD':{'price':'1'}}}],NOW)
            calls = []
            def handler(request):
                calls.append(str(request.url))
                return httpx.Response(402)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await catalogue.refresh(client,NOW+601)
                await catalogue.refresh(client,NOW+602)
            self.assertEqual(len(calls),1)
            self.assertEqual(catalogue.errors['coinpaprika:quotes']['http_status'],402)
            self.assertEqual(catalogue.global_quotes['items']['synthetic']['price'],'1')
            self.assertNotIn('Authorization',calls[0])
        finally:store.close()

    async def test_socket_failure_marks_all_directory_quotes_stale(self):
        store = Store('sqlite:///:memory:')
        catalogue = Catalogue(store,('hyperliquid',))
        catalogue.hyperliquid_metadata([{'universe':[{'name':'XRP'}]},[{}]],NOW)
        class Socket:
            def __init__(self):self.messages=iter([json.dumps({'channel':'allMids','data':{'mids':{'XRP':'1'}}})])
            async def send(self,payload):pass
            async def recv(self):
                try:return next(self.messages)
                except StopIteration:raise ConnectionError('SYNTHETIC outage')
        class Context:
            async def __aenter__(self):return Socket()
            async def __aexit__(self,*args):return False
        try:
            with patch('sentinel.market_directory.connect',return_value=Context()),patch('sentinel.market_directory.time.time',return_value=NOW):
                with self.assertRaises(ConnectionError):await directory_stream(catalogue,'hyperliquid')
            self.assertEqual(catalogue.search(now=NOW)['items'][0]['quote']['status'],'stale')
        finally:store.close()

    async def test_authenticated_search_and_no_aggregate_paper_fills(self):
        store = Store('sqlite:///:memory:')
        settings = Settings(environment='test',collect=False,providers=('kraken',),session_secret='SYNTHETIC'*10,origin='https://testserver')
        app = create_app(settings,store)
        catalogue = app.state.runtime.catalogue
        catalogue.kraken_instruments(instruments('XRP'),NOW,True)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=settings.origin) as client:
                self.assertEqual((await client.get('/api/assets')).status_code,401)
                client.cookies.set('sentinel_session',session_token(settings.session_secret,'test'))
                self.assertEqual((await client.get('/api/assets?q=XRP&source=live')).json()['total'],1)
                self.assertEqual((await client.get('/api/assets?limit=10000')).status_code,422)
                self.assertEqual((await client.post('/api/markets/watch',json={'market_id':'kraken:XRP/USD'})).status_code,403)
                response = await client.post('/api/paper/open',json={'provider':'kraken','symbol':'XRP-USD','notional':'100','idempotency_key':'a1535c18-24b9-4ef2-adcb-627f81d9c0ab'},headers={'Origin':settings.origin})
                self.assertEqual(response.status_code,409)
                self.assertEqual(store.list('paper'),[])
        finally:store.close()

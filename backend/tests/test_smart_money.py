"""All prices, wallets and fills in this module are synthetic test fixtures."""
import asyncio
from decimal import Decimal as D
import time
import unittest
from unittest.mock import patch
import httpx
from sentinel.trader_history import analyze_fills,fetch_history
from sentinel.smart_money import discover,intelligence
from sentinel.follow_evidence import VERSION,begin_sample,resolve_samples,evidence,wilson
from sentinel.storage import Store
from sentinel.models import Book
from sentinel.providers import Hyperliquid

NOW=1800000000
WALLET='0x'+'1'*40

def fill(tid,start,size,side,pnl='0',fee='1',coin='BTC',at=NOW):
    return {'tid':tid,'startPosition':str(start),'sz':str(size),'side':side,'closedPnl':pnl,'fee':fee,
        'feeToken':'USDC','coin':coin,'time':int(at*1000),'px':'100','builderFee':'1'}

def book(at=NOW,bid='99',ask='100'):
    b=Book('hyperliquid','BTC-USDC-PERP','perpetual','USDC')
    b.update([(bid,'100')],[(ask,'100')],at,at,snapshot=True)
    return b

class HistoricalCycleTests(unittest.TestCase):
    def test_partial_closures_count_as_one_cycle_and_builder_fee_once(self):
        rows=[fill(1,0,2,'B'),fill(2,2,1,'A','10',at=NOW+10),fill(3,1,1,'A','20',at=NOW+20)]
        r=analyze_fills(rows,NOW+100)
        self.assertEqual(r['complete_cycles'],1)
        self.assertEqual(r['historical_win_rate_pct'],100)
        self.assertEqual(r['net_before_funding_usdc'],'27')
        self.assertEqual(r['median_holding_seconds'],20)
        self.assertIsNone(r['follower_success_probability_pct'])
    def test_reversal_splits_fee_between_old_and_new_cycle(self):
        rows=[fill(1,0,1,'B'),fill(2,1,2,'A','10','2',at=NOW+10),fill(3,-1,1,'B','-5',at=NOW+20)]
        r=analyze_fills(rows,NOW+100)
        self.assertEqual(r['complete_cycles'],2)
        self.assertEqual(r['net_before_funding_usdc'],'1.0')
        self.assertEqual(r['historical_win_rate_pct'],50)
        self.assertEqual(r['realized_pnl_drawdown_usdc'],'7.0')
    def test_missing_initial_open_and_position_gaps_never_invent_complete_trades(self):
        self.assertEqual(analyze_fills([fill(1,2,2,'A','100')],NOW)['complete_cycles'],0)
        rows=[fill(1,0,1,'B'),fill(2,2,2,'A','100',at=NOW+1)]
        r=analyze_fills(rows,NOW+5)
        self.assertEqual(r['complete_cycles'],0)
        self.assertEqual(r['position_gaps'],1)
    def test_duplicates_future_fills_and_other_fee_tokens_do_not_inflate_win_rate(self):
        rows=[fill(1,0,1,'B'),fill(1,0,1,'B'),fill(2,1,1,'A','10',at=NOW+10)]
        self.assertEqual(analyze_fills(rows,NOW+11)['complete_cycles'],1)
        self.assertIsNone(analyze_fills(rows,NOW)['historical_win_rate_pct'])
        rows[2]['feeToken']='OTHER'
        self.assertEqual(analyze_fills(rows,NOW+11)['complete_cycles'],0)

class HistoricalProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_read_only_query_preserves_input_and_hides_no_gaps(self):
        store=Store('sqlite:///:memory:')
        def handler(request):
            self.assertEqual(request.url.path,'/info')
            self.assertIn(b'userFillsByTime',request.content)
            self.assertNotIn('Authorization',request.headers)
            return httpx.Response(200,json=[fill(1,0,1,'B'),fill(2,1,1,'A','10',at=NOW+1)])
        try:
            with patch('sentinel.trader_history.time.time',return_value=NOW+10):
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    r=await fetch_history(store,WALLET,client)
            self.assertEqual(r['complete_cycles'],1)
            self.assertEqual(len(store.get_state('trader_history:'+WALLET)['raw_fills']),2)
            self.assertEqual(len(r['input_sha256']),64)
        finally:store.close()

class DiscoveryTests(unittest.TestCase):
    def setUp(self):self.store=Store('sqlite:///:memory:')
    def tearDown(self):self.store.close()
    def trade(self,**extra):return dict({'provider':'hyperliquid','symbol':'BTC-USDC-PERP','price':'100000','quantity':'2','source_at':NOW,'received_at':NOW,'trade_id':'SYNTHETIC','public_participants':[WALLET,'0x'+'2'*40]},**extra)
    def test_large_print_discovers_actual_public_participants_without_success_claim(self):
        self.assertEqual(len(discover(self.store,self.trade(),NOW)),2)
        self.assertEqual(discover(self.store,self.trade(),NOW),[])
        row=self.store.get('watchlist',WALLET)
        self.assertEqual(row['discovery']['role_in_print'],'buyer')
        self.assertNotIn('win_rate',row)
    def test_small_stale_zero_or_missing_addresses_are_not_discovered(self):
        for trade in [self.trade(quantity='.1'),self.trade(source_at=NOW-20),self.trade(public_participants=[]),self.trade(public_participants=['0x'+'0'*40,'invalid'])]:
            self.assertEqual(discover(self.store,trade,NOW),[])
    def test_auto_discovery_caps_total_wallets(self):
        for i in range(1,20):
            discover(self.store,self.trade(public_participants=['0x'+format(i,'040x')]),NOW)
        self.assertEqual(len(self.store.list('watchlist',20)),5)
    def test_hyperliquid_adapter_preserves_documented_buyer_seller_addresses(self):
        row={'coin':'BTC','px':'100000','sz':'2','time':NOW*1000,'side':'B','tid':1,'users':[WALLET,'0x'+'2'*40]}
        event=Hyperliquid().consume({'channel':'trades','data':[row]},NOW)[0][1]
        self.assertEqual(event['public_participants'],row['users'])

class ForwardStudyTests(unittest.TestCase):
    def setUp(self):self.store=Store('sqlite:///:memory:')
    def tearDown(self):self.store.close()
    def event(self,**extra):return dict({'action':'opened','baseline':False,'side':'long','address':WALLET},**extra)
    def test_baselines_stale_quotes_and_overlapping_wallet_entries_are_not_samples(self):
        self.assertIsNone(begin_sample(self.store,self.event(baseline=True),book(),NOW))
        self.assertIsNone(begin_sample(self.store,self.event(),book(),NOW+10))
        first=begin_sample(self.store,self.event(),book(),NOW)
        self.assertIsNotNone(first)
        self.assertIsNone(first['predicted_at_entry'])
        self.assertIsNone(begin_sample(self.store,self.event(address='0x'+'2'*40),book(),NOW))
        self.assertEqual(self.store.get_state('account')['cash'],'10000')
    def test_actual_later_book_measures_net_outcome_without_changing_paper_cash(self):
        first=begin_sample(self.store,self.event(),book(),NOW)
        resolve_samples(self.store,{('hyperliquid','BTC-USDC-PERP'):book(NOW+3600,'110','111')},NOW+3600)
        row=self.store.get('follow_sample',first['id'])
        self.assertEqual(row['status'],'closed')
        self.assertGreater(D(row['net_pnl_usdc']),0)
        self.assertEqual(self.store.get_state('account')['cash'],'10000')
    def test_outage_is_missing_evidence_not_assumed_win_or_loss(self):
        first=begin_sample(self.store,self.event(),book(),NOW)
        resolve_samples(self.store,{},NOW+3661)
        row=self.store.get('follow_sample',first['id'])
        self.assertEqual(row['status'],'unavailable')
        r=evidence([row],'BTC-USDC-PERP','long',NOW+4000)
        self.assertEqual(r['missing'],1)
        self.assertIsNone(r['estimated_success_pct'])
    def test_no_sample_never_returns_made_up_odds(self):
        r=evidence([],'BTC-USDC-PERP','long',NOW)
        self.assertIsNone(r['historical_success_pct'])
        self.assertIsNone(r['estimated_success_pct'])
        self.assertIsNone(wilson(0,0))
    def test_costs_can_make_a_small_favorable_move_unsuccessful(self):
        sample=begin_sample(self.store,self.event(),book(ask='100',bid='99.99'),NOW)
        resolve_samples(self.store,{('hyperliquid','BTC-USDC-PERP'):book(NOW+3600,'100.05','100.06')},NOW+3600)
        row=self.store.get('follow_sample',sample['id'])
        self.assertLess(D(row['net_pnl_usdc']),0)
        self.assertFalse(row['success'])
    def test_future_outcomes_cannot_change_an_earlier_estimate(self):
        row={'version':VERSION,'symbol':'BTC-USDC-PERP','side':'long','entered_at':NOW-1,'closed_at':NOW+3600,'status':'closed','net_pnl_usdc':'10','predicted_at_entry':.5}
        r=evidence([row],'BTC-USDC-PERP','long',NOW)
        self.assertEqual(r['completed'],0)
    def test_calibrated_large_prospective_sample_can_expose_estimate_with_interval(self):
        rows=[]
        for i in range(120):
            entered=NOW-120*7200+i*7200
            rows.append({'version':VERSION,'symbol':'BTC-USDC-PERP','side':'long','entered_at':entered,'closed_at':entered+3600,
                'status':'closed','net_pnl_usdc':'10' if i%5 else '-10','predicted_at_entry':.8})
        r=evidence(rows,'BTC-USDC-PERP','long',NOW)
        self.assertIsNotNone(r['estimated_success_pct'])
        self.assertLess(r['interval_95_pct'][0],80)
        self.assertGreater(r['interval_95_pct'][1],80)
        for row in rows:row['predicted_at_entry']=.1
        self.assertIsNone(evidence(rows,'BTC-USDC-PERP','long',NOW)['estimated_success_pct'])

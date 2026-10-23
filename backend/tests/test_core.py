"""All prices, addresses and bars here are explicitly SYNTHETIC TEST FIXTURES."""
import asyncio
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
import httpx
from sentinel.config import Settings
from sentinel.models import Book,decimal,timestamp
from sentinel.providers import Kraken,Coinbase,Hyperliquid
from sentinel.engine import investigate,copy_decision,anomaly_facts,paper_open,paper_close
from sentinel.storage import Store
from sentinel.security import password_hash,verify_password,session_token,verify_session
from sentinel.lab import walk_forward,replay,validate_bars
from sentinel.traders import position_changes,poll_trader,ranking_evidence
from sentinel.runtime import Runtime,reconnect_delay
from sentinel.app import create_app

NOW = 1800000000.0

def book(provider='kraken',bid='99',ask='100',now=NOW,qty='100'):
    b=Book(provider,'BTC-USD')
    b.update([(bid,qty)],[(ask,qty)],now,now,snapshot=True)
    return b

class BookTests(unittest.TestCase):
    def test_decimal_rejects_nonfinite(self):
        for value in ['NaN','Infinity','-Infinity','nonsense']:
            with self.assertRaises(ValueError): decimal(value)
    def test_timestamp_units(self):
        self.assertEqual(timestamp(1800000000000),NOW)
        self.assertEqual(timestamp('2026-01-01T00:00:00Z'),1767225600)
    def test_vwap_walks_multiple_levels(self):
        b=book(qty='1');b.update([], [('101','2')],NOW,NOW)
        self.assertEqual(b.fill('buy','2'),D('100.5'))
        with self.assertRaisesRegex(ValueError,'liquidity'): b.fill('buy','4')
    def test_absolute_size_zero_removes_level(self):
        b=book();b.update([('98','2')],[],NOW,NOW)
        b.update([('99','0')],[],NOW,NOW)
        self.assertEqual(max(b.bids),D(98))
    def test_update_before_snapshot_rejected(self):
        with self.assertRaises(ValueError):Book('kraken','BTC-USD').update([('99','1')],[('100','1')],NOW,NOW)
    def test_stale_missing_clock_and_future_rejected(self):
        b=book()
        self.assertTrue(b.fresh(NOW))
        self.assertFalse(b.fresh(NOW+6))
        self.assertFalse(b.fresh(NOW-2))
        b.source_at=None
        self.assertFalse(b.fresh(NOW))
    def test_out_of_order_invalidates(self):
        b=book()
        with self.assertRaisesRegex(ValueError,'order'): b.update([],[],NOW-1,NOW)
        self.assertFalse(b.valid)
    def test_crossed_book_invalidates(self):
        b=book()
        with self.assertRaises(ValueError):b.update([('101','1')],[],NOW,NOW)
        self.assertFalse(b.valid)
    def test_depth_truncated(self):
        b=book();b.update([(str(i),'1') for i in range(80,99)],[],NOW,NOW,depth=10)
        self.assertEqual(len(b.bids),10)
        self.assertEqual(min(b.bids),D(90))

class AdapterTests(unittest.TestCase):
    def test_kraken_official_crc_vector(self):
        # Published documentation vector, not live data or claimed market observations.
        prices_b=['45283.5','45283.4','45282.1','45281.0','45280.3','45279.0','45277.6','45277.5','45277.3','45276.6']
        quantities_b=['0.10000000','1.54582015','0.10000000','0.10000000','1.54592586','0.07990000','0.03310103','0.30000000','1.54602737','0.15445238']
        prices_a=['45285.2','45286.4','45286.6','45289.6','45290.2','45291.8','45294.7','45296.1','45297.5','45299.5']
        quantities_a=['0.00100000','1.54571953','1.54571109','1.54560911','0.15890660','1.54553491','0.04454749','0.35380000','0.09945542','0.18772827']
        k=Kraken()
        m={'channel':'book','type':'snapshot','data':[{'symbol':'BTC/USD','bids':[{'price':D(p),'qty':D(q)} for p,q in zip(prices_b,quantities_b)],'asks':[{'price':D(p),'qty':D(q)} for p,q in zip(prices_a,quantities_a)],'checksum':3310070434}]}
        events=k.consume(m,NOW)
        b=events[0][1]
        self.assertEqual(k.checksum(b),3310070434)
        self.assertEqual(b.integrity,'crc32_verified')
        self.assertFalse(b.fresh(NOW)) # Source timestamp missing in snapshots.
    def test_kraken_checksum_failure_blocks(self):
        k=Kraken()
        with self.assertRaises(ValueError):k.consume({'channel':'book','type':'snapshot','data':[{'symbol':'BTC/USD','bids':[{'price':99,'qty':1}],'asks':[{'price':100,'qty':1}],'checksum':0}]},NOW)
        self.assertFalse(k.books['BTC-USD'].valid)
    def test_coinbase_snapshot_updates_and_maker_side(self):
        c=Coinbase();c.consume({'type':'snapshot','product_id':'BTC-USD','bids':[['99','2']],'asks':[['100','2']]},NOW)
        self.assertFalse(c.books['BTC-USD'].fresh(NOW))
        c.consume({'type':'l2update','product_id':'BTC-USD','time':NOW,'changes':[['buy','99','3']]},NOW)
        self.assertEqual(c.books['BTC-USD'].bids[D(99)],D(3))
        self.assertTrue(c.books['BTC-USD'].fresh(NOW))
        event=c.consume({'type':'match','product_id':'BTC-USD','time':NOW,'size':'1','price':'100','side':'sell','trade_id':1},NOW)[0][1]
        self.assertEqual(event['side'],'buy')
    def test_ticker_never_refreshes_stale_book(self):
        c=Coinbase();c.books['BTC-USD']=book('coinbase')
        c.consume({'type':'ticker','product_id':'BTC-USD','price':'100','time':NOW+10},NOW+10)
        self.assertFalse(c.books['BTC-USD'].fresh(NOW+10))
    def test_hyperliquid_perps_are_separate(self):
        h=Hyperliquid();e=h.consume({'channel':'l2Book','data':{'coin':'BTC','time':NOW*1000,'levels':[[{'px':'99','sz':'1'}],[{'px':'100','sz':'1'}]]}},NOW)
        self.assertEqual(e[0][1].quote,'USDC');self.assertEqual(e[0][1].instrument,'perpetual')
    def test_rejections_are_not_silently_ignored(self):
        for cls,m in [(Kraken,{'success':False}),(Coinbase,{'type':'error'}),(Hyperliquid,{'channel':'error'})]:
            with self.assertRaises(ValueError):cls().consume(m,NOW)
    def test_invalidation(self):
        a=Coinbase();a.books['BTC-USD']=book('coinbase');a.invalidate()
        self.assertFalse(a.books['BTC-USD'].valid)

class EngineTests(unittest.TestCase):
    def test_costs_erase_small_gross_edge(self):
        r=investigate(book(),book('coinbase','100.1','101'),now=NOW)
        self.assertEqual(r['decision'],'NO-GO')
        self.assertAlmostEqual(float(r['gross_bps']),10)
        self.assertAlmostEqual(float(r['net_bps']),-95)
    def test_positive_edge_waits_for_inventory(self):
        r=investigate(book(),book('coinbase','103','104'),now=NOW)
        self.assertEqual(r['decision'],'WAIT');self.assertFalse(r['inventory_verified'])
        self.assertAlmostEqual(float(r['net_bps']),195)
    def test_emergency_stop_is_absolute(self):
        self.assertEqual(investigate(book(),book('coinbase','103','104'),now=NOW,stopped=True)['decision'],'NO-GO')
    def test_different_quote_currency_rejected(self):
        b=book('hyperliquid','103','104');b.quote='USDC';b.instrument='perpetual'
        r=investigate(book(),b,now=NOW);self.assertEqual(r['decision'],'NO-GO');self.assertIsNone(r['net_bps'])
    def test_stale_data_and_snapshot_skew(self):
        r=investigate(book(),book('coinbase','103','104',now=NOW-3),now=NOW)
        self.assertEqual(r['decision'],'NO-GO')
        self.assertTrue(any('two seconds' in x for x in r['stages']['skeptic']['objections']))
    def test_insufficient_visible_liquidity_rejected(self):
        r=investigate(book(qty='.01'),book('coinbase','103','104'),now=NOW)
        self.assertEqual(r['decision'],'NO-GO')
    def test_copy_rejects_missing_risk_even_with_fresh_price(self):
        r=copy_decision({'entry_price':'100','observed_at':NOW,'baseline':False,'side':'long'},book(),now=NOW)
        self.assertEqual(r['decision'],'NO-GO');self.assertIn('Stop, target',r['reasons'][-1])
    def test_copy_does_not_call_baseline_new_entry(self):
        r=copy_decision({'entry_price':'100','observed_at':NOW,'baseline':True},book(),now=NOW)
        self.assertTrue(any('baseline' in reason for reason in r['reasons']))
    def test_forensics_distinguishes_observation(self):
        a=book().view(NOW);b=book(qty='1').view(NOW)
        self.assertTrue(any('50%' in f for f in anomaly_facts(b,a)))

class PaperTests(unittest.TestCase):
    def setUp(self):self.s=Store('sqlite:///:memory:')
    def tearDown(self):self.s.close()
    def test_cash_and_roundtrip_costs(self):
        p=paper_open(self.s,book(),'100','test-id',NOW)
        self.assertEqual(p['quantity'],'1')
        self.assertEqual(D(self.s.get_state('account')['cash']),D('9899.5498'))
        closed=paper_close(self.s,'test-id',book(),NOW)
        self.assertEqual(D(closed['net_pnl']),D('-1.895502'))
        self.assertEqual(D(self.s.get_state('account')['cash']),D('9998.104498'))
        self.assertEqual(paper_close(self.s,'test-id',book(),NOW),closed)
    def test_duplicate_entry_does_not_double_spend(self):
        p=paper_open(self.s,book(),'100','same',NOW)
        cash=self.s.get_state('account')['cash']
        self.assertEqual(paper_open(self.s,book(),'100','same',NOW),p)
        self.assertEqual(self.s.get_state('account')['cash'],cash)
    def test_concurrent_entries_serialized(self):
        def enter(_):return paper_open(self.s,book(),'100','concurrent',NOW)
        with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(enter,range(10)))
        self.assertEqual(len(self.s.list('paper')),1)
        self.assertEqual(len({r['id'] for r in results}),1)
    def test_stop_blocks_entry_but_allows_exit(self):
        paper_open(self.s,book(),'100','first',NOW)
        self.s.set_state('control',{'stopped':True})
        with self.assertRaises(ValueError):paper_open(self.s,book(),'100','second',NOW)
        self.assertEqual(paper_close(self.s,'first',book(),NOW)['status'],'closed')
    def test_stale_book_rejects_fill(self):
        with self.assertRaises(ValueError):paper_open(self.s,book(),'100','stale',NOW+10)
        self.assertEqual(self.s.get_state('account')['cash'],'10000')
    def test_position_and_total_limits(self):
        with self.assertRaises(ValueError):paper_open(self.s,book(),'501','big',NOW)
        for i in range(5):paper_open(self.s,book(),'499',str(i),NOW)
        with self.assertRaisesRegex(ValueError,'exposure'):paper_open(self.s,book(),'100','excess',NOW)
    def test_rollback_is_atomic(self):
        with self.assertRaises(RuntimeError):
            with self.s.transaction():
                self.s.set_state('account',{'cash':'0'})
                raise RuntimeError('injected failure')
        self.assertEqual(self.s.get_state('account')['cash'],'10000')
    def test_persistence_and_search(self):
        with tempfile.TemporaryDirectory() as d:
            path='sqlite:///'+str(Path(d)/'test.db');s=Store(path)
            doc=s.put('opportunity',{'symbol':'BTC-USD','decision':'WAIT'});s.close();s=Store(path)
            self.assertEqual(s.list('opportunity',query='btc')[0]['id'],doc['id']);s.close()

class SecurityTests(unittest.TestCase):
    def test_password_hash(self):
        encoded=password_hash('synthetic owner test password')
        self.assertTrue(verify_password('synthetic owner test password',encoded))
        self.assertFalse(verify_password('wrong',encoded))
    def test_session_tamper_expiry_environment_and_scope(self):
        token=session_token('s'*64,'test',NOW)
        self.assertTrue(verify_session(token,'s'*64,'test',NOW))
        self.assertFalse(verify_session(token+'a','s'*64,'test',NOW))
        self.assertFalse(verify_session(token,'s'*64,'production',NOW))
        self.assertFalse(verify_session(token,'s'*64,'test',NOW+30000))
        self.assertFalse(verify_session(token,'','test',NOW))
    def test_hosted_config_fails_closed(self):
        with self.assertRaises(ValueError):Settings(environment='production',database_url='sqlite:///:memory:').validate()
    def test_rate_limit(self):
        s=Store('sqlite:///:memory:');self.assertTrue(s.rate('client',1));self.assertFalse(s.rate('client',1));s.close()

class ApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):cls.pwhash=password_hash('synthetic test password')
    async def asyncSetUp(self):
        self.s=Store('sqlite:///:memory:')
        self.settings=Settings(environment='test',database_url='sqlite:///:memory:',session_secret='s'*64,password_hash=self.pwhash,origin='https://testserver',collect=False)
        self.app=create_app(self.settings,self.s)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://testserver')
    async def asyncTearDown(self):
        await self.client.aclose()
        self.s.close()
    async def login(self):
        return await self.client.post('/api/session/login',json={'password':'synthetic test password'},headers={'Origin':'https://testserver'})
    async def test_auth_and_health(self):
        self.assertEqual((await self.client.get('/api/dashboard')).status_code,401)
        self.assertEqual((await self.client.get('/health/live')).status_code,200)
        self.assertFalse((await self.client.get('/health/live')).json()['live_trading'])
    async def test_secure_cookie_and_no_secrets(self):
        r=await self.login();self.assertEqual(r.status_code,200)
        cookie=r.headers['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=strict',cookie)
        data=(await self.client.get('/api/dashboard')).json()
        self.assertNotIn('session_secret',json.dumps(data))
        self.assertEqual(len(data['markets']),6)
        self.assertTrue(all(m['status']=='unavailable' for m in data['markets']))
    async def test_origin_rejection(self):
        self.assertEqual((await self.client.post('/api/session/login',json={'password':'x'})).status_code,403)
        await self.login()
        self.assertEqual((await self.client.post('/api/control',json={'stopped':True},headers={'Origin':'https://evil.test'})).status_code,403)
    async def test_chunked_body_cannot_bypass_size_limit(self):
        async def chunks():
            yield b'x'*700000
            yield b'x'*700000
        response=await self.client.post('/api/session/login',content=chunks(),headers={'Origin':'https://testserver','Content-Type':'application/json'})
        self.assertNotIn('content-length',response.request.headers)
        self.assertEqual(response.status_code,413)
    async def test_small_chunked_body_replayed_to_json_parser(self):
        async def chunks():
            yield b'{"password":'
            yield b'"synthetic test password"}'
        response=await self.client.post('/api/session/login',content=chunks(),headers={'Origin':'https://testserver','Content-Type':'application/json'})
        self.assertEqual(response.status_code,200)
    async def test_missing_market_never_substitutes_fill(self):
        await self.login();r=await self.client.post('/api/paper/open',json={'provider':'kraken','symbol':'BTC-USD','notional':'100','idempotency_key':'a1535c18-24b9-4ef2-adcb-627f81d9c0ab'},headers={'Origin':'https://testserver'})
        self.assertEqual(r.status_code,409);self.assertEqual(self.s.list('paper'),[])
    async def test_public_address_validation(self):
        await self.login();r=await self.client.post('/api/traders',json={'address':'not-an-address'},headers={'Origin':'https://testserver'})
        self.assertEqual(r.status_code,422)
    async def test_admin_stop_is_durable_and_audited(self):
        await self.login();r=await self.client.post('/api/control',json={'stopped':True},headers={'Origin':'https://testserver'})
        self.assertEqual(r.status_code,200);self.assertTrue(self.s.get_state('control')['stopped'])
        self.assertIn('emergency_stop',[a['action'] for a in self.s.list('audit')])
    async def test_no_execution_routes(self):
        self.assertFalse(any('withdraw' in route.path or route.path.startswith('/api/orders') for route in self.app.routes))
    async def test_mobile_config_unavailable(self):
        await self.login();self.assertEqual((await self.client.post('/api/alerts/test',json={},headers={'Origin':'https://testserver'})).status_code,409)

class TraderTests(unittest.TestCase):
    def test_deltas_and_reversal(self):
        old=[{'coin':'BTC','szi':'1','entryPx':'100'}]
        for size,action in [('2','increased'),('.5','reduced'),('0','closed'),('-1','reversal')]:
            event=position_changes(old,[{'coin':'BTC','szi':size,'entryPx':'100'}],NOW)[0]
            self.assertEqual(event['action'],action)
    def test_public_baseline_no_invented_entry(self):
        async def run():
            state={'assetPositions':[{'position':{'coin':'BTC','szi':'1','entryPx':'100'}}],'marginSummary':{'accountValue':'1000'},'time':NOW*1000}
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=state)))
            s=Store('sqlite:///:memory:')
            await poll_trader(s,{'address':'0x'+'1'*40},{},client)
            self.assertEqual(s.list('trader_event'),[])
            state['assetPositions'][0]['position']['szi']='2'
            await poll_trader(s,{'address':'0x'+'1'*40},{},client)
            events=s.list('trader_event');self.assertEqual(events[0]['action'],'increased')
            self.assertEqual(events[0]['analysis']['decision'],'NO-GO')
            await client.aclose();s.close()
        asyncio.run(run())
    def test_no_equity_poll_profitability_ranking(self):
        r=ranking_evidence([100,200,10000]);self.assertIsNone(r['rank']);self.assertIsNone(r['risk_adjusted_return'])

class LabTests(unittest.TestCase):
    def setUp(self):self.bars=[{'timestamp':NOW+i*60,'close':str(100+i*.1+(i%7)*.01)} for i in range(240)]
    def test_folds_are_out_of_sample_with_embargo(self):
        r=walk_forward(self.bars,'SYNTHETIC TEST FIXTURE')
        for fold in r['folds']:
            self.assertLess(fold['training_end_exclusive'],fold['test_start'])
            self.assertGreater(fold['strategy']['transactions'],0)
        self.assertEqual(r['no_trade_return'],0)
    def test_no_lookahead_future_change_cannot_change_prefix(self):
        prices=validate_bars(self.bars)
        original=replay(prices,20,100,6)
        changed=prices[:100]+[p*50 for p in prices[100:]]
        self.assertEqual(original,replay(changed,20,100,6))
    def test_future_change_cannot_change_earlier_fold_selection(self):
        baseline=walk_forward(self.bars,'SYNTHETIC')
        changed=[dict(b) for b in self.bars]
        for b in changed[180:]:b['close']=str(float(b['close'])*10)
        self.assertEqual(baseline['folds'][0],walk_forward(changed,'SYNTHETIC')['folds'][0])
    def test_flat_prices_do_not_invent_profit(self):
        for b in self.bars:b['close']='100'
        r=walk_forward(self.bars,'SYNTHETIC FLAT')
        self.assertEqual(r['out_of_sample_return'],0)
        self.assertLess(r['buy_and_hold_return'],0)
    def test_fees_reduce_returns(self):
        no_cost=walk_forward(self.bars,'SYNTHETIC',0,0)
        costs=walk_forward(self.bars,'SYNTHETIC',60,5)
        self.assertGreater(no_cost['out_of_sample_return'],costs['out_of_sample_return'])
    def test_duplicate_gap_and_nonfinite_rejected(self):
        for val in [str(float('nan')),'0','-1']:
            bars=[dict(b) for b in self.bars];bars[10]['close']=val
            with self.assertRaises(ValueError):walk_forward(bars,'SYNTHETIC')
        bars=[dict(b) for b in self.bars];bars[10]['timestamp']=bars[9]['timestamp']
        with self.assertRaises(ValueError):walk_forward(bars,'SYNTHETIC')
        bars=[dict(b) for b in self.bars];bars[10]['timestamp']+=1
        with self.assertRaises(ValueError):walk_forward(bars,'SYNTHETIC')

class RuntimeTests(unittest.TestCase):
    def test_backoff_is_bounded(self):
        self.assertEqual(reconnect_delay(0,0),1)
        self.assertLess(reconnect_delay(100,.9),61)
    def test_disabled_collectors_never_connect(self):
        s=Store('sqlite:///:memory:');r=Runtime(s,Settings(collect=False));asyncio.run(r.start())
        self.assertEqual(r.tasks,[]);s.close()
    def test_unavailable_outcome_is_not_a_loss(self):
        s=Store('sqlite:///:memory:');r=Runtime(s,Settings(collect=False))
        signal=investigate(book(),book('coinbase','103','104'),now=NOW)
        record=s.put('opportunity',signal)
        with patch('sentinel.runtime.time.time',return_value=NOW+301):r.resolve_outcomes()
        self.assertEqual(s.get('opportunity',record['id'])['outcome']['status'],'unavailable');s.close()

if __name__=='__main__':unittest.main()

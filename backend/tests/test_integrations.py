"""Synthetic provider contracts, cryptographic authorization, and paper risk checks."""
import json
import time
import unittest
from decimal import Decimal as D
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from sentinel.access import AccessVerifier
from sentinel.changenow import estimate
from sentinel.config import Settings
from sentinel.engine import evaluate_paper_plan
from sentinel.models import Book

class ChangeNowTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_estimate_is_not_executable(self):
        def handler(request):
            self.assertEqual(request.method,'GET')
            self.assertEqual(request.url.path,'/v2/exchange/estimated-amount')
            self.assertEqual(request.url.params['toNetwork'],'eth')
            self.assertNotIn('address',request.url.params)
            return httpx.Response(200,json={'fromAmount':'0.01','toAmount':'0.25','fromCurrency':'btc','toCurrency':'eth','fromNetwork':'btc','toNetwork':'eth'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            r=await estimate(Settings(changenow_key='SYNTHETIC_TEST_KEY',changenow_approved=True),'btc','eth','.01',client)
        self.assertFalse(r['executable'])
        self.assertIsNone(r['source_at'])
        self.assertIsNone(r['provider_expiry'])
        self.assertEqual(r['decision'],'WAIT')
        self.assertNotIn('SYNTHETIC_TEST_KEY',json.dumps(r))
    async def test_key_and_permission_required(self):
        for settings in [Settings(),Settings(changenow_key='SYNTHETIC')]:
            with self.assertRaises(ValueError):await estimate(settings,'btc','eth','1')
    async def test_rate_limit_does_not_fabricate_quote(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(429))) as client:
            with self.assertRaisesRegex(ValueError,'rate limit'):
                await estimate(Settings(changenow_key='SYNTHETIC',changenow_approved=True),'btc','eth','1',client)
    async def test_malformed_and_mismatched_quotes_rejected(self):
        for row in [{'toAmount':'NaN'},{'toAmount':'0'},{'toAmount':'1','toNetwork':'btc'},{'toAmount':'1','fromAmount':'999'}]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=row))) as client:
                with self.assertRaises(ValueError):await estimate(Settings(changenow_key='SYNTHETIC',changenow_approved=True),'btc','eth','1',client)
    async def test_arbitrary_routes_rejected(self):
        with self.assertRaises(ValueError):await estimate(Settings(changenow_key='SYNTHETIC',changenow_approved=True),'https://evil.example','eth','1')

class AccessTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private.public_key()))
        cls.jwk.update(kid='SYNTHETIC_KEY',alg='RS256',use='sig')
    def token(self,**overrides):
        claims={'iss':'https://test.cloudflareaccess.com','aud':['SYNTHETIC_AUD'],'sub':'synthetic-owner','iat':int(time.time()),'exp':int(time.time())+3600,'email':'owner@example.test','type':'app'}
        claims.update(overrides)
        return jwt.encode(claims,self.private,algorithm='RS256',headers={'kid':'SYNTHETIC_KEY'})
    async def test_signature_owner_lifetime_issuer_and_audience(self):
        verifier=AccessVerifier('https://test.cloudflareaccess.com','SYNTHETIC_AUD','owner@example.test')
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={'keys':[self.jwk]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertTrue(await verifier.verify(self.token(),client))
            self.assertTrue(await verifier.verify(self.token(),client))
            self.assertEqual(len(calls),1)
            for claims in [{'aud':['WRONG']},{'email':'attacker@example.test'},{'exp':int(time.time())-30},{'iss':'https://wrong.cloudflareaccess.com'},{'type':'service'}]:
                self.assertFalse(await verifier.verify(self.token(**claims),client))
    async def test_forged_header_and_algorithm_denied(self):
        v=AccessVerifier('https://test.cloudflareaccess.com','SYNTHETIC_AUD','owner@example.test')
        self.assertFalse(await v.verify('not-a-token'))
        token=jwt.encode({'email':'owner@example.test'},'synthetic'*8,algorithm='HS256',headers={'kid':'SYNTHETIC_KEY'})
        self.assertFalse(await v.verify(token))
    async def test_arbitrary_jwks_origin_denied(self):
        self.assertFalse(await AccessVerifier('https://attacker.example','AUD','owner@example.test').verify(self.token()))
    async def test_key_service_outage_fails_closed(self):
        v=AccessVerifier('https://test.cloudflareaccess.com','SYNTHETIC_AUD','owner@example.test')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as client:
            self.assertFalse(await v.verify(self.token(),client))
            self.assertFalse(await v.verify(self.token(),client))

class PaperPlanTests(unittest.TestCase):
    def book(self):
        b=Book('kraken','BTC-USD')
        b.update([('99','100')],[('100','100')],1800000000,1800000000,snapshot=True)
        return b
    def test_go_is_only_paper_eligibility(self):
        r=evaluate_paper_plan(self.book(),'100','98','110',now=1800000000)
        self.assertEqual(r['decision'],'GO')
        self.assertFalse(r['hypothesis_validated'])
    def test_costs_invalidate_raw_risk_reward(self):
        self.assertEqual(evaluate_paper_plan(self.book(),'100','99','102',now=1800000000)['decision'],'NO-GO')
    def test_stop_stale_exposure_cash_and_daily_loss(self):
        for extra in [{'stopped':True},{'exposure':D('2499')},{'now':1800000010},{'cash':D(0)},{'daily_pnl':D('-200')}]:
            self.assertEqual(evaluate_paper_plan(self.book(),'100','98','110',**{'now':1800000000,**extra})['decision'],'NO-GO')

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_invalidates_book_and_reconnect_starts_from_snapshot(self):
        from unittest.mock import patch
        from sentinel.runtime import Runtime
        from sentinel.storage import Store
        import asyncio
        store=Store('sqlite:///:memory:')
        runtime=Runtime(store,Settings(collect=False))
        calls=[]
        now=time.time()
        class Socket:
            def __init__(self,index):self.index=index;self.cursor=0
            async def send(self,message):pass
            async def recv(self):
                self.cursor+=1
                if self.cursor==1:return json.dumps({'type':'snapshot','product_id':'BTC-USD','bids':[[str(99+self.index),'2']],'asks':[[str(101+self.index),'2']]})
                if self.cursor==2:return json.dumps({'type':'l2update','product_id':'BTC-USD','time':now,'changes':[['buy',str(99+self.index),'3']]})
                if self.index==0:raise ConnectionError('SYNTHETIC disconnect')
                raise asyncio.CancelledError()
        class Context:
            def __init__(self,index):self.socket=Socket(index)
            async def __aenter__(self):return self.socket
            async def __aexit__(self,*args):return False
        def connect(*args,**kwargs):
            index=len(calls);calls.append(index)
            return Context(index)
        async def backoff(delay):
            self.assertFalse(runtime.books[('coinbase','BTC-USD')].valid)
        with patch('sentinel.runtime.connect',connect),patch('sentinel.runtime.asyncio.sleep',backoff):
            with self.assertRaises(asyncio.CancelledError):await runtime.stream('coinbase')
        self.assertEqual(len(calls),2)
        self.assertEqual(runtime.status['coinbase']['reconnects'],1)
        self.assertEqual(max(runtime.books[('coinbase','BTC-USD')].bids),D(100))
        self.assertFalse(runtime.books[('coinbase','BTC-USD')].valid)
        store.close()

class FlowTests(unittest.TestCase):
    def test_volume_requires_complete_observed_history_and_deduplicates(self):
        from sentinel.flow import FlowDetector
        f=FlowDetector()
        def add(bucket,count,qty):
            for i in range(count):
                t=bucket*30+i*.01
                f.observe({'provider':'kraken','symbol':'BTC-USD','trade_id':str(bucket)+':'+str(i),'price':'100','quantity':qty,'source_at':t,'received_at':t,'side':'buy'})
        for i in range(10):add(i,10,'1')
        add(10,10,'10')
        events=f.anomalies(330)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['volume_ratio'],'10')
        self.assertEqual(f.anomalies(330),[])
        f.reset('kraken')
        self.assertEqual(f.anomalies(330),[])
    def test_stale_and_duplicate_trades_are_not_new_flow(self):
        from sentinel.flow import FlowDetector
        f=FlowDetector()
        t={'provider':'kraken','symbol':'BTC-USD','trade_id':'SYNTHETIC','price':'100','quantity':'1','source_at':100,'received_at':100,'side':'buy'}
        f.observe(t);f.observe(t)
        self.assertEqual(f.buckets[('kraken','BTC-USD')][3]['count'],1)
        f.observe(dict(t,trade_id='stale',received_at=200))
        self.assertEqual(f.buckets[('kraken','BTC-USD')][3]['count'],1)

class TimestampTests(unittest.TestCase):
    def test_unknown_clock_and_nonfinite_source_timestamps_rejected(self):
        from sentinel.models import timestamp
        for value in [float('nan'),float('inf'),'2026-10-23T12:00:00']:
            with self.assertRaises(ValueError):timestamp(value)

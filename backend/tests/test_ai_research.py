"""Synthetic public-only AI context; no inference, account reads or trades."""
import unittest
from unittest.mock import patch
import httpx
from sentinel.app import create_app
from sentinel.config import Settings
from sentinel.security import session_token
from sentinel.storage import Store

class ResearchContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=Store('sqlite:///:memory:')
        self.settings=Settings(environment='test',database_url='sqlite:///:memory:',collect=False,
            origin='https://testserver',session_secret='SYNTHETIC_AI_TEST_ONLY'*4)
        self.app=create_app(self.settings,self.store)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=self.settings.origin)
    async def asyncTearDown(self):await self.client.aclose();self.store.close()
    def login(self):self.client.cookies.set('sentinel_session',session_token(self.settings.session_secret,'test'))
    async def test_ai_cannot_bypass_auth_origin_or_schema_and_never_submits_orders(self):
        url='/api/ai/context';headers={'Origin':self.settings.origin}
        self.assertEqual((await self.client.post(url,json={'mode':'explain'},headers=headers)).status_code,401)
        self.login()
        self.assertEqual((await self.client.post(url,json={'mode':'explain'})).status_code,403)
        for payload in [{'mode':'execute'},{'mode':'explain','api_secret':'SYNTHETIC_NEVER_SEND'}, {'mode':'explain','risk_limit':'100'}]:
            self.assertEqual((await self.client.post(url,json=payload,headers=headers)).status_code,422)
        self.assertEqual(self.store.list('paper',10),[])
        self.assertEqual(self.store.list('kraken_order',10),[])
    async def test_packet_contains_only_allowlisted_public_facts_and_quota_is_persistent(self):
        self.login();headers={'Origin':self.settings.origin}
        card={'id':'SYNTHETIC_PUBLIC_ID','symbol':'BTC-USD','provider':'kraken','decision':'WAIT','reason':'SYNTHETIC watch condition',
            'facts':['SYNTHETIC public price observation'],'checks':[],'trader_review':[],
            'source_at':None,'received_at':1800000000,'expires_at':None,
            'account':{'balance':'SYNTHETIC_PRIVATE_BALANCE'},'api_secret':'SYNTHETIC_NEVER_SEND'}
        with patch('sentinel.ai_research.suggestions',return_value={'cards':[card]}),patch('sentinel.ai_research.intelligence',return_value={}):
            result=await self.client.post('/api/ai/context',json={'mode':'explain'},headers=headers)
            self.assertEqual(result.status_code,200);self.assertFalse(result.json()['financial_action'])
            self.assertIsNone(result.json()['success_probability_pct'])
            self.assertNotIn('SYNTHETIC_PRIVATE',result.text);self.assertNotIn('SYNTHETIC_NEVER_SEND',result.text)
            self.assertEqual(result.json()['evidence'][0]['decision'],'WAIT')
            for _ in range(3):self.assertEqual((await self.client.post('/api/ai/context',json={'mode':'search'},headers=headers)).status_code,200)
            self.assertEqual((await self.client.post('/api/ai/context',json={'mode':'search'},headers=headers)).status_code,429)
        self.assertEqual(self.store.list('paper',10),[])
        self.assertTrue(self.store.list('audit',10))
    async def test_changed_idea_is_not_replaced_with_unrelated_research(self):
        self.login()
        with patch('sentinel.ai_research.suggestions',return_value={'cards':[]}):
            result=await self.client.post('/api/ai/context',json={'mode':'explain','card_id':'missing'},headers={'Origin':self.settings.origin})
        self.assertEqual(result.status_code,409)

"""Synthetic acceptance: Google authority, viewer privacy and observed token categories."""
from dataclasses import replace
import httpx
import unittest
from sentinel.app import create_app
from sentinel.config import Settings
from sentinel.google_auth import GoogleAuth,sign_session,research_session,SESSION_COOKIE
from sentinel.members import invite,public_radar
from sentinel.storage import Store
from sentinel.catalogue import Catalogue
from sentinel.token_directory import browse

NOW=1800000000
class GoogleOwnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store=Store('sqlite:///:memory:')
        self.settings=Settings(environment='test',database_url='sqlite:///:memory:',session_secret='SYNTHETIC_SECRET_'*4,owner_email='owner@example.test',origin='https://owner.example.test',research_origin='https://research.example.test',supabase_auth_url='https://synthetic.supabase.co',supabase_publishable_key='SYNTHETIC_PUBLIC',google_owner_enabled=True,providers=(),access_aud='',access_team='')
        self.app=create_app(self.settings,self.store)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=self.settings.research_origin)
    async def asyncTearDown(self):await self.client.aclose();self.store.close()
    def session(self,email,role):self.client.cookies.set(SESSION_COOKIE,sign_session(self.settings.session_secret,email,'SYNTHETIC_GOOGLE_SUBJECT','test',role=role))
    async def test_exact_owner_google_session_can_use_controls_but_orders_still_require_exact_review(self):
        self.session('owner@example.test','owner')
        dashboard=await self.client.get('/api/dashboard')
        self.assertEqual(dashboard.status_code,200);self.assertEqual(dashboard.json()['role'],'owner');self.assertEqual(dashboard.json()['auth_method'],'supabase_google')
        self.assertEqual((await self.client.get('/api/connections')).status_code,200)
        self.assertEqual((await self.client.post('/api/control',json={'stopped':True},headers={'origin':self.settings.research_origin})).status_code,200)
        self.assertTrue(self.store.get_state('control')['stopped'])
        response=await self.client.post('/api/connections/kraken/approve',json={},headers={'origin':self.settings.research_origin})
        self.assertEqual(response.status_code,422);self.assertEqual(self.store.list('kraken_order',10),[])
        self.assertEqual((await self.client.post('/api/control',json={'stopped':False},headers={'origin':'https://attacker.example.test'})).status_code,403)
    async def test_signed_owner_role_for_another_email_does_not_grant_owner_or_viewer_access(self):
        invite(self.store,'friend@example.test',self.settings.owner_email);self.session('friend@example.test','owner')
        self.assertEqual((await self.client.get('/api/dashboard')).status_code,403)
        self.assertEqual((await self.client.get('/api/connections')).status_code,403)
    async def test_friend_google_session_cannot_mutate_from_either_allowed_hostname(self):
        invite(self.store,'friend@example.test',self.settings.owner_email);self.session('friend@example.test','viewer')
        self.assertEqual((await self.client.get('/api/tokens')).status_code,200)
        for origin in [self.settings.origin,self.settings.research_origin]:
            for path in ['/api/control','/api/connections/kraken/approve','/api/members']:
                self.assertEqual((await self.client.post(path,json={},headers={'origin':origin})).status_code,403)
        self.assertEqual((await self.client.get('/api/capital')).status_code,403)
    async def test_owner_email_requires_a_verified_google_identity_and_user_metadata_never_grants_authority(self):
        invite(self.store,'friend@example.test',self.settings.owner_email)
        for email,verified in [('owner@example.test',True),('owner@example.test',False),('friend@example.test',True)]:
            def handler(request):
                if request.url.path.endswith('/token'):return httpx.Response(200,json={'access_token':'SYNTHETIC_ACCESS','refresh_token':'SYNTHETIC_NOT_STORED'})
                return httpx.Response(200,json={'id':'SYNTHETIC_ID','email':email,'email_confirmed_at':'yes','user_metadata':{'role':'owner'},'identities':[{'provider':'google','identity_data':{'email':email,'email_verified':verified}}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as remote:
                auth=GoogleAuth(self.store,self.settings,remote);_,nonce=auth.start()
                if not verified:
                    with self.assertRaises(ValueError):await auth.finish('SYNTHETIC_CODE',nonce)
                else:
                    token=await auth.finish('SYNTHETIC_CODE',nonce);claims=research_session(token,self.settings.session_secret,'test')
                    self.assertEqual(claims['role'],'owner' if email==self.settings.owner_email else 'viewer')
        self.assertNotIn('SYNTHETIC_ACCESS',str(self.store.list('audit',100)))
    async def test_google_redirect_cookie_and_failure_callback_are_bound_and_do_not_leak_codes(self):
        response=await self.client.get('/api/auth/google/start')
        self.assertEqual(response.status_code,302);cookie=response.headers['set-cookie'].lower()
        for flag in ['httponly','secure','samesite=lax','path=/api/auth/google']:self.assertIn(flag,cookie)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'error':'SYNTHETIC invalid code'}))) as remote:
            self.app.state.google_auth.client=remote
            callback=await self.client.get('/api/auth/google/callback?code=SYNTHETIC_INVALID')
        self.assertEqual(callback.status_code,302);self.assertTrue(callback.headers['location'].endswith('/#google-signin-failed'))
        self.assertNotIn('SYNTHETIC_INVALID',callback.text)
    def test_public_radar_never_exposes_owner_sizing_or_risk_reasons(self):
        value=public_radar({'as_of':NOW,'setups':[{'id':'SYNTHETIC','symbol':'BTC-USD','provider':'kraken','decision':'GO','notional_usd':'PRIVATE_CASH','risk_inputs':{'cash':'PRIVATE_CASH'},'risk_reward':'PRIVATE_RISK','reasons':['PRIVATE_REASON'],'entry_trigger':'100','facts':['Observed price condition']} ]})
        self.assertNotIn('PRIVATE_',str(value));self.assertEqual(value['setups'][0]['decision'],'WAIT');self.assertIsNone(value['setups'][0]['notional_usd'])

class TokenDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.store=Store('sqlite:///:memory:');self.cat=Catalogue(self.store,('kraken','hyperliquid'))
        pairs=[('BTC','USD'),('BTC','EUR'),('ETH','USD'),('SOL','USD')]
        self.cat.kraken_instruments({'pairs':[{'base':base,'quote':quote,'symbol':base+'/'+quote,'status':'online'} for base,quote in pairs]},NOW,snapshot=True)
        self.cat.sessions['kraken']={'state':'connected','received_at':NOW}
        for symbol,change in [('BTC/USD','5'),('BTC/EUR','99'),('ETH/USD','10'),('SOL/USD','-8')]:self.cat.kraken_tick({'symbol':symbol,'bid':'100','ask':'101','timestamp':NOW,'change_pct':change},NOW)
    def tearDown(self):self.store.close()
    def test_main_directory_contains_one_usd_spot_token_entry_and_plain_names(self):
        value=browse(self.cat,{},now=NOW);self.assertEqual(value['total'],3)
        self.assertEqual({r['name'] for r in value['items']},{'Bitcoin','Ethereum','Solana'})
        self.assertTrue(all(r['currency']=='USD' and '/EUR' not in r['id'] and r['provider']=='kraken' for r in value['items']))
    def test_observed_performance_sorting_excludes_stale_data_and_is_not_a_prediction(self):
        self.assertEqual([r['name'] for r in browse(self.cat,{},section='best',now=NOW)['items']],['Ethereum','Bitcoin'])
        self.assertEqual(browse(self.cat,{},section='worst',now=NOW)['items'][0]['name'],'Solana')
        self.assertEqual(browse(self.cat,{},section='gainers',now=NOW+31)['items'],[])
        for section in ['predicted-best','predicted-worst']:
            value=browse(self.cat,{},section=section,now=NOW);self.assertEqual(value['items'],[]);self.assertEqual(value['status'],'unavailable')
    def test_new_tokens_use_explicit_source_flags_without_guessing_venue_identity(self):
        self.cat.set_coins([{'id':'synthetic-new','name':'SYNTHETIC New Token','symbol':'NEW','is_active':True,'is_new':True},{'id':'synthetic-old','name':'SYNTHETIC Old Token','symbol':'OLD','is_active':True,'is_new':False}],NOW)
        value=browse(self.cat,{},section='new',now=NOW)
        self.assertEqual(value['total'],1);self.assertEqual(value['items'][0]['id'],'coinpaprika:synthetic-new');self.assertIsNone(value['items'][0]['chart_symbol'])
        self.assertIsNone(value['items'][0]['quote']['price'])

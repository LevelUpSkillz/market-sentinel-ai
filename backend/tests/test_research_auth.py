"""Synthetic Google/PKCE and invitation boundaries; no external account or money."""
import asyncio
from dataclasses import replace
import hashlib
import httpx
import logging
import unittest
from urllib.parse import parse_qs,urlparse
from unittest.mock import patch
from sentinel.app import create_app
from sentinel.config import Settings
from sentinel.storage import Store
from sentinel.members import invite,revoke,active_member
from sentinel.google_auth import GoogleAuth,sign_session,research_session,SESSION_COOKIE
from sentinel.security import verify_session
from sentinel.backup import export_backup
from sentinel.log_safety import RedactAuthQuery

class ResearchAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store=Store('sqlite:///:memory:')
        self.settings=Settings(environment='test',database_url='sqlite:///:memory:',session_secret='SYNTHETIC_SESSION_SECRET_'*3,owner_email='owner@example.test',origin='https://owner.example.test',research_origin='https://research.example.test',supabase_auth_url='https://synthetic.supabase.co',supabase_publishable_key='SYNTHETIC_PUBLIC_KEY',access_aud='',access_team='',providers=())
        self.app=create_app(self.settings,self.store)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://research.example.test')
    async def asyncTearDown(self):await self.client.aclose();self.store.close()
    def viewer(self,email='friend@example.test'):
        self.client.cookies.set(SESSION_COOKIE,sign_session(self.settings.session_secret,email,'SYNTHETIC_GOOGLE_SUBJECT','test'))

    async def test_uninvited_forged_expired_and_revoked_sessions_cannot_get_research(self):
        self.viewer();self.assertEqual((await self.client.get('/api/dashboard')).status_code,403)
        invite(self.store,'friend@example.test',self.settings.owner_email)
        self.assertEqual((await self.client.get('/api/dashboard')).status_code,200)
        revoke(self.store,'friend@example.test')
        self.assertEqual((await self.client.get('/api/dashboard')).status_code,403)
        self.client.cookies.set(SESSION_COOKIE,'forged');self.assertEqual((await self.client.get('/api/dashboard')).status_code,401)
        self.client.cookies.set(SESSION_COOKIE,sign_session(self.settings.session_secret,'friend@example.test','test','test',now=1))
        self.assertEqual((await self.client.get('/api/dashboard')).status_code,401)

    async def test_viewer_sees_public_data_but_never_owner_money_history_controls_or_mutations(self):
        invite(self.store,'friend@example.test',self.settings.owner_email);self.viewer()
        self.store.set_state('account',{'cash':'PRIVATE_PAPER_CASH','initial_cash':'PRIVATE_INIT','realized_pnl':'PRIVATE_PNL'})
        # Dashboard redaction must not call calculations requiring owner account.
        self.store.set_state('connection:kraken',{'cipher':'PRIVATE_EXCHANGE_CIPHER'})
        response=await self.client.get('/api/dashboard');self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['role'],'viewer');self.assertIsNone(response.json()['account'])
        self.assertFalse(response.json()['live_trading'])
        for value in ('PRIVATE_PAPER_CASH','PRIVATE_INIT','PRIVATE_PNL','PRIVATE_EXCHANGE_CIPHER'):self.assertNotIn(value,response.text)
        self.assertEqual((await self.client.get('/api/assets')).status_code,200)
        for path in ['/api/connections','/api/connections/kraken/account','/api/connections/kraken/orders','/api/capital','/api/members','/api/records/audit','/api/records/paper','/api/records/real_plan','/api/opportunities/private']:
            self.assertEqual((await self.client.get(path)).status_code,403,path)
        for path in ['/api/control','/api/paper/open','/api/markets/watch','/api/traders','/api/backup/export','/api/members','/api/members/revoke','/api/connections/kraken/approve','/api/radar/test/paper']:
            response=await self.client.post(path,json={},headers={'origin':self.settings.origin})
            self.assertEqual(response.status_code,403,path)
        self.assertEqual(self.store.get_state('connection:kraken')['cipher'],'PRIVATE_EXCHANGE_CIPHER')

    async def test_owner_google_identity_still_mints_only_a_viewer_session(self):
        token=sign_session(self.settings.session_secret,self.settings.owner_email,'SYNTHETIC_OWNER_ID','test')
        self.assertFalse(verify_session(token,self.settings.session_secret,'test'))
        self.client.cookies.set(SESSION_COOKIE,token)
        self.assertEqual((await self.client.get('/api/dashboard')).json()['role'],'viewer')
        self.assertEqual((await self.client.get('/api/connections')).status_code,403)
        self.assertIsNone(research_session(token,self.settings.session_secret,'production'))
        self.assertIsNone(research_session(token+'x',self.settings.session_secret,'test'))

    async def test_pkce_is_bound_to_browser_single_use_and_verified_google_email(self):
        invite(self.store,'friend@example.test',self.settings.owner_email)
        sent=[]
        def provider(request):
            sent.append(request)
            if request.url.path.endswith('/token'):return httpx.Response(200,json={'access_token':'SYNTHETIC_GOOGLE_ACCESS_TOKEN','refresh_token':'SYNTHETIC_NEVER_STORED_REFRESH'})
            return httpx.Response(200,json={'id':'SYNTHETIC_GOOGLE_USER','email':'friend@example.test','email_confirmed_at':'2026-10-24T00:00:00Z','identities':[{'provider':'google'}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as provider_client:
            auth=GoogleAuth(self.store,self.settings,provider_client);url,nonce=auth.start()
            params=parse_qs(urlparse(url).query);self.assertEqual(params['provider'],['google'])
            self.assertEqual(params['redirect_to'],[self.settings.research_origin+'/api/auth/google/callback'])
            with self.assertRaises(ValueError):await auth.finish('SYNTHETIC_CODE','X'*43)
            token=await auth.finish('SYNTHETIC_CODE',nonce)
            self.assertEqual(research_session(token,self.settings.session_secret,'test')['email'],'friend@example.test')
            with self.assertRaises(ValueError):await auth.finish('SYNTHETIC_CODE',nonce)
            self.assertEqual(len(sent),2)
            import json,base64
            verifier=json.loads(sent[0].content)['code_verifier']
            self.assertEqual(params['code_challenge'][0],base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='))
            archive=export_backup(self.store).decode()
            self.assertNotIn('SYNTHETIC_GOOGLE_ACCESS_TOKEN',archive);self.assertNotIn('SYNTHETIC_NEVER_STORED_REFRESH',archive)
            self.assertNotIn('friend@example.test',archive)

    async def test_failed_identity_or_uninvited_callback_never_mints_a_session(self):
        for user in [{'id':'test','email':'unknown@example.test','email_confirmed_at':'yes','identities':[{'provider':'google'}]}, {'id':'test','email':'friend@example.test','email_confirmed_at':None,'identities':[{'provider':'google'}]}, {'id':'test','email':'friend@example.test','email_confirmed_at':'yes','identities':[{'provider':'email'}]}]:
            def provider(request):return httpx.Response(200,json={'access_token':'SYNTHETIC'} if request.url.path.endswith('/token') else user)
            async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as remote:
                auth=GoogleAuth(self.store,self.settings,remote);_,nonce=auth.start()
                with self.assertRaises(ValueError):await auth.finish('SYNTHETIC_CODE',nonce)

    async def test_backup_excludes_active_invites_and_pkce_material(self):
        invite(self.store,'friend@example.test',self.settings.owner_email)
        self.app.state.google_auth.start()
        archive=export_backup(self.store).decode()
        self.assertNotIn('friend@example.test',archive);self.assertNotIn('auth:member:',archive);self.assertNotIn('auth:oauth:',archive)

    async def test_owner_invitation_routes_cannot_grant_a_higher_role(self):
        with patch('sentinel.app.verify_session',return_value=True):
            bad=await self.client.post('/api/members',json={'email':'friend@example.test','role':'owner'},headers={'origin':self.settings.origin})
            self.assertEqual(bad.status_code,422)
            accepted=await self.client.post('/api/members',json={'email':'friend@example.test'},headers={'origin':self.settings.origin})
            self.assertEqual(accepted.status_code,200);self.assertEqual(accepted.json()['role'],'viewer')
            self.assertTrue(active_member(self.store,'friend@example.test'))

    def test_access_logger_removes_callback_query_without_changing_other_requests(self):
        record=logging.LogRecord('uvicorn.access',20,'',1,'%s %s %s %s %s',('client','GET','/api/auth/google/callback?code=SYNTHETIC_SECRET','1.1',302),None)
        RedactAuthQuery().filter(record);self.assertNotIn('SYNTHETIC_SECRET',record.getMessage())

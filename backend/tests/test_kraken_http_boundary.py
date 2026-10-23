"""Kraken HTTP boundary regression checks; no provider calls or live orders."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import httpx

from sentinel.app import create_app
from sentinel.storage import Store


class KrakenHttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store('sqlite:///:memory:')
        self.settings = SimpleNamespace(
            environment='test',database_url='sqlite:///:memory:',origin='https://example.test',
            session_secret='x'*48,password_hash='',access_team='',access_aud='',owner_email='',
            kraken_vault_key='',kraken_live_enabled=False,collect=False,providers=(),
            changenow_key='',changenow_approved=False,ntfy_topic='',ntfy_token='',
            hosting_tier='local',database_expiry='',validate=lambda:None)
        self.app=create_app(self.settings,self.store)

    def tearDown(self):
        self.store.close()

    def test_unauthenticated_kraken_routes_reject_requests(self):
        async def check():
            transport=httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport,base_url='https://example.test') as client:
                for method,path in [
                    ('GET','/api/connections'),('GET','/api/connections/kraken/account'),
                    ('POST','/api/connections/kraken'),('POST','/api/connections/kraken/disconnect'),
                    ('POST','/api/connections/kraken/preview'),('POST','/api/connections/kraken/approve'),
                    ('POST','/api/connections/kraken/reconcile')]:
                    with self.subTest(path=path):
                        response=await client.request(method,path,headers={'origin':self.settings.origin},json={} if method=='POST' else None)
                        self.assertEqual(response.status_code,401)
        asyncio.run(check())

    def test_authenticated_routes_are_wired_and_credentials_are_not_echoed(self):
        async def check():
            transport=httpx.ASGITransport(app=self.app)
            with patch('sentinel.app.verify_session',return_value=True):
                async with httpx.AsyncClient(transport=transport,base_url='https://example.test') as client:
                    status=await client.get('/api/connections')
                    self.assertEqual(status.status_code,200)
                    self.assertFalse(status.json()['order_submission_enabled'])
                    self.assertFalse(status.json()['credential_entry_enabled'])
                    self.assertNotIn('cipher',status.text)
                    # An invalid request must not expose submitted secret fields.
                    secret='DO_NOT_ECHO_THIS_TEST_SECRET'
                    invalid=await client.post('/api/connections/kraken',
                        headers={'origin':self.settings.origin},
                        json={'api_key':secret,'api_secret':secret,'country_code':'invalid'})
                    self.assertEqual(invalid.status_code,422)
                    self.assertNotIn(secret,invalid.text)
                    preview=await client.post('/api/connections/kraken/preview',
                        headers={'origin':self.settings.origin},
                        json={'symbol':'BTC-USD','side':'buy','quantity':'0.01','limit_price':'50000'})
                    self.assertEqual(preview.status_code,409)
                    self.assertIn('disabled',preview.text.lower())
        asyncio.run(check())

    def test_backup_download_requires_owner_and_excludes_exchange_credentials(self):
        async def check():
            transport=httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport,base_url='https://example.test') as client:
                denied=await client.post('/api/backup/export',headers={'origin':self.settings.origin})
                self.assertEqual(denied.status_code,401)
                with patch('sentinel.app.verify_session',return_value=True):
                    response=await client.post('/api/backup/export',headers={'origin':self.settings.origin})
                    self.assertEqual(response.status_code,200)
                    self.assertIn('attachment;',response.headers['content-disposition'])
                    self.assertEqual(response.headers['cache-control'],'no-store')
                    self.assertNotIn('connection:kraken',response.text)
                    self.assertNotIn('kraken_nonce:',response.text)
                    self.assertEqual(response.json()['format'],'market-sentinel-logical-backup')
        asyncio.run(check())

    def test_live_trading_defaults_off_and_no_credentials_in_status(self):
        self.assertFalse(self.app.state.kraken_account.enabled)
        status=self.app.state.kraken_account.status()
        self.assertFalse(status['order_submission_enabled'])
        self.assertFalse(status['credential_entry_enabled'])
        self.assertNotIn('cipher',str(status))


if __name__=='__main__':
    unittest.main()

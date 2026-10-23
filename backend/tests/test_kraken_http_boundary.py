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

    def test_live_trading_defaults_off_and_no_credentials_in_status(self):
        self.assertFalse(self.app.state.kraken_account.enabled)
        status=self.app.state.kraken_account.status()
        self.assertFalse(status['order_submission_enabled'])
        self.assertFalse(status['credential_entry_enabled'])
        self.assertNotIn('cipher',str(status))


if __name__=='__main__':
    unittest.main()

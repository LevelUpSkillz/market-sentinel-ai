"""SYNTHETIC ASGI integration: authenticated planning, no exchange or real order."""
from copy import deepcopy
from decimal import Decimal as D
import time
import unittest
from unittest.mock import patch
import httpx
from sentinel.app import create_app
from sentinel.config import Settings
from sentinel.models import Book
from sentinel.security import session_token
from sentinel.storage import Store


def profile():
    return {'capital_usd':'10000','available_cash_usd':'10000','existing_crypto_exposure_usd':'0',
        'daily_realized_pnl_usd':'0','risk_per_trade_pct':'0.5','max_position_pct':'10',
        'max_crypto_exposure_pct':'25','daily_loss_limit_pct':'2'}


class RadarApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = Store('sqlite:///:memory:')
        self.settings = Settings(environment='test',database_url='sqlite:///:memory:',
            session_secret='SYNTHETIC_TEST_SESSION_SECRET'*3,origin='https://testserver',collect=False,
            providers=('kraken',))
        self.app = create_app(self.settings,self.store)
        self.runtime = self.app.state.runtime
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=self.settings.origin)
        self.headers = {'Origin':self.settings.origin}

    async def asyncTearDown(self):
        await self.client.aclose()
        self.store.close()

    def authenticate(self):
        self.client.cookies.set('sentinel_session',session_token(self.settings.session_secret,'test'))

    def live_book(self,age=0):
        now=time.time()-age
        b=Book('kraken','SYNTHETIC-USD')
        b.update([('99','1000')],[('100','1000')],now,now,snapshot=True)
        self.runtime.books[('kraken','SYNTHETIC-USD')]=b
        return b

    def radar_view(self,decision='GO'):
        return {'strategy_version':'SYNTHETIC_TEST_RADAR','mode':'paper_only',
            'setups':[{'id':'SYNTHETIC-SIGNAL','provider':'kraken','symbol':'SYNTHETIC-USD',
                'decision':decision,'notional_usd':'250','state':'paper_ready' if decision=='GO' else 'expired'}]}

    async def test_radar_capital_and_connection_endpoints_require_owner_authentication(self):
        for path in ['/api/radar','/api/capital','/api/connections']:
            with self.subTest(path=path):self.assertEqual((await self.client.get(path)).status_code,401)
        response=await self.client.post('/api/capital',json=profile(),headers=self.headers)
        self.assertEqual(response.status_code,401)
        self.assertIsNone(self.store.get_state('real_capital_profile'))
        self.assertEqual((await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={},headers=self.headers)).status_code,401)

    async def test_saved_real_profile_does_not_change_paper_cash_and_forbids_credentials(self):
        self.authenticate()
        initial=deepcopy(self.store.get_state('account'))
        self.assertEqual((await self.client.post('/api/capital',json=profile())).status_code,403)
        response=await self.client.post('/api/capital',json=profile(),headers=self.headers)
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(data['profile']['capital_usd'],'10000')
        self.assertEqual(data['profile']['source'],'USER_DECLARED_UNVERIFIED')
        self.assertFalse(data['execution_enabled'])
        self.assertEqual((await self.client.get('/api/capital')).json()['profile'],data['profile'])
        self.assertEqual(self.store.get_state('account'),initial)
        self.assertEqual(self.store.list('paper'),[])
        response=await self.client.post('/api/capital',json=dict(profile(),exchange_private_key='SYNTHETIC_TEST_ONLY'),headers=self.headers)
        self.assertEqual(response.status_code,422)
        self.assertNotIn('exchange_private_key',self.store.get_state('real_capital_profile'))

    async def test_fresh_real_plan_returns_risk_math_but_never_trade_approval(self):
        self.authenticate()
        await self.client.post('/api/capital',json=profile(),headers=self.headers)
        initial=deepcopy(self.store.get_state('account'))
        self.live_book()
        response=await self.client.post('/api/capital/plans',json={'provider':'kraken','symbol':'SYNTHETIC-USD','stop':'98','target':'110'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(data['risk_decision'],'PASS')
        self.assertEqual(data['trade_decision'],'WAIT')
        self.assertFalse(data['execution_enabled'])
        self.assertFalse(data['connection']['connected'])
        self.assertEqual(data['validation_status'],'unvalidated')
        self.assertIsNone(data['success_probability_pct'])
        self.assertGreater(D(data['quantity']),0)
        self.assertLessEqual(D(data['modeled_loss_usd']),D(data['risk_budget_usd']))
        self.assertEqual(self.store.get_state('account'),initial)
        self.assertEqual(self.store.list('paper'),[])
        self.assertEqual(len(self.store.list('real_plan')),1)

    async def test_missing_detailed_book_and_perpetual_requests_cannot_substitute_prices(self):
        self.authenticate()
        await self.client.post('/api/capital',json=profile(),headers=self.headers)
        request={'provider':'kraken','symbol':'SYNTHETIC-USD','stop':'98','target':'110'}
        self.assertEqual((await self.client.post('/api/capital/plans',json=request,headers=self.headers)).status_code,409)
        response=await self.client.post('/api/capital/plans',json=dict(request,provider='hyperliquid',symbol='SYNTHETIC-USDC-PERP'),headers=self.headers)
        self.assertEqual(response.status_code,422)
        b=self.live_book();b.instrument='perpetual';b.quote='USDC'
        data=(await self.client.post('/api/capital/plans',json=request,headers=self.headers)).json()
        self.assertEqual(data['risk_decision'],'FAIL')
        self.assertIsNone(data['quantity'])
        self.assertEqual(self.store.list('paper'),[])

    async def test_kraken_preference_is_not_a_connected_account_or_order_permission(self):
        self.authenticate()
        data=(await self.client.get('/api/connections')).json()
        self.assertEqual(data['provider'],'kraken')
        self.assertFalse(data['connected'])
        self.assertFalse(data['order_submission_enabled'])
        self.assertFalse(data['withdrawals_enabled'])
        self.assertEqual(data['app_hosting_plan'],'free')
        for path in ['/api/orders','/api/withdrawals','/api/connections/kraken/orders']:
            self.assertEqual((await self.client.post(path,json={},headers=self.headers)).status_code,405 if path=='/api/connections/kraken/orders' else 404)

    async def test_stale_or_rejected_radar_snapshot_cannot_create_a_paper_entry(self):
        self.authenticate()
        self.live_book()
        initial=deepcopy(self.store.get_state('account'))
        for decision in ['WAIT','NO-GO']:
            with patch.object(self.runtime.radar,'snapshot',return_value=self.radar_view(decision)):
                response=await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={'decision':'GO'},headers=self.headers)
            self.assertEqual(response.status_code,409)
        self.assertEqual(self.store.get_state('account'),initial)
        self.assertEqual(self.store.list('paper'),[])

    async def test_a_client_visible_go_is_rechecked_again_on_paper_submission(self):
        self.authenticate()
        self.live_book()
        with patch.object(self.runtime.radar,'snapshot',side_effect=[self.radar_view('GO'),self.radar_view('NO-GO')]) as snapshot:
            self.assertEqual((await self.client.get('/api/radar')).json()['setups'][0]['decision'],'GO')
            response=await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={},headers=self.headers)
        self.assertEqual(snapshot.call_count,2)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.store.list('paper'),[])

    async def test_fresh_eligible_paper_entry_is_idempotent_and_only_changes_virtual_cash(self):
        self.authenticate()
        self.live_book()
        await self.client.post('/api/capital',json=profile(),headers=self.headers)
        real_profile=deepcopy(self.store.get_state('real_capital_profile'))
        with patch.object(self.runtime.radar,'snapshot',return_value=self.radar_view()) as snapshot:
            first=await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={},headers=self.headers)
            self.assertEqual(first.status_code,200)
            cash=self.store.get_state('account')['cash']
            self.live_book(age=10)
            snapshot.return_value=self.radar_view('NO-GO')
            second=await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={},headers=self.headers)
            self.assertEqual(snapshot.call_count,1)
        self.assertEqual(second.status_code,200)
        self.assertEqual(first.json()['id'],second.json()['id'])
        self.assertEqual(first.json()['mode'],'SIMULATED PAPER TRADE')
        self.assertEqual(first.json()['origin_signal_id'],'SYNTHETIC-SIGNAL')
        self.assertEqual(self.store.get_state('account')['cash'],cash)
        self.assertLess(D(cash),10000)
        self.assertEqual(self.store.get_state('real_capital_profile'),real_profile)
        self.assertEqual(len(self.store.list('paper')),1)

    async def test_current_book_and_portfolio_controls_are_rechecked_after_radar_go(self):
        self.authenticate()
        initial=deepcopy(self.store.get_state('account'))
        self.live_book(age=10)
        with patch.object(self.runtime.radar,'snapshot',return_value=self.radar_view()):
            response=await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={},headers=self.headers)
        self.assertIn(response.status_code,[409,422])
        self.assertEqual(self.store.list('paper'),[])
        self.assertEqual(self.store.get_state('account'),initial)
        self.live_book()
        self.store.set_state('control',{'stopped':True})
        with patch.object(self.runtime.radar,'snapshot',return_value=self.radar_view()):
            response=await self.client.post('/api/radar/SYNTHETIC-SIGNAL/paper',json={},headers=self.headers)
        self.assertIn(response.status_code,[409,422])
        self.assertEqual(self.store.list('paper'),[])
        self.assertEqual(self.store.get_state('account'),initial)

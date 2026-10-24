"""Synthetic timing regressions: final locked approval is the send boundary."""
from unittest.mock import patch
import unittest
import test_kraken_account as fixtures
from sentinel.capital import save_profile
from sentinel.kraken_account import AccountError,SerializedClient


class FinalApprovalTests(unittest.IsolatedAsyncioTestCase):
    setUp=fixtures.KrakenAccountTests.setUp
    tearDown=fixtures.KrakenAccountTests.tearDown
    refresh_book=fixtures.KrakenAccountTests.refresh_book
    connect=fixtures.KrakenAccountTests.connect
    preview=fixtures.KrakenAccountTests.preview

    async def test_profile_change_during_provider_checks_cannot_reuse_approval(self):
        await self.connect();review=await self.preview()
        original=type(self.account._client()[2].client).fees
        async def change_profile(client,pair):
            self.now+=1;self.refresh_book()
            save_profile(self.store,fixtures.profile(risk_per_trade_pct='1.9'),self.now)
            return await original(client,pair)
        with patch.object(type(self.account._client()[2].client),'fees',change_profile):
            with self.assertRaisesRegex(AccountError,'profile'):
                await self.account.approve(review['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])
        self.assertIsNone(self.store.get_state('kraken_live_active'))

    async def test_expiry_while_waiting_for_signed_request_lock_sends_nothing(self):
        await self.connect();review=await self.preview()
        original=SerializedClient.submit_guarded
        async def delayed(client,order,guard):
            self.now+=31;self.refresh_book()
            return await original(client,order,guard)
        with patch.object(SerializedClient,'submit_guarded',delayed):
            with self.assertRaisesRegex(AccountError,'expired'):
                await self.account.approve(review['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])
        self.assertIsNone(self.store.get_state('kraken_live_active'))

    async def test_emergency_stop_while_waiting_for_send_lock_cancels_approval(self):
        await self.connect();review=await self.preview()
        original=SerializedClient.submit_guarded
        async def stop(client,order,guard):
            self.store.set_state('control',{'stopped':True})
            return await original(client,order,guard)
        with patch.object(SerializedClient,'submit_guarded',stop):
            with self.assertRaises(AccountError):
                await self.account.approve(review['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])
        self.assertIsNone(self.store.get_state('kraken_live_active'))

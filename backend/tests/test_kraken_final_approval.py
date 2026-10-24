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

    async def test_unresolved_restore_can_reconnect_original_key_only_for_reconciliation(self):
        from sentinel.backup import export_backup,restore_backup
        from sentinel.kraken_account import KrakenAccount
        from sentinel.kraken import KrakenError
        from sentinel.storage import Store
        await self.connect();review=await self.preview()
        self.state.submit_error=KrakenError('unknown','SYNTHETIC uncertain response',uncertain=True)
        self.assertEqual((await self.account.approve(review['id'],'PLACE THIS REAL ORDER'))['status'],'unknown')
        blob=export_backup(self.store,now=self.now)
        self.assertNotIn(fixtures.API_KEY.encode(),blob)
        self.assertNotIn(fixtures.API_SECRET.encode(),blob)
        destination=Store('sqlite:///:memory:')
        try:
            restore_backup(destination,blob,environment='test',offline=True,confirm_empty=True,now=self.now+1)
            restored=KrakenAccount(destination,self.settings,self.books,lambda key,secret,nonce:fixtures.FakeKraken(self.state,key,secret,nonce))
            args=dict(api_key=fixtures.API_KEY,api_secret=fixtures.API_SECRET,country_code='US',region='SYNTHETIC REGION',eligibility_confirmed=True,dedicated_key_confirmed=True)
            with self.assertRaises(AccountError):await restored.connect(**dict(args,api_key=fixtures.OTHER_KEY))
            await restored.connect(**args)
            self.state.reconciled={'orders':{'SYNTHETIC_ID':{'status':'closed'}},'complete':True}
            self.assertEqual((await restored.reconcile(review['id']))['status'],'resolved')
            self.assertTrue(destination.get('real_order',review['id'])['restored_execution_disabled'])
            self.assertEqual(len(self.state.submitted),1)
        finally:destination.close()

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

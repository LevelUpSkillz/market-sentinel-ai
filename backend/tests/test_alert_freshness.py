"""Synthetic queue recovery: an earlier GO cannot authorize a delayed push."""
import asyncio
import time
import unittest
from unittest.mock import AsyncMock,patch
from sentinel.config import Settings
from sentinel.runtime import Runtime
from sentinel.storage import Store


class AlertFreshnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_queued_and_retried_radar_alerts_recheck_current_market_and_risk(self):
        for decision in ['WAIT','NO-GO',None]:
            for attempts in [0,2]:
                with self.subTest(decision=decision,attempts=attempts):
                    store=Store('sqlite:///:memory:')
                    try:
                        runtime=Runtime(store,Settings(ntfy_topic='SYNTHETIC_PRIVATE_TOPIC_123',collect=False))
                        alert=store.put('alert',{'title':'SYNTHETIC TEST','status':'queued','attempts':attempts,
                            'signal_id':'SYNTHETIC_RADAR','expires_at':time.time()+30})
                        setups=[{'id':'SYNTHETIC_RADAR','decision':decision}] if decision else []
                        with patch.object(runtime.radar,'snapshot',return_value={'setups':setups}) as snapshot, \
                             patch('sentinel.runtime.httpx.AsyncClient') as client, \
                             patch('sentinel.runtime.asyncio.sleep',new=AsyncMock(side_effect=asyncio.CancelledError)):
                            with self.assertRaises(asyncio.CancelledError):await runtime.alert_delivery()
                        snapshot.assert_called_once_with(runtime.books)
                        client.assert_not_called()
                        saved=store.get('alert',alert['id'])
                        self.assertEqual(saved['status'],'invalidated')
                        self.assertNotIn('delivered_at',saved)
                    finally:store.close()

    async def test_expired_alert_never_contacts_provider_or_revives_a_signal(self):
        store=Store('sqlite:///:memory:')
        try:
            runtime=Runtime(store,Settings(ntfy_topic='SYNTHETIC_PRIVATE_TOPIC_123',collect=False))
            alert=store.put('alert',{'title':'SYNTHETIC TEST','status':'queued','signal_id':'SYNTHETIC_RADAR',
                'expires_at':time.time()-1})
            with patch.object(runtime.radar,'snapshot') as snapshot, \
                 patch('sentinel.runtime.httpx.AsyncClient') as client, \
                 patch('sentinel.runtime.asyncio.sleep',new=AsyncMock(side_effect=asyncio.CancelledError)):
                with self.assertRaises(asyncio.CancelledError):await runtime.alert_delivery()
            snapshot.assert_not_called();client.assert_not_called()
            self.assertEqual(store.get('alert',alert['id'])['status'],'expired')
        finally:store.close()

"""Synthetic failure recovery; no provider connections or dashboard requests."""
import asyncio
import time
import unittest
from unittest.mock import patch
from sentinel.config import Settings
from sentinel.runtime import Runtime
from sentinel.storage import Store


class RateWindowTests(unittest.TestCase):
    def test_short_window_requests_do_not_reset_login_limit(self):
        store = Store('sqlite:///:memory:')
        try:
            with patch('sentinel.storage.time.time',return_value=1800000000):
                for i in range(5):
                    self.assertTrue(store.rate('login:SYNTHETIC',5,900))
                    self.assertTrue(store.rate('api:SYNTHETIC',180,60))
                self.assertFalse(store.rate('login:SYNTHETIC',5,900))
            with patch('sentinel.storage.time.time',return_value=1800000900):
                self.assertTrue(store.rate('login:SYNTHETIC',5,900))
        finally:store.close()


class SupervisionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = Store('sqlite:///:memory:')

    def tearDown(self):
        self.store.close()

    async def test_new_instance_stands_by_then_takes_collector_lock(self):
        runtime = Runtime(self.store, Settings(collect=True, providers=()))
        started = []
        acquired = iter([False, True])
        release = []
        ticks = []
        original_sleep = asyncio.sleep

        async def job(name):
            started.append(name)
            await asyncio.Event().wait()

        async def step(delay):
            ticks.append(runtime.collector_state)
            if len(ticks)==1:
                self.assertEqual(runtime.collector_state, 'standby')
                self.assertTrue(runtime.healthy())
            else:
                await original_sleep(0)
                self.assertEqual(runtime.collector_state, 'active')
                self.assertCountEqual(started, ['journal', 'alerts'])
                raise asyncio.CancelledError()

        with patch.object(self.store,'try_acquire_collector',lambda:next(acquired)), \
             patch.object(self.store,'release_collector',lambda:release.append(True)), \
             patch.object(runtime,'journal',lambda:job('journal')), \
             patch.object(runtime,'alert_delivery',lambda:job('alerts')), \
             patch('sentinel.runtime.asyncio.sleep',step):
            with self.assertRaises(asyncio.CancelledError):
                await runtime.coordinate()
        self.assertEqual(ticks, ['standby','active'])
        self.assertEqual(release, [True])
        self.assertEqual(runtime.collector_state, 'stopped')
        self.assertTrue(all(v['state']=='stopped' for v in runtime.job_status.values()))

    async def test_failed_background_job_restarts_without_dashboard(self):
        runtime = Runtime(self.store, Settings())
        recovered = asyncio.Event()
        attempts = []
        original_sleep = asyncio.sleep

        async def job():
            attempts.append(True)
            if len(attempts)==1:
                raise ConnectionError('SYNTHETIC failure')
            recovered.set()
            await asyncio.Event().wait()

        async def backoff(delay):
            self.assertEqual(runtime.job_status['test']['state'],'restarting')
            await original_sleep(0)

        with patch('sentinel.runtime.asyncio.sleep',backoff),patch('sentinel.runtime.log.exception'):
            task = asyncio.create_task(runtime.supervise('test',job))
            await asyncio.wait_for(recovered.wait(),timeout=2)
            self.assertEqual(len(attempts),2)
            self.assertEqual(runtime.job_status['test']['state'],'running')
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(runtime.job_status['test']['state'],'stopped')

    async def test_heartbeat_without_book_updates_forces_reconnect(self):
        runtime = Runtime(self.store, Settings())
        connections = []

        class Socket:
            async def send(self,message):pass
            async def recv(self):return '{"type":"heartbeat"}'

        class Context:
            async def __aenter__(self):
                connections.append(True)
                if len(connections)>1:raise asyncio.CancelledError()
                return Socket()
            async def __aexit__(self,*args):return False

        async def backoff(delay):
            self.assertEqual(runtime.status['coinbase']['reason'],'TimeoutError')

        with patch('sentinel.runtime.BOOK_STALL_SECONDS',0), \
             patch('sentinel.runtime.connect',lambda *a,**k:Context()), \
             patch('sentinel.runtime.asyncio.sleep',backoff):
            with self.assertRaises(asyncio.CancelledError):await runtime.stream('coinbase')
        self.assertEqual(len(connections),2)
        self.assertEqual(runtime.status['coinbase']['reconnects'],1)

    async def test_readiness_rejects_failed_or_stalled_collector(self):
        runtime = Runtime(self.store, Settings(collect=True))
        self.assertFalse(runtime.healthy())
        runtime.coordinator_heartbeat = time.monotonic()
        runtime.collector_state = 'active'
        runtime.last_persist = time.time()
        self.assertTrue(runtime.healthy())
        runtime.last_persist -= 100
        self.assertFalse(runtime.healthy())
        runtime.collector_state = 'standby'
        self.assertTrue(runtime.healthy())
        runtime.collector_state = 'failed'
        self.assertFalse(runtime.healthy())
        runtime.coordinator_heartbeat -= 30
        runtime.collector_state = 'standby'
        self.assertFalse(runtime.healthy())

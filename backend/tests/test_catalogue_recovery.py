"""Synthetic regression checks for extra-book isolation and collector handoff."""
import asyncio
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from sentinel.config import Settings
from sentinel.models import Book
from sentinel.providers import Kraken
from sentinel.runtime import Runtime
from sentinel.storage import Store


class CatalogueRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_quiet_extra_book_does_not_reconnect_healthy_core_stream(self):
        store = Store('sqlite:///:memory:')
        runtime = Runtime(store,Settings(collect=False,providers=('kraken',)))
        anchor = time.time()
        clock = [0]
        symbols = ['BTC','ETH','SOL','XRP']
        runtime.catalogue.kraken_instruments({'pairs':[{'base':coin,'quote':'USD','symbol':coin+'/USD','status':'online'} for coin in symbols]},anchor,True)
        runtime.set_market_watch('kraken:XRP/USD',True)
        connections,observations = [],[]
        check = self

        def snapshot(coins):
            rows = []
            for coin in coins:
                book = Book('kraken',coin+'-USD')
                book.update([('99','2')],[('101','2')],anchor+clock[0],anchor+clock[0],snapshot=True)
                rows.append({'symbol':coin+'/USD','timestamp':anchor+clock[0],
                    'bids':[{'price':99,'qty':2}],'asks':[{'price':101,'qty':2}],
                    'checksum':Kraken.checksum(book)})
            return json.dumps({'channel':'book','type':'snapshot','data':rows})

        class Socket:
            def __init__(self):self.cursor=0
            async def send(self,payload):pass
            async def recv(self):
                self.cursor += 1
                if self.cursor==1:return snapshot(symbols)
                if self.cursor==2:
                    clock[0] = 91
                    return snapshot(symbols[:3])
                # Assert before cancellation: stopping a collector intentionally
                # invalidates its books, independently of the watchdog behavior.
                check.assertEqual(runtime.status['kraken']['reconnects'],0)
                for coin in symbols[:3]:
                    book = runtime.books[('kraken',coin+'-USD')]
                    check.assertTrue(book.valid)
                    check.assertTrue(book.fresh(anchor+91))
                    check.assertEqual(book.integrity,'crc32_verified')
                quiet = runtime.books[('kraken','XRP-USD')]
                check.assertEqual(quiet.source_at,anchor)
                check.assertFalse(quiet.fresh(anchor+91))
                observations.append('healthy core; stale extra')
                raise asyncio.CancelledError()

        class Context:
            async def __aenter__(self):
                connections.append(True)
                check.assertEqual(len(connections),1,'A quiet extra must not restart the shared stream')
                return Socket()
            async def __aexit__(self,*args):return False

        async def no_backoff(delay):
            self.fail('A quiet extra book incorrectly forced provider reconnection')

        fake_time = SimpleNamespace(time=lambda:anchor+clock[0],monotonic=lambda:clock[0])
        try:
            with patch('sentinel.runtime.time',fake_time),patch('sentinel.runtime.connect',return_value=Context()),patch('sentinel.runtime.asyncio.sleep',no_backoff):
                with self.assertRaises(asyncio.CancelledError):await runtime.stream('kraken')
            self.assertEqual(observations,['healthy core; stale extra'])
            self.assertEqual(len(connections),1)
        finally:store.close()

    async def test_collector_handoff_reloads_selection_changed_while_standing_by(self):
        store = Store('sqlite:///:memory:')
        old = [{'id':'kraken:DOGE/USD','provider':'kraken','symbol':'DOGE-USD'}]
        latest = [{'id':'kraken:XRP/USD','provider':'kraken','symbol':'XRP-USD'}]
        store.set_state('market_watch',old)
        runtime = Runtime(store,Settings(collect=True,providers=()))
        self.assertEqual(runtime.live_watch,old)
        ticks,observed,released = [],[],[]
        acquired = iter([False,True])
        original_sleep = asyncio.sleep

        async def journal():
            observed.append(list(runtime.live_watch))
            await asyncio.Event().wait()

        async def alerts():await asyncio.Event().wait()

        async def step(delay):
            ticks.append(runtime.collector_state)
            if len(ticks)==1:
                self.assertEqual(runtime.collector_state,'standby')
                # The old serving instance persists a new selection while this
                # replacement is waiting for the PostgreSQL collector lock.
                store.set_state('market_watch',latest)
            else:
                await original_sleep(0)
                self.assertEqual(runtime.collector_state,'active')
                self.assertEqual(runtime.live_watch,latest)
                self.assertEqual(observed,[latest])
                raise asyncio.CancelledError()

        try:
            with patch.object(store,'try_acquire_collector',lambda:next(acquired)),patch.object(store,'release_collector',lambda:released.append(True)),patch.object(runtime,'journal',journal),patch.object(runtime,'alert_delivery',alerts),patch('sentinel.runtime.asyncio.sleep',step):
                with self.assertRaises(asyncio.CancelledError):await runtime.coordinate()
            self.assertEqual(ticks,['standby','active'])
            self.assertEqual(released,[True])
        finally:store.close()

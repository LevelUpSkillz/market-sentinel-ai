"""Actual disposable PostgreSQL nonce and overlapping-instance lock tests."""
import asyncio
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
from sentinel.kraken_account import KrakenAccount,AccountError
from sentinel.storage import Store


@unittest.skipUnless(os.getenv('TEST_POSTGRES_URL'),'Separate test PostgreSQL required')
class KrakenPostgresTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from psycopg.conninfo import conninfo_to_dict
        url=os.environ['TEST_POSTGRES_URL']
        if not conninfo_to_dict(url).get('dbname','').startswith('test_'):raise RuntimeError('Disposable test database required')
        self.first,self.second=Store(url),Store(url)
        self.schema='test_kraken_'+uuid.uuid4().hex
        self.first.execute('CREATE SCHEMA '+self.schema)
        for store in (self.first,self.second):store.execute('SET search_path TO '+self.schema+',public')
        for table in ('schema_version','state','records','rate_limits'):
            self.first.execute('CREATE TABLE '+self.schema+'.'+table+' (LIKE public.'+table+' INCLUDING ALL)')

    def tearDown(self):
        self.first.execute('DROP SCHEMA '+self.schema+' CASCADE')
        self.first.close();self.second.close()

    async def test_nonce_persists_across_process_connections_and_clock_stall(self):
        settings=SimpleNamespace(kraken_vault_key='',kraken_live_enabled=False)
        one,two=KrakenAccount(self.first,settings,{}),KrakenAccount(self.second,settings,{})
        with patch('sentinel.kraken_account.time.time_ns',return_value=1000000):
            first=one._nonce('SYNTHETIC_KEY')
            second=two._nonce('SYNTHETIC_KEY')
            restarted=KrakenAccount(self.first,settings,{})
            third=restarted._nonce('SYNTHETIC_KEY')
        self.assertEqual([second,third],[first+1,first+2])

    async def test_key_lock_excludes_an_overlapping_instance_until_request_finishes(self):
        entered,release=asyncio.Event(),asyncio.Event()
        class Client:
            async def read(self):
                entered.set();await release.wait();return 'SYNTHETIC_READ'
        settings=SimpleNamespace(kraken_vault_key='',kraken_live_enabled=False)
        factory=lambda *args:Client()
        one=KrakenAccount(self.first,settings,{},factory)._new_client('SYNTHETIC_KEY','SYNTHETIC_SECRET')
        two=KrakenAccount(self.second,settings,{},factory)._new_client('SYNTHETIC_KEY','SYNTHETIC_SECRET')
        task=asyncio.create_task(one.read())
        try:
            await asyncio.wait_for(entered.wait(),2)
            with self.assertRaisesRegex(AccountError,'Another account request'):await two.read()
        finally:
            release.set();await task
        self.assertEqual(await two.read(),'SYNTHETIC_READ')

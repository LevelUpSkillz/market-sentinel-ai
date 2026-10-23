"""Real PostgreSQL integration checks run in CI with a dedicated disposable database."""
import os
import unittest
import uuid
from sentinel.storage import Store
from sentinel.models import Book
from sentinel.engine import paper_open,paper_close

@unittest.skipUnless(os.getenv('TEST_POSTGRES_URL'),'Dedicated TEST_POSTGRES_URL is not configured')
class PostgresTests(unittest.TestCase):
    def setUp(self):self.store=Store(os.environ['TEST_POSTGRES_URL'])
    def tearDown(self):self.store.close()
    def test_transactional_journal(self):
        doc=self.store.put('integration_test',{'marker':str(uuid.uuid4())})
        self.assertEqual(self.store.get('integration_test',doc['id']),doc)
    def test_rollback(self):
        key='ci:'+str(uuid.uuid4())
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.store.set_state(key,{'value':1})
                raise RuntimeError('synthetic failure')
        self.assertIsNone(self.store.get_state(key))
    def test_single_collector_lock(self):
        self.store.acquire_collector()
        second=Store(os.environ['TEST_POSTGRES_URL'])
        try:
            with self.assertRaises(RuntimeError):second.acquire_collector()
        finally:second.close()

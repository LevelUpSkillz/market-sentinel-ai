"""Small transactional document journal; SQLite is explicitly development/test only."""
from contextlib import contextmanager
from threading import RLock
import json
import sqlite3
import time
import uuid

class Store:
    def __init__(self, url):
        self.lock = RLock()
        self.postgres = url.startswith(('postgres://', 'postgresql://'))
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(url, autocommit=True, row_factory=dict_row,
                                        connect_timeout=10, options='-c statement_timeout=4000 -c lock_timeout=3000')
        else:
            self.conn = sqlite3.connect(url.removeprefix('sqlite:///'), check_same_thread=False, isolation_level=None)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute('PRAGMA journal_mode=WAL')
            self.conn.execute('PRAGMA busy_timeout=5000')
        with self.transaction():
            self.execute('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)')
            self.execute('INSERT INTO schema_version(version) VALUES (1) ON CONFLICT DO NOTHING')
            self.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, at DOUBLE PRECISION NOT NULL, search TEXT NOT NULL, data TEXT NOT NULL)')
            self.execute('CREATE INDEX IF NOT EXISTS records_kind_at ON records(kind, at)')
            self.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, data TEXT NOT NULL)')
            self.execute('CREATE TABLE IF NOT EXISTS rate_limits (key TEXT PRIMARY KEY, bucket BIGINT NOT NULL, count INTEGER NOT NULL)')
            self.set_default('control', {'stopped':False})
            self.set_default('account', {'cash':'10000', 'initial_cash':'10000', 'realized_pnl':'0'})

    def execute(self, sql, args=()):
        return self.conn.execute(sql.replace('?', '%s') if self.postgres else sql, args)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.execute('BEGIN')
            try:
                yield self
                self.execute('COMMIT')
            except BaseException:
                self.execute('ROLLBACK')
                raise

    def set_default(self, key, data):
        self.execute('INSERT INTO state(key,data) VALUES (?,?) ON CONFLICT DO NOTHING',(key,json.dumps(data)))

    def get_state(self, key, default=None):
        with self.lock:
            row = self.execute('SELECT data FROM state WHERE key=?',(key,)).fetchone()
            return json.loads(row['data']) if row else default

    def set_state(self, key, data):
        self.execute('INSERT INTO state(key,data) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',(key,json.dumps(data)))

    def put(self, kind, data, id=None, at=None):
        id = id or str(uuid.uuid4())
        doc = dict(data, id=id, recorded_at=at or time.time())
        with self.lock:
            self.execute('INSERT INTO records(id,kind,at,search,data) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING',
                         (id,kind,doc['recorded_at'],json.dumps(doc).lower(),json.dumps(doc)))
        return doc

    def replace(self, id, data):
        self.execute('UPDATE records SET data=?,search=? WHERE id=?',(json.dumps(data),json.dumps(data).lower(),id))

    def get(self, kind, id):
        with self.lock:
            row = self.execute('SELECT data FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
            return json.loads(row['data']) if row else None

    def list(self, kind, limit=100, query=''):
        with self.lock:
            rows = self.execute('SELECT data FROM records WHERE kind=? AND search LIKE ? ORDER BY at DESC LIMIT ?',
                                (kind,'%'+query.lower().replace('%','').replace('_','')+'%',min(limit,10000))).fetchall()
            return [json.loads(r['data']) for r in rows]

    def rate(self, key, limit, window=60):
        # Store all windows in epoch seconds; minute requests must not erase
        # the longer login window during cleanup.
        bucket = int(time.time() // window) * window
        with self.transaction():
            row = self.execute('INSERT INTO rate_limits(key,bucket,count) VALUES (?,?,1) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN rate_limits.bucket=excluded.bucket THEN rate_limits.count+1 ELSE 1 END,bucket=excluded.bucket RETURNING count',(key,bucket)).fetchone()
            # One row per hashed client, bounded by expiry cleanup.
            self.execute('DELETE FROM rate_limits WHERE bucket < ?', (int(time.time())-86400,))
            return row['count'] <= limit

    def try_acquire_collector(self):
        if self.postgres:
            row = self.execute('SELECT pg_try_advisory_lock(71933021) AS acquired').fetchone()
            return bool(row['acquired'])
        return True

    def acquire_collector(self):
        if not self.try_acquire_collector():
            raise RuntimeError('Only one collector process per deployment is permitted')

    def release_collector(self):
        if self.postgres:
            self.execute('SELECT pg_advisory_unlock(71933021)')

    def close(self):
        self.conn.close()

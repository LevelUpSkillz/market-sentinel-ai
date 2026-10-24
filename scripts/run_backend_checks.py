"""Run release checks against a new local PostgreSQL, never the hosted database.

pgserver is a build-only binary dependency, not the application's database.
The temporary server is destroyed after verification and receives synthetic data.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlencode
import pgserver
import psycopg
from psycopg.conninfo import conninfo_to_dict


def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'backend'))
    with tempfile.TemporaryDirectory(prefix='sentinel-postgres-tests-') as directory:
        server=pgserver.get_server(Path(directory),cleanup_mode='stop')
        try:
            local_uri=server.get_uri()
            with psycopg.connect(local_uri,autocommit=True) as connection:
                connection.execute('CREATE DATABASE test_market_sentinel')
            params=conninfo_to_dict(local_uri)
            params.pop('dbname',None)
            test_uri='postgresql:///test_market_sentinel?'+urlencode(params)
            os.environ['TEST_POSTGRES_URL']=test_uri
            os.environ['ENVIRONMENT']='test'
            os.environ['DATABASE_URL']=test_uri
            os.environ['KRAKEN_LIVE_ENABLED']='false'
            suite=unittest.defaultTestLoader.discover(str(root/'backend/tests'))
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            print('ISOLATED_POSTGRES_ACCEPTANCE local_only=true production_access=false tests='+str(result.testsRun)+' skipped='+str(len(result.skipped)),flush=True)
            if not result.wasSuccessful() or result.skipped:raise SystemExit(1)
        finally:
            server.cleanup()


if __name__=='__main__':main()

"""Synthetic offline recovery checks; no production database or provider calls."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from sentinel.backup import (BackupError, export_backup, validate_backup,
                             restore_backup, MAX_BACKUP_BYTES)
from sentinel.storage import Store

NOW = 1_800_000_000


def resign(doc):
    unsigned = {key: value for key, value in doc.items() if key != 'sha256'}
    doc['sha256'] = sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return json.dumps(doc).encode()


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.source, self.destination = Store('sqlite:///:memory:'), Store('sqlite:///:memory:')
        with self.source.transaction():
            self.source.set_state('account', {'cash': '9749', 'initial_cash': '10000', 'realized_pnl': '-1'})
            self.source.set_state('market_watch', [{'provider': 'kraken', 'symbol': 'SYNTHETIC-USD'}])
            self.source.set_state('trader:0x'+'7'*40, {'positions': [], 'received_at': NOW-2})
            self.source.set_state('real_capital_profile', {'confirmed_at': NOW-3, 'capital_usd': '5000', 'execution_enabled': False})
            self.paper = self.source.put('paper', {'status': 'open', 'entry_notional': '250',
                'source': 'SYNTHETIC OFFLINE BACKUP FIXTURE'}, id='synthetic-position', at=NOW-15)
            self.market = self.source.put('market_snapshot', {'source_at': NOW-500, 'received_at': NOW-499,
                'status': 'live', 'mid': '100', 'source': 'SYNTHETIC EXPIRED MARKET FIXTURE'}, id='synthetic-market', at=NOW-498)
            self.source.put('alert', {'status': 'queued', 'mode': 'delivery_test', 'title': 'SYNTHETIC'}, id='synthetic-alert', at=NOW-20)

    def tearDown(self):
        self.source.close()
        self.destination.close()

    def restore(self, blob=None, **kwargs):
        return restore_backup(self.destination, blob or export_backup(self.source, now=NOW),
                              environment='test', offline=True, confirm_empty=True, now=NOW+10, **kwargs)

    def test_complete_archive_preserves_paper_account_ids_and_source_times(self):
        blob = export_backup(self.source, now=NOW)
        doc = validate_backup(blob)
        self.assertEqual(doc['counts'], {'state': 5, 'records': 3})
        report = self.restore(blob)
        self.assertEqual(report['records'], 3)
        self.assertEqual(self.destination.get('paper', self.paper['id']), self.paper)
        self.assertEqual(self.destination.get('market_snapshot', self.market['id']), self.market)
        self.assertEqual(self.destination.get_state('account'), self.source.get_state('account'))
        self.assertTrue(self.destination.get_state('control')['stopped'])
        self.assertFalse(report['collectors_started'])
        self.assertFalse(report['orders_submitted'])

    def test_restore_requires_fresh_wallet_and_market_evidence_and_profile_reconfirmation(self):
        report = self.restore()
        self.assertEqual(report['discarded_active_cache_state'], 1)
        self.assertIsNone(self.destination.get_state('trader:0x'+'7'*40))
        profile = self.destination.get_state('real_capital_profile')
        self.assertEqual(profile['confirmed_at'], 0)
        self.assertEqual(profile['backup_original_confirmed_at'], NOW-3)
        self.assertEqual(self.destination.get('market_snapshot', 'synthetic-market')['received_at'], NOW-499)
        self.assertEqual(self.destination.get('alert', 'synthetic-alert')['status'], 'restore_suppressed')

    def test_session_credentials_and_rate_limits_are_excluded_and_counted(self):
        with self.source.transaction():
            self.source.set_state('credential:kraken', {'api_key': 'SYNTHETIC_NEVER_EXPORT'})
            self.source.set_state('session:owner', {'secret': 'SYNTHETIC_NEVER_EXPORT'})
            self.source.set_state('connection:kraken', {'cipher': 'SYNTHETIC_NEVER_EXPORT', 'connection_id': 'SYNTHETIC'})
            self.source.set_state('kraken_nonce:synthetic_hash', {'nonce': 123})
            self.source.put('credential', {'api_secret': 'SYNTHETIC_NEVER_EXPORT'}, at=NOW)
        self.source.rate('SYNTHETIC_HASHED_CLIENT', 5)
        blob = export_backup(self.source, now=NOW)
        doc = validate_backup(blob)
        self.assertNotIn(b'SYNTHETIC_NEVER_EXPORT', blob)
        self.assertNotIn(b'SYNTHETIC_HASHED_CLIENT', blob)
        self.assertEqual(doc['excluded'], {'credential_state': 4, 'credential_records': 1, 'rate_limits': 1})
        self.restore(blob)
        self.assertEqual(self.destination.execute('SELECT COUNT(*) AS count FROM rate_limits').fetchone()['count'], 0)

    def test_unresolved_order_reference_requires_matching_preserved_record(self):
        with self.source.transaction():
            self.source.set_state('kraken_live_active', 'synthetic-unresolved-order')
        with self.assertRaisesRegex(BackupError, 'order reference'):
            export_backup(self.source, now=NOW)
        self.source.put('real_order', {'status': 'unknown',
            'source': 'SYNTHETIC OFFLINE ORDER; NEVER SUBMIT'},
            id='synthetic-unresolved-order', at=NOW-10)
        blob = export_backup(self.source, now=NOW)
        self.assertEqual(validate_backup(blob)['counts']['state'], 6)
        self.restore(blob)
        self.assertEqual(self.destination.get_state('kraken_live_active'), 'synthetic-unresolved-order')
        recovered = self.destination.get('real_order', 'synthetic-unresolved-order')
        self.assertTrue(recovered['restored_execution_disabled'])
        self.assertFalse(recovered['execution_enabled'])
        self.assertTrue(self.destination.get_state('control')['stopped'])

    def test_real_order_financial_evidence_is_preserved_but_never_reenabled_on_restore(self):
        original = self.source.put('real_order', {'status': 'unknown', 'connection_id': 'SYNTHETIC_CONNECTION',
            'preview': {'symbol': 'SYNTHETIC-USD', 'quantity': '1'}, 'txids': ['SYNTHETIC_TXID'],
            'source': 'SYNTHETIC ORDER FIXTURE; NO REAL ORDER'}, id='synthetic-order', at=NOW-10)
        self.restore()
        restored = self.destination.get('real_order', 'synthetic-order')
        self.assertEqual(restored['status'], original['status'])
        self.assertEqual(restored['preview'], original['preview'])
        self.assertEqual(restored['txids'], original['txids'])
        self.assertTrue(restored['restored_execution_disabled'])
        self.assertFalse(restored['execution_enabled'])
        self.assertIsNone(self.destination.get_state('connection:kraken'))

    def test_nested_credential_fields_in_research_fail_closed_without_leaking_values(self):
        self.source.put('audit', {'nested': [{'api_secret': 'SYNTHETIC_SECRET_VALUE'}]}, at=NOW)
        with self.assertRaises(BackupError) as error:
            export_backup(self.source)
        self.assertNotIn('SYNTHETIC_SECRET_VALUE', str(error.exception))

    def test_unknown_state_or_record_category_needs_format_review(self):
        self.source.set_state('future_unreviewed_state', {'anything': 1})
        with self.assertRaisesRegex(BackupError, 'format review'):
            export_backup(self.source)
        self.source.execute("DELETE FROM state WHERE key='future_unreviewed_state'")
        self.source.put('future_unreviewed_record', {'anything': 1}, at=NOW)
        with self.assertRaisesRegex(BackupError, 'format review'):
            export_backup(self.source)

    def test_size_limit_refuses_truncation_and_leaves_source_unchanged(self):
        before = self.source.get_state('account')
        with self.assertRaisesRegex(BackupError, 'size limit'):
            export_backup(self.source, max_bytes=512)
        self.assertEqual(self.source.get_state('account'), before)
        self.assertEqual(len(self.source.list('paper')), 1)
        self.assertEqual(validate_backup(export_backup(self.source))['counts']['records'], 3)

    def test_checksum_change_and_truncation_are_rejected_before_destination_writes(self):
        blob = export_backup(self.source, now=NOW)
        tampered = json.loads(blob)
        tampered['payload']['records'][0]['data']['title'] = 'SYNTHETIC_CHANGED'
        for invalid in (json.dumps(tampered).encode(), blob[:-10], b'{}', b'x'*(MAX_BACKUP_BYTES+1)):
            with self.subTest(size=len(invalid)):
                with self.assertRaises(BackupError):
                    self.restore(invalid)
        self.assertEqual(self.destination.list('paper'), [])
        self.assertFalse(self.destination.get_state('control')['stopped'])

    def test_schema_counts_duplicate_ids_and_identity_mismatch_fail_before_writes(self):
        original = json.loads(export_backup(self.source, now=NOW))
        variants = []
        value = deepcopy(original); value['schema_version'] = 2; variants.append(value)
        value = deepcopy(original); value['counts']['records'] += 1; variants.append(value)
        value = deepcopy(original); value['payload']['records'][1]['id'] = value['payload']['records'][0]['id']; variants.append(value)
        value = deepcopy(original); value['payload']['records'][0]['data']['recorded_at'] = NOW+1; variants.append(value)
        value = deepcopy(original); value['payload']['records'][0]['kind'] = ['invalid']; variants.append(value)
        value = deepcopy(original); next(row for row in value['payload']['state'] if row['key'] == 'account')['data'] = {'cash': 'NaN', 'initial_cash': '10000', 'realized_pnl': '0'}; variants.append(value)
        for value in variants:
            with self.subTest(value=value['schema_version']):
                with self.assertRaises(BackupError):
                    self.restore(resign(value))
        self.assertEqual(self.destination.list('paper'), [])

    def test_duplicate_json_members_are_rejected(self):
        blob = export_backup(self.source, now=NOW)
        with self.assertRaises(BackupError):
            validate_backup(blob.replace(b'{', b'{"version":1,', 1))

    def test_hosted_or_unconfirmed_or_online_restore_is_refused(self):
        blob = export_backup(self.source)
        for environment, offline, confirm in [('production', True, True), ('staging', True, True),
                                              ('test', False, True), ('test', True, False)]:
            with self.subTest(environment=environment, offline=offline, confirm=confirm):
                with self.assertRaises(BackupError):
                    restore_backup(self.destination, blob, environment=environment,
                                   offline=offline, confirm_empty=confirm)
        self.assertEqual(self.destination.list('paper'), [])

    def test_nested_export_or_restore_cannot_commit_the_callers_transaction(self):
        blob = export_backup(self.source)
        for target, action in ((self.source, lambda: export_backup(self.source)),
                               (self.destination, lambda: self.restore(blob))):
            with self.subTest(target=target), self.assertRaisesRegex(RuntimeError, 'SYNTHETIC OUTER ROLLBACK'):
                with target.transaction():
                    target.set_state('SYNTHETIC_CALLER_STATE', {'marker': 1})
                    with self.assertRaisesRegex(BackupError, 'idle database connection'):
                        action()
                    raise RuntimeError('SYNTHETIC OUTER ROLLBACK')
            self.assertIsNone(target.get_state('SYNTHETIC_CALLER_STATE'))

    def test_existing_records_modified_account_or_rate_limits_are_never_overwritten(self):
        for prepare in ('record', 'account', 'rate'):
            with self.subTest(prepare=prepare):
                target = Store('sqlite:///:memory:')
                try:
                    if prepare == 'record': target.put('audit', {'action': 'SYNTHETIC_EXISTING'}, at=NOW)
                    elif prepare == 'account': target.set_state('account', {'cash': '123', 'initial_cash': '10000', 'realized_pnl': '0'})
                    else: target.rate('SYNTHETIC_CLIENT', 5)
                    before = target.get_state('account')
                    with self.assertRaisesRegex(BackupError, 'not empty'):
                        restore_backup(target, export_backup(self.source), environment='test', offline=True, confirm_empty=True)
                    self.assertEqual(target.get_state('account'), before)
                finally:
                    target.close()

    def test_insert_failure_rolls_back_account_records_and_emergency_control(self):
        execute = self.destination.execute
        def fail(sql, args=()):
            if sql.startswith('INSERT INTO records') and args[0] == 'synthetic-position':
                raise RuntimeError('SYNTHETIC STORAGE FAILURE')
            return execute(sql, args)
        with patch.object(self.destination, 'execute', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC STORAGE FAILURE'):
                self.restore()
        self.assertEqual(self.destination.list('paper'), [])
        self.assertEqual(self.destination.list('alert'), [])
        self.assertEqual(self.destination.get_state('account')['cash'], '10000')
        self.assertFalse(self.destination.get_state('control')['stopped'])

    def test_export_is_one_consistent_snapshot_despite_another_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            url = 'sqlite:///'+str(Path(folder)/'test_snapshot.db')
            reader, writer = Store(url), Store(url)
            try:
                execute = reader.execute
                injected = False
                def concurrent(sql, args=()):
                    nonlocal injected
                    cursor = execute(sql, args)
                    if 'FROM state ORDER BY key' in sql and not injected:
                        injected = True
                        with writer.transaction():
                            writer.set_state('account', {'cash': '9500', 'initial_cash': '10000', 'realized_pnl': '0'})
                            writer.put('paper', {'source': 'SYNTHETIC CONCURRENT WRITE'}, at=NOW)
                    return cursor
                with patch.object(reader, 'execute', side_effect=concurrent):
                    doc = validate_backup(export_backup(reader, now=NOW))
                accounts = [row['data'] for row in doc['payload']['state'] if row['key'] == 'account']
                self.assertEqual(accounts[0]['cash'], '10000')
                self.assertEqual(doc['payload']['records'], [])
                self.assertEqual(writer.get_state('account')['cash'], '9500')
            finally:
                reader.close(); writer.close()


class RestoreCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[2]/'scripts'/'restore_backup.py'
        spec = importlib.util.spec_from_file_location('restore_backup_script', path)
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def test_cli_refuses_hosted_process_or_application_database_without_opening_it(self):
        for values in ({'ENVIRONMENT': 'production'}, {'ENVIRONMENT': 'staging'},
                       {'ENVIRONMENT': 'test', 'COLLECT_MARKETS': 'true'},
                       {'ENVIRONMENT': 'test', 'RESTORE_DATABASE_URL': 'sqlite:///sentinel.dev.db'},
                       {'ENVIRONMENT': 'test', 'RESTORE_DATABASE_URL': 'sqlite:///test_same.db', 'DATABASE_URL': 'sqlite:///test_same.db'}):
            with self.subTest(values=values), patch.dict(os.environ, values, clear=True), patch.object(self.cli, 'Store') as opened:
                with self.assertRaises(BackupError):
                    self.cli.main(['missing.json', '--destination-env', 'RESTORE_DATABASE_URL', '--confirm-empty-disposable-database'])
                opened.assert_not_called()

    def test_cli_restores_only_explicit_disposable_target(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Store('sqlite:///:memory:')
            try:
                source.put('audit', {'action': 'SYNTHETIC_CLI_DRILL'}, at=NOW)
                archive = Path(folder)/'research-backup.json'
                archive.write_bytes(export_backup(source, now=NOW))
            finally:
                source.close()
            target = 'sqlite:///'+str(Path(folder)/'sentinel_restore_drill.db')
            with patch.dict(os.environ, {'ENVIRONMENT': 'test', 'COLLECT_MARKETS': 'false', 'RESTORE_DATABASE_URL': target}, clear=True), patch('builtins.print'):
                self.assertEqual(self.cli.main([str(archive), '--destination-env', 'RESTORE_DATABASE_URL', '--confirm-empty-disposable-database']), 0)
            restored = Store(target)
            try:
                self.assertEqual(restored.list('audit')[0]['action'], 'SYNTHETIC_CLI_DRILL')
                self.assertTrue(restored.get_state('control')['stopped'])
            finally:
                restored.close()


@unittest.skipUnless(os.getenv('TEST_POSTGRES_URL'), 'Dedicated TEST_POSTGRES_URL is not configured')
class PostgresRestoreTests(unittest.TestCase):
    def test_isolated_postgres_snapshot_and_restore_drill(self):
        # Never infer a target from DATABASE_URL or open the production firewall.
        from psycopg.conninfo import conninfo_to_dict
        url = os.environ['TEST_POSTGRES_URL']
        name = conninfo_to_dict(url).get('dbname', '')
        self.assertTrue(name.startswith(('test_', 'sentinel_restore_')), 'Use a separately named disposable test database')
        source, destination = Store(url), Store(url)
        schemas = ['test_backup_'+uuid.uuid4().hex, 'test_restore_'+uuid.uuid4().hex]
        try:
            for store, schema in zip((source, destination), schemas):
                # schemas isolate this drill from the three existing PG tests.
                store.execute('CREATE SCHEMA '+schema)
                store.execute('SET search_path TO '+schema+',public')
                for table in ('schema_version', 'records', 'state', 'rate_limits'):
                    store.execute('CREATE TABLE '+schema+'.'+table+' (LIKE public.'+table+' INCLUDING ALL)')
                store.execute('INSERT INTO schema_version(version) VALUES (1)')
                store.set_default('control', {'stopped': False})
                store.set_default('account', {'cash': '10000', 'initial_cash': '10000', 'realized_pnl': '0'})
            item = source.put('paper', {'source': 'SYNTHETIC_POSTGRES_RESTORE_DRILL'}, at=NOW)
            connection_id=str(uuid.uuid4())
            order=source.put('real_order',{'status':'unknown','connection_id':connection_id,'order_ids':['SYNTHETIC_PROVIDER_ID']},at=NOW)
            source.set_state('kraken_live_active',order['id'])
            source.set_state('kraken_order_binding',{'id':connection_id,'fingerprint':'a'*64})
            source.set_state('account', {'cash': '9750', 'initial_cash': '10000', 'realized_pnl': '0'})
            blob = export_backup(source, now=NOW)
            report = restore_backup(destination, blob, environment='test', offline=True, confirm_empty=True, now=NOW+10)
            self.assertEqual(destination.get('paper', item['id']), item)
            self.assertEqual(destination.get_state('account')['cash'], '9750')
            self.assertTrue(report['emergency_stop'])
            self.assertEqual(destination.get_state('kraken_live_active'),order['id'])
            self.assertEqual(destination.get('real_order',order['id'])['order_ids'],['SYNTHETIC_PROVIDER_ID'])
            self.assertTrue(destination.get('real_order',order['id'])['restored_execution_disabled'])
        finally:
            for store, schema in zip((source, destination), schemas):
                store.execute('SET search_path TO public')
                store.execute('DROP SCHEMA IF EXISTS '+schema+' CASCADE')
                store.close()


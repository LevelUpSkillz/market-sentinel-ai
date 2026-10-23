"""Versioned logical research backup; no HTTP restore or credential backup.

The caller must protect downloads with owner authentication, no-store headers
and a low request limit. This module never starts collectors or sends orders.
"""
from copy import deepcopy
from contextlib import closing, contextmanager
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import json
from math import isfinite
import re
import time

FORMAT = 'market-sentinel-logical-backup'
VERSION = 1
MAX_BACKUP_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 100_000
MAX_STATE = 10_000
RECORD_KINDS = frozenset({
    'paper', 'audit', 'watchlist', 'trader_event', 'trader_snapshot', 'trader_cohort',
    'follow_sample', 'market_snapshot', 'forensic', 'opportunity', 'alert',
    'radar_signal', 'entry_plan', 'real_plan', 'real_order', 'lab', 'quote',
})
STATE_KEYS = frozenset({
        'kraken_live_active',
    'control', 'account', 'market_watch', 'real_capital_profile',
    'catalogue:coins', 'catalogue:quotes', 'catalogue:venues',
    'public_leaderboard', 'public_leaderboard_error',
})
STATE_PREFIXES = ('trader:', 'trader_error:', 'trader_history:',
                  'trader_history_error:', 'follow-last:', 'radar-alert:', 'quote-cache:')
SECRET_KEYS = frozenset({
    'secret', 'password', 'password_hash', 'owner_password_hash', 'session_secret',
    'private_key', 'api_key', 'api_secret', 'api_token', 'access_token',
    'refresh_token', 'recovery_phrase', 'seed', 'mnemonic', 'authorization',
    'cookie', 'ntfy_token', 'encryption_key', 'credential', 'credentials',
    'client_secret', 'secret_key', 'signing_key', 'session_token', 'api_sign',
    'cipher', 'encrypted_credentials',
})
SECRET_CATEGORIES = ('credential', 'secret', 'session', 'auth', 'token',
                     'exchange_connection', 'connection', 'kraken_nonce')


class BackupError(ValueError):
    """Safe message that contains no record contents or credential values."""


def _require_idle(store):
    # PostgreSQL warns on nested BEGIN, then a later COMMIT would commit the
    # caller's transaction. Never borrow an already active Store transaction.
    active = store.conn.info.transaction_status != 0 if store.postgres else store.conn.in_transaction
    if active:
        raise BackupError('Backup/restore requires an idle database connection.')


@contextmanager
def _restore_transaction(store):
    with store.lock:
        _require_idle(store)
        with store.transaction():
            yield


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise BackupError('Backup contains unsupported or nonfinite JSON data.') from error


def _timestamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value <= 253402300799 and isfinite(value)


def _state_allowed(key):
    return isinstance(key, str) and len(key) <= 512 and (
        key in STATE_KEYS or any(key.startswith(prefix) for prefix in STATE_PREFIXES))


def _secret_category(value):
    if not isinstance(value, str):
        raise BackupError('Invalid stored research category.')
    lowered = value.lower().replace('-', '_')
    return any(lowered == key or lowered.startswith(key + ':') or lowered.startswith(key + '_')
               for key in SECRET_CATEGORIES)


def _check_data(value, depth=0):
    if depth > 64:
        raise BackupError('Backup JSON exceeds the nesting limit.')
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or key.lower().replace('-', '_') in SECRET_KEYS:
                raise BackupError('A credential field is present in research data; export was refused.')
            _check_data(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_data(child, depth + 1)
    elif value is not None and not isinstance(value, (str, bool, int, float)):
        raise BackupError('Backup contains unsupported JSON data.')
    elif isinstance(value, float) and not isfinite(value):
        raise BackupError('Backup contains nonfinite JSON data.')


def _decode(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise BackupError('Stored research data is not valid JSON.') from error
    _check_data(value)
    return value


def export_backup(store, *, now=None, max_bytes=MAX_BACKUP_BYTES):
    """Return a complete bounded archive, or fail without a partial download.

    PostgreSQL uses one repeatable-read read-only transaction. The local Store
    lock protects its single connection; concurrent collector handoff instances
    cannot make state and records come from different PostgreSQL snapshots.
    Unknown research categories fail closed until this format is reviewed.
    Explicit credential/session categories and rate-limit rows are excluded.
    """
    if not isinstance(max_bytes, int) or not 1 <= max_bytes <= MAX_BACKUP_BYTES:
        raise BackupError('Invalid backup size limit.')
    now = time.time() if now is None else now
    if not _timestamp(now):
        raise BackupError('Invalid backup timestamp.')
    payload = {'state': [], 'records': []}
    omitted = {'credential_state': 0, 'credential_records': 0, 'rate_limits': 0}
    used = 1024
    with store.lock:
        _require_idle(store)
        store.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY' if store.postgres else 'BEGIN')
        try:
            versions = [row['version'] for row in store.execute('SELECT version FROM schema_version ORDER BY version').fetchall()]
            if versions != [1]:
                raise BackupError('Unsupported database schema version.')
            omitted['rate_limits'] = store.execute('SELECT COUNT(*) AS count FROM rate_limits').fetchone()['count']
            for table, columns, ordering, maximum in (
                ('state', 'key', 'key', MAX_STATE),
                ('records', 'id,kind,at', 'id', MAX_RECORDS),
            ):
                allowed = ('key IN ('+','.join("'"+key+"'" for key in sorted(STATE_KEYS))+') OR '+
                           ' OR '.join("SUBSTR(key,1,"+str(len(prefix))+")='"+prefix+"'" for prefix in STATE_PREFIXES)) if table == 'state' else (
                           'kind IN ('+','.join("'"+kind+"'" for kind in sorted(RECORD_KINDS))+')')
                size = 'OCTET_LENGTH(data)' if store.postgres else 'LENGTH(CAST(data AS BLOB))'
                # Never retrieve credential payloads or an over-limit row from
                # the database. A named PostgreSQL cursor also avoids libpq
                # buffering the entire historical journal in process memory.
                sql = (f'SELECT {columns},CASE WHEN ({allowed}) AND {size}<={max_bytes} THEN data ELSE NULL END AS data,'
                       f'CASE WHEN ({allowed}) THEN {size} ELSE 0 END AS data_bytes FROM {table} ORDER BY {ordering}')
                if store.postgres:
                    cursor = store.conn.cursor(name='sentinel_backup_'+table)
                    cursor.execute(sql)
                else:
                    cursor = store.execute(sql)
                scanned = 0
                with closing(cursor):
                    while True:
                        row = cursor.fetchone()
                        if row is None:
                            break
                        scanned += 1
                        if scanned > maximum:
                            raise BackupError('Backup row limit reached; no partial archive was created.')
                        category = row['key'] if table == 'state' else row['kind']
                        if _secret_category(category):
                            omitted['credential_state' if table == 'state' else 'credential_records'] += 1
                            continue
                        if (table == 'state' and not _state_allowed(category)) or (
                                table == 'records' and category not in RECORD_KINDS):
                            raise BackupError('An unsupported research category requires a backup format review.')
                        if row['data_bytes'] > max_bytes:
                            raise BackupError('Backup size limit reached; no partial archive was created.')
                        item = {'key': row['key'], 'data': _decode(row['data'])} if table == 'state' else {
                            'id': row['id'], 'kind': row['kind'], 'at': row['at'], 'data': _decode(row['data'])}
                        used += len(_canonical(item)) + 1
                        if used > max_bytes:
                            raise BackupError('Backup size limit reached; no partial archive was created.')
                        payload[table].append(item)
            store.execute('COMMIT')
        except BaseException:
            store.execute('ROLLBACK')
            raise
    envelope = {'format': FORMAT, 'version': VERSION, 'schema_version': 1,
                'created_at': now, 'counts': {key: len(value) for key, value in payload.items()},
                'excluded': omitted, 'payload': payload}
    envelope['sha256'] = sha256(_canonical(envelope)).hexdigest()
    result = _canonical(envelope)
    if len(result) > max_bytes:
        raise BackupError('Backup size limit reached; no partial archive was created.')
    # Revalidate before returning so corrupt stored IDs/timestamps never produce
    # a download that cannot be restored.
    validate_backup(result, max_bytes=max_bytes)
    return result


def validate_backup(blob, *, max_bytes=MAX_BACKUP_BYTES):
    """Validate checksum, exact format, row identities and limits before writes."""
    if not isinstance(blob, bytes) or len(blob) > max_bytes or max_bytes > MAX_BACKUP_BYTES:
        raise BackupError('Backup is missing or exceeds the supported size limit.')
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise BackupError('Backup JSON contains duplicate member names.')
            out[key] = value
        return out
    try:
        doc = json.loads(blob, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise BackupError('Backup is not valid UTF-8 JSON.') from error
    fields = {'format', 'version', 'schema_version', 'created_at', 'counts', 'excluded', 'payload', 'sha256'}
    if not isinstance(doc, dict) or set(doc) != fields or doc['format'] != FORMAT or (
            type(doc['version']) is not int or doc['version'] != VERSION or
            type(doc['schema_version']) is not int or doc['schema_version'] != 1):
        raise BackupError('Unsupported backup format or schema.')
    digest = doc['sha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise BackupError('Backup checksum is missing or invalid.')
    unsigned = {key: value for key, value in doc.items() if key != 'sha256'}
    if not hmac.compare_digest(digest, sha256(_canonical(unsigned)).hexdigest()):
        raise BackupError('Backup checksum does not match; restore was refused.')
    if not _timestamp(doc['created_at']):
        raise BackupError('Invalid backup timestamp.')
    payload = doc['payload']
    if not isinstance(payload, dict) or set(payload) != {'state', 'records'} or not all(
            isinstance(payload[key], list) for key in payload):
        raise BackupError('Invalid backup payload.')
    if len(payload['state']) > MAX_STATE or len(payload['records']) > MAX_RECORDS:
        raise BackupError('Backup row limit exceeded.')
    if not isinstance(doc['counts'], dict) or any(type(value) is not int for value in doc['counts'].values()) or doc['counts'] != {key: len(value) for key, value in payload.items()}:
        raise BackupError('Backup row counts do not match the payload.')
    excluded = doc['excluded']
    if not isinstance(excluded, dict) or set(excluded) != {'credential_state', 'credential_records', 'rate_limits'} or any(
            type(value) is not int or value < 0 for value in excluded.values()):
        raise BackupError('Invalid backup exclusion counts.')
    seen_state, seen_records = set(), set()
    for row in payload['state']:
        if not isinstance(row, dict) or set(row) != {'key', 'data'} or not _state_allowed(row['key']):
            raise BackupError('Invalid or unsupported backup state.')
        if row['key'] in seen_state:
            raise BackupError('Duplicate backup state key.')
        seen_state.add(row['key'])
        _check_data(row['data'])
    for row in payload['records']:
        if not isinstance(row, dict) or set(row) != {'id', 'kind', 'at', 'data'} or (
                not isinstance(row['id'], str) or not 1 <= len(row['id']) <= 512 or
                not isinstance(row['kind'], str) or row['kind'] not in RECORD_KINDS or not _timestamp(row['at']) or
                not isinstance(row['data'], dict)):
            raise BackupError('Invalid backup journal record.')
        if row['id'] in seen_records or row['data'].get('id') != row['id'] or row['data'].get('recorded_at') != row['at']:
            raise BackupError('Backup record identity or timestamp does not match.')
        seen_records.add(row['id'])
        _check_data(row['data'])
    if not {'control', 'account'}.issubset(seen_state):
        raise BackupError('Backup lacks required account/control state.')
    state = {row['key']: row['data'] for row in payload['state']}
    active_order = state.get('kraken_live_active')
    if active_order is not None and (not isinstance(active_order, str) or
            not 1 <= len(active_order) <= 512 or
            not any(row['kind'] == 'real_order' and row['id'] == active_order
                    for row in payload['records'])):
        raise BackupError('Unresolved Kraken order reference lacks preserved order evidence.')
    if not isinstance(state['control'], dict) or type(state['control'].get('stopped')) is not bool or not isinstance(state['account'], dict):
        raise BackupError('Backup account/control state is invalid.')
    try:
        account = state['account']
        for key in ('cash', 'initial_cash', 'realized_pnl'):
            if not isinstance(account.get(key), str) or len(account[key]) > 100:
                raise BackupError('Backup paper accounting is invalid.')
            value = Decimal(account[key])
            if not value.is_finite() or (key != 'realized_pnl' and value < 0):
                raise BackupError('Backup paper accounting is invalid.')
    except InvalidOperation as error:
        raise BackupError('Backup paper accounting is invalid.') from error
    return doc


def restore_backup(store, blob, *, environment, offline=False, confirm_empty=False, now=None):
    """Restore ONLY a stopped, empty development/test destination.

    This is an offline drill primitive, never an application endpoint. PostgreSQL
    targets must be named test_* or sentinel_restore_* and have no collector.
    """
    if environment not in {'development', 'test'} or not offline or not confirm_empty:
        raise BackupError('Restore requires an offline, explicitly confirmed development/test destination.')
    doc = validate_backup(blob)
    now = time.time() if now is None else now
    if not _timestamp(now):
        raise BackupError('Invalid restore timestamp.')
    with _restore_transaction(store):
        if store.postgres:
            database = store.execute('SELECT current_database() AS name').fetchone()['name']
            if not (database.startswith('test_') or database.startswith('sentinel_restore_')):
                raise BackupError('Restore requires a separately named disposable PostgreSQL database.')
            occupied = store.execute("SELECT COUNT(*) AS count FROM pg_locks WHERE locktype='advisory' AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) AND classid=0 AND objid=71933021 AND objsubid=1 AND granted").fetchone()['count']
            if occupied or not store.execute('SELECT pg_try_advisory_xact_lock(71933021) AS acquired').fetchone()['acquired']:
                raise BackupError('A collector is using the destination; restore was refused.')
            # Block another connection from racing this emptiness check/insert.
            store.execute('LOCK TABLE records, state, rate_limits IN ACCESS EXCLUSIVE MODE')
        existing = store.execute('SELECT key,data FROM state').fetchall()
        defaults = {'control': {'stopped': False}, 'account': {'cash': '10000', 'initial_cash': '10000', 'realized_pnl': '0'}}
        if store.execute('SELECT COUNT(*) AS count FROM records').fetchone()['count'] or (
                store.execute('SELECT COUNT(*) AS count FROM rate_limits').fetchone()['count']) or any(
                    row['key'] not in defaults or _decode(row['data']) != defaults[row['key']] for row in existing):
            raise BackupError('Destination is not empty; no existing application state was overwritten.')
        versions = [row['version'] for row in store.execute('SELECT version FROM schema_version ORDER BY version').fetchall()]
        if versions != [1]:
            raise BackupError('Destination schema is unsupported.')
        omitted_state = 0
        for row in doc['payload']['state']:
            key, data = row['key'], deepcopy(row['data'])
            # Recovered market evidence remains in historical records/archive.
            # Drop active caches so reopening the app requires new observations;
            # the first wallet poll must be a baseline after the collection gap.
            if key.startswith(('trader:', 'quote-cache:')) or key in {'catalogue:quotes', 'catalogue:venues'}:
                omitted_state += 1
                continue
            if key == 'control':
                data = {'stopped': True, 'changed_at': now, 'reason': 'Offline restore requires owner review.'}
            elif key == 'real_capital_profile' and isinstance(data, dict):
                data['backup_original_confirmed_at'] = data.get('confirmed_at')
                data['confirmed_at'] = 0
                data['execution_enabled'] = False
            store.set_state(key, data)
        for row in doc['payload']['records']:
            data = deepcopy(row['data'])
            if row['kind'] == 'alert' and data.get('status') == 'queued':
                data.update(status='restore_suppressed', backup_original_status='queued',
                            restore_note='Historical queued delivery was suppressed during restore.')
            elif row['kind'] == 'real_order':
                # Preserve original status/txids for reconciliation. Recovery is
                # never approval to submit/retry an old pending/unknown order.
                data.update(restored_execution_disabled=True, execution_enabled=False,
                            restore_note='Historical order restored; reconcile with exchange before any new action.')
            # Original recorded_at/source_at/received_at values are retained.
            # Restoring does not make any historical quote a current live book.
            store.execute('INSERT INTO records(id,kind,at,search,data) VALUES (?,?,?,?,?)',
                          (row['id'], row['kind'], row['at'], json.dumps(data).lower(), json.dumps(data)))
    return {'format': FORMAT, 'version': VERSION, 'source_sha256': doc['sha256'],
            'restored_at': now, 'records': len(doc['payload']['records']),
            'state': len(doc['payload']['state']) - omitted_state,
            'discarded_active_cache_state': omitted_state, 'emergency_stop': True,
            'collectors_started': False, 'orders_submitted': False}

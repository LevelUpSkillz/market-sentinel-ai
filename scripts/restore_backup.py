"""Offline, empty disposable-database restore drill. Never uses DATABASE_URL."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sentinel.backup import BackupError, MAX_BACKUP_BYTES, restore_backup, validate_backup
from sentinel.storage import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--destination-env', choices=['TEST_POSTGRES_URL', 'RESTORE_DATABASE_URL'], required=True)
    parser.add_argument('--confirm-empty-disposable-database', action='store_true', required=True)
    args = parser.parse_args(argv)
    # No hosted-process environment or collection process is accepted.
    environment = os.getenv('ENVIRONMENT', 'development')
    if environment not in {'development', 'test'} or os.getenv('COLLECT_MARKETS', 'false').lower() != 'false':
        raise BackupError('Run offline in development/test with COLLECT_MARKETS=false.')
    destination = os.getenv(args.destination_env, '')
    if not destination or destination == os.getenv('DATABASE_URL'):
        raise BackupError('Configure a separate disposable restore destination; DATABASE_URL is never a target.')
    if args.destination_env == 'TEST_POSTGRES_URL' and not destination.startswith(('postgres://', 'postgresql://')):
        raise BackupError('TEST_POSTGRES_URL must reference a disposable PostgreSQL database.')
    if not destination.startswith(('postgres://', 'postgresql://', 'sqlite:///')):
        raise BackupError('Unsupported restore database scheme.')
    # Verify the resolved target name BEFORE Store can initialize schema/defaults.
    if destination.startswith(('postgres://', 'postgresql://')):
        from psycopg.conninfo import conninfo_to_dict
        name = conninfo_to_dict(destination).get('dbname', '')
    else:
        name = Path(destination.removeprefix('sqlite:///')).name
        configured = os.getenv('DATABASE_URL', '')
        if configured.startswith('sqlite:///') and Path(configured.removeprefix('sqlite:///')).resolve() == Path(destination.removeprefix('sqlite:///')).resolve():
            raise BackupError('The configured application database is never a restore target.')
    if not re.fullmatch(r'(test_|sentinel_restore_)[A-Za-z0-9_.-]+', name):
        raise BackupError('Destination name must start test_ or sentinel_restore_; use a separate disposable database.')
    # Validate before opening a destination or creating schema/default rows.
    with args.archive.open('rb') as archive:
        blob = archive.read(MAX_BACKUP_BYTES + 1)
    validate_backup(blob)
    store = Store(destination)
    try:
        report = restore_backup(store, blob, environment=environment, offline=True,
                                confirm_empty=args.confirm_empty_disposable_database)
    finally:
        store.close()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (BackupError, OSError) as error:
        # Do not expose DB URLs, SQL, records, or archive contents in diagnostics.
        print('Restore refused: '+str(error) if isinstance(error, BackupError) else 'Restore refused: archive is unavailable.', file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        # Provider errors can contain host/user/connection details. Keep them
        # out of an operator's shared terminal and diagnose privately instead.
        print('Restore failed: destination unavailable or unsupported. Inspect private database logs.', file=sys.stderr)
        raise SystemExit(1)

# Protected research export and offline restore

This milestone adds backend backup primitives and an offline restore drill. It
does not yet add a dashboard download or HTTP endpoint. No production export or
PostgreSQL restore has been performed merely by adding these files. Production
integration and acceptance must be recorded in HANDOFF.md separately.

The current Render Free PostgreSQL expires **November 22, 2026 at 04:35 UTC**.
A downloadable archive helps preserve research and paper accounting; it does not
extend that deadline, supply scheduled backups or guarantee permanent storage.
Keep archives outside this public repository in storage you control. They contain
private capital declarations, public-wallet watchlists and research history.

## Archive contract

`sentinel.backup.export_backup(store)` returns UTF-8 JSON with format
`market-sentinel-logical-backup`, format version 1, database schema version 1,
creation time, exact state/record counts, explicit exclusion counts and SHA-256.
It reads one consistent PostgreSQL repeatable-read read-only transaction, under
the local connection lock. SQLite is used for development checks only.

Records preserve IDs, kinds, original `recorded_at`, source/receipt timestamps and
input data. Paper cash and positions come from the same snapshot. Export includes
the known research journal categories, public-wallet observations and history,
declared capital profile, paper account and controls. A format review is required
for newly introduced state or record categories; unknown categories refuse export
instead of silently producing an incomplete research backup.

Environment variables, session cookies, provider API secrets and signing keys are
never read by the export. Rate-limit rows and explicitly named credential/session
storage categories are excluded and counted. Nested credential fields in a
research record refuse the export rather than leaking or silently changing the
record. Do not place secrets in labels, research inputs or other free text.
Credential recovery and secret-key rotation require a separate secure workflow.
Encrypted `connection:kraken` state and all `kraken_nonce:*` signing state are
explicitly excluded. Recovered accounts must be securely linked again. Future
`real_order` financial records are retained with their original status, preview
and exchange transaction IDs, but receive `restored_execution_disabled=true` and
`execution_enabled=false`. Any order-submission implementation must reject those
markers and reconcile ambiguous historical outcomes with the exchange; recovery
is never authorization to submit or blindly retry an old order.

The default limit is **16 MiB, 100,000 journal records and 10,000 state rows**.
An over-limit export fails without a partial archive; no history is truncated or
deleted to make an export pass. A larger retained journal will need a separately
reviewed streaming/paged archive implementation. SHA-256 detects accidental
corruption; it is not a signature or encryption and cannot establish who created
an archive. Restore only an archive from your own trusted export.

Any future download endpoint must require the existing verified owner session,
rate-limit exports, return `Cache-Control: no-store`, use attachment disposition,
exclude credentials from logs and avoid constructing archives on every poll.
There is deliberately no HTTP restore endpoint.

## Offline drill

Stop all processes that could use the disposable destination. Use development or
test mode, `COLLECT_MARKETS=false`, and a separate target named `test_*` or
`sentinel_restore_*`. The CLI never chooses `DATABASE_URL`, refuses a destination
equal to that application URL, refuses production/staging environments, validates
the archive before opening a destination, and refuses nonempty application data.
PostgreSQL restore additionally rejects an active collector lock.

For a local SQLite drill after obtaining a trusted archive:

```sh
ENVIRONMENT=test COLLECT_MARKETS=false \
RESTORE_DATABASE_URL=sqlite:////tmp/sentinel_restore_drill.db \
python scripts/restore_backup.py /private/path/research-backup.json \
  --destination-env RESTORE_DATABASE_URL \
  --confirm-empty-disposable-database
```

For a PostgreSQL drill, configure `TEST_POSTGRES_URL` through a secure local
environment mechanism for a **separate disposable PostgreSQL database** whose
name starts `test_` or `sentinel_restore_`, then run:

```sh
ENVIRONMENT=test COLLECT_MARKETS=false \
python scripts/restore_backup.py /private/path/research-backup.json \
  --destination-env TEST_POSTGRES_URL \
  --confirm-empty-disposable-database
```

Never paste connection credentials into chat, put them in source, reuse the
production database, or open its firewall for this test. The success report shows
counts and source checksum without database URLs or record content. No collectors,
orders or mobile deliveries are started by the CLI.

Restore writes are transactional. Original journal evidence and timestamps remain
historical. Active wallet/quote caches are discarded so a restarted collector
must establish new market observations and a new wallet baseline. The original
archive still retains those snapshot state values. Queued historical mobile
deliveries become `restore_suppressed`, the real-capital profile must be confirmed
again, and emergency stop is forced on until the owner reviews the recovered app.

## Checks and limits

Run synthetic backup/restore checks with:

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_backup.py -v
```

The PostgreSQL drill test runs only with `TEST_POSTGRES_URL`. It uses separate
temporary schemas inside that disposable database and removes them afterward.
Without that variable, the PostgreSQL drill is skipped. SQLite test success is
not proof that a production PostgreSQL export/restore or durable offsite copy has
been completed. Recovered paper results also do not prove trading profitability.


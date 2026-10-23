# Security boundaries

No exchange order routing, signing, custody, withdrawals, deposit addresses or live execution are implemented. Paper trades are explicitly simulated database records. ChangeNOW implements only a fixed-host GET quote request. Mobile delivery uses a fixed ntfy.sh destination and backend secrets.

Production authentication uses a separate Cloudflare Access application restricted to the owner. The API validates RS256 signature, pinned issuer, audience, issued-at, expiry, token type and exact email against cached public keys. Forged email headers are never trusted. Local password access uses scrypt with a random salt and expiring HttpOnly/SameSite cookies. Production secrets live in hosting environment variables, never source or frontend responses.

Mutations check the configured Origin. API and login rate limits are stored in PostgreSQL. Paper entries have idempotency UUIDs and transactional cash accounting. Single-process collection is enforced with a PostgreSQL advisory lock. The persistent emergency stop blocks paper entries and push delivery while allowing fresh-book paper exits. Stale or insufficient books fail closed.

Authentication, watchlist and paper/control operations are audited. The journal is durable but not externally tamper-proof. Readiness checks report database/journal health separately from provider connectivity. Test PostgreSQL must always be disposable and separate from production. Hosted SQLite is rejected.

Known limits: single owner/process, proxy-conservative rate limits, no immutable audit export or formal penetration test, no verified multi-user isolation, and no automatic assurance of database backups. ntfy is at-least-once with bounded retries and can duplicate after a send/commit crash. Commercial/multi-user use requires additional review. The current free Render database expires on November 22, 2026; export or migrate before then.

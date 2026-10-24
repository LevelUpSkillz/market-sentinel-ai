# Market Sentinel AI — continuation checkpoint

Updated 2026-10-24. Inspect current repository refs, deployment commits, logs and tests before acting. Preserve newer work; this is not an instruction to roll back.

## Current milestone

Version 0.5.0 integrates secure own-account Kraken linking, individually approved real USD spot IOC limit orders and protected research backup download. Application source is b23fb6c559ff28c60ff683ecdad98af3bdf0d6a8. It includes current main’s owner-password OR verified-Access authentication, mobile/login fixes and 0.4.1 live chart work. The release branch is release/kraken-account-v050; it was promoted using a main expected-SHA lease. Do not return to the stale local checkout or overwrite newer branches.

Release acceptance: 256 Python tests passed with zero skips, including actual ephemeral PostgreSQL nonce/advisory-lock, accounting and backup/restore checks; 21 Chromium checks; TypeScript/Next.js build, Blueprint schema, dependency audits and real public provider probes. Successful preview 33b91f87-0515-4142-a2cd-4c541f1e17b9 completed at 04:51:53 UTC. The first preview stopped before tests because the runner default Python could not install the build-only pgserver wheel; .python-version now pins 3.12.14. No failing security check was bypassed.

Render deployment dep-dbe3jkvb9u1s73c2ec7g reached live at 04:54:41 UTC on that exact source. Cloudflare production 02f1e365-d4f1-4e26-8c1d-c1879775b0ac succeeded at 04:57:09 UTC on the same source. External checks at 04:56:54 UTC verified version 0.5.0, ready/live HTTP 200 and manual-only boundaries, unauthenticated/forged direct/proxy HTTP 401 and sign-in HTTP 302. See DELIVERY.md. Passing tests never proves provider-private acceptance, trading profitability or predictive advantage.

## Account connection and execution boundaries

The user chose Kraken and explicitly requested genuine account linking and individually approved own-account trades; a readiness screen alone was insufficient. Broad eligible spot markets are intended, not just BTC/ETH/SOL. No account key was collected, no account was connected and no real order was submitted during engineering acceptance. The owner must link through Settings → Your Kraken account after signing in. Never ask for credentials in chat.

Implemented in kraken.py/kraken_account.py and protected app routes:

- Fixed-host signed REST, dedicated restricted-key verification, actual BalanceEx/open orders/positions, country/pair identity, actual tick/lot/minimum and account fees. All unknown/funding/withdrawal permissions are rejected. A read-only key can link without trading authority; owner confirms regional/account eligibility.
- Credentials use Fernet in the dedicated database, with a separate server-only Render vault. No browser storage, source, response/error/audit/backup secret reflection. Same-origin authentication and shared PostgreSQL rate limits protect account and backup routes.
- Durable per-key monotonic nonce and local/PostgreSQL advisory serialization across overlapping instances. No retries of signed submission.
- Only observed Kraken USD spot books with current CRC verification are eligible. Core books plus six selected extra markets are supported; eligible native spot catalogue is broader. Every nonzero account holding needs verified USD valuation. Unknown/unsupported portfolios fail closed.
- Immutable 30-second validation-only preview, exact typed PLACE THIS REAL ORDER confirmation, current profile/fee/balance/market checks, emergency stop and active-order blocker. Final send rechecks expiry/profile/connection/stop/current risk after acquiring request locks.
- Intent commits before the sole IOC AddOrder. Duplicate approvals cannot resend completed/unknown orders. Transport/deadline/duplicate or uncertain outcomes stay blocked until manual reconciliation. Empty bounded history is never proof of failure. Inspect actual fills and fees directly in Kraken.
- No protective stop is placed. Full buy cost plus fee reserve counts as at-risk. Hard limits 500 USD order/asset and 2,500 USD correlated exposure; lower owner cash/risk/daily limits apply. Real-capital and UTC-day P&L remain owner-declared and require daily/24-hour reconfirmation. Open orders, borrowing/margin and unverifiable exposure block orders.
- Disconnect removes the cipher without canceling exchange orders. Restore permanently disables old execution, preserves txids/unresolved blocker and a nonsecret original-key binding; only the original dedicated key can reconnect to reconcile that order.

Server configuration was merge-updated only on Market Sentinel API: new MARKET_SENTINEL_VAULT_20261024 and KRAKEN_LIVE_ENABLED=true. No values belong in documentation or source. An existing KRAKEN_VAULT_KEY has precedence and was not changed. Never rotate either key casually. Render secrets are the source of truth for these omitted Blueprint keys; Blueprint sync must preserve them. No secrets are configured on Cloudflare. Enabled capability is not a connected account or a placed trade.

There is no self-custody wallet signer/spending connector, withdrawal/transfer, leverage, derivative or autonomous execution. A watched public address is observation, not ownership verification or spending authority. Do not merge the separate futures-readiness branch into this spot workflow without review. No paid upgrade or real-money acceptance trade is authorized.

## Established application

- Cloudflare Next.js/TypeScript dashboard, Render FastAPI with independent supervised collectors and dedicated PostgreSQL. Never modify Sentinel Intelligence.
- Source-aware global catalogue and delayed aggregate search, Kraken native spot ticker coverage and Hyperliquid native perpetual quotes; quote currencies/instruments remain distinct. No provider covers every token.
- Kraken CRC32 books, Hyperliquid books/trades/context, reconnection, stale rejection, sequencing/clock checks and lock-based collector handoff. Broad catalogue prices are not fill prices; selected detailed books are required.
- Deterministic opportunity finder → skeptic → risk → decision; visible-depth fees/latency, explainable rejections and factual forensic memory.
- Paper accounting/idempotency/costs/limits, opportunity autopsies, causal walk-forward lab with embargo and benchmarks. Paper radar GO permits an experiment; real-capital risk PASS does not establish a trading edge.
- Live sampled charts freeze verified values on staleness and break across outages. Mobile wallet actions show reported asset/size/direction/entry, plain-language rejection and actual address navigation.
- Public Hyperliquid candidate directory is experimental: bounded background feed, 100 retained candidates, six-hour cache and dated selection cohorts. Available reported historical fills/cycles, up to ten public watched wallets and independent forward follower observations. No worldwide-best or real-identity claim. ROI units/redistribution rights remain unverified. Success odds stay hidden/null until actual held-out validation and freshness pass; sample count alone is insufficient.
- Owner password session OR independently verified Cloudflare Access JWT; Origin checks, database rate limits/audit, emergency stop, optional private ntfy mobile delivery. No real mobile delivery was sent for acceptance.
- Settings backup export uses consistent PG read-only snapshot, 16 MiB/100k journal/10k state bounds, checksums/counts, secret/session/nonce exclusions. Offline restore only to empty isolated development/test databases, forced stop/profile reconfirmation and suppressed old alert deliveries. Actual disposable PG recovery passed; no production archive has been downloaded or stored offsite automatically.

## Fixed infrastructure and costs

Free plans only. Never add paid services/subscriptions/workers, upgrade compute/database, or create artificial keep-alive traffic without new cost approval. Render Free sleeps; no 24/7 monitoring/protective execution guarantee. PostgreSQL expires November 22, 2026 at 04:35 UTC; protected export does not extend retention. Durable free replacement/offsite archive remains an owner setup priority.

- App https://market.getlevelupskillz.com ; repo https://github.com/LevelUpSkillz/market-sentinel-ai (user temporarily made it public; no secrets).
- Cloudflare account f11da4c37ab8e27585d927a2c3cef02d; Pages market-sentinel-ai, production main, root frontend, bash ../scripts/cloudflare-build.sh, output out. Separate owner Access app. Automatic previews disabled; manual preview POST works. Logs need size:10000 and may publish only near completion.
- Render workspace tea-db64u6h42hec73atqvng; API srv-dbdg71jrjlhs73d6cprg, https://market-sentinel-ai-api.onrender.com ; Free Ohio, Python 3.12.14, backend root, one Uvicorn, /health/ready.
- Dedicated PG16 dpg-dbde83ks728c73bku27g-a; external access closed, internal Blueprint binding. Blueprint exs-dbdg49t9fdbs73b16nsg. Do not create duplicates or add unsupported Free maxShutdownDelaySeconds.
- Render advertises autoDeploy yes/commit but public-Git-URL pushes have not triggered deployment reliably. The environment update triggered the current exact-source build. Inspect active deploys before any new trigger; do not duplicate them.
- GitHub is source storage only; no GitHub Actions CI/deployment. Cloudflare performs all release checks and dashboard deployment; Render builds Python. Build-only ephemeral pgserver is not a migration of the backend/database to Cloudflare.

## Next priorities

1. Verify actual final production state in DELIVERY.md, then let the owner link their own restricted Kraken key in protected Settings. Do not claim the account is connected until provider verification succeeds. No seed phrases or keys in chat.
2. Preserve actual order intent/reconciliation and archive recovery evidence. Download a protected production backup and retain it outside source before the database expires; no automatic/offsite backup is claimed. Larger histories need a reviewed paged/streaming archive beyond current bounds.
3. Observe real public data and improve risk-adjusted trader evaluation using cash-flow-aware complete histories and point-in-time cohorts. Do not fabricate predictive odds, silently promote unvalidated strategies or label suspicions manipulation.
4. Obtain qualified Canadian/Québec advice before commercialization, third-party account linking or broader execution. Coinbase remains disabled for research-use restrictions; ChangeNOW awaits separate business key/use approval. Own-account API keys do not require Kraken partner OAuth approval.
5. Chain-wide whale discovery, worldwide verified rankings, validated liquidation cascade/forecasting models, advanced cross-asset risk and complete multi-phase mission remain unfinished. Avoid claiming otherwise.

## Working cautions

Active workspace for this release: /workspace/market-sentinel-release. /workspace/market-sentinel-ai is a stale checkout and must not be bulk-added or pushed. Current refs were reconstructed through exact remote files and combined without overwriting newer main. Connected GitHub create-tree/commit/update-ref tools use expected-SHA leases. Shell HTTP proxy was unavailable; connectors and Cloudflare runners worked. Never dump credential environments.

Plain local command: PYTHONPATH=backend python -m unittest discover -s backend/tests -q. Local result was 256 run/250 pass/6 PG skips; authoritative Cloudflare gate ran all 256 with no skips against ephemeral PG. Never use production for tests. Frontend dependencies are absent locally; Cloudflare runs TypeScript/Next/Chromium. Build scripts/check_deployed_auth.py makes bounded read-only production/auth probes. No owner session is impersonated to inspect private JSON.

Keep this checkpoint current after verification. Documentation-only commits may use [CF-Pages-Skip] [skip render] to avoid redundant deploys; distinguish later documentation head from the actual deployed application SHA. Continue autonomously within authorized free private-owner research/paper/planning/manual-spot scope, with concise progress updates and truthful limits.

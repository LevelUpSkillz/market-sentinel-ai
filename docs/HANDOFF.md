# Market Sentinel AI — current continuation checkpoint

Updated 2026-10-23. Inspect newer repository refs, files, deployment commits, logs and tests before acting; this is a checkpoint, never an instruction to roll back.

## Current milestone

**Production 0.4.1 is verified live.** Application source is `e30c2815f30042d111d8be6c533289d8f8d444cb`. Cloudflare production `eb316fdc-9c34-41f3-b6f1-3c46f09b258f` succeeded 2026-10-23 18:36:13 UTC. Render `dep-dbdqhb59fdbs738ase9g` reached live at 18:35:23 UTC on the existing Free service. External production acceptance at 18:36:01 UTC returned app_version0.4.1, both health endpoints200, anonymous/forged direct/proxied data requests401 and custom-domain sign-in302.

The exact application commit passed **190 Python run,187 passed,3 isolated PostgreSQL skipped;15 Chromium passed;TypeScript,Next.js build,Blueprint schema and dependency audits passed** in Cloudflare. Successful preview `c2a1a40a-3b2b-4f17-a338-951c2fd2764c` finished18:33:48UTC. The first preview failed one ambiguous Playwright alert selector (Next.js also creates an alert); this was corrected before release. No application failure was bypassed.

### Implemented, tested and deployed in 0.4.1

- Selectable live charts on Mission Control and Live Markets use actual distinct provider timestamps and visible-page two-second sampling. Invalid/stale prices freeze the last verified price, bid, ask, spread and source time. Outages break chart paths; no interpolated prices or perpetual flash animation.
- Plain-language trader cards show Ethereum/Bitcoin names, reported quantity, direction, reported average entry versus fresh quote, actual rejection cause and the next step. Current positions remain snapshots, not invented executions.
- Direct wallet navigation focuses the correct section, supports reduced motion, and associates observed position changes with their actual wallet. Public addresses can be copied with readable mobile buttons.
- Success percentages and95% bounds remain hidden until backend validation passes and observations stay fresh. Minimum sample count alone never validates odds.
- Hidden tabs stop dashboard/history/wallet/intelligence polling. Older detail responses cannot replace newer intelligence.
- Kraken connection guidance now accurately distinguishes standard owner-created API keys from partner OAuth. Coinbase own-account API keys and Crypto.com Exchange/App differences are documented in ACCOUNT_CONNECTIONS.md. **0.4.1 still has no credential-ingestion or real-order endpoint.** No account was connected or trade submitted.

### New user steering — active implementation after 0.4.1

The owner explicitly wants to connect their own wallet/exchange account and place individually approved real trades from this app, and also has Coinbase and Crypto.com. They clarified that connection/trading functionality is requested, not merely a readiness screen. Kraken remains selected; no actual order is approved by this feature request.

**Next code is in progress and NOT deployed or release-verified.** New Kraken REST adapter, encrypted account/execution module, account UI, protected logical-backup primitives and offline restore CLI are being developed locally. Do not claim these are available in production or enable them without the complete preview/security gate. The intended first scope is dedicated restricted Kraken owner keys, own-cash BTC/ETH/SOL USD spot IOC limit orders, immutable preview, explicit exact-order approval, durable intent/idempotency and no retry after unknown submission. No withdrawals, leverage, autonomous orders, private-key chat requests or real-money acceptance tests.

## Fixed user decisions

- Build an evidence-based crypto investigation and decision product. Prioritize actual data, costs, reliability, explainable rejection, prospective validation and premium mobile usability.
- Dashboard https://market.getlevelupskillz.com . Repository https://github.com/LevelUpSkillz/market-sentinel-ai . User temporarily made the repository public; no secrets in source.
- Keep Next.js/TypeScript on Cloudflare Pages; Python/FastAPI and independent collectors on Render; dedicated PostgreSQL. Completely isolate this from Sentinel Intelligence. Do not move the whole backend to Cloudflare.
- **Free plans only.** No paid upgrades, subscriptions, workers or artificial keep-alive traffic without explicit new cost approval. Render Free can sleep; no 24/7 guarantee. Database expires **2026-11-22 at 04:35 UTC**. Unlimited permanent retention is not available on that expiring database.
- GitHub is source storage; no GitHub Actions CI/deployment. Cloudflare runs checks and dashboard deployment; Render builds the Python backend.
- Latest selected exchange is **Kraken**. The user wants both manual real-capital planning and a future secure connection with individual approval for each real order. No autonomous trades or withdrawals are authorized. Never request exchange private keys, passwords, recovery phrases or seeds in chat.
- Kraken standard own-account API keys are supported by the provider; partner OAuth separately requires approval. The deployed0.4.1 implementation has no credential flow. New secure linking/execution work is in progress. Every real order requires separate explicit owner approval. Actual trading fees apply.
- No invented prices, trades, identities, performance, profitability, worldwide ranking or success percentages. Historical reported ROI is not a follower success probability.

## Implemented application

1. Broad source-aware catalogue and live quote search: CoinPaprika identities with up to 2,000 delayed aggregate USD quotes, Kraken native crypto spot listings/tickers across actual quote currencies, Hyperliquid native perpetual metadata/allMids. Listings and identical symbols are not silently merged. No source covers every blockchain token.
2. Detailed real books for BTC/ETH/SOL on Kraken and Hyperliquid, with up to six additional selected books. Kraken CRC32, sequencing, clock/freshness checks, disconnect invalidation and bounded reconnects. Quiet extra markets cannot restart healthy core streams. Collector handoff reloads stored selections.
3. Deterministic opportunity finder, skeptic, risk and decision stages; real visible-depth economics, both-leg modeled fees, latency, stale/outage rejection, observed flow/liquidity anomalies and factual forensic records.
4. Protected transactional paper positions, idempotency, modeled cash/fees, $500 actual position / $2,500 correlated-exposure / $200 daily realized-loss caps and emergency stop. Actual depth-adjusted cost is rechecked before writes, so thin-book slippage cannot bypass limits.
5. Causal `observed-breakout-v1` radar over approved Kraken USD spot quotes: ten completed 30-second bins/about five minutes warmup, frozen trigger/entry cap/stop/cost-derived target, gap reset over 15 seconds, 180-second setup life, first-crossing 30-second entry window, fresh matching depth and current risk checks. Targets are mechanical hypotheses, possibly far beyond the sampled range, not forecasts. GO permits a paper experiment only; success odds stay null.
6. Owner-declared real-capital USD profile, cash/exposure/daily P&L and bounded limits. Monetary inputs start blank. Daily/24-hour reconfirmation, visible-depth sizing, downward rounding, cost/risk/cash checks, and expiry tied to both source and receipt freshness. Risk PASS remains trade WAIT; no exchange balance or personal fee tier is verified. Real profiles never change paper cash.
7. Trader Actions in Smart Money: experimental public Hyperliquid candidate search/pagination/Track, actual monitored position changes and position previews, available historical fills/cycles, independent follower evidence and selection disclosures. Historical event reviews cannot imply a current GO. Provider display names are unverified.
8. Candidate feed is a bounded background download, never a page-request download: max100 candidates, 1MiB pending JSON, 100MiB download, 200k rows, 120-second total deadline, cooperative event-loop yields, six-hour cache, last-good timestamp and outage backoff. Dated `trader_cohort` archives preserve original compact metrics/selection. Raw ROI remains unconverted; risk-adjusted rank/odds are null. The provider feed is undocumented and commercial redistribution rights are unverified.
9. Up to ten public wallets, including up to five automatically discovered from actual large Hyperliquid prints; ~30-second full-watchlist position polling. First snapshots are baselines. Available actual historical fills are analyzed with truncation, funding, unfinished cycles and selection limitations. Forward shadow-follow odds require adequate nonoverlapping held-out evidence; no percentage is fabricated during insufficient evidence.
10. Searchable opportunity/radar lifecycle memory, preserved original inputs, edge-persistence autopsies, causal CSV walk-forward lab with embargo, out-of-sample and buy/hold/no-trade comparisons, modeled costs and latency sensitivity.
11. Owner-only Cloudflare Access plus independent backend RS256 owner-token validation, origin checks, persistent API limits/audit and emergency controls. In-app alerts and optional private ntfy delivery; radar queue/retry delivery rechecks current GO, suppresses invalidations and expires. No actual mobile delivery was submitted during release acceptance.

Important versions: `spot-cross-v1.1.0`, `manual-paper-v2`, `paper-risk-v2`. Kraken's conservative modeled public base taker assumption is **80bps per leg**, reviewed 2026-10-23; actual account/product/regional fees require verification. Do not revert to old40bps examples without evidence.

## APIs and source files

- `backend/sentinel/radar.py`, `capital.py`, `leaderboard.py`, `runtime.py`, `app.py`, `engine.py`.
- `/api/radar`, `/api/radar/{id}/paper` with server current-state recheck and stable idempotency, `/api/capital`, `/api/capital/plans`, `/api/connections`.
- `/api/trader-directory?q=&page=1&limit=12` reads approved-provider cache only. `/api/traders` manages protected public watchlist. `/api/records/trader_cohort` exposes dated selection evidence.
- Frontend `radar.tsx`, `capital.tsx`, `connection.tsx`, `radar-archive.tsx`, `trader-discovery.tsx`, `smart-money.tsx`, wired in `page.tsx`.
- Read `docs/RELEASE_0_4.md`, `RADAR.md`, `TRADER_DISCOVERY.md`, `TRADER_EVIDENCE.md`, `ACCOUNT_CONNECTIONS.md`, `PROVIDERS.md`, `MARKET_COVERAGE.md`, `SECURITY.md`, `REGULATORY.md`, `DEPLOYMENT.md` and `DELIVERY.md`.

## Infrastructure

- Cloudflare account `f11da4c37ab8e27585d927a2c3cef02d`; zone `b4675f14f1aefa9233d52d40356ce0f2`; Pages `market-sentinel-ai`; default https://market-sentinel-ai.pages.dev . Production branch main.
- Build root frontend, command `bash ../scripts/cloudflare-build.sh`, output out. Main automatically deploys. Automatic preview builds are disabled; manual preview deployment POST works. Pages logs need `size:10000` and filtering; container logs may appear only near completion.
- Owner Access app `06cba819-2920-4f77-bed3-d2ba9215b0cb`, team https://icy-water-baae.cloudflareaccess.com . Owner email levelupskillz.store@gmail.com. Existing configured audience is pinned server-side. Do not impersonate an owner session or disable auth to inspect private production JSON.
- Render workspace `tea-db64u6h42hec73atqvng`; API `srv-dbdg71jrjlhs73d6cprg`, https://market-sentinel-ai-api.onrender.com ; https://dashboard.render.com/web/srv-dbdg71jrjlhs73d6cprg . Free, Ohio, Python3.12, root backend, one Uvicorn worker, health /health/ready.
- Dedicated free PG16 `dpg-dbde83ks728c73bku27g-a`, market-sentinel-ai-db, Ohio. Internal connection is bound through Blueprint. External access disabled; never open its firewall for tests.
- Blueprint `exs-dbdg49t9fdbs73b16nsg`. Do not create duplicates. No maxShutdownDelaySeconds on Free.
- Render autoDeploy advertises yes/commit but pushes did not trigger deployments. Public Git-URL services can require manual deployment. An unchanged Blueprint Manual sync was a no-op. Inspect current state; follow tool rules; the release used one clear-cache rebuild after source promotion. Do not duplicate an active deployment or falsely say a sync deployed new code.

## Remaining work and next priorities

Production0.4.1 is verified. Finish the active secure Kraken linking/execution and durability work with separate full acceptance before promotion:
- Durable history beyond the expiring database: implement protected export and perform a restore drill on a separate disposable database; choose any replacement only within the user's free-only approval.
- Better independent risk-adjusted trader evidence requires cash-flow-aware histories, documented metric semantics, retained point-in-time cohorts and adequate prospective/out-of-sample observations. Do not turn recent P&L or overlapping windows into a skill score or success odds.
- Expand useful market investigations and validated strategy comparisons with measured false positives, liquidity/latency constraints and realistic execution costs. No automatic promotion from unvalidated outcomes.
- Source rights and eligibility review before commercial signals or distribution; Coinbase is disabled because of current data-use restrictions. ChangeNOW estimates await its separate public business key/use approval, not private exchange keys.
- Kraken owner API-key integration is technically supported. Implement secure encrypted secret storage, restricted permission verification, regional/account eligibility, actual balances/fees/lot rules, immutable short-lived individually approved orders and durable unknown-outcome reconciliation. Partner OAuth remains separately blocked by provider approval. No real-money acceptance trade.
- Chain-wide whale discovery, complete worldwide trader rankings, validated liquidation-cascade models and advanced cross-asset risk are not complete. Do not claim the whole multi-phase mission is finished.

## Working and verification cautions

Workspace `/workspace/market-sentinel-ai`. This resumed environment restored all94 tracked files from exact remote blob hashes and reconstructed a shallow git checkout of `live-market-motion-v041-preview`; local HEAD is the deployed0.4.1 application commit. New next-version files may be untracked. Do not bulk git-add/push. Connected GitHub tools create trees/commits with expected-SHA leases; preserve newer user commits.

Local backend command: `env PYTHONPATH=backend python -m unittest discover -s backend/tests -q`. Frontend dependencies are absent locally; use the Cloudflare release runner for TypeScript/Next/Chromium. The0.4.1 frontend gate has now passed. The three PostgreSQL integration tests require a separate disposable TEST_POSTGRES_URL; never use production.

Shell HTTP proxy was unavailable; sufficient connected GitHub/Cloudflare/Render tools and Cloudflare build runners worked. No credential environments were dumped. Tool store() state can disappear on user steering; persist state in files/commits. Useful metadata: /tmp/market-sentinel-resumed.json, /tmp/market-sentinel-v04.json, /tmp/market-sentinel-release.json.

Documentation-only checkpoint commits can use the verified Cloudflare prefix [CF-Pages-Skip] and Render [skip render] to avoid another application deployment. Confirm actual deployment source separately from a later documentation-only main head.

Continue autonomously within the authorized free read-only/paper/manual-planning scope. Give concise updates, answer steering and retain the goal. Ask only for genuinely missing information, external setup or cost approval, and explain the exact blocker. Passing tests never establishes profitability.

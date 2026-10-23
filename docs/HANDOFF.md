# Market Sentinel AI — current continuation checkpoint

Updated 2026-10-23. Inspect newer repository refs, files, deployment commits, logs and tests before acting; this is a checkpoint, never an instruction to roll back.

## Current milestone

**Production 0.4.0 is verified live.** Application source is `69e97de9bf33a752849118373468cd45acde233c`; main can include a later documentation-only checkpoint without another application deploy. Cloudflare production `033fe02a-33c5-4cbc-8a23-0733973479d4` succeeded 2026-10-23 18:01:15 UTC. Render `dep-dbdq0urncjis73d3pldg` reached live at 18:00:22 UTC on the existing Free service. External acceptance reported app_version0.4.0, both health endpoints200, anonymous/forged direct/proxied data requests401 and custom-domain sign-in302.

Acceptance: **182 Python run,179 passed,3 isolated PostgreSQL skipped;9 Chromium passed; TypeScript, Next.js build, Blueprint schema and dependency audits passed.** Final preview `f820f94d-95da-4d38-ad06-6e8bdd1d33e9` also passed. No known dependency vulnerabilities were reported. Actual full-feed parser probe returned47,622 rows,100 retained candidates,39,183,901 bytes and17,266 peak pending JSON bytes (not whole-process memory). Actual Render logs independently confirmed the same directory load, six fresh BTC/ETH/SOL books, Kraken CRCs and independent radar scans. Process memory was about180MB within512MB. No production paper order or mobile delivery was submitted.

**The user's latest request is a portable continuation prompt. Work is saved; the next application update is NOT deployed.** Resume feature branch **`live-market-motion-v041-preview`**, application code checkpoint **`951f90b9b5444849fca3ec4a2eb7c7f91d182b01`**, tree `6bccded6544186a1fc7e5f5b06e640db9d2cf706`. Later checkpoint commits can advance the branch. Main/production application remains0.4.0 until the next version is tested and deliberately released.

### Prepared 0.4.1 follow-up — needs frontend acceptance

Latest steering: the user wants live graphics and visibly moving data, says raw “LONG ETH-USDC-PERP / Avoid chasing / 0x...” means nothing, and wants easy access to a trader's wallet/actions.

- New `frontend/app/live-market-chart.tsx` prominently on Mission Control and Live Markets: selectable currently detailed markets, actual timestamped sampled midpoints, real time axis, bid/ask/spread, source/receipt ages, bounded180 samples/ten minutes, discontinuous outage segments, hover/keyboard inspection and finite actual-change flashes. New points require a distinct fresh provider timestamp. The latest fix freezes all summary price/bid/ask/spread/source values to the last verified sample when stale/invalid data changes; a regression injects900 after valid103 and expects103 to remain. This fix is saved but not browser-verified.
- Dashboard, visible all-market pages and relevant next-action intelligence poll every2seconds, using the independent backend's provider WebSockets. This is sampled live data, not every exchange tick or a new frontend WebSocket feed. Hidden pages do not fetch; no keep-alive service was added.
- Plain-language ActionBriefing in `smart-money.tsx`: Ethereum/Bitcoin names, rise/fall meaning, perpetual/USDC versus Kraken spot context, original reported average versus current best quote before costs, actual rejection cause, signed favorable/adverse price difference, readable mobile typography. Full public wallet/source detail is expandable and copyable.
- “View this wallet’s actions” calls root navigation to Smart Money and scrolls to that wallet's investigation after actual watchlist data loads. No wallet actions are fabricated from a current position baseline.
- Unvalidated success odds stay “Not validated”; the95% interval card is absent unless a backend-validated estimate exists and both position and market data remain fresh. Two completed observations are not a usable forecast. The minimum100-sample threshold alone is insufficient; seven-day span, held-out calibration, coverage and uncertainty gates still apply.
- Backend `smart_money.py` now maps headlines to actual cause: emergency stop, stale position, missing book, nearby liquidation, adverse entry, historical losses. Favorable drift is not incorrectly called chasing. New optional DTO fields contain actual reported average entry/current fresh best bid/ask, source timestamps and current-position timing caveat.
- Local backend **190 run,187 passed,3 isolated PG skipped**. Eight new backend regression cases pass. Three new ActionBriefing and two live-chart browser cases are written (total expected14 browser cases) but **have NOT run**. The local frontend lacks node_modules/tsc; “tsc not found” is an environment limitation, not a passed typecheck.
- Local app/public version strings say0.4.1; this does NOT mean production runs0.4.1.
- Next step: run the full Cloudflare preview gate on the current feature-branch head, inspect TypeScript/build/Chromium and actual probes, fix failures, and only then promote/deploy the authorized free read-only/paper/manual-planning update. Check stale-source chart freezing, valid/stale odds, mobile sizing, direct-wallet navigation and API rate behavior. Do not skip this gate or call prepared code live.

## Fixed user decisions

- Build an evidence-based crypto investigation and decision product. Prioritize actual data, costs, reliability, explainable rejection, prospective validation and premium mobile usability.
- Dashboard https://market.getlevelupskillz.com . Repository https://github.com/LevelUpSkillz/market-sentinel-ai . User temporarily made the repository public; no secrets in source.
- Keep Next.js/TypeScript on Cloudflare Pages; Python/FastAPI and independent collectors on Render; dedicated PostgreSQL. Completely isolate this from Sentinel Intelligence. Do not move the whole backend to Cloudflare.
- **Free plans only.** No paid upgrades, subscriptions, workers or artificial keep-alive traffic without explicit new cost approval. Render Free can sleep; no 24/7 guarantee. Database expires **2026-11-22 at 04:35 UTC**. Unlimited permanent retention is not available on that expiring database.
- GitHub is source storage; no GitHub Actions CI/deployment. Cloudflare runs checks and dashboard deployment; Render builds the Python backend.
- Latest selected exchange is **Kraken**. The user wants both manual real-capital planning and a future secure connection with individual approval for each real order. No autonomous trades or withdrawals are authorized. Never request exchange private keys, passwords, recovery phrases or seeds in chat.
- No approved Kraken secure account-linking client exists. Connection and order submission remain disabled. A preferred provider or OAuth consent is not approval of future orders. Actual trading fees apply.
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

Finish and verify the prepared0.4.1 follow-up first. Production0.4.0 is already verified. Then improve the product incrementally without restarting:
- Durable history beyond the expiring database: implement protected export and perform a restore drill on a separate disposable database; choose any replacement only within the user's free-only approval.
- Better independent risk-adjusted trader evidence requires cash-flow-aware histories, documented metric semantics, retained point-in-time cohorts and adequate prospective/out-of-sample observations. Do not turn recent P&L or overlapping windows into a skill score or success odds.
- Expand useful market investigations and validated strategy comparisons with measured false positives, liquidity/latency constraints and realistic execution costs. No automatic promotion from unvalidated outcomes.
- Source rights and eligibility review before commercial signals or distribution; Coinbase is disabled because of current data-use restrictions. ChangeNOW estimates await its separate public business key/use approval, not private exchange keys.
- Kraken future execution is externally blocked by provider-approved secure account-linking configuration. Obtain appropriate application permission first; verify region/account/product eligibility, balances, lot rules and actual costs, then implement immutable short-lived individually approved orders and idempotency. No real-money acceptance trade.
- Chain-wide whale discovery, complete worldwide trader rankings, validated liquidation-cascade models and advanced cross-asset risk are not complete. Do not claim the whole multi-phase mission is finished.

## Working and verification cautions

Workspace `/workspace/market-sentinel-ai`. Local git reported all files untracked, with stale local .github content absent remotely. Do not bulk git-add/push. Connected GitHub tools created trees/commits with expected-SHA leases; preserve newer user commits. Current local source contains the prepared0.4.1 feature branch and checkpoint docs, not just the deployed0.4.0 release.

Local backend command: `env PYTHONPATH=backend python -m unittest discover -s backend/tests -q`. Frontend dependencies were absent locally; use the Cloudflare release runner for TypeScript/Next/Chromium. The three PostgreSQL integration tests require a separate disposable TEST_POSTGRES_URL; never use production.

Shell HTTP proxy was unavailable; sufficient connected GitHub/Cloudflare/Render tools and Cloudflare build runners worked. No credential environments were dumped. Tool store() state can disappear on user steering; persist state in files/commits. Useful metadata: /tmp/market-sentinel-resumed.json, /tmp/market-sentinel-v04.json, /tmp/market-sentinel-release.json.

Documentation-only checkpoint commits can use the verified Cloudflare prefix [CF-Pages-Skip] and Render [skip render] to avoid another application deployment. Confirm actual deployment source separately from a later documentation-only main head.

Continue autonomously within the authorized free read-only/paper/manual-planning scope. Give concise updates, answer steering and retain the goal. Ask only for genuinely missing information, external setup or cost approval, and explain the exact blocker. Passing tests never establishes profitability.

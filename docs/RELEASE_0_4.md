# Market Sentinel AI 0.4 — decision desk and public trader actions

This release adds conditional paper-entry research, manual real-capital sizing and a dedicated public trader-actions interface. It does not establish trading profitability or enable exchange orders.

## Behavior

- The radar observes approved Kraken USD spot quotes independently of the dashboard. A causal sampled baseline produces frozen trigger, entry cap, stop and cost-derived target hypotheses. Source gaps reset the baseline; short entry windows expire. A GO permits a paper experiment only after current executable depth and deterministic risk checks. Targets are mechanical hypotheses, not price forecasts. Success odds remain unavailable until validated.
- Real-capital settings start with blank monetary fields and preserve user-declared USD cash, exposure, realized daily P&L and limits separately from virtual paper balances. Sizing uses current visible depth, conservative costs and downward rounding. A numerical risk PASS remains trade WAIT. Plans expire with the remaining lifetime of both source and receipt timestamps.
- Smart Money combines a public Hyperliquid candidate directory, observed changes from monitored wallets, current position previews, available historical fills/cycles and the existing independent follower-evidence review. Provider results are reported metrics, not a verified worldwide skill ranking or an identification of the wallet owner. Raw ROI units are left unverified instead of silently converted into percentages.
- Candidate collection is a bounded background task. The experimental public frontend feed has strict parsing/download limits, a compact cached cohort, backoff and a last-good receipt timestamp. Dashboard searches never start large downloads. Dated candidate cohorts preserve the discovery sample; excluded or absent traders cannot be reconstructed from a current leaderboard.
- Paper fills now recheck actual depth-adjusted notional and aggregate exposure before changing virtual cash. A requested amount cannot bypass the $500 position or $2,500 correlated-exposure limit by walking an unusually thin book. Queued radar pushes recheck current GO conditions before delivery; invalidated signals are suppressed.

## Sources and limits

See [TRADER_DISCOVERY.md](TRADER_DISCOVERY.md), [RADAR.md](RADAR.md), [TRADER_EVIDENCE.md](TRADER_EVIDENCE.md) and [ACCOUNT_CONNECTIONS.md](ACCOUNT_CONNECTIONS.md). The leaderboard is an undocumented official-frontend dependency with no verified publication timestamp, ROI-unit contract, service guarantee or broad commercial redistribution license. Public observed wallet changes have polling latency and do not establish an exact execution time, complete portfolio, risk-adjusted skill or profitable copy trade.

Kraken remains the preferred future exchange connection. A provider-approved secure account-linking client is not configured; account connection, order submission and withdrawals remain disabled. Personal planning and paper experiments need no exchange secrets. Trading fees still apply to any trades the owner places independently.

## Operations and acceptance

Architecture remains isolated Cloudflare Pages plus the existing free Render FastAPI service and dedicated free PostgreSQL. No paid service, keep-alive workaround or live-order acceptance test is used. Free Render can sleep; the free database expires 2026-11-22 at 04:35 UTC. Collection cannot be promised around the clock, nor retention beyond the current database lifetime.

Release acceptance and actual deployment IDs will be recorded after the integrated source passes local backend, Cloudflare TypeScript/build/browser, public-provider, dependency, schema and production-boundary checks. The three isolated PostgreSQL integration checks require a separate disposable test database and must never use production. Synthetic test data is never inserted into production.

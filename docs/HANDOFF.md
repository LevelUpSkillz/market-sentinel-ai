# Market Sentinel AI — continuation checkpoint

Checkpoint created 2026-10-23. This is a snapshot, not an instruction to roll back. Inspect current repository refs, files, deployment commits, logs and tests before acting. Newer verified state and later user instructions take precedence.

## Mission and fixed user decisions

Build a credible, premium crypto investigation and decision platform: live market intelligence, public trader/whale actions, independent copyability analysis, realistic costs, explainable GO/WAIT/NO-GO, forensic investigations, opportunity memory/autopsies, causal strategy validation, paper experiments, real-capital risk planning, and actionable alerts. Reliability and rejection of unsupported opportunities matter more than generating signals.

- Repository: https://github.com/LevelUpSkillz/market-sentinel-ai . The user created it and temporarily made it public. Keep secrets out of source. Do not touch the separate Sentinel Intelligence project or its resources.
- Architecture stays Next.js/TypeScript on Cloudflare and Python/FastAPI plus independent collectors on Render, with dedicated PostgreSQL. Do not migrate the backend/collectors to Cloudflare.
- Strict free hosting/provider plans only. No paid worker, upgrade, subscription or keep-alive workaround without explicit new cost approval. Free Render sleeps; never promise 24/7 monitoring. The current free PostgreSQL expires 2026-11-22 at 04:35 UTC.
- GitHub stores source; no GitHub Actions deployment/CI. Cloudflare runs the frontend build, Python/browser checks, audits and deployment. Keep isolated Market Sentinel names/configuration.
- Latest exchange choice is **Kraken**, confirmed after considering Coinbase. The user wants BOTH manual real-capital planning and a future secure account connection with individual approval of every real order. This does not authorize autonomous trading, withdrawals, exposing secrets or bypassing provider approval/risk gates.
- Actual trading fees still apply. Free hosting does not mean fee-free exchange trades. Never request exchange private keys, passwords, recovery phrases or seeds in chat.
- No fabricated prices, trades, trader identities, historical performance, profitability or success percentages. A public anonymous wallet does not identify a real person. Label real/delayed/unavailable/simulated data and source freshness.
- The user wants premium usability and strong features, all available crypto/token coverage, and a prominent section showing leading public traders' actions. Do not call a venue-specific public leaderboard the verified best traders in the world.

## Verified production before this checkpoint

Production code was version 0.3.0 on main commit `95afa2d02fe9e1b605a3531a63d35b6a7de6ab55`.

- Dashboard: https://market.getlevelupskillz.com . Cloudflare Pages project `market-sentinel-ai`; account `f11da4c37ab8e27585d927a2c3cef02d`. Production deployment `a6c0eb70-6ad7-4b86-a0f0-d9032218bf45` succeeded.
- Backend: https://market-sentinel-ai-api.onrender.com . Render workspace `tea-db64u6h42hec73atqvng`; service `srv-dbdg71jrjlhs73d6cprg`. Deployment `dep-dbdp6aon74is73ee4uig` of the same code reached live 2026-10-23 17:03:51 UTC.
- Dedicated database: `dpg-dbde83ks728c73bku27g-a`, `market-sentinel-ai-db`, PostgreSQL 16, Free, Ohio. Internal connection is bound in Blueprint. External database access is disabled; do not open its firewall to test it.
- Owner-only Cloudflare Access with independent backend RS256 owner-JWT verification; same-origin API proxy and authorization/rate/audit controls. Do not disable auth to inspect private production JSON.
- Public build probes observed about 62,351 catalogue identities, 2,000 delayed aggregate USD quotes, 1,451 Kraken crypto spot listings and 234 native Hyperliquid perpetual listings. Counts change; not every listing has a fresh quote. Source tokens/quote currencies are not silently equated.
- Actual Render logs confirmed broad Kraken ticker collection, Hyperliquid streaming/context, CoinPaprika cache loads, six fresh BTC/ETH/SOL books and healthy readiness. Memory was about 207 MB within the existing Free instance.
- Detailed core books: BTC/ETH/SOL; six additional selected books allowed. Paper fills require real fresh USD spot depth. Coinbase remains disabled pending data-use permission; ChangeNOW read-only estimate adapter remains unavailable without its separate business key/use approval. No private exchange keys were requested.
- Version 0.3 acceptance: 113 Python tests passed, three isolated PostgreSQL checks skipped, four Chromium tests passed, TypeScript/Next build/Blueprint/audits passed. No profitability was established.

See `docs/RELEASE_0_3.md`, `PROVIDERS.md`, `MARKET_COVERAGE.md`, `DEPLOYMENT.md`, `SECURITY.md` and `REGULATORY.md` for details.

## New work saved in the preview branch, not yet production

Resume from branch **`decision-desk-v04-preview`**. Code checkpoint: `5eaf43aa5aa012ba711b203032a4ee277b7f4ece`; tree `da82b364ba665e878513ffe9c3f6892a1da12d88`. Later checkpoint/documentation commits may advance this branch. Inspect its current head, not only this SHA. Main was still the production commit above.

Cloudflare preview deployment **`ba9f2d81-0652-4b21-9c7f-f8bbc9b7ffec`** succeeded on code `5eaf43aa5aa012ba711b203032a4ee277b7f4ece` at 17:33:03 UTC: 147 Python checks passed, three PostgreSQL checks skipped, seven Chromium checks passed, and TypeScript/Next build/Blueprint validation/dependency audits passed. Its production health probe still correctly reported backend 0.3.0: the new backend was NOT deployed. The later prepared trader-discovery component was not in that tested build and still needs type/browser acceptance after integration. Inspect newer results before acting. Pages logs should be requested with `size:1000` and filtered before printing; default logs may show only cloning.

Implemented preview features:

1. `backend/sentinel/radar.py`: fixed, causal `observed-breakout-v1` conditional-entry radar over approved Kraken USD spot quotes. Ten completed 30-second sampled bins/about five minutes warmup, fresh provider times, no gap filling. A source gap over 15 seconds invalidates old setups and resets history. Frozen trigger, entry cap, stop and cost-derived target; actual crossing; 180-second setup expiry and 30-second entry window. Fresh matching depth, current entry/exit liquidity, costs and existing risk limits required. GO is paper eligibility only; no validated edge or invented probability. Target is a mechanical hypothesis, possibly far beyond the sampled range, not a forecast.
2. `backend/sentinel/capital.py`: separate owner-declared USD real-capital profile, cash/exposure/daily P&L and risk limits, bounded numeric input, daily/24-hour reconfirmation. Sizing uses real visible depth, modeled costs and downward rounding; risk PASS still retains trade WAIT and execution disabled. It never changes the virtual account.
3. `app.py`/`runtime.py`: independent supervised radar job, `/api/radar`, idempotent `/api/radar/{id}/paper` with server rechecks, `/api/capital`, `/api/capital/plans`, `/api/connections`, archived radar/real-plan records, short-lived in-app alerts and expiry protection before optional ntfy retry delivery.
4. Premium components `radar.tsx`, `capital.tsx`, `connection.tsx`, `radar-archive.tsx`, page wiring and responsive styling: conditional trade briefs, deadlines/freshness, separate real-budget calculations, explicit Kraken setup status, searchable historical lifecycle autopsies. Historical GO cannot authorize a current entry. Real-capital form monetary fields start blank. Radar never invents example trades to fill empty state.
5. Conservative Kraken fee assumption updated from 40 to **80 bps per leg**, based on the current public base taker schedule. Actual personal/product/regional fees remain unverified. `spot-cross-v1.1.0`, `manual-paper-v2`, `paper-risk-v2` preserve version distinctions; paper records store fee values. Do not revert this from stale old examples without checking current official/account fees.
6. Local full backend suite: **150 run, 147 passed, 3 skipped**. New tests include 13 radar, 12 capital and 9 ASGI integration cases. All seven Chromium tests passed in the preview, including three new synthetic tests for real-capital saving, stale GO rejection and risk PASS versus trade WAIT. TypeScript/Next build also passed for that tested code; the later unwired trader-discovery file was not included and must be checked before promotion.

Read `docs/RADAR.md` and `docs/ACCOUNT_CONNECTIONS.md` before changing these semantics. Tests are explicitly synthetic fixtures and are never seeded into production.

## Immediate unfinished request: leading public traders and actions

The user requested a dedicated section showing the actions of the best traders in the world. Current production already monitors up to ten public wallets, five auto-discovered from actual large Hyperliquid prints, with public positions, changes and available actual fill-history reconstruction. That is not global skill ranking.

Prepared frontend **`frontend/app/trader-discovery.tsx`** is saved in this preview branch as unfinished integration. It has authenticated candidate search/pagination, actual monitored events/position previews and Track actions callbacks; reported metrics and provider units are explicit. It is NOT imported/wired into `page.tsx`, has no backend directory endpoint, and has not been type/browser tested. Do not present this as an implemented working leaderboard.

No `backend/sentinel/leaderboard.py` or leaderboard tests were written yet. Planned next steps:

- Verify the real public official-frontend feed `https://stats-data.hyperliquid.xyz/Mainnet/leaderboard` from the network-capable Cloudflare runner. The official UI is https://app.hyperliquid.xyz/leaderboard . No official documented API contract or commercial redistribution license was verified. Browser retrieval failed; third-party schema claims are not real acceptance.
- Reported, unverified shape: `{leaderboardRows:[{ethAddress,accountValue,displayName,windowPerformances:[[day|week|month|allTime,{pnl,roi,vlm}]],prize}]}`. Validate actual response before claiming fields/units/ROI semantics.
- The feed may be roughly 40 MB. Do not load a full body plus full parsed JSON on the 512 MB Render instance. Use bounded incremental UTF-8/JSON row parsing, about 1 MB maximum pending buffer, explicit total download/row bounds, retain compact bounded candidate summaries (e.g. top 100), cache six hours and back off on errors. Keep last good data with its original receipt time. Source event timestamps are not verified.
- Implement owner-only `/api/trader-directory`, then wire TraderDiscovery into Smart Money with existing traders/events/onTrack. Respect ten tracked-wallet capacity, actual polling limits and preserved dated cohorts. Test malformed/chunked/oversized input, cache/outage handling, pagination, no invented odds/identity and real feed contract acceptance.
- Candidate selection must use transparent multi-window/data-availability criteria, disclose survivorship/selection bias and overlapping windows, and NOT equate reported recent P&L with independently validated skill. Unknown drawdown, cash-flow-adjusted returns and copyability stay unavailable. Independent ranking/success probability must remain null without evidence.
- Official portfolio data is documented: POST `https://api.hyperliquid.xyz/info` with `{type:'portfolio',user:'0x...'}` returns window tuples with accountValueHistory, pnlHistory and vlm. Raw equity history is confounded by deposits/withdrawals; do not label it cash-flow-adjusted drawdown or validated skill. Primary docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#query-a-users-portfolio .

## Exchange connection is genuinely blocked, not secretly complete

Latest provider choice is Kraken. Its current developer index places OAuth REST under Embed/B2B partner agreement, and legacy Connect requires provider-provisioned client credentials. No approved client exists here. The app correctly says not connected and order submission disabled.

Coinbase's official OAuth quickstart currently limits new clients to approved partners and says new client creation is temporarily disabled; its data-use terms are separate. It is not a free instant alternative. Neither OAuth consent nor a paper risk pass constitutes approval for future orders. Before future execution, obtain suitable approved app configuration/data rights, verify actual account/region/product eligibility, execution-venue quotes/fees/balances/lot rules, immutable per-order review, expiry and idempotency. Never enable withdrawals or autonomous LLM execution. No real-money order should be used as an acceptance test.

Sources: https://docs.kraken.com/llms.txt ; https://docs-legacy.kraken.com/api/docs/oauth/kraken-connect/ ; https://www.kraken.com/features/fee-schedule ; https://docs.cdp.coinbase.com/coinbase-app/oauth2-integration/quickstart .

## Resume and release workflow

1. Inspect latest branch/main refs and actual live deployment commits. Preserve all work, isolate Market Sentinel and read relevant project/skill instructions. Continue implementation; do not restart with only a plan or mock dashboard.
2. Check the existing preview build result and fix real failures. Finish the trader-discovery vertical slice and its real-data probe. Keep unavailable states honest if provider access/schema is unavailable.
3. Run meaningful checks: `env PYTHONPATH=backend python -m unittest discover -s backend/tests -q`. The comprehensive Cloudflare command is `bash ../scripts/cloudflare-build.sh` from frontend; it runs Python checks, real public probes, Blueprint validation, dependency audits, TypeScript/Next build and Chromium. The three PostgreSQL integration tests require a separate disposable `TEST_POSTGRES_URL`; never run destructive tests against production.
4. Only promote the tested preview code after required checks pass. Verify server-side auth, expiry, risk, idempotency and paper/real-account separation. No fake production data or live-order test.
5. Deploy frontend on Cloudflare and backend on the existing free Render service. Current Render Git auto-deploy flag says enabled but pushes did not start deployments. Blueprint Manual sync with unchanged YAML was a no-op. The last successful backend release used one deliberate full rebuild with cleared build cache through the Render tool; inspect current behavior and follow current tool instructions, avoiding duplicate deploys or paid changes. Never falsely tell the user a sync deployed new code.
6. Verify actual deployed source/version, readiness, authenticated boundaries and real collector/radar logs. After deployment radar must warm up; no candidate is an acceptable real outcome. Report features, limitations, costs, test results, URLs and anything still blocked. Do not confuse tests with trading profitability. Update this handoff when the state changes.

## Workspace/tool cautions

The shared workspace was `/workspace/market-sentinel-ai`. Local git status showed all files untracked; some stale local files, including old `.github` content, were not present in the remote source tree. Do not blindly `git add .`. GitHub connected tools wrote trees/commits/refs using expected-SHA leases. Source promotion is not a GitHub Actions deploy.

Shell HTTP/network was denied and repeated network/approval requests previously caused stalls. Prefer sufficient connected GitHub/Cloudflare/Render tools and Cloudflare build runners for networked builds/probes. Local Python checks work; local frontend dependencies were not installed. Do not expose credential environments or disable database/auth protections to work around a tool limit.

`/tmp/market-sentinel-v04.json` and `/tmp/market-sentinel-release.json` contained useful local release metadata. Tool `store()` data was lost after new user messages, so persist important state in files and remote commits. Give concise progress updates at least every minute during active work and answer user steering while preserving the task. No unnecessary confirmations: the implementation and free read-only/paper/manual-planning deployment are already authorized.

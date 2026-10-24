# Delivery status — premium workspace 0.6.0

Verified live October 24, 2026:

- App https://market.getlevelupskillz.com ; Live Money /#live-money ; Market Radar /#radar.
- Exact application source 388ee3fced05513218b93b437bc5e6ad59ecd2ed.
- Cloudflare production 4103d811-df2a-4946-b367-91f8dd7ebfd5 succeeded at 19:48:41 UTC (15:48 Toronto).
- Render dep-dbegl0tg1s2s73fhkj90 reached live at 19:44:52 UTC on the same source, existing Free service and unchanged vault/connection configuration.
- Preview 20f3b097-e7b0-44d3-82a2-fcc567e86373 passed before promotion: all 260 Python checks with actual isolated temporary PostgreSQL and zero skips, 25 Chromium checks, TypeScript/Next build, Blueprint schema and dependency audits. Production repeated the checks successfully. No known dependency vulnerabilities were reported.

External acceptance at 19:48:30 UTC verified backend 0.6.0, ready/live HTTP 200, manual-only approval boundaries, anonymous/forged direct/proxied APIs HTTP 401 and custom-domain sign-in HTTP 302. New Render logs showed 255, 258 and 242 fresh USD observations per scan during warmup; older trade-triggered production scans showed about 14–17. These are distinct timed observations, not a fixed coverage guarantee or profitable strategy validation.

Delivered: a new slate/mint research and gold real-capital visual system; grouped navigation and mobile quick navigation; bookmarkable screens; dedicated Live Money Overview, Budget & limits, Trade ticket and Connection; actual manually refreshed Kraken balances/open orders with freshness; separate declared capital; explicit pause control; current verified bid/ask helper; immutable validation/exact individual approval; safe unknown-order reconciliation; latest-50 owner-only app order journal. No total portfolio valuation, filled-trade claim or real profitability is invented. Private backup remains in Settings.

The radar now subscribes to documented BBO changes for Kraken USD spot, retains five-second freshness and strict baseline/entry/risk gates, and versions its observation input as observed-breakout-v1.1. New observation rows expose actual midpoint/source times, ten-bin warmup progress and five-minute movement only after the full continuous baseline exists. Filters/search organize actual candidates. GO remains paper-only and success probabilities remain unvalidated. The old duplicate historical chart/poll was removed while actual live sampled charts remain.

The first preview attempts caught JSX/nullable typing errors and then an accessible-name change from the REAL navigation badge plus an obsolete history-poll expectation. These were corrected, not skipped. Final financial and failure-recovery browser checks all passed. The mobile design review used explicitly labeled synthetic fixtures, never production balances.

Owner reports Kraken is connected. Engineering did not read credentials, impersonate the owner, submit a real-money order, send a mobile alert or rotate the vault key. No paid service/upgrade, keep-alive workaround or Sentinel Intelligence modification occurred. Hosting remains free within quotas, actual Kraken trading fees apply, Render can sleep, and the free PostgreSQL expires November 22, 2026 at 04:35 UTC. No 24/7 guarantee or permanent offsite archive is claimed.

Google sign-in / friend access is a separate next milestone, NOT part of 0.6.0. The user selected read-only markets/radar/public-trader access and requested Supabase for authentication only. Existing Sentinel uses Supabase Google; Market will keep its own invitations, roles and data in Render PostgreSQL. The owner reports adding the Market callback redirect. New research hostname market-research.getlevelupskillz.com is attached to the same Pages project; authentication code is still under separate implementation/testing and must not be called live yet. No Sentinel code, RPC, RLS policy or database was changed. The Supabase dashboard also showed an actual organization quota warning; no paid upgrade is authorized.

# Prior release — 0.5.0

Version 0.5.0 application source b23fb6c559ff28c60ff683ecdad98af3bdf0d6a8 is deployed:

- Dashboard: https://market.getlevelupskillz.com . Cloudflare production 02f1e365-d4f1-4e26-8c1d-c1879775b0ac succeeded at 04:57:09 UTC.
- Backend: https://market-sentinel-ai-api.onrender.com . Render dep-dbe3jkvb9u1s73c2ec7g reached live at 04:54:41 UTC on the same source and existing Free plan.
- Preview acceptance: 33b91f87-0515-4142-a2cd-4c541f1e17b9 succeeded at 04:51:53 UTC. All 256 Python checks passed with zero skips against isolated temporary PostgreSQL, including nonce serialization, overlapping-instance locks and backup/restore; 21 Chromium tests passed. TypeScript/Next build, Blueprint schema and both dependency audits passed with no known vulnerabilities. Actual public-provider probes observed Kraken CRC books, Hyperliquid books/positions/history, 1,685 native venue markets, 942 distinct streaming quote records during bounded sampling and a 100-candidate public trader cache. These are timed build-runner observations, not an exhaustive permanent coverage or independent trader-skill claim.

External production checks at 04:56:54 UTC verified app_version 0.5.0, both health endpoints HTTP 200, manual real-order capability enabled, individual approval required, autonomous trading false and withdrawals false. Anonymous/forged direct and proxied dashboard requests returned HTTP 401; custom-domain anonymous access redirected to sign-in with HTTP 302. These probes used no owner session or account credentials.

The integrated account feature supports restricted encrypted own-account Kraken keys, actual balances/open orders/fees/pair rules, broad eligible USD spot markets with selected fresh CRC books, conservative profile/exposure limits, immutable 30-second validate-only review, exact typed approval, one IOC submission, durable intent/idempotency and unknown-outcome manual reconciliation. No protective stop is placed and the full buy plus fee reserve counts as at-risk. Initial hard limits are 500 USD per order/asset and 2,500 USD correlated exposure; lower owner limits apply. Unsupported portfolios fail closed. Every real order is an individual owner instruction, never an autonomous AI action or validated profitability claim.

A separate Render-only Fernet vault secret and manual-spot feature flag were provisioned with merge-only environment updates. Existing variables were preserved. No credentials were collected, no account was connected, no private provider request or actual-money order was used in acceptance. The owner links only inside authenticated HTTPS Settings → Your Kraken account, using a dedicated restricted Kraken key. Never send credentials in chat. A watched wallet is not a connected spending wallet. No self-custody signer, withdrawal, transfer, borrowing, leverage or derivative execution is implemented.

Settings now offers protected bounded research/accounting backup download; isolated actual PostgreSQL export/restore passed. Credentials/sessions/nonces are excluded, original financial IDs and unresolved blockers preserved, and restored orders are permanently non-submittable. This does not mean a production archive is already downloaded/offsite, nor does it provide automatic backups or permanent retention.

Production logs on new instance srv-dbdg71jrjlhs73d6cprg-7hgkz confirmed independent collection after deployment: all six BTC/ETH/SOL Kraken/Hyperliquid books persisted as live at 04:55:41 and 04:56:41 UTC, with source/receipt timestamps. Radar resumed over a 620-market eligible quote universe and correctly remained collecting during warmup. Deployment did not depend on opening the dashboard.

Costs remain $0 within current free quotas. No paid upgrade, service duplication, keep-alive workaround or change to Sentinel Intelligence was introduced. Actual exchange trading fees apply. Render Free can sleep, so 24/7 monitoring and protective execution are not guaranteed. The free dedicated PostgreSQL expires November 22, 2026 at 04:35 UTC; preserve protected archives and arrange a suitable replacement before then.

Limits remain: no independently proven profitable strategy or validated follower success odds, no worldwide verified best-trader ranking, no complete every-token/on-chain coverage, and no commercial signal launch. Coinbase research remains disabled for data-use restrictions; ChangeNOW awaits its separate public business key/use approval. Hyperliquid candidate-feed metric units/commercial redistribution rights remain unverified. See HANDOFF.md for the continuing mission and exact boundaries.

No owner session was impersonated to inspect protected production JSON. Browser fixtures and database drills are synthetic and never inserted into production. No real-money order or mobile notification was sent for release verification. Passing checks is not proof of trading profitability.

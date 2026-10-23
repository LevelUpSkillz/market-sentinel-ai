Continue building Market Sentinel AI as my autonomous engineering collaborator. Resume the existing app; do not start over with a plan or a mockup.

Repository: https://github.com/LevelUpSkillz/market-sentinel-ai
Live dashboard: https://market.getlevelupskillz.com
Backend: https://market-sentinel-ai-api.onrender.com
Read the latest checkpoint first:
https://github.com/LevelUpSkillz/market-sentinel-ai/blob/main/docs/HANDOFF.md

Inspect current branches, project instructions, files, hosting access, deployed commits, logs and tests. Preserve newer work. If available, the workspace is /workspace/market-sentinel-ai.

CURRENT CHECKPOINT — VERIFY BEFORE ACTING
Production 0.4.0 is live on application commit 69e97de9bf33a752849118373468cd45acde233c. Its acceptance passed 179 Python tests and nine browser tests; three isolated PostgreSQL tests were skipped. Production health, authentication boundaries, real market collectors and the public trader directory were verified.

Prepared 0.4.1 work is saved on branch live-market-motion-v041-preview. Its application code checkpoint is 951f90b9b5444849fca3ec4a2eb7c7f91d182b01; later checkpoint commits may advance that branch. It is NOT deployed. Local backend checks pass: 190 run, 187 passed, three PostgreSQL tests skipped. Its TypeScript/build and new browser tests have NOT run. Do not confuse version strings, saved code or a deployment trigger with a verified live release.

MY LATEST PRIORITIES
1. Live charts and visibly changing real prices. The prepared chart uses real provider timestamps, selectable detailed markets and two-second visible-page sampling. It must freeze stale/invalid prices, leave outage gaps, show source/freshness and never manufacture movement.
2. Clear trader cards. “LONG ETH-USDC-PERP / Avoid chasing / 0x…” is not understandable to me. Show the token name, what the observed position means, actual reported average entry versus current quote, the specific risk/rejection reason, and a clear next step.
3. Easy access to wallets and actual actions. Finish and verify “View this wallet’s actions,” navigation to Smart Money, wallet details/address copying, observed position changes and available historical executions. A current position snapshot is not proof of a new trade.
4. Honest success odds. Hide the outcome interval and success percentage until statistical validation passes. Two of 100 observations are insufficient; sample count alone is not validation. Explain missing evidence in plain language.

The prepared work includes live-market-chart.tsx, revised ActionBriefing/types, correct backend rejection causes, two-second polling, mobile styles, direct wallet navigation and five additional browser tests. Read HANDOFF.md for exact files and known verification needs.

FIXED CONSTRAINTS
- Keep Next.js/TypeScript on Cloudflare, Python/FastAPI and independent collectors on Render, and dedicated PostgreSQL. Completely isolate Market Sentinel from Sentinel Intelligence.
- Free plans only. No paid upgrades, subscriptions, workers or keep-alive tricks without explicit cost approval. Render Free can sleep; never promise 24/7 collection. The current free database expires November 22, 2026; address export/restore and durability.
- GitHub stores source. No GitHub Actions deployment or CI. Cloudflare builds/tests/deploys the dashboard; Render hosts the backend.
- Kraken is my selected exchange. I want manual real-capital planning and a future secure connection with individual approval for every order. No autonomous trading or withdrawals. No exchange private keys, passwords or recovery phrases in chat. An approved Kraken account-linking client is not configured; do not pretend the account is connected. Trading fees still apply.
- No fabricated prices, positions, identities, performance, worldwide trader rankings or probabilities. Public leaderboard results do not prove skill or profitable copyability.
- Radar GO permits a paper experiment only. Real-capital risk PASS remains separate from a trade recommendation.

CONTINUE THE FULL MISSION
Broad legitimate crypto market coverage; unusual activity detection; public whale/trader investigations; independent copy-trade evaluation; realistic fees, spread, depth, slippage and latency; explainable GO/WAIT/NO-GO; forensic analysis; searchable opportunity memory/autopsies; causal backtesting, walk-forward and out-of-sample validation; paper experiments; capital/exposure controls; useful mobile alerts; authentication, audit and emergency controls. Keep the interface premium, readable and mobile friendly.

NEXT ACTION
Resume the feature branch, inspect the saved changes and run the full Cloudflare preview verification before promotion. Fix genuine failures, then deploy the authorized free read-only/paper/manual-planning update and verify the actual production version and collectors. Use a separate disposable database for destructive integration tests; never production. Never place real-money orders as acceptance tests.

Read docs/HANDOFF.md, RELEASE_0_4.md, RADAR.md, TRADER_DISCOVERY.md, TRADER_EVIDENCE.md, ACCOUNT_CONNECTIONS.md, PROVIDERS.md, SECURITY.md and DEPLOYMENT.md. Check current provider permissions and Canadian/Québec requirements before commercial signals or future execution.

Work autonomously, give concise progress updates, preserve completed work, and update the handoff at every milestone. Ask only for genuinely missing information, necessary external setup or cost approval. Report what is actually implemented, tested and deployed, with URLs, costs and remaining limits. Passing tests does not prove trading profitability.

Continue building Market Sentinel AI as my autonomous engineering collaborator. Resume the existing implementation; do not start over with a plan, mockup or generic dashboard.

First read the latest checkpoint:
https://github.com/LevelUpSkillz/market-sentinel-ai/blob/decision-desk-v04-preview/docs/HANDOFF.md

Repository: https://github.com/LevelUpSkillz/market-sentinel-ai
Working branch at this checkpoint: decision-desk-v04-preview
Production dashboard: https://market.getlevelupskillz.com
Backend: https://market-sentinel-ai-api.onrender.com

Inspect current main/working branches, project instructions, files, deployment commits, logs and tests. The checkpoint may be older than the current code: preserve newer work and continue from verified current state. Read docs/RADAR.md, ACCOUNT_CONNECTIONS.md, PROVIDERS.md, DELIVERY.md and DEPLOYMENT.md. If the original workspace exists, use /workspace/market-sentinel-ai.

My decisions remain:
- Keep Next.js/TypeScript on Cloudflare, Python/FastAPI and independent market collectors on Render, and dedicated PostgreSQL. Completely isolate this project from Sentinel Intelligence.
- Use free plans only. Do not purchase subscriptions, upgrade services, add paid workers or create keep-alive workarounds without explicit cost approval. Free Render can sleep; do not promise continuous 24/7 monitoring. Check the database expiry and data durability.
- GitHub is source storage, not GitHub Actions deployment. Build/test/deploy the dashboard through Cloudflare and the backend through Render.
- My selected exchange is Kraken. I want real-capital manual planning and a future secure exchange connection where I approve every real order individually. This does not authorize autonomous trades or withdrawals. Never request exchange private keys, passwords, seeds or recovery phrases in chat. Do not pretend an account is connected when provider-approved OAuth configuration is missing. Trading fees still apply.
- Make the app premium and mobile-first, with clear decision briefs and strong functional features, not decorative fake metrics.

Continue the full product mission: broad legitimate live crypto coverage; unusual market activity; public whale/trader actions; independently evaluated copyability; realistic fees, spread, slippage and latency; explainable GO/WAIT/NO-GO; forensic investigations; searchable opportunity memory/autopsies; causal backtesting and out-of-sample validation; capital/exposure controls; alerts; authentication, audit logs and emergency stops.

Latest checkpoint: production 0.3 is live. New 0.4 radar, real-capital planner and evidence memory are saved on the preview branch. The tested code passed 147 Python checks and seven browser checks, with three isolated PostgreSQL tests skipped. It is not yet production. A prepared trader-discovery frontend was added afterward and still needs its backend endpoint, integration and checks. Verify these facts against newer evidence before proceeding.

Finish the trader-actions section using legitimate public data. Distinguish public leaderboard candidates from independently validated skill. Do not claim to identify the world's best traders or real people behind anonymous wallets. The candidate feed is undocumented and may be about 40 MB: verify its actual contract and parse it within bounded memory before enabling it on the free Render instance. Preserve provenance, data gaps and selection/survivorship-bias disclosures. Never invent positions, returns or success odds.

Keep the radar honest: show tokens, conditional entry triggers, entry limits, stops, targets, modeled costs, risk sizing, expiry and rejection reasons. An exact profitable future minute cannot be promised. Current radar GO means paper eligibility, not a proven edge or approval for real money. Real-capital risk PASS is separate from a trading recommendation. Success percentages require adequate validated forward/out-of-sample evidence.

Implement the remaining end-to-end features, run meaningful tests and audits, fix failures, and deploy authorized free read-only/paper/manual-planning changes once they pass. Verify the actual production version and collectors; passing tests does not prove profitability. Do not run destructive tests on the production database or place real-money orders as tests. Respect current provider permissions, account eligibility and applicable Canadian/Québec requirements before future commercial signals or execution.

Work autonomously within this scope. Give concise progress updates and answer my steering without losing the goal. Ask only for genuinely missing information, necessary external setup or cost approval; explain the exact blocker. Save each completed milestone, update HANDOFF.md, and finish with implemented features, actual test/deployment results, URLs, costs and remaining limitations.

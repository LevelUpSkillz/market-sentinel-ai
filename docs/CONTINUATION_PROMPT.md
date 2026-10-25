Continue Market Sentinel AI from its CURRENT implementation. Do not restart,
produce only a plan, or overwrite newer source with an older checkout.

First read current main docs/HANDOFF.md and docs/DELIVERY.md, then inspect actual
refs, source, tests and deployments. Current published dashboard is terminal
0.6.3 on Cloudflare, source 1033c5fa035831bac2cf3490cf94e523d7da6edf, production 1cd76ab6-008f-460b-8bd1-ec307b449ba1, completed
2026-10-25T03:35:24.158732Z. Backend remains 0.6.2 on Render source
4b768b3ff1c9452a34b2bb4b7027c5db6c977f00. Use
/workspace/market-sentinel-cloudflare-ai if this workspace exists; old premium,
premium-ui, release and market-sentinel-ai directories are stale.

App https://market.getlevelupskillz.com
Repo https://github.com/LevelUpSkillz/market-sentinel-ai

I want a premium minimalist futuristic market panel as user-friendly as Coinbase,
Kraken or Crypto.com, with restrained NASA-style live graphics. Keep plain labels,
readable mobile charts, a clear next action, tutorial/help, and a strong distinction
between research, practice and Live Money. Show actual source/freshness everywhere;
no fake activity, prices, profits, identities, world rankings or success odds.

0.6.3 includes chart-focused Home, public trade activity, coverage/connection
telemetry, market shortcuts, actual historical line/candle zoom/pan/reset,
expandable visible depth and clear Big Traders cards. Trader views: Open positions,
Actual executions, Closed trades, Observed changes. Show token, direction, available
entry/fill price, quantity, USDC value, margin, fees and open versus closed result.
Historical snapshot changes must not borrow current P&L or invent missing entry
prices. Closed results exclude funding; previous wins are not my odds of success.
Existing tutorial, Workers AI, radar, history/autopsies, strategy validation,
manual practice, real-capital planning, backups and Live Money must stay intact.

Keep Next.js/TypeScript Cloudflare frontend, Python/FastAPI and independent
collectors on Render, dedicated PostgreSQL. Completely isolated from Sentinel
Intelligence. FREE ONLY: no paid plans/upgrades/credits or keep-alive tricks.
Render Free can sleep, so never promise 24/7 monitoring. Current free PostgreSQL
expires November 22, 2026 at 04:35 UTC; protected export is not permanent offsite
retention. User screenshot already confirmed Workers Free as the current plan.

Kraken is selected. Only individually approved USD spot IOC limit orders are
currently authorized: immutable fresh 30-second review, exact typed PLACE THIS
REAL ORDER, deterministic limits, durable intent and one submission. Unknown
outcomes must block resends until explicit reconciliation. No autonomous real
trading, withdrawals, transfers, leverage, borrowing, derivatives or engineering
real-money test orders. Planning stops are not attached exchange orders. Preserve
vault-key precedence and credentials; never retrieve, expose, rotate or request
secrets in chat. Never let AI submit orders or override risk rules.

Workers AI is on-demand explanation / skeptical review / English-French /
meaning-based search over public allowlisted evidence only. Keep persistent
4/minute and 30/day quotas and logging off; no private account data in prompts.

Owner email-code Access sign-in is configured without forced Cloudflare admin
redirect; exact owner policy/audience remain intact. Google research-only friend
login is SAVED BUT NOT DEPLOYED on feature/supabase-research-access at
19fcfddac0526eeda25d307df892705cd9ea11e3. Rebase onto current UI and run all
OAuth/PKCE/proxy/revocation/viewer gates before deployment. Supabase identity only;
Market roles/data remain in Render PG. Friends see markets/radar/public trader
research only, never owner capital/accounts/orders/paper/private history/settings.

A question about an automatic bot did not authorize automatic real-money trading.
A validated automatic PRACTICE bot is possible future work, not shipped. Glitches
may be invalid or unfillable; all-time lows do not guarantee a rebound.

Latest release passed 273 backend checks with actual isolated PostgreSQL / zero
skips and 38 Chromium tests, type/build/AI/schema/audit gates, real public probes
and protected production checks. These tests prove no profitability. Work
autonomously, give concise updates, validate meaningful behavior, verify the
actual published source and save an accurate checkpoint. Avoid asking me to
repeat already answered questions or making paid changes without authorization.

# Professional readiness review — October 25, 2026

Reviewed frontend Graphite Edition 0.7.1 (application source
7b47e1c1ae632b60f6727d45be5ee317056ef384) and the existing Render 0.6.2 backend.
Current state: functional owner-only private beta. No numeric readiness score or
profitability claim is justified. This is a source/configuration review; private
balances, credentials and actual owner orders were not inspected.

## Existing foundation

Actual source-aware market feeds, book integrity/freshness checks, collector
supervision/reconnects, deterministic risk/cost checks, evidence memory, prospective
shadow-follow machinery, historical validation tools, paper accounting, restricted
Kraken vault, exact individual approval and no-resend reconciliation, audit records,
manual research export/restore, protected owner access, AI explanation/search and
mobile controls. Current release passed 273 backend tests with isolated PostgreSQL
and zero skips, 47 Chromium tests and existing build/contracts/probe/audit gates.
Passing these checks does not prove profitable trading or operational availability.

## Ordered gaps and acceptance criteria

| Priority | Area | Present | Still required for professional use |
| --- | --- | --- | --- |
| P0 | Continuous operation | Backend collectors run independently of dashboard; recovery/health checks exist | An approved hosting arrangement that actually stays awake, measured feed continuity and explicit coverage/freshness objectives. Render Free can sleep; no artificial keepalive. |
| P0 | Durable history/recovery | Dedicated PostgreSQL, consistent manual exports and tested disposable restore | Replace the current expiring database before November 22, 2026 at 04:35 UTC; scheduled protected offsite backups, monitored completion/expiry and periodic restore drills from actual archives. The manual export is limited to 16 MiB/100,000 records and is not permanent retention. |
| P0 for reliance on account protection | Trade lifecycle | Immutable reviews, deterministic limits, durable one-shot intent and explicit reconciliation | Actual fills/fees/balance reconciliation in a clear account ledger; tested partial-fill/cancel/recovery flows; carefully designed exchange-held protective exits where supported. Planning stops/targets do not place stop orders. Emergency stop does not cancel already accepted exchange orders. Current buy risk conservatively includes the full purchase. |
| P1 | Evidence of useful decisions | Backtesting/walk-forward tools and prospective shadow-follow gates | Freeze at least one strategy, collect enough clean forward outcomes, evaluate after realistic fees/slippage/latency/funding, compare against benchmarks across regimes and report uncertainty, drawdown and missing data. Radar thresholds remain unvalidated hypotheses. |
| P1 | Probabilities | Sample/coverage/held-out/Brier/interval checks withhold weak estimates | Adequate actual prospective evidence, dependence-aware uncertainty, stronger calibration evaluation and drift monitoring. Existing global calibration checks are not comprehensive validation; historical win rate is not follower odds or expected profit. |
| P1 | Operations and mobile alerts | Readiness, client issue status, logs, supervised tasks, queued/expiring optional ntfy alerts | Monitoring independent of the app process, incident notifications, provider/asset data-gap and latency metrics, measured phone delivery latency/receipt and documented incident recovery. ntfy is at-least-once and a send/commit crash can duplicate delivery. Configuration does not prove device delivery. |
| P1 before invitations | Authentication and isolation | Verified owner-only Access; research Google-login work saved separately | Rebase and publish the Google invitation branch only after OAuth/PKCE, revocation and server-side viewer isolation are proven. Research viewers must never access owner capital, accounts, orders, private journals or mutations. Google invites are not live. |
| P1 | Security assurance | Restricted API permissions, encrypted vault, server-side auth, limits and audit journal | Independent application/security review, stronger operational MFA/session and secret-management procedures, recovery exercises and externally protected audit retention. Existing audits check dependencies; they are not a penetration test. |
| P1 | Usability | Existing tutorial, clear research/practice/Live Money sections, mobile tests, actual charts and detail views | First-time-user task testing: understand an idea, identify token/venue/currency, entry/expiry, risk in cash and next action without coaching. Keep diagrams secondary to actionable evidence and make unavailable states clear. |
| P2 | Public-trader and market depth | Broad indicative listings, selected detailed books and public Hyperliquid snapshots/fills | Explicit coverage and delay targets, better funding/cash-flow/hedge completeness, cohort-aware risk-adjusted rankings and additional licensed sources. Validate rankings within a defined public cohort; public data does not establish the world's best traders. Position snapshots do not reveal every execution or outside hedge. |
| P2 | AI quality | Deployed Workers AI binding, public-evidence explanations/challenge/EN-FR and embedding search, quotas/citation/output guards | A measured factuality/citation/failure evaluation set and operational latency/limit/error monitoring. Release inference contracts use mocks; this review did not invoke production inference. Models stay outside pricing, risk approval and order submission. |
| Launch gate for commercialization | Legal/data rights | Engineering review and documented limitations | Qualified Canadian/Québec regulatory/privacy review and confirmed provider redistribution/commercial rights for the actual service before selling signals or opening wider execution. Current CoinPaprika use is personal/noncommercial; Hyperliquid commercial rights remain unverified; Coinbase research is disabled and ChangeNOW separately gated. |

## Recommended sequence

1. Resolve reliable operation and permanent, recoverable history.
2. Validate one understandable strategy prospectively with honest net outcomes.
3. Complete the account lifecycle and a simple tested idea-to-plan-to-review flow.
4. Establish independent security/operations assurance and research-only invitations.
5. Expand sources, trader rankings and commercial access after rights/review gates.

The user's free-only constraint remains in force. Much of the software/UX/testing
work can continue on the current tools, but the existing free sleeping service
and expiring database do not satisfy continuous professional monitoring and
retention. No paid resource, upgrade or real-money test was performed.

## Evidence

- docs/DEPLOYMENT.md and docs/HANDOFF.md: hosting mode, expiration, unpublished auth.
- docs/BACKUP.md: manual export/restore, bounds, offsite retention limits.
- docs/SECURITY.md and docs/ACCOUNT_CONNECTIONS.md: one-shot execution, stops,
  reconciliation, emergency-stop scope and known security limits.
- backend/sentinel/kraken_account.py: explicit owner-initiated reconciliation;
  submitted IOC may partially fill; no attached protective stop.
- docs/RADAR.md: frozen assumptions and outstanding prospective validation.
- backend/sentinel/follow_evidence.py and docs/TRADER_EVIDENCE.md: actual gating,
  modeled costs, interval assumptions, limited history and residual dependence.
- docs/MARKET_COVERAGE.md, docs/TRADER_DISCOVERY.md and docs/PROVIDERS.md: actual
  indicative/book coverage, public cohort caveats and data rights.
- frontend/functions/api/ai.ts, frontend/app/ai-research.tsx and production Pages
  AI binding: on-demand Workers AI scope, public context and no financial tools.
- backend/sentinel/runtime.py and docs/SECURITY.md: alert retries/expiry and
  at-least-once delivery limits.
- docs/REGULATORY.md: qualified review required for commercialization scope.

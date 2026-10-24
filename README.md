# Market Sentinel AI

Private cryptocurrency investigation, paper trading, real-capital planning and individually approved Kraken USD spot limit orders. **No autonomous trades, withdrawals, leverage or wallet seeds.** This is independent of Sentinel Intelligence.

## Implemented vertical slice

- FastAPI backend; decimal order-book calculations; timestamped provenance; reconnect backoff and stale-data rejection.
- Public Kraken v2 (CRC32-verified books), Coinbase Exchange (unauthenticated `level2_batch`), Hyperliquid books/trades/asset context. Provider connections require explicit documented-use approval.
- Four deterministic evaluation stages; visible-depth cross-exchange economics with both venue fees and a latency reserve. Unverified inventory prevents executable GO claims.
- Hyperliquid public-address watchlist and position changes; initial snapshots are baselines, not invented new trades. No profitability ranking without adequate evidence.
- Trader Actions: bounded experimental public candidate discovery, reported historical windows, observed wallet changes and available fill-history investigation. No worldwide best-trader claim or invented success odds.
- Conditional Kraken USD spot radar with frozen hypotheses, short entry windows, source-gap invalidation and current depth/cost/risk checks. GO permits a paper experiment only.
- Separate user-declared real-capital settings and manual sizing; risk PASS remains trade WAIT. Secure own-account Kraken linking verifies restricted permissions; each real spot order requires a separate immutable review and exact owner approval.
- Read-only ChangeNOW standard swap estimates, stored separately from executable books. Requires a public business API key in backend secrets and confirmed research-use permission.
- Durable opportunity snapshots, explanations, five-minute edge persistence outcomes and autopsies. Missing outcomes remain unavailable. Edge persistence is not P&L.
- Transactional manual paper trading, idempotency, modeled fees/depth/latency, exposure caps, daily realized-loss limits and persistent emergency stop.
- Expanding-window historical strategy lab with an embargo, out-of-sample comparison, buy-and-hold/no-trade benchmarks and latency sensitivity.
- Next.js/TypeScript mobile dashboard with all research sections plus a dedicated Live Money workspace, source/freshness labels, paper labeling and actual empty states.
- Owner authentication, secure expiring cookies, origin validation, rate limiting, audit journal and optional ntfy mobile delivery tests.

## Run locally

Requires Python 3.12 and Node.js 22. No provider or credential is enabled by default.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
python scripts/setup_owner.py
```

Set `OWNER_PASSWORD_HASH` to the generated hash and `SESSION_SECRET` to at least 48 cryptographically random characters in your local environment. Load `.env` with your process manager; Python does not silently source it. Start the API:

```sh
cd backend
python -m sentinel
```

For the frontend, in a second terminal:

```sh
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

The default development origin is `http://localhost:3000`. Approve provider use in deployment configuration before setting `COLLECT_MARKETS=true` and `APPROVED_PROVIDERS`. No sample prices are substituted when providers are disabled.

## Verification

```sh
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
cd frontend
npm run typecheck
npm run build
npm run test:e2e
```

The backend suite uses clearly synthetic fixtures and one published Kraken checksum vector. Cloudflare runs the release checks. The Cloudflare release runner starts an ephemeral isolated PostgreSQL for all checks and rejects skipped tests. Plain local unittest runs require a separate disposable `TEST_POSTGRES_URL` to include PostgreSQL checks. No production database or real-money trade is used for tests. No test result establishes profitable trading.

## Hosting

`render.yaml` declares a separate API and dedicated PostgreSQL database. `deploy/cloudflare-pages.json` configures the Next.js static export with a Pages Functions API proxy. The production domain is `market.getlevelupskillz.com`. Review `docs/DEPLOYMENT.md`, `docs/PROVIDERS.md` and `docs/SECURITY.md` before enabling sources or hosting. Deployment status and acceptance results are recorded in `docs/DELIVERY.md`.

## Boundaries

Owner-only research, paper execution, real-capital planning and individually approved Kraken spot orders. Advanced cash-flow-adjusted trader rankings, chain-wide whale discovery, validated liquidation models, genuine out-of-sample strategy promotion and autonomous or derivative execution require later review, implementation and evidence. No commercial signal launch is implied. Review Canadian/Québec regulatory applicability before commercialization or execution.

No profitability, statistical significance or edge claim is made.

Paper hypothesis evaluation now supports GO eligibility based on stop/target, visible depth, both-leg costs, cash, exposure, loss limits and net reward/risk. GO explicitly means a paper experiment with unvalidated predictive edge. Production Access JWT verification and free-plan retention/sleep limits are documented in docs/.

Live screens: [Live Money](https://market.getlevelupskillz.com/#live-money), [Market Radar](https://market.getlevelupskillz.com/#radar). Account connections, capital and real-order reviews are in Live Money. Google research invitations are a separate in-progress milestone; see HANDOFF.md.

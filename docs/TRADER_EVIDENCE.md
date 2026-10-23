# Public trader investigation, version 0.2

The collector observes documented Hyperliquid WebSocket trades, including the public buyer/seller address pair. A genuine print of at least 100,000 USDC may admit its public participants to a fixed discovery cohort, capped at five automatic wallets and ten total wallets including manual selections. Size is not a performance rank or a statement about a person's identity or wealth. The original discovery timestamp and print provenance are retained. No reputation, position or historical P&L is seeded.

Current positions are queried through the public clearinghouseState info request in approximately thirty-second rounds at full capacity, plus provider response time. Initial snapshots are baselines. Opens, increases, reductions, closures and reversals are inferred only from subsequent observed differences. Changes between polls and external hedges remain unknown. Free Render sleeping creates visible collection gaps.

Historical analysis queries userFillsByTime for a requested thirty-day window, bounded to one response of at most 2,000 fills per wallet. Hyperliquid only makes recent fills available; returned data is never labeled a complete lifetime history. Fetches are spaced by ten seconds and historical results refresh every six hours. The exact raw response is retained in the latest history state with a SHA-256 digest; the API returns the computed summary and a small recent-execution list, not the entire input.

Native perpetual fills are grouped into complete flat-to-flat cycles (expanded beyond BTC, ETH and SOL in public-cycles-v2). Spot IDs and namespaced HIP-3 markets are excluded. Partial closures do not inflate the trade count. Reversals divide their reported fee between the closing and opening portions. Provider builderFee is already included in fee and is not subtracted twice. A missing initial open, position-size gap, incompatible fee token, future timestamp or invalid value prevents an invented complete trade. Open cycles remain unfinished.

Historical win rate is the fraction of complete observed cycles with positive P&L after reported trading fees, before funding. It is not follower odds. P&L drawdown is measured in USDC on that realized-cycle series and is not account-equity drawdown. Funding, full account cash flows and outside positions are not reconstructed. Small samples and provider truncation are disclosed.

Follower evidence is a separate prospective study (follow-shadow-v1). A newly observed opening, increase or reversal can start an isolated 250-USDC shadow observation using fresh executable visible-depth prices. It never changes the owner's paper cash or places an order. A single sample per asset per hour across all wallets limits overlapping selections. A fixed one-hour exit uses a fresh later book within sixty seconds; otherwise the outcome is unavailable. Both legs include modeled five-basis-point taker fees and adverse five-basis-point latency, plus a twenty-basis-point funding reserve. That reserve is an assumption, not an observed funding payment or a guarantee that all actual costs are covered.

Each asset/direction estimate uses only outcomes available before its prediction time. Future follower odds remain unavailable until at least one hundred non-overlapping completions, seven days of history, ninety-percent outcome availability, thirty predictions made before their outcomes, Brier score below the constant-fifty-percent benchmark, calibration error at most ten percentage points, and a 95% Wilson interval no wider than twenty-five percentage points. No fake default percentage is used. Historical outcome rate and interval can be inspected independently. Residual serial dependence, selection bias and regime shifts remain limitations; the interval can understate uncertainty. Calibration does not establish expected financial profit.

Next-action reviews combine fresh positions, entry deterioration, liquidation proximity, historical-cycle losses and the prospective evidence packet. They return WAIT or NO-GO until independent stop/target, cash, exposure and cost checks are made in the existing paper planner. This feature does not enable live trades or automatically promote a strategy.

Primary documentation reviewed on 2026-10-23:

- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits

The undocumented third-party-described leaderboard download was not used. This implementation discovers actual participants from the documented public trade feed. Read-only private-owner research remains subject to provider terms and Canadian/Québec commercialization review documented elsewhere.

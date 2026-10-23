# Public trader discovery: sources and evidence limits

Reviewed 2026-10-23. This section covers a public Hyperliquid sample, not all traders worldwide. A wallet's position size, reported profit, or place on a venue leaderboard does not establish identity, skill, future profitability, or copyability.

## Source verification

The official public leaderboard is at https://app.hyperliquid.xyz/leaderboard . It is a browser application; this review could not retrieve its rendered table through the available browsing tool.

The candidate data URL is https://stats-data.hyperliquid.xyz/Mainnet/leaderboard . It is on the provider's public stats host, but this review found no corresponding schema or service-level guarantee in the official API documentation or the current official documentation index, https://hyperliquid.gitbook.io/hyperliquid-docs/llms.txt . A bounded Cloudflare network probe on **2026-10-23 at 17:46:21 UTC** returned HTTP 200 JSON and checked the first three rows (probe build `b1489`, commit `76b968`). This verifies a live sample of the response shape; it does not establish whole-feed validity, timestamp semantics, eligibility criteria, refresh cadence, or a stable API contract. The adapter must validate every downloaded row before presenting available candidates.

Do not describe this source as a documented, stable leaderboard API. Use an experimental adapter with strict response validation, bounded response size and memory, last-good caching, independent failure reporting, server-side pagination, and an explicit unavailable state. Fetching a public response does not establish a commercial redistribution license.

## Leaderboard fields and units

The live sample contained a top-level `leaderboardRows` array with `ethAddress`, `displayName`, `accountValue`, and `windowPerformances` tuples. The sampled tuple labels were `day`, `week`, `month`, and `allTime`, with `pnl`, `roi`, and `vlm` fields. These fields are an observed frontend response shape, not a documented provider contract. Synthetic fixtures remain explicitly labeled as tests and are never substitute market or performance data.

This review did not find a primary-source specification establishing the leaderboard's exact ROI unit, denominator, funding/fee treatment, P&L scope, or reporting-window boundaries. Preserve raw provider fields and label conversions as explicit adapter assumptions until independently verified. A decimal ROI value must not silently become a claimed verified percentage. Do not treat missing metrics as zero. A response receipt time is not a source publication time; a cache hit must not refresh either timestamp.

No source count, top-wallet identity, real trading action, historical win rate, or world's-best rank should be invented from an unavailable feed. Public display names are self-reported labels and do not identify an anonymous wallet's real person.

## Documented wallet investigation

The official info endpoint is https://api.hyperliquid.xyz/info . Its documented public `portfolio` request is:

```json
{"type":"portfolio","user":"0x..."}
```

The documented response is an array of `[window, metrics]` tuples. Metrics contain `accountValueHistory` and `pnlHistory` arrays of `[epoch_milliseconds, numeric_string]` points and `vlm`. Listed windows include `day`, `week`, `month`, `allTime`, `perpDay`, `perpWeek`, `perpMonth`, and `perpAllTime`.

Primary reference: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#query-a-users-portfolio . The same reference documents `userRole`, which distinguishes users, agents, vaults, subaccounts, and missing accounts. A leaderboard row alone does not establish that it represents an independently trading individual rather than one of these other account roles.

Use documented public position and fill queries to investigate chosen addresses, and retain actual request/receipt times, fill coverage, provider caps, unfinished position cycles, and gaps. Initial position snapshots are baselines. A subsequent position difference is an observed change, not proof of an exact execution time, order intent, or all of the trader's exposure.

## Performance and drawdown limits

The official portfolio-graphs documentation says account value includes unrealized cross/isolated position P&L and vault balances. The displayed histories are sampled on deposits and withdrawals and every 15 minutes; the provider cautions against using graph interpolation for precise accounting. Missing intraperiod losses cannot be reconstructed from those points.

Primary reference: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/portfolio-graphs . The provider's frontend drawdown definition uses P&L changes with account value at the start of each evaluated interval, rather than a simple peak-to-trough decline in the account-value series. Reference: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/miscellaneous-ui . Do not relabel a naive account-value decline as independently validated trader drawdown, or treat deposits and withdrawals as trading return.

Reported day/week/month/all-time results overlap. Positive values across these windows are not four independent trades or four independent performance samples. Leaderboard membership is a selected and changing cohort; rankings based on today's visible profitable accounts contain selection and survivorship bias. Preserve point-in-time discovery cohorts if comparing subsequent performance. No complete population, closed-account history, external hedges, or independently audited return record is claimed.

Prefer transparent discovery filters and reported longer-window statistics to a manufactured skill score. Missing risk, data-completeness, sample-size, or latency-adjusted copyability evidence must remain explicit. Following a public trader never bypasses the app's independent market, execution-cost, exposure, freshness, or risk checks. Historical performance is not a future success probability.

## Licensing, privacy, and costs

The official app's terms page, https://app.hyperliquid.xyz/terms , did not expose readable text through the browsing tool. This review therefore does not verify a broad data-redistribution or commercial-use license. Retain the existing authenticated personal-research scope; review actual provider terms and obtain any necessary permission before commercial display or wider distribution. Public API documentation is not itself a blanket license.

Do not request wallet private keys, recovery phrases, trading authority, or withdrawal permissions for discovery. Public-wallet observations require no order submission or funded trading account. The existing free-hosting limits remain applicable: use bounded caches and requests, respect provider rate limits, and show collection gaps. Do not add a paid data service or imply guaranteed 24/7 collection on sleeping Render Free hosting.

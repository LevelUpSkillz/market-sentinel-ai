# Premium workspace and Live Money — 0.6

This release introduces a dedicated Live Money workspace with Overview, Budget & limits, Trade ticket and Connection. Actual Kraken USD cash, asset counts and open orders appear only after a successful manual account read, with source/freshness labels. USDC is not counted as USD and no portfolio valuation or real profitability is invented. User-declared budget stays distinct from exchange balances. The persistent pause control blocks new app orders without canceling orders already accepted at Kraken.

The trade ticket retains a short-lived immutable provider-validation review, exact typed approval and durable unknown-outcome reconciliation. A verified current bid/ask can be copied into the proposed limit only on an explicit click. It never submits an order. Account setup, budget confirmation, current account read, fresh detailed USD spot book and individual approval remain separate requirements. No protective stop is attached and full buy cost counts as at-risk. The owner's existing encrypted connection and vault are preserved.

An owner-only GET /api/connections/kraken/orders returns the latest 50 allowlisted application intents. It is explicitly not complete exchange history, a fill record or a P&L statement. No provider account request is made by this journal read. Historical/unknown requests cannot be resent from the journal.

The public-data radar now requests documented BBO-triggered ticker updates for Kraken USD spot. Other quote currencies retain trade-triggered quotes. This addresses sparse trade-event sampling without weakening provider timestamps, five-second freshness, continuity, ten completed baseline bins, executable-depth or risk checks. Input-feed provenance changes the strategy version to observed-breakout-v1.1; old records retain their versions and rules are not promoted based on unvalidated results. New observation rows show actual midpoint/source/receipt times, ten-bin progress and a five-minute move only when the full continuous baseline exists. Gaps reset it. The list is sorted by absolute observed move/progress, not claimed skill or profitability. Filters/search organize actual setups. GO remains paper-only and no success probability is manufactured.

A new visual system provides readable slate/mint research screens, gold actual-capital controls, grouped navigation, mobile quick navigation, bookmarkable hash screens, deliberate order review, and preserved live sampled charts. Duplicated old chart/history polling and paper-cash headline cards are removed from Mission Control; paper accounting stays in Performance & Risk. Private backup and operational settings remain in Settings.

Direct screens after sign-in:
- https://market.getlevelupskillz.com/#live-money
- https://market.getlevelupskillz.com/#radar
- https://market.getlevelupskillz.com/#live-markets

Security: existing independent owner sessions/Access JWTs, Origin checks, persistent rate limits, server-side deterministic rules, encrypted restricted credentials, monotonic nonces, intent-before-submit, no blind retries, emergency stop and restored-order execution disablement remain mandatory. No real-money test trade, key rotation, paid service or change to Sentinel Intelligence is part of this release. Free Render collection can sleep. The free PostgreSQL expiry remains November 22, 2026. Actual fees still apply.

Release verification and actual deployment results are recorded in DELIVERY.md and HANDOFF.md after acceptance. Browser fixtures and design-review images in build logs are explicitly synthetic, never production account data. Passing checks is not proof of profitable trading.

Verified provider contract: https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/ticker — event_trigger=bbo publishes changes in best bid/offer price levels; timestamp is provider ticker data time.

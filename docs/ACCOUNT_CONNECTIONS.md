# Real-capital planning and exchange readiness — 2026-10-23

The owner selected Kraken after considering Coinbase. Both manual real-capital planning and a future individually approved exchange workflow are intended. Only manual planning and connection readiness are implemented in this release. No account is connected and no real order, withdrawal, transfer, signer or credential-upload endpoint exists.

## Real-capital profile

The authenticated owner supplies USD-denominated total capital, available cash, existing correlated crypto exposure, current UTC-day realized P&L, per-trade risk, position, total exposure and daily loss limits. Actual monetary amounts start blank. Editable initial percentage examples are labeled as examples, not advice. Inputs are explicitly USER_DECLARED_UNVERIFIED and are separate from the virtual paper account. They expire after 24 hours and across a UTC-day boundary until reconfirmed. CAD, USDC and USD are not silently converted.

The manual planner uses current source-venue USD spot depth, modeled fees and latency, risk and daily-loss budgets, declared cash, position and concentration limits, downward quantity rounding and post-VWAP limit checks. A risk PASS is arithmetic only: trade decision stays WAIT, predictive edge is unvalidated and execution remains disabled. Prices expire after five seconds. Future exit liquidity, lot rules, eligibility, balances and actual fees are unverified. A stop is not a guaranteed maximum loss. The current Kraken fee assumption is 80 bps per leg based on the public base spot taker schedule, with regional/product/account-tier uncertainty.

## Secure account-linking boundary

Kraken's current developer index describes OAuth REST under Embed, requiring a B2B partner agreement. The official legacy Kraken Connect guide also requires provider-provisioned client credentials. This workspace has no approved OAuth client configured. The app therefore displays “awaiting provider setup,” not “connected.” No exchange private key, password, recovery phrase or seed is requested. No paid hosting or provider plan is automatically selected.

Coinbase's current OAuth quickstart states that new client creation is temporarily disabled and access is limited to approved partners; existing approved clients continue to work. OAuth has no sandbox. Its market-data terms separately restrict AI/automated-system uses absent suitable consent. Coinbase remains disabled as a radar source. Neither OAuth permission nor a virtual paper result establishes a profitable strategy or commercial signal permission.

Future implementation must first obtain approved application credentials and appropriate data-use permissions, verify regional/account/product eligibility, use execution-venue quotes and actual fees/balances/lot rules, and enforce immutable order details, a short expiry, explicit per-order owner confirmation and idempotency on the server. Account OAuth consent must not be treated as approval for future orders. Transfers and withdrawals remain outside scope. No real-money orders are submitted as acceptance tests for this release.

Kraken and Coinbase charge transaction fees; free app hosting does not make actual trading free. Applicable Canadian/Québec requirements must be reviewed before any commercial signal service or execution capability is introduced; catalogue listing does not imply that a product can be traded by a particular resident/account.

## Official references

- Kraken current integration index: https://docs.kraken.com/llms.txt
- Kraken Connect: https://docs-legacy.kraken.com/api/docs/oauth/kraken-connect/
- Kraken fees: https://www.kraken.com/features/fee-schedule
- Kraken regional eligibility: https://support.kraken.com/ca/articles/where-is-kraken-licensed-or-regulated
- Coinbase OAuth prerequisites: https://docs.cdp.coinbase.com/coinbase-app/oauth2-integration/quickstart
- Coinbase order preview: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/preview-orders
- Coinbase order creation/idempotency: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/create-order
- Coinbase fees: https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees
- Coinbase market-data terms: https://www.coinbase.com/legal/market_data

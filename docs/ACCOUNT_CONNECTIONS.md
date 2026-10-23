# Real-capital planning and exchange readiness — 2026-10-23

The owner selected Kraken after considering Coinbase. Both manual real-capital planning and a future individually approved exchange workflow are intended. Only manual planning and connection readiness are implemented in this release. No account is connected and no real order, withdrawal, transfer, signer or credential-upload endpoint exists.

## Real-capital profile

The authenticated owner supplies USD-denominated total capital, available cash, existing correlated crypto exposure, current UTC-day realized P&L, per-trade risk, position, total exposure and daily loss limits. Actual monetary amounts start blank. Editable initial percentage examples are labeled as examples, not advice. Inputs are explicitly USER_DECLARED_UNVERIFIED and are separate from the virtual paper account. They expire after 24 hours and across a UTC-day boundary until reconfirmed. CAD, USDC and USD are not silently converted.

The manual planner uses current source-venue USD spot depth, modeled fees and latency, risk and daily-loss budgets, declared cash, position and concentration limits, downward quantity rounding and post-VWAP limit checks. A risk PASS is arithmetic only: trade decision stays WAIT, predictive edge is unvalidated and execution remains disabled. Prices expire after five seconds. Future exit liquidity, lot rules, eligibility, balances and actual fees are unverified. A stop is not a guaranteed maximum loss. The current Kraken fee assumption is 80 bps per leg based on the public base spot taker schedule, with regional/product/account-tier uncertainty.

## Secure account-linking boundary

The owner wants real, individually approved in-app trades and also has Coinbase and Crypto.com accounts. Kraken remains the selected exchange. A supported provider API makes this technically possible; this release has no secret-ingestion, account-linking or real-order implementation. No account is connected. The connection screen now says “Secure setup required” and describes both owner API keys and partner OAuth, without accepting credentials or offering real order submission.

Provider routes were rechecked against official documentation on 2026-10-23:

| Account | Supported route | Current constraint |
| --- | --- | --- |
| Kraken exchange account | Owner-created Spot API key with restricted permissions; alternatively Kraken Connect OAuth/Fast API | Standard API-key integration is documented for third-party apps. OAuth is under Embed and requires B2B partner approval and a provisioned client. Neither route is configured here. |
| Coinbase exchange account | An owner's own account can use a CDP API key for Advanced Trade; other users require OAuth | Coinbase App authentication requires ECDSA/ES256 keys and supports portfolio/permission restrictions. New OAuth clients remain disabled except for approved partners. No connector is implemented. |
| Crypto.com Exchange | Exchange API key, initially read-only, with trading enabled deliberately | Trading requires an IP allowlist. Exchange account access and current deployment egress addresses must be verified; having the retail app does not establish Exchange API eligibility. |
| Crypto.com App Agent Key | Separate provider-documented OpenClaw/Agent Key integration | Current official availability excludes Canada and South Korea, and the documented integration offers market orders. General Market Sentinel integration rights, protocol, eligibility and permissions remain unverified. Do not assume an Exchange key and an App Agent Key are interchangeable. |

Kraken explicitly documents owner-created keys for third-party account balances, history and orders; this route does not depend on obtaining an OAuth client. A future private owner integration could provision a restricted key through secure server-side secret storage, outside chat. Permission checks must reject funding/withdrawal/transfer authority. Begin with verified account access and non-executing validation before enabling individually approved orders. Kraken's `AddOrder` supports `validate=true` without trading in the matching engine. The app must keep validation requests separate from the real submission operation. A provider validation result is not a fill, available-liquidity guarantee or profitable trade.

Public wallet observation, wallet dApp connection and exchange account linking are distinct. A public address allows observation only. Connecting a self-custody wallet or signing an ownership message does not authorize spending or expose exchange account balances. Any future on-chain swap path would need a separate network/asset/fee review and the owner's transaction signature in their wallet for each action; no wallet private key, seed or recovery phrase belongs in this app or chat.

No exchange secret, password, recovery phrase or seed is requested in chat, committed to source, stored in browser storage or logged. This release has no secure credential-entry flow and must not solicit keys until that flow and server-side secret protection have been implemented and reviewed. No paid hosting or provider plan is selected automatically. Provider account permission is separate from individual order approval.

Coinbase market-data terms separately restrict AI/automated-system uses absent suitable consent. Coinbase remains disabled as a radar source; a personal account API connection would not by itself authorize that data use. Neither a provider connection nor a paper result establishes profitable trading or commercial signal permission.

Future execution must verify regional/account/product eligibility, execution-venue quotes, available balances, actual fees, lot/price minima and current portfolio exposure. Enforce immutable order details, a short expiry, explicit per-order owner confirmation, durable idempotency and reconciliation after ambiguous timeouts. Kraken's `cl_ord_id` uniqueness covers open orders, so it cannot replace application-level prevention of duplicate completed orders. Strictly increasing per-key nonces must also survive overlapping instances and restarts. Transfers, withdrawals, autonomous orders and real-money acceptance tests remain outside scope.

Kraken and Coinbase charge transaction fees; free app hosting does not make actual trading free. Applicable Canadian/Québec requirements must be reviewed before any commercial signal service or execution capability is introduced; catalogue listing does not imply that a product can be traded by a particular resident/account.

## Official references

- Kraken current integration index: https://docs.kraken.com/llms.txt
- Kraken Connect: https://docs-legacy.kraken.com/api/docs/oauth/kraken-connect/
- Kraken third-party API use: https://support.kraken.com/au/articles/360041395271-using-the-kraken-api-with-a-third-party-service
- Kraken key permissions and restrictions: https://support.kraken.com/ca/articles/how-to-create-an-api-key-on-kraken-pro
- Kraken private API authentication: https://docs.kraken.com/exchange/guides/rest/authentication
- Kraken order validation and submission: https://docs.kraken.com/api-reference/trading/add-order
- Kraken fees: https://www.kraken.com/features/fee-schedule
- Kraken regional eligibility: https://support.kraken.com/ca/articles/where-is-kraken-licensed-or-regulated
- Coinbase OAuth prerequisites: https://docs.cdp.coinbase.com/coinbase-app/oauth2-integration/quickstart
- Coinbase own-account API authentication: https://docs.cdp.coinbase.com/coinbase-app/authentication-authorization/api-key-authentication
- Coinbase Advanced Trade: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview
- Coinbase order preview: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/preview-orders
- Coinbase order creation/idempotency: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/create-order
- Coinbase fees: https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees
- Coinbase market-data terms: https://www.coinbase.com/legal/market_data
- Crypto.com Exchange API keys and IP restrictions: https://help.crypto.com/en/articles/3511424-api
- Crypto.com App Agent Key scope and regional availability: https://help.crypto.com/en/articles/13843765-openclaw-trading-overview
- Crypto.com App Agent Key setup and secret handling: https://help.crypto.com/en/articles/13843782-getting-started

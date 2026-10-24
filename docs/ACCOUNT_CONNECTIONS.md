# Own-account Kraken connection and manual spot orders — 2026-10-24

Version 0.5 implements a protected connection to the owner's own Kraken account, account reads and individually approved USD spot IOC limit orders. Deployment/feature-flag status is recorded in DELIVERY.md. Implemented code does not mean an account is connected. No credentials or real-money trade are used for acceptance tests. Public-wallet observation is separate from an exchange account connection.

## Link in the protected app

1. Sign in at https://market.getlevelupskillz.com and open Live Money → Connection. Credential fields appear only with a configured server vault and HTTPS.
2. Create a dedicated Kraken Spot API key. Enable funds query, open-order query and closed-order query. For manual placement also enable modify/create orders and cancel/close orders. Leave every other permission, particularly funding and withdrawals, disabled. Remove history-date restrictions so unresolved orders can be reconciled. Use this key only with this app.
3. Enter the key and secret in the protected form. Confirm country/region, account/product eligibility and dedicated-key use. Never send credentials in chat. Actual exchange fees and regional restrictions still apply.
4. Verify actual balances and open orders. A read-only key can link without order authority. Linking never sends a trade.
5. Open Live Money → Budget & limits and confirm your capital. Select an observed eligible Kraken USD spot market, side, quantity and limit price. Additional markets require selected detailed books in Live Markets. Review actual account fees, lot/tick/minimum rules, available cash and portfolio limits.
6. A validation-only provider request creates an immutable 30-second review. To send that exact real order, type `PLACE THIS REAL ORDER`. One IOC limit instruction may fill partly or not at all. Reconcile status and inspect actual fills/fees directly in Kraken before another order.

No protective stop is placed. A buy's full purchase plus fee reserve must fit declared per-trade and remaining daily loss budgets. Hard limits are 500 USD per order/asset and 2,500 USD correlated exposure, with lower owner limits enforced. Open orders, margin/credit, missing valuations, stale/unverified books, changed fees/profile/connection and emergency stop block submission. Some portfolios cannot trade through the app until every held asset can be valued with a fresh verified USD book; use Kraken directly for unsupported portfolios.

Durable intent is committed before the sole submission POST. Duplicate approval cannot resend it. Transport timeouts, deadline/duplicate errors and uncertain acknowledgments lock subsequent orders until exchange reconciliation. Absence from bounded history is never proof of failure. Disconnect removes credentials but does not cancel an exchange order. Restore permanently disables historical order execution; a nonsecret original-key fingerprint/connection binding allows the same dedicated key to reconcile an unresolved restored order without restoring its credentials.

## Secret storage and provider boundaries

Credentials use Fernet encryption with a separate server-only Render vault key. Keys never enter source, frontend configuration, browser storage, backups or audit records. Transient form values clear after an attempt and validation errors do not reflect raw input. Never rotate an existing vault key casually: a different key cannot decrypt the connection. A separate server feature flag, verified trading permissions and individual owner approval are all required for real submission.

Kraken's documented owner-created API-key route does not require partner OAuth approval. Kraken Connect OAuth is a separate B2B route and is not implemented. Coinbase own-account CDP keys and partner OAuth, and Crypto.com Exchange keys versus retail App Agent Keys, are distinct integrations; neither is implemented here. Crypto.com App Agent Key availability/third-party protocol remains unsuitable or unverified for this deployment. Coinbase market-data restrictions separately keep Coinbase disabled as a research source; personal account permission would not automatically authorize that data use. ChangeNOW still awaits its separate public business key/use approval.

No self-custody wallet signer or on-chain spending connection is implemented. A watched public address allows observation only and does not identify its real owner. Connecting a dApp wallet or signing an ownership message would not itself authorize spending or expose exchange balances. Never request wallet private keys, seeds or recovery phrases.

Free hosting does not make trading free. Render Free can sleep: inspect orders directly in Kraken and do not rely on this app for protective execution or continuous monitoring. The free database expires November 22, 2026; use the protected backup export and preserve archives outside the repository. Manual owner-account trading is separate from a commercial signal/advisory service. Commercialization or wider execution needs qualified Canadian/Québec review; no legal or profitability conclusion is implied.

## Real-capital profile

The authenticated owner supplies USD-denominated total capital, available cash, existing correlated crypto exposure, current UTC-day realized P&L, per-trade risk, position, total exposure and daily loss limits. Actual monetary amounts start blank. Editable initial percentage examples are labeled as examples, not advice. Inputs are explicitly USER_DECLARED_UNVERIFIED and are separate from the virtual paper account. They expire after 24 hours and across a UTC-day boundary until reconfirmed. CAD, USDC and USD are not silently converted.

The manual planner uses current source-venue USD spot depth, modeled fees and latency, risk and daily-loss budgets, declared cash, position and concentration limits, downward quantity rounding and post-VWAP limit checks. A risk PASS is arithmetic only: trade decision stays WAIT, predictive edge is unvalidated and execution remains disabled. Prices expire after five seconds. Future exit liquidity, lot rules, eligibility, balances and actual fees are unverified. A stop is not a guaranteed maximum loss. The current Kraken fee assumption is 80 bps per leg based on the public base spot taker schedule, with regional/product/account-tier uncertainty.

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


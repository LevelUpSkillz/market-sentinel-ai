# Provider documentation and permitted use

Reviewed 2026-10-23. Technical API availability does not establish an unrestricted commercial data license.

Version 0.3 broadens Kraken crypto spot quote coverage through instrument/ticker WebSockets and Hyperliquid native perpetual quote coverage through metaAndAssetCtxs/allMids. It also adds the CoinPaprika Free identity catalogue and delayed aggregate USD quotes for owner-only noncommercial research, with attribution and no paid fallback. Detailed semantics, native identity handling, freshness, quotas, licensing and primary references are in [MARKET_COVERAGE.md](MARKET_COVERAGE.md). Directory quotes never replace validated execution books. The original BTC/ETH examples below describe the initial release; SOL and up to six owner-selected additional detailed books are supported.

- Kraken: public WebSocket v2 book, ticker and trades; BTC/USD and ETH/USD; Decimal parsing and top-10 CRC32 validation. Sources: https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book and https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2 . Canadian terms: https://www.kraken.com/legal/ca-terms . General automation/application/content restrictions require review for uses beyond permitted documented API access and private research. No broad redistribution license is claimed.
- Coinbase: public Exchange level2_batch, matches and ticker. https://docs.cdp.coinbase.com/exchange/websocket-feed/channels . The August 7, 2026 Market Data Terms at https://www.coinbase.com/legal/market_data restrict external display/derived works and AI/automated-system uses. This adapter remains disabled pending suitable written permission.
- Hyperliquid: public l2Book/trades/activeAssetCtx plus clearinghouseState for user-selected public addresses. https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions and https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint . Rate limits: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits . USDC perpetuals are never treated as USD spot. Funding context has receipt time only. Trading eligibility and complete historical performance are not inferred. Terms at app.hyperliquid.xyz/terms were not machine-readable; commercial rights remain unverified.
- ChangeNOW: https://changenow.io/api links official Postman documentation. API terms: https://changenow.io/terms-of-use/changenow-api . Setup: https://support.changenow.io/hc/en-us/articles/22686553746204-Integration-API-setup-and-customization . Fees: https://support.changenow.io/hc/en-us/articles/22686447453596-Integration-Commissions-fees-and-payouts . Implemented GET /v2/exchange/estimated-amount with standard/direct flow and explicit currency networks. API terms constrain derived work and independent use; standalone research permission must be confirmed. The Postman client was not fully machine-readable, so the contract requires credentialed live acceptance. Only a public business key is used. No swap creation, private exchanges-management key, deposit-address or transfer operation exists.

Provider clients are disabled by default locally. The owner-only Render Blueprint selects documented public Kraken and Hyperliquid feeds for private research; this does not establish commercial redistribution rights. Coinbase stays disabled. ChangeNOW remains credential- and use-permission-gated. Original source and receipt timestamps, instrument, quote and integrity accompany books. Ticker/heartbeat activity never refreshes a book. Coinbase snapshot timestamps remain null until a timestamped update. USD and USDC are never silently equated.

Cross-exchange economics use visible-depth VWAP, both venue fees (conservative model: Kraken 80 bps and Coinbase 60 bps), plus 5 bps latency reserve. These are assumptions rather than verified personal fee tiers. Unverified prefunded inventory keeps an apparent executable edge at WAIT. Paper plan GO only indicates deterministic risk eligibility, with unvalidated probability of profit. No provider data is sent to an LLM or used for autonomous strategy changes.

The Kraken base taker planning assumption was updated to 80 bps in spot-cross-v1.1.0 after reviewing the current public fee schedule (https://www.kraken.com/features/fee-schedule) on 2026-10-23. This is not an authenticated personal fee quote; regional/product/tier differences remain unverified. Real order economics must come from the execution venue and account. Paper records preserve entry/exit fee amounts and current fee-bps fields. OAuth account-linking prerequisites and the absence of live execution are documented in ACCOUNT_CONNECTIONS.md.

### Historical display charts (0.6.1)
Kraken public `GET /0/public/OHLC` and Hyperliquid public `POST /info`
`candleSnapshot` supply actual 1/5/15-minute exchange trade candles. Contract
checked against the providers' official documentation on October 24, 2026.
Kraken returns at most 720 rows and includes an unfinished current candle;
Hyperliquid native perpetuals require their exact metadata coin IDs. The app
returns at most 180 rows, marks unfinished candles, preserves missing periods,
bounds responses, caches for 20 seconds, and never uses these display candles
as executable prices or strategy training data. Existing provider approvals and
permitted-use limits still apply. No extra provider subscription is purchased.

- https://docs.kraken.com/api-reference/market-data/get-ohlc-data
- https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#candle-snapshot

# Market coverage and free data policy

Version 0.3.0, 2026-10-23. This is an owner-only personal/noncommercial research workspace. No paid feed, worker or instance is created.

## Live venue directory

Kraken's public WebSocket v2 instrument channel supplies native active crypto spot pair identifiers. Tokenized assets are excluded and fiat/fiat pairs are filtered. Ticker subscriptions cover every returned online crypto pair, across its actual quote currencies, in batches of 50. The directory uses the best bid/ask midpoint, carries the provider's ticker timestamp and receipt time, and marks a quote stale after 30 seconds or disconnection. Illiquid markets may have no recent trade-triggered update. USD, USDC, BTC, EUR and other quote currencies are not equated.

Hyperliquid's public metaAndAssetCtxs response supplies the native perpetual universe; allMids supplies broad streaming midpoint updates. This feed has no event timestamp: the interface labels it “streaming · receipt time,” never a timestamp-verified book. Mark funding/context data is refreshed every two minutes and retains its separate receipt time. Native units such as kPEPE are preserved. Namespaced HIP-3 markets and spot IDs need separate adapters and are explicitly excluded.

These directory quotes are indicative and are not inputs to paper fills or risk approval. Market counts are measured from actual provider responses, not promised constants. Connected providers do not cover every token on every blockchain, and listing does not imply accessibility, quality or eligibility to trade.

## Broad token catalogue

CoinPaprika GET /v1/coins is refreshed every six hours and provides its complete returned identity catalogue, including inactive listings. GET /v1/tickers?quotes=USD is refreshed no more than every ten minutes and supplies the Free plan's available aggregate USD quotes (documented maximum 2,000). A token ID, not its ticker symbol, is the identity. Same-symbol tokens are never merged with each other or automatically matched to venue instruments.

The Free API allows personal/noncommercial research and requires attribution; the app displays “Powered by CoinPaprika.” This is not a commercial redistribution license. Reassess licensing before selling the app, opening data access, exporting bulk provider data or introducing commercial signals. There is no automatic paid fallback. HTTP 402/403/429 causes a one-hour retry backoff; last good prices retain their original timestamps. Missing coverage remains unavailable. The authenticated API paginates results and does not expose a public bulk feed. Aggregate prices are labeled delayed, become stale after 20 minutes, and cannot cause simulated execution.

The two CoinPaprika refresh schedules consume approximately 4,440 requests per 30 days when always awake, below the documented 20,000/month Free allowance. Repeated restarts without persisted state, provider changes or shared egress can affect quotas. No paid upgrade is authorized.

## Detailed books and research

BTC, ETH and SOL remain the core detailed books. Select up to six additional active Kraken USD spot pairs or native Hyperliquid perpetuals from the directory. Selection is stored in the dedicated database, and collectors resubscribe without requiring an open dashboard. Removing a book needed to exit an open paper position is blocked. Removed/delisted markets cannot produce fresh simulated entries.

Paper entries remain USD spot only, with real fresh visible depth, existing fee/latency models and deterministic position/exposure/daily loss limits. Perpetuals remain research only. Public trader cycle reconstruction now accepts native perpetual identifiers beyond BTC/ETH/SOL; unsupported spot/HIP-3 identifiers and non-USDC fee records are excluded. Missing matching detailed books produce NO-GO research reviews, not guessed fills or follower success percentages.

The UI polls the authenticated API every five seconds while visible. WebSocket collectors run in the Render backend independently of the page. Render Free can sleep and cannot provide guaranteed 24/7 monitoring. Catalogue refreshes and feed recovery resume when the backend is awake. No keep-alive mechanism or paid hosting is introduced.

## Primary documentation

- Kraken instruments: https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/instrument
- Kraken ticker and trade-triggered timestamps: https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/ticker
- Hyperliquid WebSocket subscriptions: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions
- Hyperliquid native perpetual metadata: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- CoinPaprika catalogue: https://docs.coinpaprika.com/api-reference/coins/list-coins
- CoinPaprika aggregate tickers: https://docs.coinpaprika.com/api-reference/tickers/get-tickers-for-all-active-coins
- CoinPaprika API license: https://coinpaprika.com/api/licensing
- CoinPaprika API terms: https://coinpaprika.com/terms-api
- CoinPaprika free limits: https://coinpaprika.com/api/pricing

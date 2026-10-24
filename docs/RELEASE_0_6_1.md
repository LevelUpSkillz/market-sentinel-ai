# 0.6.1 — Plain-language guide, evidence-based suggestions, actual chart history

Status: implementation complete; preview/production acceptance pending.

- Primary screens: Home, Prices, Trade Ideas, Big Traders, Live Money. Practice
  and advanced research live under More tools. Existing deep links stay valid.
- Show me how: six short, keyboard-accessible tutorial steps. Navigation only;
  no financial writes, order prefill, approval, or automatic trade.
- Home is reduced to a start card, suggestions and the price chart; detailed
  book tables and individual research reviews have their own screens.
- Home suggestions join deterministic radar evidence with matching token
  public-wallet profiles. A token match never equates a perpetual to spot or
  authorizes an order. Available past execution, small samples, truncated history,
  net trading losses and opposing direction are explained as separate evidence.
  Historical wins remain historical; future odds remain
  unvalidated. Stale prices/expired windows remove actionable price levels.
- Actual Kraken/Hyperliquid historical line/candlestick charts appear without
  waiting for browser observations. Current candles remain provisional; missing
  intervals remain gaps. Live tick mode preserves freshness and outage checks.
- No changes to execution permissions, vault keys, database, hosting plan,
  financial limits, approval phrase, or unknown-result reconciliation.
- Separate unfinished Supabase Google/research invitation work is kept in
  /workspace/market-sentinel-premium and is not part of this release.

Validation is recorded after the isolated PostgreSQL and Chromium preview gate.
Passing tests does not establish profitable trading.

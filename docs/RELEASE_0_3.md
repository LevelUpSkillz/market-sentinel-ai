# Market Sentinel AI 0.3 release acceptance — 2026-10-23

Production dashboard: https://market.getlevelupskillz.com
Production backend: https://market-sentinel-ai-api.onrender.com
Source commit: 95afa2d02fe9e1b605a3531a63d35b6a7de6ab55
Cloudflare production deployment: a6c0eb70-6ad7-4b86-a0f0-d9032218bf45 (success).
Render deployment: dep-dbdp6aon74is73ee4uig (live at 17:03:51 UTC).

113 Python checks passed; three isolated PostgreSQL checks skipped. Four Chromium checks, TypeScript/Next.js build, Blueprint schema and dependency audits passed. Audits reported zero known vulnerabilities. Actual public build-runner probes returned 62,351 catalogue identities, 2,000 delayed aggregate USD quotes, 1,451 Kraken spot listings and 234 native Hyperliquid perpetual listings. Counts change with provider coverage; inactive/quiet listings do not imply fresh streaming prices.

Production Render logs confirm fresh BTC/ETH/SOL books on both enabled venues, CRC validation on Kraken, the broad Kraken directory with 1,451 native listings, receipt of Hyperliquid allMids messages, successful native perpetual metadata loading, and successful loading/persistence of CoinPaprika catalogue and quote caches. Readiness checks return HTTP 200. No warning/error logs were observed in the checked startup window. Render reports approximately 207 MB process memory after catalogue loading, within the existing Free instance. No existing Sentinel Intelligence resource was modified.

The owner API remains authenticated. No owner session was impersonated to inspect private production JSON. UI behavior is covered by the Chromium tests, while deployed collection is verified through actual service logs. Production paper trades and mobile alert delivery were not submitted during acceptance.

Search/filter/pagination, per-source timestamps, actual quote currencies, native IDs and explicit delayed/stale/unavailable states are available in Live Markets > All crypto markets. Select up to six extra detailed books beyond the core BTC/ETH/SOL books. Indicative catalogue/directory prices cannot open paper positions or bypass risk checks. Quiet extra markets cannot restart healthy core feeds, and collector handoff reloads the latest stored selections.

Costs remain $0 within provider/free-hosting quotas. CoinPaprika Free is personal/noncommercial research with attribution and a maximum documented 2,000 aggregate prices. No source covers every blockchain token. Render Free can sleep, so 24/7 collection is not guaranteed. The current free PostgreSQL database expires November 22, 2026. No real-money trading, paid service, keep-alive mechanism or exchange private key was introduced.

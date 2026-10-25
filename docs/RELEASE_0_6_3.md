# 0.6.3 — Minimal market terminal

Status: implementation ready for preview acceptance. Not yet published.
Base: verified Cloudflare production 0.6.2, source
593884370bc75346fcaf2ecd3dfeae1024793660, deployment
0eaa7633-2526-41bc-b0df-88bcb2dc5935. Render remains on 0.6.2,
4b768b3ff1c9452a34b2bb4b7027c5db6c977f00.

This frontend-only release puts the chart ahead of detailed research, with a
consistent dark terminal theme, restrained mission-control graphics, direct
market selection and a smaller home-screen idea selection. The coverage ring
counts verified fresh detailed books; it is not a success or performance score.

New public activity tape shows actual exchange trades with provider, event and
receipt times. Freshness requires both timestamps; stale observations never
become fresh because dashboard polling succeeds. Empty feeds stay empty.
Connection telemetry independently checks book freshness.

Historical charts add actual-data zoom, pan and reset, a second crosshair,
responsive candlestick widths and separate filled segments across missing
candles. Zoom is client-side and cannot manufacture candles or trigger orders.
An expandable order book visualizes up to eight real levels per side and their
visible notional balance, with explicit snapshot freshness and provenance.
Displayed liquidity can disappear and is not a prediction or an order signal.

Primary navigation, guided tutorial, Cloudflare AI, public wallet research,
practice controls and Live Money remain available. Homepage market shortcuts,
chart interactions and activity display make no private exchange account reads
or mutations. Individually approved Kraken orders, vault configuration, backend
services, collector behavior and database are unchanged.

Acceptance includes the existing full PostgreSQL/backend/provider/security gates
and browser tests plus new 320/390/768/1440px navigation, actual-data chart
zoom/pan/reset and stale-feed/coverage checks. Screenshots use labeled synthetic
fixtures only. No real account, key or order is used for acceptance. Free plans
remain unchanged; no always-on monitoring claim or automatic real trading.

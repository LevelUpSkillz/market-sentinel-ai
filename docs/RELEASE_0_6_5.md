# 0.6.5 — Contextual visual instruments across the app

Status: implementation prepared; preview acceptance pending. Not deployed.

Retains the Home orbital scene and adds a distinct instrument to every other
main section: visible order-book landscape, public wallet/token constellation,
recorded opportunity timeline, signal evaluation pipeline, saved-spread forensic
spectrum, walk-forward validation bands, virtual cash/entry-cost orbit, alert
record timeline, settings systems core and Live Money capital readiness shield.

Where data exists, models use existing loaded evidence, with currency, timestamps
and stale/unknown states. Depth markets do not mix USD and USDC; wallet links are
reported positions, not transfers or identities; practice basis is cash plus
original entry cost, never inferred equity; lab bands use actual fold boundaries;
alerts establish delivery only from records. Empty evidence stays empty.

Each instrument supports 3D/flat presentation, a grid layer and recorded-item
inspection. Wallet inspection opens the exact existing wallet detail. FX pause,
reduced motion and offscreen/hidden-page shutdown are preserved. Real data can
refresh while decorative motion is paused. Canvas is capped at 30/24 fps and
1.5 DPR, and only the active section renders its instrument.

No new provider fetches, automatic balance requests, account mutations, order
behavior, backend/database/collector configuration, paid resources or dependencies.
Existing owner-only data boundaries and explicit Kraken approvals stay intact.
The capital instrument is omitted from the active trade-ticket subview to keep
exact order review readable; it remains on the Live Money overview/budget/link
views. Emergency stop also suppresses any practice-GO count in the new display.

New model contracts cover real-depth/currency/stale-data boundaries, wallet links,
recorded-only forensic values and virtual-account basis. Browser acceptance adds
all-section mobile coverage, 3D/flat inspection, quote separation, aging books,
exact wallet navigation and absence of automatic account reads/order writes.

User steering: removed the technical Connections card from Home because its
rapidly changing freshness labels looked like an application fault. Optional
provider diagnostics now live in a collapsed Settings disclosure, separating
reported connection state from actual book event age. The orbital provider
map shows stable market-source labels. Quote timestamps, stale indicators and
five-second trade safeguards remain unchanged. Live Render logs showed ongoing
radar scans; no backend or rate-limit change was required for this UI correction.

The new wallet-constellation test found a real focus race when inspecting a
wallet already on the Big Traders page: the page-navigation RAF stole focus
back from the target wallet. Wallet navigation now skips that generic focus
step and preserves exact-wallet focus. The assertion remains intact.

User clarification: retain a compact issue indicator. Header status now reports
actual API/collector/persistence/provider issues, enabled-feed message gaps over
one minute, or all loaded books without receipts over 30 seconds. Disabled
providers are expected, and a quiet book crossing five seconds alone does not
raise a global fault. Exact per-quote five-second guards remain unchanged. The
status disclosure explains scope and opens Settings diagnostics. No new health
probe, exchange request, smoothing of source timestamps or risk-limit change.

User image also showed empty Coinbase shortcut tiles alongside real Kraken
quotes. Main chart shortcuts now omit never-observed markets (zero receipt
time). Previously observed stale markets remain explicitly old; prices are
not substituted, and full market/provider diagnostics remain available.

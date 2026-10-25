# 0.6.4 — Animated orbital mission control

Status: candidate awaiting release acceptance. Not yet deployed.

The user asked for a substantially more futuristic NASA-style interface with
prominent motion. This frontend-only release adds an animated projected
wireframe globe, orbital lights/rings, moving star field and perspective grid,
radar sweeps, cyan/blue illuminated panels, transitions and a globally available
FX switch. Motion is expressly decorative; provider badges and all market
readouts still require actual source evidence. No synthetic financial activity,
worldwide coverage or geographic provider locations are implied.

The FX preference stores only a visual on/off choice. OS reduced motion is
respected; animation stops for hidden pages and the globe stops offscreen.
Canvas is capped at 30 fps desktop / 24 fps mobile and 1.5 pixel ratio. No
external assets, rendering libraries, new dependencies or paid services.
Real order review and financial calculations are unchanged. No backend,
collectors, auth proxy, database, vault or service configuration change.

Acceptance includes all existing tests and new actual-canvas motion/pause,
preference persistence, reduced-motion, hidden-page and no-account-read/write
checks. Screenshots use labeled synthetic fixtures only.

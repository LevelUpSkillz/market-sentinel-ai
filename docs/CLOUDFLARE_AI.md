# Cloudflare AI research (0.6.2, not yet released)

The existing Next.js dashboard stays on Cloudflare Pages and the Python API,
collectors and dedicated PostgreSQL stay on Render. No Sentinel Intelligence
service, database or configuration is changed.

Implemented integration:
- Workers AI Llama 3.2 3B: plain-language English/French explanation and a separate
  skeptical review of supplied public market evidence. Explicit source references.
- Workers AI BGE Small embeddings: meaning-based search of the bounded current
  research set. Similarity measures text relevance, not profitability.
- Dedicated Market AI Gateway: caching, request limits and analytics. No prompt
  logging, external-provider fallback, provider secrets or purchased credits.
- Render issues public-only context packets after owner authentication and origin
  checks. Four/minute and thirty/day app-wide reservations persist in PostgreSQL.
  No private account/balance, risk profile, API secret or order data is passed.
- AI output cannot change a deterministic decision. Numerical price/probability
  claims, uncited output and direct order instructions are rejected. Model text
  is rendered as text, never HTML. AI has no trading tools.

Free-only activation:
`AI_FREE_PLAN_CONFIRMED` fails closed when absent. The user supplied an account
Workers Plans screenshot showing Free as Current plan on October 24, 2026;
this release explicitly configures true on that verified Free account. Verify Workers Free before enabling;
Cloudflare Free stops at its daily allowance instead of charging overages.
Workers Paid can charge above the shared free allowance. Billing-read access is
not available through the connected OAuth tools. Never silently infer a Free
plan from public pricing documentation, upgrade the account or buy AI credits.
No real inference is performed by synthetic CI tests.

Vectorize and AI Search have not been provisioned. They require a separate
current-plan/quota assessment; they are not needed to search this small research
set. Adding storage must not migrate the permanent PostgreSQL journal.

Verified official documentation October 24, 2026:
https://developers.cloudflare.com/workers-ai/platform/pricing/
https://developers.cloudflare.com/workers-ai/models/llama-3.2-3b-instruct/
https://developers.cloudflare.com/ai-gateway/usage/providers/workersai/
https://developers.cloudflare.com/vectorize/platform/pricing/

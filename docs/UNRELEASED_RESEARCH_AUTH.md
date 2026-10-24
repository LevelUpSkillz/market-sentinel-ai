# Unreleased Supabase Google research access

This branch preserves separate unfinished work. It is NOT deployed and must
not replace main. Rebase onto the latest tutorial/Cloudflare AI release before
finishing the full isolated PostgreSQL, proxy and browser acceptance gates.

Supabase is used only for verified Google identity and PKCE. Exact email invites
and viewer permissions remain in Market Sentinel Render PostgreSQL. Invited
viewers have no owner money, paper accounts, order, secrets or mutation access.
Owner Google login on the research hostname remains viewer-only. No Sentinel
Intelligence code, database or membership RPC is modified.

User reports adding only this redirect in existing Supabase Auth configuration:
https://market-research.getlevelupskillz.com/api/auth/google/callback
The correct existing project must be verified by an actual human Google flow.
No OAuth login, real invite or production auth change has been verified.

Local result before later app releases: 268 tests run, 262 pass, six PG skips.
Proxy cookie/redirect tests, generated types, viewer browser tests, real PG
acceptance and production configuration are still pending. No secret values
should be retrieved, copied to source, rotated or pasted in chat.

Later owner login fix: Market app received email-code login on October 24,
2026, with auto-redirect disabled and exact owner policy preserved. That Access
change is independent of this unfinished Google integration.

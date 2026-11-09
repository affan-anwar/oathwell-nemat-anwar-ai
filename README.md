# NematAnwar AI — Autonomous Marketing Agent

Marketing-only AI platform. Backend, React app (black and emerald, dark default with light mode), Owner Console, roles and permissions, multi-provider AI layer and browser tests are built and verified against mock providers. See docs/IMPLEMENTATION_REPORT.md for exactly what is and is not done. Not production ready (see `docs/IMPLEMENTATION_REPORT.md`).

## What works (verified, see `docs/VERIFICATION.md`)
- Register, login, workspaces, roles (viewer, editor, admin, owner), tenant isolation
- Brand profile saved in the database
- Campaigns with a state machine
- Content documents with immutable versions, hashes and diffs
- AI generation through the Anthropic API (returns an honest "not configured" error until you add a key)
- Approvals bound to the exact content version; any edit invalidates them
- Execution guard (pause, limits, disconnect, revoke, expiry) and idempotent WordPress publishing
- Scheduled publishing (separate worker), saved-schedule calendar, notifications, AI usage limit, quality checks, export
- Login rate limiting, server-side logout, security headers
- Audit trail, Alembic migrations, PostgreSQL support

## What is not done
Password reset, email verification, Redis/Celery (a database-backed scheduler is used instead), research, calendar API, analytics, notifications, campaign tasks, other integrations.
Real WordPress and the real AI provider are NOT verified (only mock-tested). Nothing is deployed.

## Run it
See `docs/SETUP.md` (API) and `apps/web/README.md` (web). Audit: `docs/PROJECT_AUDIT.md`.

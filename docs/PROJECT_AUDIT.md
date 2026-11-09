# Project Audit
Audit date: 2026-10-17. Method: read the files in this repository and ran the existing tests. Observations are separated from assumptions.

## Observed
- The repository is not a Git repository in this environment (`git status` fails). No history to review.
- Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL or SQLite. About 1,470 lines of Python in `apps/api/app`. 47 test functions plus parametrized cases (49 test cases).
- Frontend: before this change only `apps/web/design-preview/index.html`, a static HTML preview with sample data. There was no React app.
- No Redis, Celery, scheduler, or worker exists. No rate limiting. No analytics, research, calendar-backed schedules, notifications, or campaign tasks.
- Integrations: one WordPress adapter. AI: one Anthropic adapter. Both are tested with mock transports only.

## Status by area
| Area | Evidence | Status |
|---|---|---|
| Auth, workspaces, roles, isolation | 6 tests, run on SQLite and PostgreSQL 16 | Works |
| Brand profile, campaigns, content versions | tests | Works |
| Approvals and execution guard | tests | Works |
| AI generation | mock-tested; honest 503 when unconfigured | Awaiting credentials |
| WordPress publishing | mock-tested | Awaiting a real site |
| Migrations | upgrade and `alembic check` on PostgreSQL | Works |
| Frontend app | did not exist | Missing (built in this change) |
| Scheduling, workers, analytics, research, email, other channels | no code | Missing |

## Security and integrity risks (observed in code)
1. No login rate limiting or lockout.
2. No request size limit.
3. Access token has no refresh and no server-side revocation. Logout only discards the token in the browser.
4. SSRF check resolves DNS once (rebinding not fully covered).
5. Registration reveals whether an email exists (409).
6. Timestamps are naive UTC; time zone handling for schedules does not exist yet.
7. Password reset and email verification are missing.

## Credentials and decisions still needed
Anthropic API key, a WordPress site with an Application Password, an email provider, OAuth app registrations for LinkedIn and Meta. Decision: default autonomy per channel (see DECISIONS D3).

## Plan
P0 done earlier (auth, isolation, guard). P1 this change: React app on the real API. P2 next: scheduler and worker, scheduled publishing, rate limiting. P3: more channels, analytics, email.

## Redesign direction
Light-first premium B2B SaaS with an indigo accent, dark mode with charcoal (not navy), Inter typography, 8-pt spacing, one card style, consistent tables and forms, visible focus, honest empty, loading and error states.

## Addendum: real-browser audit (2026-10-24)
Method: Chromium 153 driven by Playwright and axe-core against the running app. Findings before fixes:
- Phone width: the top bar pushed Theme and Sign out off-screen (unreachable), and the page scrolled sideways.
- The hamburger button showed on desktop and did nothing.
- Calendar month and year dropdowns stretched to full width.
- Accessibility (axe): two serious label-mismatch violations on every page, one contrast failure, heading levels skipped on three pages.
- The app depended on Google Fonts.
All were fixed and are now guarded by browser tests (docs/IMPLEMENTATION_REPORT.md).

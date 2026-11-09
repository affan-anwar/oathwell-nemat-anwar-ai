# Product Requirements
## Purpose
NematAnwar AI is a marketing-only SaaS. An AI agent drafts content, a person approves the exact version, and a worker publishes it at the scheduled time. A result counts as published only when the provider confirms it.

## Users and roles
Viewer (read), Editor (create, request approval, publish approved posts), Admin (approve, connect accounts, pause), Owner (everything, adds admins). A new account owns only the workspace it creates. Roles are enforced on the server.

## Principles (non-negotiable)
1. No invented data. A number appears only if it is counted from this app's records or fetched from a connected provider. Otherwise the screen says "Not connected" or "Unavailable".
2. Human approval is the default. Approval is bound to one immutable content version; any edit cancels it.
3. The backend enforces every rule. The frontend is never a security boundary.
4. Unknown outcomes are shown as "unclear" and checked before any retry.

## Functional requirements and status
See `docs/IMPLEMENTATION_REPORT.md` (section "Comparison with the master prompt") for the current status of each requirement.

## Non-functional requirements
Light and dark themes (dark default); keyboard accessible, no serious axe violations; no horizontal scroll from 390 px; tenant isolation tests; no secrets in code; audit trail for external side effects.

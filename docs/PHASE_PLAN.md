# Phase Plan
Each phase ends with a sign-off gate. Do not start the next phase before sign-off.

| Phase | Deliverables | Tests | Acceptance | Gate |
|---|---|---|---|---|
| 0 Discovery | BRD approved, assumptions answered, provider list | none | Owner signs BRD | Signed BRD |
| 1 Identity, tenancy, DB, CI | Login, workspaces, roles, migrations, CI | Tenant isolation, auth | Two tenants cannot see each other's data | CI green |
| 2 Brief and workspace | Marketing brief, brand voice, calendar service (Hijri) | Unit, API | Brief saved per tenant | Demo |
| 3 Agent runtime | Planner, tool registry, model gateway, memory, limits | State machine, policy, AI evals | Agent cannot bypass the policy engine | Eval report |
| 4 Planner and Content Studio | Occasion planner, content versions, languages, repurposing | Version, hash | Plan generated from calendar | Demo |
| 5 First integration | Blog to WordPress end to end, execution tracking | Contract, failure, idempotency | Real post published and confirmed by provider | Real-account test log |
| 6 Analytics | Connected metrics, weekly report | Contract | Real numbers shown, sample clearly labeled | Demo |
| 7 Controlled autonomy | Automatic mode per channel, learning loop | Guard, limits | Automatic runs only inside rules | Risk review |
| 8 Hardening | Security review, backups, monitoring, kill switch drill | Restore test, pen test | Restore proven | Security sign-off |
| 9 Scale | Load tests, sharding plan, cost model | Load tests | Measured capacity report | Report |

Already done early (base for Phases 3 and 7): state machine, policy engine, execution guard and idempotent executor, with unit tests.

## Status (2026-10-26)
Phases 1 to 5 are implemented and tested (accounts, content and approvals, agent guard, first integration with WordPress, scheduling). Phase 6 (analytics) is not started because it needs provider credentials. Phase 7 (controlled autonomy) has its guard and scheduler but no settings screen. Phases 8 (hardening) is partly done: rate limiting, security headers, CSP, browser tests. Phase 9 (scale) is not started.

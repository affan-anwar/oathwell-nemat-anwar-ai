# API (prefix /api/v1). All workspace routes need `Authorization: Bearer <token>`.
Roles: viewer < editor < admin < owner. A workspace you do not belong to returns 404.

| Route | Role |
|---|---|
| POST /auth/register, POST /auth/login, GET /auth/me | public / user |
| POST, GET /workspaces | user |
| GET, PUT /workspaces/{ws}/profile | viewer, editor |
| GET, POST /workspaces/{ws}/members | viewer, admin |
| POST /workspaces/{ws}/pause | admin |
| GET /workspaces/{ws}/audit | admin |
| POST, GET /workspaces/{ws}/campaigns; GET, PATCH /{id}; POST /{id}/transition | editor / viewer |
| POST, GET /workspaces/{ws}/content; GET /{id}; POST /{id}/versions; GET /{id}/diff?a=&b=; POST /generate | editor / viewer |
| POST, GET /workspaces/{ws}/integrations/wordpress; POST /{id}/test; DELETE /{id} | admin |
| POST, GET /workspaces/{ws}/approvals; GET /{id}; POST /{id}/decision; POST /{id}/revoke | editor requests, admin decides |
| POST /workspaces/{ws}/approvals/{id}/execute | editor |
| GET /health, GET /health/ready | public |

Execution results: PUBLISHED (provider confirmed), FAILED (provider refused), UNCLEAR (result unknown, never retried automatically).

## Added in v4
| Route | Role |
|---|---|
| POST /auth/logout (cancels all tokens), POST /auth/change-password | user |
| POST /workspaces/{ws}/approvals  (optional `scheduled_at` with a time zone offset) | editor |
| PATCH /workspaces/{ws}/approvals/{id}/schedule (pending only) | editor |
| GET /workspaces/{ws}/notifications, POST /notifications/read | viewer (own only) |
| GET /workspaces/{ws}/ai/usage | viewer |
| GET /workspaces/{ws}/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD (max 62 days, times in UTC) | viewer |
| GET /workspaces/{ws}/metrics/operations?days=30 (internal workflow counts, not marketing results) | viewer |
| GET /workspaces/{ws}/content/{id}/check, GET /content/{id}/export?format=md or html | viewer |

Rules: sign-in locks for 15 minutes after 5 failures per email. A scheduled approval is published only by the scheduler worker, never by hand before its time. Two posts for the same account within 15 minutes are rejected. Requests over 1 MB are rejected (413).

## Added in v5
| Route | Role |
|---|---|
| GET /workspaces/{ws}/jobs?state=pending, blocked, processing, unclear, failed, published, expired (Publishing Failure Center) | viewer |
| POST /workspaces/{ws}/approvals/{id}/reconcile (asks the site whether an unclear publish happened; never publishes) | editor |
| POST /workspaces/{ws}/content/{id}/ai  `action`: rewrite_tone (needs `tone`), improve, to_linkedin, to_email, to_social, headlines, cta, brand_check | editor |
| GET /workspaces/{ws}/ai/usage now includes `by_action`, `estimated_cost` (only if prices are configured) | viewer |

Rules: an AI rewrite or improvement adds a new immutable version and invalidates any open approval for the document. Repurposing creates a new document linked to its source. Headlines, CTAs and brand checks are returned but not saved. Posts are published with a deterministic slug so a lost answer can be reconciled by looking the post up. A job stuck in EXECUTING for more than 5 minutes becomes UNCLEAR.

## Added in v6
| Route | Role |
|---|---|
| GET /workspaces/{ws}/dashboard?days=7..90 (agent state, KPIs with definitions, series, campaigns with progress, upcoming, integrations) | viewer |
| GET /workspaces/{ws}/activity?limit= (whitelisted audit events, no raw details) | viewer |
| GET /workspaces/{ws}/search?q= (campaign names and content titles, wildcards escaped, minimum 2 characters) | viewer |

Agent state rules: Paused (workspace paused) > Needs attention (unclear or failed jobs) > Running (scheduler heartbeat within 90 seconds) > Unavailable. Engagement rate is always reported as unavailable until an analytics source exists.

## Added in v7
| Route | Permission |
|---|---|
| GET /workspaces/{ws}/permissions | read (what the signed-in person may do) |
| PATCH /workspaces/{ws}/members/{user_id} (role, suspended), DELETE /workspaces/{ws}/members/{user_id} | member.manage (see RBAC.md for limits) |
| PUT /workspaces/{ws}/admin-permissions, POST /workspaces/{ws}/emergency-shutdown | Owner only |
| GET /workspaces/{ws}/theme | read |
| PUT /workspaces/{ws}/theme, POST .../theme/check, DELETE .../theme?scope= | Owner only (theme.write) |
| PUT /workspaces/{ws}/preferences (a person's own dark/light/system) | read; refused if the Owner locked the mode |
| GET /workspaces/{ws}/ai/providers, POST .../ai/providers/{provider}/test, PUT/DELETE .../ai/config | Owner only (ai.manage) |
| GET /workspaces/{ws}/ai/usage now includes `by_provider` and `unpriced_requests` | read |

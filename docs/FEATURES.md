# Features
Status: **Designed** = in the preview only. **Implemented** = code exists and is tested. **Planned** = not started.

| Feature | Status |
|---|---|
| Dashboard, Today, Autopilot, Channels, Performance screens | Designed |
| Calendar 570 to 2099 with Hijri dates and occasions | Designed (logic in the preview) |
| Occasion planner (countdown, offer, greeting, thank-you) | Designed |
| Content in 4 languages, repurposing, Brand Voice | Designed |
| Cancel window, learning loop card, weekly report | Designed |
| Approval and execution state machine | Implemented |
| Policy engine (modes, pause, caps, quiet hours, consent) | Implemented |
| Execution guard and idempotent executor | Implemented |
| Login, workspaces, roles, tenant isolation | Implemented (tested) |
| Brand profile saved in database | Implemented (tested) |
| Campaigns and state machine | Implemented (tested) |
| Content versions, hashes, diff | Implemented (tested) |
| AI generation (Anthropic API) | Implemented, mock-tested only |
| Approvals tied to exact version, invalidation | Implemented (tested) |
| WordPress publishing with idempotency | Implemented, mock-tested only |
| Audit trail, migrations, PostgreSQL | Implemented (tested) |
| AI model gateway, planner, memory | Planned |
| WordPress, email, social, ads, WhatsApp, CRM adapters | Planned |
| Real analytics | Planned |
| Agency mode, lead capture, competitor watch, review replies, A/B tests | Planned (ideas) |

## Frontend (React) status
| Screen | Status |
|---|---|
| Sign in, register, workspace creation | Implemented (render-tested with mock API; API journey verified on PostgreSQL) |
| Dashboard (counts from real API, honest empty states) | Implemented |
| Campaigns, Content Studio (versions, diff, AI generate, request approval) | Implemented |
| Approvals inbox (approve, reject, revoke, publish with confirmation) | Implemented |
| Brand Voice, Team, Audit log, Integrations (WordPress) | Implemented |
| Occasions calendar (Gregorian + Hijri) | Implemented (no scheduled items: scheduling not built) |
| Analytics, scheduling calendar, other channels, notifications | Not built |

## Added in v4
| Feature | Status |
|---|---|
| Login rate limiting, request size limit, security headers | Implemented (tested) |
| Server-side logout and change password (token versioning) | Implemented (tested) |
| Scheduled publishing with worker, time zones, conflict detection | Implemented (tested; live test used a local fake WordPress) |
| Calendar backed by saved schedules | Implemented (tested) |
| In-app notifications (bell) | Implemented (tested) |
| AI usage tracking and monthly limit | Implemented (mock provider tests) |
| Content quality checks, duplicate detection, export | Implemented (tested) |
| Workflow metrics (internal, not marketing results) | Implemented (tested) |
| Password reset, email verification | Not built: needs an email provider |

## Added in v5
| Feature | Status |
|---|---|
| Publishing Failure Center (all states, next step, check-the-site, retry) | Implemented (API tests, 12 real-browser tests) |
| Safe reconciliation of unclear results by slug lookup | Implemented (mock WordPress only) |
| Stuck job recovery (lease of 5 minutes) | Implemented (tested) |
| AI Copilot: rewrite tone, improve, headlines, CTAs, brand check, LinkedIn, email, social caption | Implemented (mock provider only) |
| Claim warnings (absolute claims, unapproved numbers), heuristic only | Implemented (tested) |
| AI cost estimate from configured prices | Implemented (tested) |
| New design system, account menu, collapsible sidebar, no external fonts | Implemented (browser tested) |
| Strict CSP and security headers on the web server | Implemented (browser tests ran under it); nginx file untested |
| Docker, docker-compose | Written, NOT tested |
| Campaign tasks and occasion planner, rich text editor, autosave | Not built |
| Analytics (Google Analytics, Search Console), visual automation builder, agency and billing | Not built |

## Added in v6
| Feature | Status |
|---|---|
| Dark-default design system, working theme switch (dark, light, match system), no flash | Implemented (unit and browser tests) |
| Dashboard: agent banner, KPIs, performance chart, quick actions, activity, campaigns, upcoming, accounts | Implemented, real data only |
| Scheduler heartbeat and honest agent state | Implemented (tested) |
| Top-bar search | Implemented (tested) |
| Agent Control Center (read-only), Analytics (publishing activity, CSV export, honest empty states) | Implemented |
| AI Copilot chat with tool calling | Not built (the page says so) |
| Campaign tasks, rich text editor, autosave, week and day calendar views | Not built |


## Added in v7
| Feature | Status |
|---|---|
| Roles: Owner, Admin, Super Agent, Editor, Viewer, Research/Content/Analytics/Publishing Agent; per-action permissions; suspend and remove; Owner protection; emergency shutdown | Implemented and tested |
| Owner Console: Theme Studio (live preview, validated, global or workspace), AI Providers, Access and Safety | Implemented and tested |
| Per-person dark/light mode with Owner default and lock | Implemented and tested |
| Multi-provider AI layer with verified models, health, usage, optional cost estimate, explicit fallback | Implemented, mock-tested only |
| Gesture controls (camera swipe, indicator, keyboard fallback) | Implemented (motion swipe only) |
| Autonomous research/analysis agents, event and job intelligence, social connectors | Not built |

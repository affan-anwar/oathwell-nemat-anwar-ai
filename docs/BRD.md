# Business Requirements Document — NematAnwar AI
Version 0.1 (draft). Not baselined. The approval record at the end is unsigned.

## 1. Purpose
Help businesses run daily marketing with an AI agent that works on its own inside client-set rules.

## 2. Scope
In scope: marketing only. Blog, email, social, SEO, leads, messaging, paid ads, content repurposing, analytics, Hijri-aware occasion planning.
Out of scope: accounting, HR, inventory, or any non-marketing business function.

## 3. Confirmed requirements (stated by the product owner)
- C1 Marketing only.
- C2 The agent is autonomous and works daily, not manual.
- C3 Real production system. No fake results, no simulated success.
- C4 Light and dark mode, professional and friendly UI.
- C5 Calendar from 570 CE to 2099 with Hijri dates, starting from 12 Rabi' al-Awwal (Monday).
- C6 Stack: React + Vite, FastAPI, PostgreSQL, Redis.
- C7 Multi-tenant, usable by many clients.

## 4. Assumptions (need confirmation)
- A1 A new channel starts at "Ask me first". "Automatic" is chosen per channel by a tenant admin. Email, WhatsApp and ads need an extra explicit opt-in for Automatic.
- A2 First vertical slice: Blog to WordPress.
- A3 Hijri dates use the tabular calendar, with a per-tenant adjustment of one day.
- A4 The exact Gregorian date of 12 Rabi' al-Awwal 570 CE is not pinned (sources differ, 569 to 571). Owner to supply the date to mark.
- A5 First customers: to be decided (small shops, agencies, or community organizations).

## 5. Functional requirements
FR1 Workspaces, users, roles. FR2 Marketing brief and brand voice. FR3 Daily plan from goals, results and calendar occasions.
FR4 Content generation with versions, languages (English, Hindi, Urdu, Arabic) and repurposing. FR5 Autopilot rules per channel: Automatic, Ask me first, Off.
FR6 Limits: posts per day, daily spend cap, quiet hours, time zone. FR7 Pause switch (tenant and global).
FR8 Execution only through allowlisted provider adapters, with idempotency and provider confirmation. FR9 Cancel window before execution.
FR10 Activity log of every agent step. FR11 Analytics from connected accounts only, sample data clearly labeled. FR12 Weekly report.
FR13 Consent, unsubscribe, disconnect, export and delete flows. FR14 Calendar 570 to 2099 with occasions.

## 6. Non-functional requirements
Tenant isolation. Secrets in a managed secrets service. TLS and encryption at rest. Audit log that cannot be edited. Accessible UI (keyboard, contrast, reduced motion).
Performance and 10-million-user scale are design targets, proven only by load tests.

## 7. Acceptance criteria
1. Content cannot execute without a valid approval or a policy that allows automatic action.
2. Any change to approved content invalidates the approval.
3. Paused, disconnected, over-limit or quiet-hour actions are blocked.
4. Retries never repeat an external action.
5. Missing credentials show a setup step, never a fake success.
6. Tenant isolation tests pass.

## 8. Dependencies
Provider API access (WordPress, Meta, LinkedIn, email provider, Google). AI model provider. Cloud account.

## 9. Risks
Platform policy changes. Provider rate limits. AI writes wrong claims (mitigation: source links, fact flags, banned words). Spam or reputation harm from email (mitigation: consent, caps, Ask-first default).

## 10. Approval record
| Role | Name | Decision | Date |
|---|---|---|---|
| Product owner | | | |
| Technical lead | | | |

# Roles and permissions
Generated from `apps/api/app/core/permissions.py`. Every API route checks a permission (never a role name). Deny by default.

| Permission | Viewer | Research Agent | Analytics Agent | Content Agent | Publishing Agent | Super Agent | Editor | Admin | Owner |
|---|---|---|---|---|---|---|---|---|---|
| `admin.delegate` |  |  |  |  |  |  |  |  | yes |
| `ai.manage` |  |  |  |  |  |  |  |  | yes |
| `analytics.sync` |  |  | yes |  |  | yes |  | yes | yes |
| `approval.decide` |  |  |  |  |  |  |  | yes | yes |
| `approval.request` |  |  |  |  |  | yes | yes | yes | yes |
| `audit.read` |  |  |  |  |  |  |  | yes | yes |
| `automation.pause` |  |  |  |  |  |  |  | yes | yes |
| `brand.write` |  |  |  |  |  |  | yes | yes | yes |
| `campaign.write` |  |  |  |  |  | yes | yes | yes | yes |
| `content.write` |  |  |  | yes |  | yes | yes | yes | yes |
| `credentials.revoke` |  |  |  |  |  |  |  |  | yes |
| `emergency.shutdown` |  |  |  |  |  |  |  |  | yes |
| `events.manage` |  |  |  |  |  |  |  | yes | yes |
| `events.plan` |  |  |  |  |  | yes | yes | yes | yes |
| `integration.manage` |  |  |  |  |  |  |  | yes | yes |
| `member.manage` |  |  |  |  |  |  |  | yes | yes |
| `publish.execute` |  |  |  |  | yes |  | yes | yes | yes |
| `read` | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| `research.write` |  | yes |  |  |  | yes |  | yes | yes |
| `role.manage_privileged` |  |  |  |  |  |  |  |  | yes |
| `theme.write` |  |  |  |  |  |  |  |  | yes |

## Owner protection and escalation rules (all enforced by the API and covered by tests in `tests/test_rbac.py`)
- Nobody can demote, suspend or remove the Owner, and ownership cannot be assigned through the API (the role is rejected, and the database CHECK constraint `ck_membership_role` only accepts known roles).
- Nobody can change their own role, suspension or membership, including the Owner and AI agents.
- Admins can manage only: analytics_agent, content_agent, editor, publishing_agent, research_agent, viewer. They cannot create or change Admins or Super Agents, and cannot edit themes, AI providers, delegation or trigger the emergency shutdown.
- The Owner can withdraw these delegated powers from Admins at any time: approval.decide, integration.manage, member.manage, automation.pause, audit.read, events.manage.
- Owner-only: theme.write, admin.delegate, role.manage_privileged, credentials.revoke, emergency.shutdown, ai.manage.
- A suspended member is denied everywhere (403) and the workspace disappears from their list. A removed member gets 404.
- Foreign workspaces and foreign object ids return 404 for every role (no cross-workspace access or object-id guessing).
- AI agent roles: the Super Agent can plan, draft and request approval, but it cannot approve, publish, connect accounts, manage people, read the audit log or widen its own powers. The Publishing Agent can run only an approval a human approved for that exact version. A Content Agent edit invalidates a human approval.
- Sensitive actions are audited with actor, time, action and result.

## Status
| Item | Status |
|---|---|
| Role/permission matrix enforced on the server | Implemented and tested (SQLite and PostgreSQL) |
| Owner cannot be removed, demoted, suspended or overridden | Implemented and tested |
| Privilege escalation, IDOR and cross-workspace attempts | Tested |
| Approval cannot be bypassed by any agent role | Tested |
| Emergency shutdown (pause and withdraw unrun approvals) | Implemented and tested |
| Owner recovery and strong authentication (2FA, recovery codes) | **Not built.** Owner uses the same password login as everyone |
| Owner access to *all* workspaces on the platform | **Not built.** The Owner role is per workspace; an Owner controls every workspace they own |
| Billing permissions | **Not built** (there is no billing) |
| Per-agent task assignment and tool allow-lists beyond the permission table | **Not built** |

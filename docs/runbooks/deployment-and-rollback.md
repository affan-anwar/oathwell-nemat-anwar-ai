# Runbook: Deployment and rollback (target process, not yet used)
Deploy: CI green, tag release, apply a backward-compatible database migration, deploy API, deploy web, run smoke checks (`/health`, login, one read).
Before release: confirm the global kill switch works.
Rollback: redeploy the previous tag. Do not roll back a migration that dropped data; use a forward fix. Pause autopilot for affected tenants while fixing.
Backups: daily database backup, restore tested every quarter (Phase 8).

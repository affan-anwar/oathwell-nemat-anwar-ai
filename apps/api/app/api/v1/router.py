from fastapi import APIRouter

from app.api.v1 import ai_providers, approvals, auth, campaigns, content, copilot, extras, integrations, theme, workspaces

api = APIRouter(prefix="/api/v1")
for m in (auth, workspaces, campaigns, content, copilot, integrations, approvals, extras, theme, ai_providers):
    api.include_router(m.router)

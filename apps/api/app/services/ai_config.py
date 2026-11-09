from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AiProviderConfig


def resolve_cfg(db, ws: str):
    """The Owner's saved AI selection for this workspace, or None to use the server's environment defaults."""
    c = db.scalar(select(AiProviderConfig).where(AiProviderConfig.workspace_id == ws, AiProviderConfig.enabled.is_(True)))
    if not c:
        return None
    fb = {"provider": c.fallback_provider, "model": c.fallback_model} if c.fallback_enabled and c.fallback_provider and c.fallback_model else None
    return {"provider": c.provider, "model": c.model, "fast_model": c.fast_model, "fallback": fb}


def who(cfg, usage=None):
    """(provider, model) to record for a request, taken from what actually answered."""
    u = usage or {}
    if u.get("provider"):
        return u["provider"], u.get("model", "")
    return (cfg["provider"], cfg["model"]) if cfg else ("anthropic", get_settings().llm_model)

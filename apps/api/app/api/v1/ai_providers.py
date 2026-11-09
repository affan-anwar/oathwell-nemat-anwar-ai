from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import current_user, require_perm
from app.db.models import AiProviderConfig, AiProviderHealth, utcnow
from app.db.session import get_db
from app.services import llm, providers
from app.services.audit import record

router = APIRouter(prefix="/workspaces/{ws}/ai", tags=["ai providers"])
PROV = "^(" + "|".join(providers.PROVIDERS) + ")$"


class ConfigIn(BaseModel):
    provider: str = Field(pattern=PROV)
    model: str = Field(min_length=1, max_length=120)
    fast_model: str | None = Field(default=None, max_length=120)
    fallback_enabled: bool = False
    fallback_provider: str | None = Field(default=None, pattern=PROV)
    fallback_model: str | None = Field(default=None, max_length=120)


def _health(db, provider):
    return db.get(AiProviderHealth, provider)


def _verified(db, provider, model, label):
    h = _health(db, provider)
    if not (h and h.last_ok_at and model in (h.models or [])):
        raise HTTPException(422, f"{label} model “{model}” is not verified for {providers.PROVIDERS[provider]['label']}. Run the connection test first and choose a model from the list your account can use")


@router.get("/providers")
def list_providers(ws: str, db=Depends(get_db), user=Depends(current_user)):
    """Status of each provider. API keys are never returned: only whether the server has one."""
    require_perm(db, user, ws, "ai.manage")
    out = []
    for key, meta in providers.PROVIDERS.items():
        h = _health(db, key)
        configured = bool(providers.key_for(key))
        out.append({"provider": key, "label": meta["label"], "env": meta["env"], "docs": meta["docs"], "key_configured": configured,
                    "connected": bool(configured and h and h.last_ok_at and not h.last_error),  # only after a real test succeeded
                    "last_test_at": h.last_test_at if h else None, "last_ok_at": h.last_ok_at if h else None, "last_error": h.last_error if h else None,
                    "models": (h.models or [])[:300] if h and h.last_ok_at else []})
    c = db.scalar(select(AiProviderConfig).where(AiProviderConfig.workspace_id == ws))
    cfg = None if not c else {"provider": c.provider, "model": c.model, "fast_model": c.fast_model, "fallback_enabled": c.fallback_enabled,
                              "fallback_provider": c.fallback_provider, "fallback_model": c.fallback_model, "updated_at": c.updated_at}
    return {"providers": out, "config": cfg, "note": "Model IDs differ between accounts. Only models returned by the provider for your key can be selected."}


@router.post("/providers/{provider}/test")
def test_provider(ws: str, provider: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "ai.manage")
    if provider not in providers.PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    h = _health(db, provider) or AiProviderHealth(provider=provider)
    db.add(h)
    h.last_test_at = utcnow()
    key = providers.key_for(provider)
    result = {"provider": provider}
    if not key:
        h.last_error = f"The API key is not set on the server. Set {providers.PROVIDERS[provider]['env']} in the server environment, then test again"
        result.update(ok=False, error=h.last_error)
    else:
        try:
            with llm.http_client() as c:
                models = providers.list_models(c, provider, key)
            h.last_ok_at, h.last_error, h.models = utcnow(), None, sorted(models)[:1000]
            result.update(ok=True, model_count=len(models), models=h.models[:300])
        except providers.ProviderError as e:
            h.last_error = str(e)
            result.update(ok=False, error=h.last_error)
    record(db, ws, user.id, "ai.provider_test", "ai_provider", provider, "success" if result["ok"] else "failed", {"provider": provider, "error": result.get("error")})
    db.commit()
    return result


@router.put("/config")
def put_config(ws: str, body: ConfigIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "ai.manage")
    _verified(db, body.provider, body.model, "Primary")
    if body.fast_model:
        _verified(db, body.provider, body.fast_model, "Fast")
    if body.fallback_enabled:
        if not (body.fallback_provider and body.fallback_model):
            raise HTTPException(422, "Choose the fallback provider and model, or turn the fallback off")
        _verified(db, body.fallback_provider, body.fallback_model, "Fallback")
    c = db.scalar(select(AiProviderConfig).where(AiProviderConfig.workspace_id == ws)) or AiProviderConfig(workspace_id=ws, updated_by=user.id)
    db.add(c)
    c.provider, c.model, c.fast_model, c.enabled, c.updated_by = body.provider, body.model, body.fast_model or None, True, user.id
    c.fallback_enabled = body.fallback_enabled
    c.fallback_provider, c.fallback_model = (body.fallback_provider, body.fallback_model) if body.fallback_enabled else (None, None)
    record(db, ws, user.id, "ai.config", "workspace", ws, detail={"provider": c.provider, "model": c.model, "fast_model": c.fast_model, "fallback": c.fallback_enabled})
    db.commit()
    return {"saved": True, "provider": c.provider, "model": c.model, "fast_model": c.fast_model, "fallback_enabled": c.fallback_enabled}


@router.delete("/config")
def reset_config(ws: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "ai.manage")
    c = db.scalar(select(AiProviderConfig).where(AiProviderConfig.workspace_id == ws))
    if c:
        db.delete(c)
    record(db, ws, user.id, "ai.config_reset", "workspace", ws)
    db.commit()
    return {"saved": False}

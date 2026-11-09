from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import current_user, require_perm, scoped
from app.api.v1.content import _new_doc, append_version, doc_out, ver_out
from app.api.v1.workspaces import profile_dict
from app.core.config import get_settings
from app.services.ai_config import resolve_cfg, who
from app.db.models import AiUsage, BusinessProfile, ContentDocument, ContentVersion, utcnow
from app.db.session import get_db
from app.services import llm
from app.services.audit import record

router = APIRouter(prefix="/workspaces/{ws}/content", tags=["ai copilot"])
TARGET = {"to_linkedin": "social_post", "to_email": "email", "to_social": "social_post"}


class AiIn(BaseModel):
    action: str = Field(pattern="^(rewrite_tone|improve|to_linkedin|to_email|to_social|headlines|cta|brand_check)$")
    tone: str | None = Field(default=None, min_length=2, max_length=60)


def _usage(db, ws, user, action, campaign_id, usage, status, cfg=None):
    pv, md = who(cfg, usage)
    db.add(AiUsage(workspace_id=ws, user_id=user.id, model=md, provider=pv, action=action, campaign_id=campaign_id,
                   input_tokens=(usage or {}).get("input_tokens", 0), output_tokens=(usage or {}).get("output_tokens", 0), status=status))


@router.post("/{did}/ai")
def run(ws: str, did: str, body: AiIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "content.write")
    d = scoped(db, ContentDocument, did, ws)
    v = db.scalar(select(ContentVersion).where(ContentVersion.document_id == did).order_by(ContentVersion.number.desc()).limit(1))
    if body.action == "rewrite_tone" and not body.tone:
        raise HTTPException(422, "Choose a tone")
    s = get_settings()
    month = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if db.scalar(select(func.count()).select_from(AiUsage).where(AiUsage.workspace_id == ws, AiUsage.created_at >= month)) >= s.ai_monthly_limit:
        raise HTTPException(429, f"Monthly AI limit of {s.ai_monthly_limit} requests reached")
    try:
        cfg = resolve_cfg(db, ws)
        out, used, usage = llm.transform(profile_dict(db.get(BusinessProfile, ws)), body.action, d.title, v.body, body.tone, cfg)
    except llm.LLMNotConfigured as e:
        raise HTTPException(503, str(e))
    except llm.LLMError as e:
        _usage(db, ws, user, body.action, d.campaign_id, e.usage, "rejected" if e.usage else "failed", cfg)
        record(db, ws, user.id, "content.ai", "content_document", did, "failed", {"action": body.action, "reason": str(e)})
        db.commit()
        raise HTTPException(502, str(e))
    _usage(db, ws, user, body.action, d.campaign_id, usage, "success", cfg)
    meta = {"ai_action": body.action, "parent_version": v.number, "tone": body.tone, "model": usage.get("model", s.llm_model), "provider": usage.get("provider", "anthropic"), "used_profile_fields": used}
    if isinstance(out, llm.Items):
        record(db, ws, user.id, "content.ai", "content_document", did, detail={"action": body.action})
        db.commit()
        return {"kind": "suggestions", "action": body.action, "items": out.items, "saved": False}
    if isinstance(out, llm.Rewritten):  # a new immutable version; the source version is never changed
        nv = append_version(db, ws, user, d, out.body, meta, "ai", {"ai_action": body.action})
        db.commit()
        return {"kind": "version", "version": ver_out(nv)}
    meta["derived_from"] = {"document_id": d.id, "version_id": v.id, "version_number": v.number}
    nd, nv = _new_doc(db, ws, user, TARGET[body.action], out.title, out.body, meta, d.campaign_id, "ai")
    db.commit()
    return {"kind": "document", "document": doc_out(nd, [nv])}

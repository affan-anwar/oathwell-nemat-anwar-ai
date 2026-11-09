import difflib
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import current_user, require_perm, scoped
from app.api.v1.workspaces import profile_dict
from app.core.config import get_settings
from app.services.ai_config import resolve_cfg, who
from app.db.models import (AiUsage, ApprovalRequest, BusinessProfile, Campaign, ContentDocument, ContentVersion, utcnow)
from app.db.session import get_db
from app.services import llm
from app.services.audit import record

router = APIRouter(prefix="/workspaces/{ws}/content", tags=["content"])
KINDS = "^(blog|social_post|email|ad_copy|product_description|landing_page|video_script|content_brief|seo_metadata)$"


def content_hash(body: str, meta: dict | None) -> str:
    return hashlib.sha256(json.dumps({"body": body, "meta": meta or {}}, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


class ContentIn(BaseModel):
    kind: str = Field(pattern=KINDS)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    meta: dict = Field(default_factory=dict)
    campaign_id: str | None = None


class VersionIn(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    meta: dict = Field(default_factory=dict)


class GenerateIn(BaseModel):
    kind: str = Field(pattern=KINDS)
    brief: str = Field(min_length=3, max_length=4000)
    language: str | None = Field(default=None, max_length=40)
    campaign_id: str | None = None


def ver_out(v: ContentVersion) -> dict:
    return {"id": v.id, "number": v.number, "body": v.body, "meta": v.meta, "content_hash": v.content_hash,
            "source": v.source, "author_id": v.author_id, "created_at": v.created_at}


def doc_out(d: ContentDocument, versions=None) -> dict:
    o = {"id": d.id, "kind": d.kind, "title": d.title, "status": d.status, "campaign_id": d.campaign_id,
         "created_at": d.created_at}
    if versions is not None:
        o["versions"] = [ver_out(v) for v in versions]
    return o


def _check_campaign(db, ws, campaign_id):
    if campaign_id:
        scoped(db, Campaign, campaign_id, ws)


def _new_doc(db, ws, user, kind, title, body, meta, campaign_id, source):
    _check_campaign(db, ws, campaign_id)
    d = ContentDocument(workspace_id=ws, campaign_id=campaign_id, kind=kind, title=title, created_by=user.id)
    db.add(d)
    db.flush()
    v = ContentVersion(document_id=d.id, workspace_id=ws, number=1, body=body, meta=meta,
                       content_hash=content_hash(body, meta), source=source, author_id=user.id)
    db.add(v)
    db.flush()
    record(db, ws, user.id, "content.create", "content_document", d.id, detail={"source": source})
    return d, v


@router.post("", status_code=201)
def create(ws: str, body: ContentIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "content.write")
    d, v = _new_doc(db, ws, user, body.kind, body.title, body.body, body.meta, body.campaign_id, "human")
    db.commit()
    return doc_out(d, [v])


@router.post("/generate", status_code=201)
def generate(ws: str, body: GenerateIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "content.write")
    _check_campaign(db, ws, body.campaign_id)
    s = get_settings()
    month = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used_now = db.scalar(select(func.count()).select_from(AiUsage).where(AiUsage.workspace_id == ws, AiUsage.created_at >= month))
    if used_now >= s.ai_monthly_limit:
        raise HTTPException(429, f"Monthly AI limit of {s.ai_monthly_limit} requests reached")
    profile = profile_dict(db.get(BusinessProfile, ws))
    cfg = resolve_cfg(db, ws)
    try:
        out, used, usage = llm.generate(profile, body.kind, body.brief, body.language, cfg)
    except llm.LLMNotConfigured as e:
        raise HTTPException(503, str(e))
    except llm.LLMError as e:
        u = e.usage or {}
        pv, md = who(cfg, u)
        db.add(AiUsage(workspace_id=ws, user_id=user.id, model=md, provider=pv, input_tokens=u.get("input_tokens", 0),
                       output_tokens=u.get("output_tokens", 0), status="rejected" if e.usage else "failed"))
        record(db, ws, user.id, "content.generate", "content_document", None, "failed", {"reason": str(e)})
        db.commit()
        raise HTTPException(502, str(e))
    pv, md = who(cfg, usage)
    db.add(AiUsage(workspace_id=ws, user_id=user.id, model=md, provider=pv, input_tokens=usage["input_tokens"],
                   output_tokens=usage["output_tokens"], status="success"))
    meta = {"used_profile_fields": used, "meta_title": out.meta_title, "meta_description": out.meta_description, "model": md, "provider": pv}
    if usage.get("fallback_used"):
        meta.update(fallback_used=True, primary_error=usage.get("primary_error"))
    d, v = _new_doc(db, ws, user, body.kind, out.title, out.body, meta, body.campaign_id, "ai")
    db.commit()
    return doc_out(d, [v])


@router.get("")
def list_(ws: str, kind: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
          db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    q = select(ContentDocument).where(ContentDocument.workspace_id == ws)
    if kind:
        q = q.where(ContentDocument.kind == kind)
    return [doc_out(d) for d in db.scalars(q.order_by(ContentDocument.created_at.desc()).limit(limit).offset(offset))]


@router.get("/{did}")
def get(ws: str, did: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    d = scoped(db, ContentDocument, did, ws)
    vs = db.scalars(select(ContentVersion).where(ContentVersion.document_id == did).order_by(ContentVersion.number)).all()
    return doc_out(d, vs)


def append_version(db, ws, user, d, body, meta, source="human", extra=None):
    """The only way a version is added. Older approvals for the document are invalidated here."""
    n = (db.scalar(select(func.max(ContentVersion.number)).where(ContentVersion.document_id == d.id)) or 0) + 1
    v = ContentVersion(document_id=d.id, workspace_id=ws, number=n, body=body, meta=meta,
                       content_hash=content_hash(body, meta), source=source, author_id=user.id)
    db.add(v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another edit was saved at the same time. Reload and try again")
    res = db.execute(update(ApprovalRequest).where(ApprovalRequest.document_id == d.id,
                                                  ApprovalRequest.status.in_(["PENDING", "APPROVED"])).values(status="INVALIDATED"))
    if d.status != "published":
        d.status = "draft"
    record(db, ws, user.id, "content.version", "content_document", d.id,
           detail={"number": n, "source": source, "approvals_invalidated": res.rowcount, **(extra or {})})
    return v


@router.post("/{did}/versions", status_code=201)
def new_version(ws: str, did: str, body: VersionIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "content.write")
    d = scoped(db, ContentDocument, did, ws)
    v = append_version(db, ws, user, d, body.body, body.meta)
    db.commit()
    return ver_out(v)


@router.get("/{did}/diff")
def diff(ws: str, did: str, a: int, b: int, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    scoped(db, ContentDocument, did, ws)
    got = {v.number: v for v in db.scalars(select(ContentVersion).where(
        ContentVersion.document_id == did, ContentVersion.number.in_([a, b])))}
    if a not in got or b not in got:
        raise HTTPException(404, "Version not found")
    lines = difflib.unified_diff(got[a].body.splitlines(), got[b].body.splitlines(), f"v{a}", f"v{b}", lineterm="")
    return {"from": a, "to": b, "diff": "\n".join(lines)}

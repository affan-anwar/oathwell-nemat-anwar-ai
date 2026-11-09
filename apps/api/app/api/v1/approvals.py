from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.api.deps import current_user, require_perm, scoped
from app.api.v1.workspaces import profile_dict
from app.core.config import get_settings
from app.db.models import (ApprovalRequest, BusinessProfile, ContentDocument, ContentVersion, Integration, utcnow)
from app.db.session import get_db
from app.services import quality
from app.services.audit import record
from app.services.execution import Blocked, reconcile, run_approval
from app.services.notifications import admin_ids, notify

router = APIRouter(prefix="/workspaces/{ws}/approvals", tags=["approvals"])
CONFLICT_MINUTES = 15


def _aware(v):
    if v is not None and v.tzinfo is None:
        raise ValueError("include a time zone offset, for example +05:30 or Z")
    return v


class RequestIn(BaseModel):
    version_id: str
    integration_id: str
    action: str = Field(pattern="^publish_blog$")
    scheduled_at: datetime | None = None
    _v = field_validator("scheduled_at")(_aware)


class ScheduleIn(BaseModel):
    scheduled_at: datetime | None = None
    _v = field_validator("scheduled_at")(_aware)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject|request_changes)$")
    comment: str | None = Field(default=None, max_length=2000)


def to_utc(dt: datetime | None):
    """Validates a requested schedule and returns naive UTC."""
    if dt is None:
        return None
    u = dt.astimezone(timezone.utc).replace(tzinfo=None)
    now = utcnow()
    if not (now + timedelta(minutes=1) <= u <= now + timedelta(days=365)):
        raise HTTPException(422, "scheduled_at must be between 1 minute and 1 year from now")
    return u


def _conflict(db, ws, integration_id, when, exclude=None):
    q = select(ApprovalRequest).where(
        ApprovalRequest.workspace_id == ws, ApprovalRequest.integration_id == integration_id,
        ApprovalRequest.status.in_(["PENDING", "APPROVED"]),
        ApprovalRequest.scheduled_at.between(when - timedelta(minutes=CONFLICT_MINUTES), when + timedelta(minutes=CONFLICT_MINUTES)))
    if exclude:
        q = q.where(ApprovalRequest.id != exclude)
    other = db.scalar(q.limit(1))
    if other:
        raise HTTPException(409, f"Another post for this account is scheduled at {other.scheduled_at.isoformat()} UTC (within {CONFLICT_MINUTES} minutes)")


def out(a: ApprovalRequest, db, detail=False) -> dict:
    o = {"id": a.id, "document_id": a.document_id, "version_id": a.version_id, "content_hash": a.content_hash,
         "action": a.action, "integration_id": a.integration_id, "status": a.status, "requested_by": a.requested_by,
         "decided_by": a.decided_by, "decided_at": a.decided_at, "comment": a.comment, "expires_at": a.expires_at,
         "scheduled_at": a.scheduled_at, "block_reason": a.block_reason, "created_at": a.created_at}
    if detail:
        v, d, i = db.get(ContentVersion, a.version_id), db.get(ContentDocument, a.document_id), db.get(Integration, a.integration_id)
        o["preview"] = {"title": d.title, "body": v.body, "version_number": v.number, "source": v.source,
                        "destination": f"{i.label} ({i.config.get('site_url')})", "risk": "Publishes live to a public website"}
    return o


@router.post("", status_code=201)
def request_approval(ws: str, body: RequestIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "approval.request")
    v = scoped(db, ContentVersion, body.version_id, ws)
    i = scoped(db, Integration, body.integration_id, ws)
    d = db.get(ContentDocument, v.document_id)
    latest = db.scalar(select(func.max(ContentVersion.number)).where(ContentVersion.document_id == d.id))
    if d.kind != "blog" or i.provider != "wordpress":
        raise HTTPException(422, "publish_blog needs a blog document and a WordPress integration")
    if v.number != latest:
        raise HTTPException(409, "Only the latest version can be sent for approval")
    if db.scalar(select(ApprovalRequest.id).where(ApprovalRequest.version_id == v.id, ApprovalRequest.action == body.action,
                                                  ApprovalRequest.status.in_(["PENDING", "APPROVED"]))):
        raise HTTPException(409, "This version already has an open approval")
    errors = [x["message"] for x in quality.check(db, ws, d, v, profile_dict(db.get(BusinessProfile, ws))) if x["level"] == "error"]
    if errors:
        raise HTTPException(422, "Content check failed: " + " ".join(errors))
    when = to_utc(body.scheduled_at)
    if when:
        _conflict(db, ws, i.id, when)
    a = ApprovalRequest(workspace_id=ws, document_id=d.id, version_id=v.id, content_hash=v.content_hash,
                        action=body.action, integration_id=i.id, requested_by=user.id, scheduled_at=when)
    db.add(a)
    d.status = "review"
    db.flush()
    notify(db, ws, [x for x in admin_ids(db, ws) if x != user.id], "approval_requested", f"Approval needed: “{d.title}”",
           f"{user.email} asked to publish v{v.number}" + (f" at {when.isoformat()} UTC" if when else ""), "/approvals")
    record(db, ws, user.id, "approval.request", "approval", a.id, detail={"version": v.number, "scheduled_at": when.isoformat() if when else None})
    db.commit()
    return out(a, db, True)


@router.get("")
def list_(ws: str, status: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
          db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    q = select(ApprovalRequest).where(ApprovalRequest.workspace_id == ws)
    if status:
        q = q.where(ApprovalRequest.status == status)
    return [out(a, db) for a in db.scalars(q.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset))]


@router.get("/{aid}")
def get(ws: str, aid: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    return out(scoped(db, ApprovalRequest, aid, ws), db, True)


@router.patch("/{aid}/schedule")
def reschedule(ws: str, aid: str, body: ScheduleIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "approval.request")
    a = scoped(db, ApprovalRequest, aid, ws)
    if a.status != "PENDING":
        raise HTTPException(409, "Only a pending request can be rescheduled. Revoke the approval and request again")
    when = to_utc(body.scheduled_at)
    if when:
        _conflict(db, ws, a.integration_id, when, exclude=a.id)
    a.scheduled_at = when
    record(db, ws, user.id, "approval.reschedule", "approval", a.id, detail={"scheduled_at": when.isoformat() if when else None})
    db.commit()
    return out(a, db)


@router.post("/{aid}/decision")
def decide(ws: str, aid: str, body: DecisionIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "approval.decide")
    a = scoped(db, ApprovalRequest, aid, ws)
    if a.status != "PENDING":
        raise HTTPException(409, f"Approval is {a.status}, not pending")
    now = utcnow()
    if body.decision == "approve" and a.scheduled_at and a.scheduled_at <= now:
        raise HTTPException(409, "The scheduled time has already passed. Ask for a new schedule")
    a.status = {"approve": "APPROVED", "reject": "REJECTED", "request_changes": "CHANGES_REQUESTED"}[body.decision]
    a.decided_by, a.decided_at, a.comment = user.id, now, body.comment
    d = db.get(ContentDocument, a.document_id)
    if a.status == "APPROVED":
        a.expires_at = max(now + timedelta(hours=get_settings().approval_hours), (a.scheduled_at or now) + timedelta(hours=6))
        d.status = "approved"
    notify(db, ws, [a.requested_by], "approval_decided", f"“{d.title}”: {a.status.replace('_', ' ').lower()}", body.comment, "/approvals")
    record(db, ws, user.id, f"approval.{body.decision}", "approval", a.id)
    db.commit()
    return out(a, db)


@router.post("/{aid}/revoke")
def revoke(ws: str, aid: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "approval.decide")
    a = scoped(db, ApprovalRequest, aid, ws)
    if a.status != "APPROVED":
        raise HTTPException(409, "Only an approved request can be revoked")
    a.status = "REVOKED"
    record(db, ws, user.id, "approval.revoke", "approval", a.id)
    db.commit()
    return out(a, db)


@router.post("/{aid}/execute")
def execute(ws: str, aid: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "publish.execute")
    a = scoped(db, ApprovalRequest, aid, ws)
    res = run_approval(db, a, user.id, "manual")
    if isinstance(res, Blocked):
        record(db, ws, user.id, "execution.blocked", "approval", a.id, "blocked", {"reason": res.reason})
        db.commit()
        raise HTTPException(409, f"Blocked: {res.reason}")
    r = res.record
    return {"execution": {"id": r.id, "status": r.status, "detail": r.detail, "external_id": r.external_id,
                          "external_url": r.external_url}, "repeated": res.repeated}


@router.post("/{aid}/reconcile")
def reconcile_route(ws: str, aid: str, db=Depends(get_db), user=Depends(current_user)):
    """Asks the site whether an unclear publish actually happened. Never publishes anything."""
    require_perm(db, user, ws, "publish.execute")
    appr = scoped(db, ApprovalRequest, aid, ws)
    res = reconcile(db, appr, user.id)
    if res is None:
        raise HTTPException(409, "Only an unclear result can be checked")
    r = res["execution"]
    return {"outcome": res["outcome"], "detail": res["detail"],
            "execution": {"id": r.id, "status": r.status, "detail": r.detail, "external_id": r.external_id, "external_url": r.external_url}}

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import current_user, require_perm
from app.core.permissions import ASSIGNABLE, DELEGABLE, LABELS, ROLE_PERMS, can_assign, effective_perms
from app.db.models import ApprovalRequest, AuditEvent, BusinessProfile, Membership, User, Workspace, utcnow
from app.db.session import get_db
from app.services.audit import record

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
PROFILE_COLS = ["business_name", "description", "website", "industry", "products", "target_audience", "market",
                "languages", "brand_voice", "guidelines", "approved_claims", "prohibited_claims", "competitors",
                "objectives", "currency", "budget_limit", "channels", "timezone", "occasions"]


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProfileIn(BaseModel):
    business_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=120)
    products: str | None = Field(default=None, max_length=4000)
    target_audience: str | None = Field(default=None, max_length=4000)
    market: str | None = Field(default=None, max_length=200)
    languages: list[str] | None = Field(default=None, max_length=10)
    brand_voice: str | None = Field(default=None, max_length=4000)
    guidelines: str | None = Field(default=None, max_length=8000)
    approved_claims: str | None = Field(default=None, max_length=4000)
    prohibited_claims: str | None = Field(default=None, max_length=4000)
    competitors: list[str] | None = Field(default=None, max_length=20)
    objectives: str | None = Field(default=None, max_length=4000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    budget_limit: float | None = Field(default=None, ge=0)
    channels: list[str] | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    occasions: list[str] | None = Field(default=None, max_length=50)


ROLE_RE = "^(" + "|".join(ASSIGNABLE) + ")$"


class MemberIn(BaseModel):
    email: str
    role: str = Field(pattern=ROLE_RE)


class MemberPatch(BaseModel):
    role: str | None = Field(default=None, pattern=ROLE_RE)
    suspended: bool | None = None


class RevokeIn(BaseModel):
    revoked: list[str] = Field(default_factory=list, max_length=20)


class PauseIn(BaseModel):
    paused: bool


def profile_dict(p: BusinessProfile) -> dict:
    d = {c: getattr(p, c) for c in PROFILE_COLS}
    d["budget_limit"] = float(d["budget_limit"]) if d["budget_limit"] is not None else None
    return d


@router.post("", status_code=201)
def create_workspace(body: WorkspaceIn, db=Depends(get_db), user=Depends(current_user)):
    ws = Workspace(name=body.name.strip())
    db.add(ws)
    db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
    db.add(BusinessProfile(workspace_id=ws.id, business_name=ws.name))
    record(db, ws.id, user.id, "workspace.create", "workspace", ws.id)
    db.commit()
    return {"id": ws.id, "name": ws.name, "role": "owner", "paused": ws.paused}


@router.get("")
def list_workspaces(db=Depends(get_db), user=Depends(current_user)):
    rows = db.execute(select(Workspace, Membership.role).join(Membership, Membership.workspace_id == Workspace.id)
                      .where(Membership.user_id == user.id, Membership.suspended.is_(False)).order_by(Workspace.created_at)).all()
    return [{"id": w.id, "name": w.name, "role": r, "paused": w.paused} for w, r in rows]


@router.get("/{ws}/profile")
def get_profile(ws: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    return profile_dict(db.get(BusinessProfile, ws))


@router.put("/{ws}/profile")
def put_profile(ws: str, body: ProfileIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "brand.write")
    p = db.get(BusinessProfile, ws)
    changed = []
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
        changed.append(k)
    record(db, ws, user.id, "profile.update", "business_profile", ws, detail={"fields": changed})
    db.commit()
    return profile_dict(p)


@router.get("/{ws}/members")
def members(ws: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    rows = db.execute(select(User, Membership).join(Membership, Membership.user_id == User.id).where(Membership.workspace_id == ws)).all()
    return [{"user_id": u.id, "email": u.email, "full_name": u.full_name, "role": m.role, "label": LABELS[m.role], "suspended": m.suspended} for u, m in rows]


def _guard(me, user, target, w, new_role):
    """The rules that keep the Owner safe and stop privilege escalation. Applied to every change of another person's access."""
    if target.user_id == user.id:
        raise HTTPException(403, "You cannot change your own access")
    if target.role == "owner":
        raise HTTPException(403, "The Owner cannot be changed")
    if not can_assign(me.role, target.role, new_role, w.admin_revoked):
        raise HTTPException(403, "Your role cannot manage this member")


def _target(db, ws, user_id):
    t = db.scalar(select(Membership).where(Membership.workspace_id == ws, Membership.user_id == user_id))
    if not t:
        raise HTTPException(404, "Member not found")
    return t


@router.post("/{ws}/members", status_code=201)
def add_member(ws: str, body: MemberIn, db=Depends(get_db), user=Depends(current_user)):
    me = require_perm(db, user, ws, "member.manage")
    w = db.get(Workspace, ws)
    if not can_assign(me.role, None, body.role, w.admin_revoked):
        raise HTTPException(403, "Your role cannot add this kind of member")
    target = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not target:
        raise HTTPException(404, "No account with this email. Ask them to register first")
    if db.scalar(select(Membership).where(Membership.workspace_id == ws, Membership.user_id == target.id)):
        raise HTTPException(409, "Already a member")
    db.add(Membership(workspace_id=ws, user_id=target.id, role=body.role))
    record(db, ws, user.id, "member.add", "user", target.id, detail={"role": body.role})
    db.commit()
    return {"user_id": target.id, "role": body.role}


@router.patch("/{ws}/members/{user_id}")
def update_member(ws: str, user_id: str, body: MemberPatch, db=Depends(get_db), user=Depends(current_user)):
    me = require_perm(db, user, ws, "member.manage")
    w, t = db.get(Workspace, ws), _target(db, ws, user_id)
    _guard(me, user, t, w, body.role)
    if body.role and body.role != t.role:
        old, t.role = t.role, body.role
        record(db, ws, user.id, "member.role_change", "user", user_id, detail={"from": old, "to": body.role})
    if body.suspended is not None and body.suspended != t.suspended:
        t.suspended = body.suspended
        record(db, ws, user.id, "member.suspend" if body.suspended else "member.unsuspend", "user", user_id)
    db.commit()
    return {"user_id": user_id, "role": t.role, "suspended": t.suspended}


@router.delete("/{ws}/members/{user_id}")
def remove_member(ws: str, user_id: str, db=Depends(get_db), user=Depends(current_user)):
    me = require_perm(db, user, ws, "member.manage")
    w, t = db.get(Workspace, ws), _target(db, ws, user_id)
    _guard(me, user, t, w, None)
    db.delete(t)
    record(db, ws, user.id, "member.remove", "user", user_id, detail={"role": t.role})
    db.commit()
    return {"removed": user_id}


@router.get("/{ws}/permissions")
def permissions(ws: str, db=Depends(get_db), user=Depends(current_user)):
    """What the signed-in person may do here. The web app uses this to show or hide controls; the server still checks every request."""
    me = require_perm(db, user, ws, "read")
    w = db.get(Workspace, ws)
    return {"role": me.role, "label": LABELS[me.role], "permissions": effective_perms(me.role, w.admin_revoked), "admin_revoked": w.admin_revoked or [],
            "delegable": DELEGABLE, "roles": [{"role": r, "label": LABELS[r], "permissions": sorted(p)} for r, p in ROLE_PERMS.items()]}


@router.put("/{ws}/admin-permissions")
def admin_permissions(ws: str, body: RevokeIn, db=Depends(get_db), user=Depends(current_user)):
    """Owner only: choose which delegated powers Admins keep."""
    require_perm(db, user, ws, "admin.delegate")
    bad = [p for p in body.revoked if p not in DELEGABLE]
    if bad:
        raise HTTPException(422, f"Not a delegable permission: {', '.join(bad)}")
    w = db.get(Workspace, ws)
    w.admin_revoked = sorted(set(body.revoked))
    record(db, ws, user.id, "owner.admin_permissions", "workspace", ws, detail={"revoked": w.admin_revoked})
    db.commit()
    return {"admin_revoked": w.admin_revoked}


@router.post("/{ws}/emergency-shutdown")
def emergency_shutdown(ws: str, db=Depends(get_db), user=Depends(current_user)):
    """Owner only: pause the workspace and withdraw every approval that has not run yet. Nothing is deleted."""
    require_perm(db, user, ws, "emergency.shutdown")
    w = db.get(Workspace, ws)
    w.paused = True
    n = 0
    for a in db.scalars(select(ApprovalRequest).where(ApprovalRequest.workspace_id == ws, ApprovalRequest.status == "APPROVED")):
        a.status, n = "REVOKED", n + 1
    record(db, ws, user.id, "owner.emergency_shutdown", "workspace", ws, detail={"approvals_revoked": n})
    db.commit()
    return {"paused": True, "approvals_revoked": n}


@router.post("/{ws}/pause")
def pause(ws: str, body: PauseIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "automation.pause")
    w = db.get(Workspace, ws)
    w.paused = body.paused
    record(db, ws, user.id, "workspace.pause" if body.paused else "workspace.resume", "workspace", ws)
    db.commit()
    return {"paused": w.paused}


@router.get("/{ws}/audit")
def audit(ws: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
          db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "audit.read")
    rows = db.scalars(select(AuditEvent).where(AuditEvent.workspace_id == ws)
                      .order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)).all()
    return [{"id": e.id, "actor_id": e.actor_id, "action": e.action, "target_type": e.target_type,
             "target_id": e.target_id, "outcome": e.outcome, "detail": e.detail, "created_at": e.created_at}
            for e in rows]

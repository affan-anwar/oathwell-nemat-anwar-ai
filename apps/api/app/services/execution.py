"""The single place where an approved action reaches the outside world. Used by the API and the scheduler."""
import hashlib
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.agent.policy_engine import Action, Approval, Context, Mode, Policy, execution_guard
from app.api.v1.content import content_hash
from app.api.v1.integrations import adapter_for
from app.core.config import get_settings
from app.db.models import (ApprovalRequest, ContentDocument, ContentVersion, ExecutionRecord, Integration, Workspace, utcnow)
from app.integrations import wordpress as wp
from app.services.audit import record
from app.services.notifications import admin_ids, notify


@dataclass
class Blocked:
    reason: str


@dataclass
class Done:
    record: ExecutionRecord
    repeated: bool


def slug_for(key: str) -> str:
    return "na-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def run_approval(db, a: ApprovalRequest, actor_id, trigger: str = "manual", now=None):
    s, now = get_settings(), now or utcnow()
    ws = a.workspace_id
    w, v, d = db.get(Workspace, ws), db.get(ContentVersion, a.version_id), db.get(ContentDocument, a.document_id)
    i = db.get(Integration, a.integration_id)
    latest = db.scalar(select(func.max(ContentVersion.number)).where(ContentVersion.document_id == d.id))
    policy = Policy(tenant_id=ws, modes={"blog": Mode.REVIEW}, paused=w.paused, max_actions_per_day=s.max_actions_per_day)
    action = Action(ws, "blog", "publish", content_hash(v.body, v.meta), v.number, a.scheduled_at or a.created_at)
    approval = None
    if a.status in ("APPROVED", "REVOKED"):
        approval = Approval(a.workspace_id, "blog", "publish", a.content_hash, v.number, "human", a.decided_by,
                            a.expires_at or now, revoked=a.status == "REVOKED")
    today = db.scalar(select(func.count()).select_from(ExecutionRecord).where(
        ExecutionRecord.workspace_id == ws, ExecutionRecord.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        ExecutionRecord.status.in_(["EXECUTING", "PUBLISHED", "UNCLEAR"])))
    ctx = Context(now=now, actions_today=today, channel_connected=i.status == "connected")
    decision = execution_guard(policy, action, approval, ctx)
    reason = None if decision.allowed else decision.reason
    if reason is None and v.number != latest:
        reason = "a newer version exists"
    if reason is None and a.scheduled_at and now < a.scheduled_at:
        reason = f"scheduled for {a.scheduled_at.isoformat()} UTC; the scheduler will run it then"
    if reason:
        return Blocked(reason)
    key = f"{a.id}:{a.content_hash}"
    rec = db.scalar(select(ExecutionRecord).where(ExecutionRecord.idempotency_key == key))
    if rec and rec.status != "FAILED":
        return Done(rec, True)  # never call the provider twice for the same approved action
    if rec:
        rec.status, rec.detail, rec.trigger = "EXECUTING", None, trigger
    else:
        rec = ExecutionRecord(workspace_id=ws, approval_id=a.id, idempotency_key=key, status="EXECUTING", trigger=trigger)
        db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return Done(db.scalar(select(ExecutionRecord).where(ExecutionRecord.idempotency_key == key)), True)
    try:
        res = adapter_for(i).publish_post(d.title, v.body, slug=slug_for(key))
        rec.status, rec.external_id, rec.external_url, rec.detail = "PUBLISHED", res["external_id"], res["external_url"], "provider confirmed"
        d.status = "published"
    except wp.ProviderRejected as e:
        rec.status, rec.detail = "FAILED", str(e)
        d.status = "failed"
    except wp.ProviderUnclear as e:
        rec.status, rec.detail = "UNCLEAR", f"{e}. Check the site before trying again"
    a.block_reason = None
    record(db, ws, actor_id, "execution.run", "approval", a.id, "success" if rec.status == "PUBLISHED" else rec.status.lower(),
           {"execution_id": rec.id, "external_id": rec.external_id, "trigger": trigger})
    kind = {"PUBLISHED": "publish_succeeded", "FAILED": "publish_failed", "UNCLEAR": "publish_unclear"}[rec.status]
    notify(db, ws, [a.requested_by, *admin_ids(db, ws)], kind, f"“{d.title}”: {rec.status.lower()}", rec.detail, "/approvals")
    db.commit()
    return Done(rec, False)


STUCK_MINUTES = 5


def reconcile(db, a: ApprovalRequest, actor_id):
    """Checks the site for an UNCLEAR publish. Returns None if there is nothing to check."""
    rec = db.scalar(select(ExecutionRecord).where(ExecutionRecord.approval_id == a.id))
    if rec is None or rec.status != "UNCLEAR":
        return None
    i, d = db.get(Integration, a.integration_id), db.get(ContentDocument, a.document_id)
    slug = slug_for(rec.idempotency_key)
    try:
        found = adapter_for(i).find_post_by_slug(slug)
    except (wp.ProviderRejected, wp.ProviderUnclear) as exc:
        record(db, a.workspace_id, actor_id, "execution.reconcile", "approval", a.id, "failed", {"reason": str(exc)})
        db.commit()
        return {"outcome": "lookup_failed", "detail": f"Could not check the site: {exc}", "execution": rec}
    if found and found["status"] == "publish":
        rec.status, rec.external_id, rec.external_url = "PUBLISHED", found["id"], found["link"]
        rec.detail, d.status, outcome = "confirmed by checking the site", "published", "published"
    elif found:
        rec.detail, outcome = f"A post exists on the site with status “{found['status']}” but it is not published. Fix it in WordPress.", "needs_manual_check"
    else:
        rec.status, rec.detail, outcome = "FAILED", "Checked the site: no post was found, so retrying is safe", "not_found"
        d.status = "failed"
    record(db, a.workspace_id, actor_id, "execution.reconcile", "approval", a.id, "success", {"outcome": outcome, "external_id": rec.external_id})
    notify(db, a.workspace_id, [a.requested_by, *admin_ids(db, a.workspace_id)], f"publish_{outcome}", f"“{d.title}”: {outcome.replace('_', ' ')}", rec.detail, "/publishing")
    db.commit()
    return {"outcome": outcome, "detail": rec.detail, "execution": rec}


def recover_stuck(db, now=None) -> int:
    """A worker that died mid-call leaves EXECUTING rows. After a lease period they become UNCLEAR so they can be reconciled."""
    now = now or utcnow()
    n = 0
    for rec in db.scalars(select(ExecutionRecord).where(ExecutionRecord.status == "EXECUTING", ExecutionRecord.updated_at < now - timedelta(minutes=STUCK_MINUTES))):
        rec.status, rec.detail = "UNCLEAR", "The worker stopped during the call. Check the site before doing anything else"
        a = db.get(ApprovalRequest, rec.approval_id)
        record(db, rec.workspace_id, None, "execution.stuck_recovered", "approval", rec.approval_id, "unclear", {})
        notify(db, rec.workspace_id, [a.requested_by, *admin_ids(db, rec.workspace_id)], "publish_unclear", "A publish needs checking", rec.detail, "/publishing")
        n += 1
    if n:
        db.commit()
    return n

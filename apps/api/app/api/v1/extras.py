from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.api.deps import current_user, require_perm, scoped
from app.api.v1.workspaces import profile_dict
from app.core.config import get_settings
from app.db.models import (Membership, AiUsage, ApprovalRequest, AuditEvent, BusinessProfile, Campaign, ContentDocument, ContentVersion,
                           ExecutionRecord, Integration, Notification, Workspace, WorkerHeartbeat, utcnow)
from app.db.session import get_db
from app.services import quality

router = APIRouter(prefix="/workspaces/{ws}", tags=["workspace tools"])


class ReadIn(BaseModel):
    ids: list[str] | None = None  # null means all


@router.get("/notifications")
def notifications(ws: str, unread: bool = False, limit: int = Query(30, ge=1, le=100), db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    q = select(Notification).where(Notification.workspace_id == ws, Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.read_at.is_(None))
    unread_count = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.workspace_id == ws, Notification.user_id == user.id, Notification.read_at.is_(None)))
    rows = db.scalars(q.order_by(Notification.created_at.desc()).limit(limit)).all()
    return {"unread": unread_count, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
                                               "read": n.read_at is not None, "created_at": n.created_at} for n in rows]}


@router.post("/notifications/read")
def mark_read(ws: str, body: ReadIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    q = select(Notification).where(Notification.workspace_id == ws, Notification.user_id == user.id, Notification.read_at.is_(None))
    if body.ids is not None:
        q = q.where(Notification.id.in_(body.ids))
    n = 0
    for x in db.scalars(q):
        x.read_at = utcnow()
        n += 1
    db.commit()
    return {"marked": n}


@router.get("/ai/usage")
def ai_usage(ws: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    s = get_settings()
    month = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = db.execute(select(AiUsage.provider, AiUsage.model, func.count(), func.coalesce(func.sum(AiUsage.input_tokens), 0), func.coalesce(func.sum(AiUsage.output_tokens), 0))
                      .where(AiUsage.workspace_id == ws, AiUsage.created_at >= month).group_by(AiUsage.provider, AiUsage.model)).all()
    by_provider, cost, priced, unpriced = {}, 0.0, False, 0
    for p, m, n, i, o in rows:
        price = s.prices.get(f"{p}:{m}") or ({"in": s.price_in, "out": s.price_out} if p == "anthropic" and s.price_in is not None and s.price_out is not None else None)
        bp = by_provider.setdefault(p, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost": None})
        bp["requests"] += n
        bp["input_tokens"] += int(i)
        bp["output_tokens"] += int(o)
        if price:
            c = (int(i) * price["in"] + int(o) * price["out"]) / 1_000_000
            bp["estimated_cost"] = round((bp["estimated_cost"] or 0) + c, 4)
            cost, priced = cost + c, True
        else:
            unpriced += n
    by_action = {k: v for k, v in db.execute(select(AiUsage.action, func.count()).where(AiUsage.workspace_id == ws, AiUsage.created_at >= month).group_by(AiUsage.action)).all()}
    requests = sum(v["requests"] for v in by_provider.values())
    return {"month_start": month, "requests": requests, "input_tokens": sum(v["input_tokens"] for v in by_provider.values()),
            "output_tokens": sum(v["output_tokens"] for v in by_provider.values()), "by_action": by_action, "by_provider": by_provider,
            "limit": s.ai_monthly_limit, "remaining": max(s.ai_monthly_limit - requests, 0),
            "estimated_cost": round(cost, 4) if priced else None, "unpriced_requests": unpriced, "currency": s.price_currency,
            "cost_note": ("Estimate from token counts and the prices you configured. It is not your provider bill." if priced
                          else "Unavailable. Set AI_PRICES (or LLM_PRICE_INPUT_PER_MTOK and LLM_PRICE_OUTPUT_PER_MTOK) to see an estimate."),
            "note": "Token counts come from the provider's responses."}


@router.get("/calendar")
def calendar(ws: str, start: date, end: date, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    if end < start or (end - start).days > 62:
        raise HTTPException(422, "Choose a range of at most 62 days")
    lo, hi = datetime.combine(start, datetime.min.time()), datetime.combine(end + timedelta(days=1), datetime.min.time())
    rows = db.execute(select(ApprovalRequest, ContentDocument.title, Integration.label).join(ContentDocument, ContentDocument.id == ApprovalRequest.document_id)
                      .join(Integration, Integration.id == ApprovalRequest.integration_id)
                      .where(ApprovalRequest.workspace_id == ws, ApprovalRequest.scheduled_at >= lo, ApprovalRequest.scheduled_at < hi)
                      .order_by(ApprovalRequest.scheduled_at)).all()
    items = []
    for a, title, label in rows:
        ex = db.scalar(select(ExecutionRecord.status).where(ExecutionRecord.approval_id == a.id))
        items.append({"id": a.id, "document_id": a.document_id, "title": title, "destination": label, "status": a.status,
                      "scheduled_at": a.scheduled_at, "execution_status": ex, "block_reason": a.block_reason})
    camps = db.scalars(select(Campaign).where(Campaign.workspace_id == ws, Campaign.status != "ARCHIVED",
                                              Campaign.start_date <= end, func.coalesce(Campaign.end_date, Campaign.start_date) >= start)).all()
    return {"scheduled": items, "campaigns": [{"id": c.id, "name": c.name, "status": c.status, "start_date": c.start_date, "end_date": c.end_date} for c in camps],
            "times_are": "UTC"}


@router.get("/metrics/operations")
def operations(ws: str, days: int = Query(30, ge=1, le=365), db=Depends(get_db), user=Depends(current_user)):
    """Counts from this app's own workflow records. These are NOT marketing performance results."""
    require_perm(db, user, ws, "read")
    since = utcnow() - timedelta(days=days)
    by = lambda col, model, *w: {k: v for k, v in db.execute(select(col, func.count()).where(model.workspace_id == ws, model.created_at >= since, *w).group_by(col)).all()}
    ex = by(ExecutionRecord.status, ExecutionRecord)
    done = ex.get("PUBLISHED", 0) + ex.get("FAILED", 0) + ex.get("UNCLEAR", 0)
    return {"days": days, "source": "internal workflow records (not marketing performance)", "approvals": by(ApprovalRequest.status, ApprovalRequest),
            "executions": ex, "publish_success_rate": round(ex.get("PUBLISHED", 0) / done, 3) if done else None,
            "content_created": db.scalar(select(func.count()).select_from(ContentDocument).where(ContentDocument.workspace_id == ws, ContentDocument.created_at >= since)),
            "ai_requests": db.scalar(select(func.count()).select_from(AiUsage).where(AiUsage.workspace_id == ws, AiUsage.created_at >= since))}


def _latest(db, ws, did):
    d = scoped(db, ContentDocument, did, ws)
    v = db.scalar(select(ContentVersion).where(ContentVersion.document_id == did).order_by(ContentVersion.number.desc()).limit(1))
    return d, v


@router.get("/content/{did}/check")
def check(ws: str, did: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    d, v = _latest(db, ws, did)
    issues = quality.check(db, ws, d, v, profile_dict(db.get(BusinessProfile, ws)))
    return {"version": v.number, "ok": not any(i["level"] == "error" for i in issues), "issues": issues}


@router.get("/content/{did}/export")
def export(ws: str, did: str, format: str = Query("md", pattern="^(md|html)$"), db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    d, v = _latest(db, ws, did)
    if format == "md":
        body, media = f"# {d.title}\n\n{v.body}\n", "text/markdown; charset=utf-8"
    else:
        import html
        paras = "".join(f"<p>{html.escape(p)}</p>" for p in v.body.split("\n\n") if p.strip())
        body, media = f"<!doctype html><meta charset=utf-8><title>{html.escape(d.title)}</title><h1>{html.escape(d.title)}</h1>{paras}", "text/html; charset=utf-8"
    name = "".join(c if c.isalnum() else "-" for c in d.title)[:50] or "content"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}-v{v.number}.{format}"'})


NEXT = {"pending": "Waiting for the scheduled time, or publish it now.", "blocked": "Fix the cause shown, then it will run on the next check.",
        "processing": "Wait. If it stays here more than 5 minutes it becomes unclear and can be checked.",
        "unclear": "Check the site now. Do not retry before checking.", "failed": "Fix the cause shown, then retry.",
        "published": "Nothing to do.", "expired": "The approval expired. Request approval again."}


@router.get("/jobs")
def jobs(ws: str, state: str | None = Query(None, pattern="^(pending|blocked|processing|unclear|failed|published|expired)$"),
         limit: int = Query(50, ge=1, le=200), db=Depends(get_db), user=Depends(current_user)):
    """Publishing Failure Center: every approved action and what happened to it."""
    require_perm(db, user, ws, "read")
    rows = db.execute(select(ApprovalRequest, ExecutionRecord, ContentDocument.title, Integration.label)
                      .join(ContentDocument, ContentDocument.id == ApprovalRequest.document_id)
                      .join(Integration, Integration.id == ApprovalRequest.integration_id)
                      .outerjoin(ExecutionRecord, ExecutionRecord.approval_id == ApprovalRequest.id)
                      .where(ApprovalRequest.workspace_id == ws, or_(ExecutionRecord.id.is_not(None), ApprovalRequest.status.in_(["APPROVED", "EXPIRED"])))
                      .order_by(func.coalesce(ExecutionRecord.updated_at, ApprovalRequest.scheduled_at, ApprovalRequest.created_at).desc()).limit(400)).all()
    items, counts = [], {}
    for a, rec, title, label in rows:
        st = ({"PUBLISHED": "published", "FAILED": "failed", "UNCLEAR": "unclear", "EXECUTING": "processing"}[rec.status] if rec
              else "expired" if a.status == "EXPIRED" else "blocked" if a.block_reason else "pending")
        counts[st] = counts.get(st, 0) + 1
        if state and st != state:
            continue
        items.append({"approval_id": a.id, "title": title, "destination": label, "state": st, "scheduled_at": a.scheduled_at,
                      "last_attempt_at": rec.updated_at if rec else None, "provider_summary": rec.detail if rec else a.block_reason,
                      "external_url": rec.external_url if rec and rec.external_id else None, "trigger": rec.trigger if rec else None,
                      "retry_eligible": st == "failed", "can_check_site": st == "unclear", "next_action": NEXT[st]})
    return {"counts": counts, "items": items[:limit]}


LABELS = {"content.create": "Content created", "content.version": "New content version", "content.generate": "AI generation", "content.ai": "AI Copilot action",
          "approval.request": "Approval requested", "approval.approve": "Content approved", "approval.reject": "Content rejected",
          "approval.request_changes": "Changes requested", "approval.revoke": "Approval revoked", "approval.reschedule": "Post rescheduled",
          "execution.run": "Publishing attempt", "execution.blocked": "Publishing blocked", "execution.reconcile": "Site checked",
          "execution.expired": "Approval expired", "execution.stuck_recovered": "Stuck job recovered", "integration.create": "Account added",
          "integration.test": "Connection tested", "integration.disconnect": "Account disconnected", "campaign.create": "Campaign created",
          "campaign.transition": "Campaign status changed", "workspace.pause": "Workspace paused", "workspace.resume": "Workspace resumed",
          "member.add": "Member added", "profile.update": "Brand settings updated"}


@router.get("/activity")
def activity(ws: str, limit: int = Query(12, ge=1, le=50), db=Depends(get_db), user=Depends(current_user)):
    """Recent events from the audit trail, safe for every role. Only whitelisted event types, no raw details."""
    require_perm(db, user, ws, "read")
    rows = db.scalars(select(AuditEvent).where(AuditEvent.workspace_id == ws, AuditEvent.action.in_(list(LABELS)))
                      .order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": e.id, "action": e.action, "title": LABELS[e.action], "outcome": e.outcome, "created_at": e.created_at,
             "reason": (e.detail or {}).get("reason") if e.outcome != "success" else None, "automated": e.actor_id is None} for e in rows]


@router.get("/search")
def search(ws: str, q: str = Query(..., min_length=2, max_length=80), db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    pat = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    camps = db.scalars(select(Campaign).where(Campaign.workspace_id == ws, Campaign.name.ilike(pat, escape="\\")).limit(5)).all()
    docs = db.scalars(select(ContentDocument).where(ContentDocument.workspace_id == ws, ContentDocument.title.ilike(pat, escape="\\")).limit(5)).all()
    return {"campaigns": [{"id": c.id, "name": c.name, "status": c.status} for c in camps],
            "content": [{"id": d.id, "title": d.title, "kind": d.kind, "status": d.status} for d in docs]}


def _count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


@router.get("/dashboard")
def dashboard(ws: str, days: int = Query(7, ge=1, le=90), db=Depends(get_db), user=Depends(current_user)):
    """Everything the dashboard shows. Each number is counted from this app's own records. Nothing is estimated."""
    require_perm(db, user, ws, "read")
    w, now = db.get(Workspace, ws), utcnow()
    since, before = now - timedelta(days=days), now - timedelta(days=2 * days)
    created = lambda a, b: _count(db, ContentDocument, ContentDocument.workspace_id == ws, ContentDocument.created_at >= a, ContentDocument.created_at < b)
    published = lambda a, b: _count(db, ExecutionRecord, ExecutionRecord.workspace_id == ws, ExecutionRecord.status == "PUBLISHED", ExecutionRecord.created_at >= a, ExecutionRecord.created_at < b)
    day0 = (now - timedelta(days=days - 1)).date()
    series = {(day0 + timedelta(days=i)).isoformat(): {"date": (day0 + timedelta(days=i)).isoformat(), "content_created": 0, "posts_published": 0} for i in range(days)}
    for (t,) in db.execute(select(ContentDocument.created_at).where(ContentDocument.workspace_id == ws, ContentDocument.created_at >= datetime.combine(day0, datetime.min.time()))):
        if t.date().isoformat() in series:
            series[t.date().isoformat()]["content_created"] += 1
    for (t,) in db.execute(select(ExecutionRecord.created_at).where(ExecutionRecord.workspace_id == ws, ExecutionRecord.status == "PUBLISHED", ExecutionRecord.created_at >= datetime.combine(day0, datetime.min.time()))):
        if t.date().isoformat() in series:
            series[t.date().isoformat()]["posts_published"] += 1
    by_status = {k: v for k, v in db.execute(select(Campaign.status, func.count()).where(Campaign.workspace_id == ws).group_by(Campaign.status)).all()}
    hb = db.get(WorkerHeartbeat, "scheduler")
    alive = bool(hb and (now - hb.beat_at) < timedelta(seconds=90))
    attention = _count(db, ExecutionRecord, ExecutionRecord.workspace_id == ws, ExecutionRecord.status.in_(["UNCLEAR", "FAILED"]))
    state = "Paused" if w.paused else "Needs attention" if attention else "Running" if alive else "Unavailable"
    reason = {"Paused": "The workspace is paused. Nothing will publish.", "Needs attention": f"{attention} publishing job(s) need a person.",
              "Running": "The scheduler worker is reporting in.", "Unavailable": "The scheduler worker is not running or has not reported in the last 90 seconds."}[state]
    sched = db.execute(select(ApprovalRequest, ContentDocument.title, Integration.label).join(ContentDocument, ContentDocument.id == ApprovalRequest.document_id)
                       .join(Integration, Integration.id == ApprovalRequest.integration_id)
                       .where(ApprovalRequest.workspace_id == ws, ApprovalRequest.status.in_(["PENDING", "APPROVED"]), ApprovalRequest.scheduled_at >= now - timedelta(hours=12))
                       .order_by(ApprovalRequest.scheduled_at).limit(8)).all()
    upcoming = [{"approval_id": a.id, "document_id": a.document_id, "title": t, "destination": lab, "status": a.status, "scheduled_at": a.scheduled_at} for a, t, lab in sched]
    next_task = next((u for u in upcoming if u["status"] == "APPROVED" and u["scheduled_at"] > now), None)
    last = db.scalar(select(ExecutionRecord).where(ExecutionRecord.workspace_id == ws).order_by(ExecutionRecord.updated_at.desc()).limit(1))
    camps = []
    for c in db.scalars(select(Campaign).where(Campaign.workspace_id == ws, Campaign.status.in_(["ACTIVE", "DRAFT", "PAUSED", "COMPLETED"])).order_by(Campaign.updated_at.desc()).limit(8)):
        n = _count(db, ContentDocument, ContentDocument.campaign_id == c.id)
        p = _count(db, ContentDocument, ContentDocument.campaign_id == c.id, ContentDocument.status == "published")
        camps.append({"id": c.id, "name": c.name, "objective": c.objective, "status": c.status, "channels": c.channels or [], "start_date": c.start_date, "end_date": c.end_date,
                      "content_count": n, "published_count": p, "progress": round(p / n, 3) if n else None})
    integ = [{"id": i.id, "provider": i.provider, "label": i.label, "status": i.status, "site_url": i.config.get("site_url")} for i in
             db.scalars(select(Integration).where(Integration.workspace_id == ws).order_by(Integration.created_at))]
    agent_roles = ["super_agent", "research_agent", "analytics_agent", "content_agent", "publishing_agent"]
    ag = db.execute(select(Membership.suspended).where(Membership.workspace_id == ws, Membership.role.in_(agent_roles))).all()
    day0_dt = datetime.combine(now.date(), datetime.min.time())
    quick = {"active_campaigns": by_status.get("ACTIVE", 0),
             "content_in_review": _count(db, ContentDocument, ContentDocument.workspace_id == ws, ContentDocument.status == "review"),
             "scheduled": _count(db, ApprovalRequest, ApprovalRequest.workspace_id == ws, ApprovalRequest.status == "APPROVED", ApprovalRequest.scheduled_at > now),
             "published_today": _count(db, ExecutionRecord, ExecutionRecord.workspace_id == ws, ExecutionRecord.status == "PUBLISHED", ExecutionRecord.created_at >= day0_dt)}
    c_now, c_prev, p_now, p_prev = created(since, now + timedelta(days=1)), created(before, since), published(since, now + timedelta(days=1)), published(before, since)
    return {
        "days": days, "agent": {"state": state, "reason": reason, "worker_last_seen": hb.beat_at if hb else None,
                                "next_task": next_task, "last_execution": {"status": last.status, "at": last.updated_at} if last else None},
        "kpis": {"campaigns": {"total": sum(by_status.values()), "by_status": by_status},
                 "content_created": {"value": c_now, "previous": c_prev}, "posts_published": {"value": p_now, "previous": p_prev},
                 "engagement_rate": {"state": "unavailable", "reason": "No analytics source is connected, so engagement cannot be measured."}},
        "definitions": {"campaigns": "All campaigns in this workspace, by status.", "content_created": f"Content documents created in the last {days} days, compared with the {days} days before.",
                        "posts_published": "Publishing attempts the site confirmed, in the same windows.", "progress": "Published content divided by all content linked to the campaign."},
        "series": list(series.values()), "today_tasks": [u for u in upcoming if u["scheduled_at"].date() == now.date()],
        "quick": quick, "agents": {"active": sum(1 for (s,) in ag if not s), "total": len(ag)},
        "campaigns": camps, "upcoming": [u for u in upcoming if u["scheduled_at"] > now][:5], "integrations": integ}

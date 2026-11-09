"""Runs approved posts when their time arrives.  python -m app.workers.scheduler  [--once] [--interval 15]
State lives in PostgreSQL, so a restart loses nothing. Several workers are safe: the idempotency key allows one attempt."""
import argparse
import logging
import signal
import time

from sqlalchemy import select

from app.db.models import ApprovalRequest, ExecutionRecord, WorkerHeartbeat, utcnow
from app.db.session import SessionLocal
from app.services.audit import record
from app.services.execution import Blocked, recover_stuck, run_approval
from app.services.notifications import notify

log = logging.getLogger("scheduler")


def beat(db, now) -> None:
    hb = db.get(WorkerHeartbeat, "scheduler")
    if hb:
        hb.beat_at = now
    else:
        db.add(WorkerHeartbeat(name="scheduler", beat_at=now))
    db.commit()


def run_due(db, now=None, limit: int = 20) -> list:
    now = now or utcnow()
    beat(db, now)
    recover_stuck(db, now)
    ids = db.scalars(select(ApprovalRequest.id).where(
        ApprovalRequest.status == "APPROVED", ApprovalRequest.scheduled_at.is_not(None), ApprovalRequest.scheduled_at <= now)
        .order_by(ApprovalRequest.scheduled_at).limit(limit)).all()
    results = []
    for aid in ids:
        a = db.get(ApprovalRequest, aid)
        if db.scalar(select(ExecutionRecord.id).where(ExecutionRecord.approval_id == aid)):
            continue  # already attempted. A failed attempt is retried by a person, never automatically
        out = run_approval(db, a, None, "scheduler", now)
        if isinstance(out, Blocked):
            if "expired" in out.reason:
                a.status = "EXPIRED"
                notify(db, a.workspace_id, [a.requested_by], "approval_expired", "Scheduled post not published", "The approval expired before the scheduled time.", "/approvals")
                record(db, a.workspace_id, None, "execution.expired", "approval", a.id, "blocked", {"reason": out.reason})
            elif a.block_reason != out.reason:  # log a changed reason once, not every poll
                a.block_reason = out.reason
                record(db, a.workspace_id, None, "execution.blocked", "approval", a.id, "blocked", {"reason": out.reason, "trigger": "scheduler"})
            db.commit()
        results.append((aid, out))
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=15)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    while not stop["now"]:
        with SessionLocal() as db:
            try:
                res = run_due(db)
                log.info("checked: %d due approvals handled", len(res))
            except Exception:  # keep the loop alive; the error is logged with a traceback
                log.exception("scheduler pass failed")
                db.rollback()
        if args.once:
            break
        for _ in range(args.interval):
            if stop["now"]:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()

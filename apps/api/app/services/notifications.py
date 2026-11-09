from sqlalchemy import select

from app.db.models import Membership, Notification


def admin_ids(db, ws_id: str) -> list[str]:
    return list(db.scalars(select(Membership.user_id).where(Membership.workspace_id == ws_id, Membership.role.in_(["admin", "owner"]))))


def notify(db, ws_id: str, user_ids, kind: str, title: str, body: str | None = None, link: str | None = None) -> None:
    """Adds in-app notifications. The caller commits."""
    for uid in {u for u in user_ids if u}:
        db.add(Notification(workspace_id=ws_id, user_id=uid, kind=kind, title=title[:200], body=body, link=link))

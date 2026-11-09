from app.db.models import AuditEvent


def record(db, ws_id, actor_id, action, target_type, target_id=None, outcome="success", detail=None):
    """Adds an audit row. The caller commits. Never put secrets in `detail`."""
    db.add(AuditEvent(workspace_id=ws_id, actor_id=actor_id, action=action, target_type=target_type,
                      target_id=target_id, outcome=outcome, detail=detail or {}))

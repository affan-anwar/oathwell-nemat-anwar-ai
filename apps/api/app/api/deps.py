from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.security import decode_token
from app.core.permissions import has_perm
from app.db.models import Membership, User, Workspace
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)) -> User:
    tok = decode_token(creds.credentials) if creds else None
    user = db.get(User, tok[0]) if tok else None
    if not user or not user.is_active or user.token_version != tok[1]:
        raise HTTPException(401, "Not authenticated")
    return user


def require_perm(db, user: User, ws_id: str, perm: str) -> Membership:
    """Checked on the server for every workspace route. Unknown or foreign workspaces look the same (404). Deny by default."""
    m = db.scalar(select(Membership).where(Membership.workspace_id == ws_id, Membership.user_id == user.id))
    if not m:
        raise HTTPException(404, "Workspace not found")
    if m.suspended:
        raise HTTPException(403, "Your access to this workspace is suspended")
    w = db.get(Workspace, ws_id)
    if not has_perm(m.role, perm, w.admin_revoked):
        raise HTTPException(403, "Your role does not allow this")
    return m


def scoped(db, model, obj_id: str, ws_id: str):
    obj = db.get(model, obj_id)
    if obj is None or obj.workspace_id != ws_id:
        raise HTTPException(404, "Not found")
    return obj

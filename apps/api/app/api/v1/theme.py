from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import current_user, require_perm
from app.db.models import Membership, ThemeSetting, Workspace
from app.db.session import get_db
from app.services import themes
from app.services.audit import record

router = APIRouter(prefix="/workspaces/{ws}", tags=["theme"])


class ThemeIn(BaseModel):
    scope: str = Field(pattern="^(workspace|global)$")
    tokens: dict = Field(default_factory=dict)
    default_mode: str = Field(default="dark", pattern="^(dark|light)$")
    allow_user_mode: bool = True


class CheckIn(BaseModel):
    tokens: dict = Field(default_factory=dict)


class PrefIn(BaseModel):
    mode: str = Field(pattern="^(dark|light|system)$")


def resolve(db, ws: str):
    """The workspace's own theme wins, then the global theme of one of its owners, then the built-in defaults."""
    own = db.scalar(select(ThemeSetting).where(ThemeSetting.workspace_id == ws))
    if own:
        return own, "workspace"
    owners = [m.user_id for m in db.scalars(select(Membership).where(Membership.workspace_id == ws, Membership.role == "owner"))]
    glob = db.scalar(select(ThemeSetting).where(ThemeSetting.owner_user_id.in_(owners))) if owners else None
    return (glob, "global") if glob else (None, "default")


def body(db, ws, me, t, source):
    return {"source": source, "tokens": t.tokens if t else themes.DEFAULTS, "default_mode": t.default_mode if t else "dark",
            "allow_user_mode": t.allow_user_mode if t else True, "defaults": themes.DEFAULTS, "labels": themes.LABELS,
            "editable": me.role == "owner", "my_mode": me.theme_mode, "updated_at": t.updated_at if t else None}


@router.get("/theme")
def get_theme(ws: str, db=Depends(get_db), user=Depends(current_user)):
    me = require_perm(db, user, ws, "read")
    t, source = resolve(db, ws)
    return body(db, ws, me, t, source)


@router.post("/theme/check")
def check_theme(ws: str, payload: CheckIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "theme.write")
    clean, problems = themes.validate(payload.tokens)
    return {"ok": not problems, "problems": problems, "tokens": clean}


@router.put("/theme")
def put_theme(ws: str, payload: ThemeIn, db=Depends(get_db), user=Depends(current_user)):
    me = require_perm(db, user, ws, "theme.write")
    clean, problems = themes.validate(payload.tokens)
    if problems:
        raise HTTPException(422, {"message": "This theme cannot be saved", "problems": problems})
    q = ThemeSetting.workspace_id == ws if payload.scope == "workspace" else ThemeSetting.owner_user_id == user.id
    t = db.scalar(select(ThemeSetting).where(q))
    if not t:
        t = ThemeSetting(scope=payload.scope, workspace_id=ws if payload.scope == "workspace" else None,
                         owner_user_id=user.id if payload.scope == "global" else None, updated_by=user.id)
        db.add(t)
    t.tokens, t.default_mode, t.allow_user_mode, t.updated_by = clean, payload.default_mode, payload.allow_user_mode, user.id
    record(db, ws, user.id, "theme.update", "theme", ws, detail={"scope": payload.scope, "default_mode": payload.default_mode, "allow_user_mode": payload.allow_user_mode})
    db.commit()
    return body(db, ws, me, t, payload.scope)


@router.delete("/theme")
def reset_theme(ws: str, scope: str = Query(pattern="^(workspace|global)$"), db=Depends(get_db), user=Depends(current_user)):
    me = require_perm(db, user, ws, "theme.write")
    q = ThemeSetting.workspace_id == ws if scope == "workspace" else ThemeSetting.owner_user_id == user.id
    t = db.scalar(select(ThemeSetting).where(q))
    if t:
        db.delete(t)
    record(db, ws, user.id, "theme.reset", "theme", ws, detail={"scope": scope})
    db.commit()
    cur, source = resolve(db, ws)
    return body(db, ws, me, cur, source)


@router.put("/preferences")
def put_preferences(ws: str, payload: PrefIn, db=Depends(get_db), user=Depends(current_user)):
    """A person's own Dark/Light/System choice. It never changes the Owner's brand colours. The Owner may lock it."""
    me = require_perm(db, user, ws, "read")
    t, _ = resolve(db, ws)
    if t and not t.allow_user_mode and me.role != "owner":
        raise HTTPException(403, "The Owner has set the display mode for everyone")
    me.theme_mode = payload.mode
    db.commit()
    return {"my_mode": me.theme_mode}

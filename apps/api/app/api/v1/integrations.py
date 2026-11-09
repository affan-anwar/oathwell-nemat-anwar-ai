from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import current_user, require_perm, scoped
from app.core.config import get_settings
from app.core.security import decrypt, encrypt
from app.db.models import Integration, utcnow
from app.db.session import get_db
from app.integrations import wordpress as wp
from app.services.audit import record
from app.services.ssrf import validate_site_url

router = APIRouter(prefix="/workspaces/{ws}/integrations", tags=["integrations"])


class WordPressIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    site_url: str = Field(max_length=500)
    username: str = Field(min_length=1, max_length=120)
    app_password: str = Field(min_length=8, max_length=200)


def out(i: Integration) -> dict:  # the secret is never returned
    return {"id": i.id, "provider": i.provider, "label": i.label, "site_url": i.config.get("site_url"),
            "username": i.config.get("username"), "status": i.status, "status_detail": i.status_detail,
            "last_tested_at": i.last_tested_at}


def adapter_for(i: Integration) -> wp.WordPressAdapter:
    pw = decrypt(i.secret_encrypted) if i.secret_encrypted else None
    if not pw:
        raise HTTPException(409, "Stored credentials cannot be read. Reconnect this integration")
    return wp.WordPressAdapter(i.config["site_url"], i.config["username"], pw)


@router.post("/wordpress", status_code=201)
def connect_wordpress(ws: str, body: WordPressIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "integration.manage")
    try:
        url = validate_site_url(body.site_url, get_settings().allow_private_urls)
    except ValueError as e:
        raise HTTPException(422, str(e))
    i = Integration(workspace_id=ws, provider="wordpress", label=body.label,
                    config={"site_url": url, "username": body.username}, secret_encrypted=encrypt(body.app_password),
                    status="unverified", status_detail="Run a connection test")
    db.add(i)
    db.flush()
    record(db, ws, user.id, "integration.create", "integration", i.id, detail={"provider": "wordpress"})
    db.commit()
    return out(i)


@router.get("")
def list_(ws: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    return [out(i) for i in db.scalars(select(Integration).where(Integration.workspace_id == ws)
                                       .order_by(Integration.created_at))]


@router.post("/{iid}/test")
def test(ws: str, iid: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "integration.manage")
    i = scoped(db, Integration, iid, ws)
    if i.status == "disconnected":
        raise HTTPException(409, "This integration was disconnected")
    try:
        r = adapter_for(i).test_connection()
        i.status, i.status_detail = "connected", f"Authenticated as {r['user']}"
    except wp.ProviderRejected as e:
        i.status, i.status_detail = "failed", str(e)
    except wp.ProviderUnclear as e:
        i.status, i.status_detail = "unverified", str(e)
    i.last_tested_at = utcnow()
    record(db, ws, user.id, "integration.test", "integration", i.id,
           "success" if i.status == "connected" else "failed", {"status": i.status})
    db.commit()
    return out(i)


@router.delete("/{iid}")
def disconnect(ws: str, iid: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "integration.manage")
    i = scoped(db, Integration, iid, ws)
    i.secret_encrypted, i.status = None, "disconnected"
    i.status_detail = "Disconnected. Also revoke the application password inside WordPress"
    record(db, ws, user.id, "integration.disconnect", "integration", i.id)
    db.commit()
    return out(i)

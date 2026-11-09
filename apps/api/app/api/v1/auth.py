import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.security import create_token, hash_password, verify_password
from app.db.models import LoginAttempt, User, utcnow
from app.db.session import get_db
from app.services.audit import record

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY = hash_password("not-a-real-password")


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) or len(v) > 255:
            raise ValueError("invalid email")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


@router.post("/register", status_code=201)
def register(body: RegisterIn, db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email, password_hash=hash_password(body.password), full_name=body.full_name)
    db.add(user)
    db.flush()
    record(db, None, user.id, "user.register", "user", user.id)
    db.commit()
    return {"id": user.id, "email": user.email, "full_name": user.full_name}


@router.post("/login")
def login(body: LoginIn, request: Request, db=Depends(get_db)):
    s = get_settings()
    key = body.email.strip().lower()[:255]
    ip = (request.client.host if request.client else "unknown")[:64]
    since = utcnow() - timedelta(minutes=s.login_window_minutes)
    by_email = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.email_key == key, LoginAttempt.created_at >= since))
    by_ip = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip == ip, LoginAttempt.created_at >= since))
    if by_email >= s.login_max_failures or by_ip >= s.login_max_failures * 6:
        raise HTTPException(429, f"Too many failed sign-in attempts. Try again in {s.login_window_minutes} minutes.",
                            headers={"Retry-After": str(s.login_window_minutes * 60)})
    user = db.scalar(select(User).where(User.email == key))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY)
    if not user or not ok or not user.is_active:
        db.add(LoginAttempt(email_key=key, ip=ip))
        record(db, None, user.id if user else None, "user.login", "user", None, "failed")
        db.commit()
        raise HTTPException(401, "Wrong email or password")
    db.execute(delete(LoginAttempt).where(LoginAttempt.email_key == key))
    db.commit()
    return {"access_token": create_token(user.id, user.token_version), "token_type": "bearer"}


@router.get("/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name}


@router.post("/logout")
def logout(db=Depends(get_db), user=Depends(current_user)):
    """Invalidates every token issued to this user, on every device."""
    user.token_version += 1
    record(db, None, user.id, "user.logout", "user", user.id)
    db.commit()
    return {"ok": True}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, db=Depends(get_db), user=Depends(current_user)):
    if not verify_password(body.current_password, user.password_hash):
        record(db, None, user.id, "user.change_password", "user", user.id, "failed")
        db.commit()
        raise HTTPException(400, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    record(db, None, user.id, "user.change_password", "user", user.id)
    db.commit()
    return {"access_token": create_token(user.id, user.token_version), "token_type": "bearer"}

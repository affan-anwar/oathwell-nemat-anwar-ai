import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _secret() -> str:
    s = get_settings().secret_key
    if len(s) < 32:
        raise RuntimeError("APP_SECRET_KEY must be set to at least 32 characters")
    return s


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def create_token(user_id: str, version: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=get_settings().token_minutes)
    return jwt.encode({"sub": user_id, "tv": version, "exp": exp}, _secret(), algorithm="HS256")


def decode_token(token: str) -> tuple[str, int] | None:
    try:
        d = jwt.decode(token, _secret(), algorithms=["HS256"])
        return d["sub"], int(d.get("tv", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("fernet:" + _secret()).encode()).digest()))


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None

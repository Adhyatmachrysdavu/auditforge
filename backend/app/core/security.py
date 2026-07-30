"""Utilitas keamanan: hashing kata sandi (bcrypt) & token akses (JWT)."""
from __future__ import annotations

from datetime import timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.db.base import utcnow

_settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(
    subject: str | int, *, role: str | None = None, expires_minutes: int | None = None
) -> str:
    now = utcnow()
    payload: dict = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or _settings.access_token_expire_minutes),
    }
    if role:
        payload["role"] = role
    return jwt.encode(payload, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _settings.secret_key, algorithms=[_settings.jwt_algorithm])

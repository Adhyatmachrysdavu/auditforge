"""Dependency FastAPI: pengguna aktif & pemeriksaan peran (RBAC)."""
from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Kredensial tidak valid",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise _CRED_EXC
    except jwt.PyJWTError as exc:
        raise _CRED_EXC from exc
    user = db.get(User, int(sub))
    if user is None or not user.is_active:
        raise _CRED_EXC
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    """Buat dependency yang mensyaratkan peran pengguna termasuk `roles`."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses ditolak: peran tidak mencukupi",
            )
        return user

    return checker

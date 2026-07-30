"""Router pengguna — hanya admin (demonstrasi RBAC)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.auth import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))
) -> list[UserOut]:
    users = db.scalars(select(User)).all()
    return [
        UserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.name,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> UserOut:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email sudah terdaftar")
    role = db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Peran tidak dikenal: {payload.role}",
        )
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=role.name,
        is_active=user.is_active,
    )

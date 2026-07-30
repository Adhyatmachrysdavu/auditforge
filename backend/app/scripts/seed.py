"""Seed data awal: 3 peran (admin/auditor/analyst) + satu admin.

Idempoten — aman dijalankan berulang. Jalankan:
    docker compose exec api python -m app.scripts.seed
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import RoleName
from app.models.user import Role, User


def seed() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        roles: dict[str, Role] = {}
        for rn in RoleName:
            role = db.scalar(select(Role).where(Role.name == rn.value))
            if role is None:
                role = Role(name=rn.value, description=f"Peran {rn.value}")
                db.add(role)
                db.flush()
            roles[rn.value] = role

        admin = db.scalar(select(User).where(User.email == settings.seed_admin_email))
        if admin is None:
            db.add(
                User(
                    email=settings.seed_admin_email,
                    full_name=settings.seed_admin_name,
                    hashed_password=hash_password(settings.seed_admin_password),
                    role_id=roles[RoleName.admin.value].id,
                )
            )
            print(
                f"[seed] Admin dibuat: {settings.seed_admin_email} "
                f"/ {settings.seed_admin_password}"
            )
        else:
            print(f"[seed] Admin sudah ada: {settings.seed_admin_email}")

        db.commit()
        print("[seed] Selesai. Peran:", ", ".join(roles.keys()))
    finally:
        db.close()


if __name__ == "__main__":
    seed()

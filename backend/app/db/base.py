"""Basis deklaratif SQLAlchemy + utilitas waktu.

Semua model mewarisi `Base`. Alembic membaca `Base.metadata` untuk autogenerate.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Waktu sekarang dalam UTC (timezone-aware)."""
    return datetime.now(timezone.utc)

"""Branding/letterhead laporan (D15) — konfigurasi runtime.

Pola sama seperti konfigurasi LLM: **DB (`app_settings`) → fallback `.env`**.
Admin mengubah nama organisasi, judul laporan, dan warna aksen lewat panel;
letterhead DOCX memakai nilai efektif ini.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.app_setting import AppSetting

BRAND_KEYS = ("brand_org_name", "brand_report_title", "brand_accent")


@dataclass
class Branding:
    org_name: str
    report_title: str
    accent: str


def _db_overrides() -> dict[str, str]:
    try:
        db = SessionLocal()
    except Exception:  # noqa: BLE001 — DB tak siap → pakai .env saja
        return {}
    try:
        rows = db.scalars(select(AppSetting).where(AppSetting.key.in_(BRAND_KEYS))).all()
        return {r.key: r.value for r in rows if r.value}
    except Exception:  # noqa: BLE001 — tabel belum dimigrasi
        return {}
    finally:
        db.close()


def load_branding() -> Branding:
    """Branding efektif (DB menimpa `.env`/default)."""
    s = get_settings()
    o = _db_overrides()
    return Branding(
        org_name=o.get("brand_org_name", s.brand_org_name),
        report_title=o.get("brand_report_title", s.brand_report_title),
        accent=o.get("brand_accent", s.brand_accent),
    )


def save_branding(
    db: Session,
    *,
    org_name: str | None = None,
    report_title: str | None = None,
    accent: str | None = None,
) -> None:
    """Upsert override branding ke DB. Field `None` diabaikan."""
    updates = {
        "brand_org_name": org_name,
        "brand_report_title": report_title,
        "brand_accent": accent,
    }
    for key, value in updates.items():
        if value is None:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()

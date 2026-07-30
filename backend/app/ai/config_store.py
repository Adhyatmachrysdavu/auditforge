"""Resolver konfigurasi LLM efektif (D9/R2).

Prioritas: **DB (`app_settings`) → fallback `.env`**. Admin mengubah nilai lewat
panel; bila belum diatur, nilai `.env` dipakai. Key hanya ditulis, tak pernah
dikembalikan utuh oleh API.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.app_setting import AppSetting

# Kunci yang dikelola panel LLM.
LLM_KEYS = ("ai_format", "ai_base_url", "ai_api_key", "ai_model")


@dataclass
class LLMConfig:
    format: str
    base_url: str
    api_key: str | None
    model: str


def _db_overrides() -> dict[str, str]:
    """Ambil override LLM dari DB (kosong bila tabel/baris belum ada)."""
    try:
        db = SessionLocal()
    except Exception:  # noqa: BLE001 — DB tak siap → pakai .env saja
        return {}
    try:
        rows = db.scalars(
            select(AppSetting).where(AppSetting.key.in_(LLM_KEYS))
        ).all()
        return {r.key: r.value for r in rows if r.value}
    except Exception:  # noqa: BLE001 — mis. tabel belum dimigrasi
        return {}
    finally:
        db.close()


def load_llm_config() -> LLMConfig:
    """Konfigurasi LLM efektif (DB menimpa `.env`)."""
    s = get_settings()
    o = _db_overrides()
    return LLMConfig(
        format=o.get("ai_format", s.ai_format),
        base_url=o.get("ai_base_url", s.ai_base_url),
        api_key=o.get("ai_api_key", s.ai_api_key),
        model=o.get("ai_model", s.ai_model),
    )


def save_llm_config(
    db: Session,
    *,
    format: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> None:
    """Upsert override LLM ke DB. Field `None` diabaikan (tak menimpa)."""
    updates = {
        "ai_format": format,
        "ai_base_url": base_url,
        "ai_api_key": api_key,
        "ai_model": model,
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

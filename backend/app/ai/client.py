"""Klien terpusat untuk AI Claude (Anthropic SDK).

Seluruh pemanggilan AI di AuditForge melewati modul ini agar konfigurasi model,
penyamaran data, dan pencatatan biaya dapat dikelola di satu tempat pada
fase berikutnya. Model default: claude-opus-4-8.
"""
from __future__ import annotations

from functools import lru_cache

import anthropic

from app.core.config import get_settings


@lru_cache
def get_client() -> anthropic.Anthropic:
    """Bangun klien Anthropic.

    Anthropic() otomatis membaca ANTHROPIC_API_KEY dari environment; kunci
    hanya diberikan eksplisit bila tersedia di konfigurasi.
    """
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()


def ping(model: str | None = None) -> str:
    """Panggilan sanity-check singkat untuk memverifikasi akses Claude API."""
    settings = get_settings()
    client = get_client()
    resp = client.messages.create(
        model=model or settings.ai_model,
        max_tokens=64,
        messages=[{"role": "user", "content": "Balas persis dengan: AuditForge OK"}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()

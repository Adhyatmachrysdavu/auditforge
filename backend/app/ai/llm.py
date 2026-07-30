"""Klien LLM terpusat AuditForge (D9).

SEMUA pemanggilan LLM fitur (naratif, ringkasan, triase) harus lewat `draft()`,
bukan langsung ke provider. Di sini masking dipasang otomatis: teks temuan
disamarkan sebelum keluar mesin (mis. ke OpenRouter), lalu placeholder
dikembalikan pada hasilnya. Termasuk retry ringan untuk galat sesaat.

System prompt = templat milik kami (tanpa data klien) → tak perlu disamarkan.
Hanya `prompt` (berisi konten temuan) yang di-mask.
"""
from __future__ import annotations

import time
from collections.abc import Iterable

from app.ai.masking import mask_text, unmask_text
from app.ai.providers import AINotConfigured, get_provider


def draft(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 1024,
    extra_domains: Iterable[str] = (),
    retries: int = 2,
) -> str:
    """Hasilkan teks dari LLM dengan masking data sensitif otomatis.

    1. Samarkan `prompt` (IP internal, hostname, kredensial, dll.).
    2. Panggil provider aktif (retry pada galat sesaat).
    3. Kembalikan placeholder ke nilai asli pada hasil.
    """
    masked = mask_text(prompt, extra_domains=extra_domains)
    provider = get_provider()

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            reply = provider.generate(masked.text, system=system, max_tokens=max_tokens)
            return unmask_text(reply, masked.mapping)
        except AINotConfigured:
            raise  # konfigurasi salah → tak ada gunanya retry
        except Exception as exc:  # noqa: BLE001 — retry galat sesaat (jaringan/rate limit)
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def preview_masked(prompt: str, *, extra_domains: Iterable[str] = ()) -> str:
    """Kembalikan teks tersamar (tanpa memanggil LLM) — untuk audit/uji apa yang keluar."""
    return mask_text(prompt, extra_domains=extra_domains).text

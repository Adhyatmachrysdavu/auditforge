"""Verifikasi akses Claude API (Sprint 1 / D1).

Jalankan:  python scripts/verify_claude.py
Pastikan ANTHROPIC_API_KEY tersedia di environment atau di berkas .env.
"""
from __future__ import annotations

import sys

from app.ai import client as ai_client
from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("[!] ANTHROPIC_API_KEY belum diisi (env/.env). Batal.")
        return 1
    try:
        reply = ai_client.ping(settings.ai_model)
    except Exception as exc:  # noqa: BLE001
        print(f"[x] Gagal memanggil Claude API: {exc}")
        return 2
    print(f"[ok] Model: {settings.ai_model}")
    print(f"[ok] Balasan: {reply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

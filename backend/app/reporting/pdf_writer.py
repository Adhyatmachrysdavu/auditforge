"""Render HTML laporan ke PDF via WeasyPrint (D16).

Impor WeasyPrint ditunda ke dalam fungsi agar modul tetap dapat diimpor di
lingkungan tanpa pustaka sistemnya (mis. saat uji unit non-PDF).
"""
from __future__ import annotations

from typing import cast


def render_pdf(html: str, *, base_url: str | None = None) -> bytes:
    """Ubah string HTML menjadi byte PDF (A4, sesuai @page di template)."""
    from weasyprint import HTML

    return cast(bytes, HTML(string=html, base_url=base_url).write_pdf())

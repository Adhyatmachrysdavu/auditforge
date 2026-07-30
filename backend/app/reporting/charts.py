"""Grafik laporan sebagai SVG inline (D16) — house-style, tanpa dependensi.

Deterministik & dapat diuji: fungsi mengembalikan string `<svg>` yang bisa
disematkan langsung ke HTML (pratinjau) maupun PDF (WeasyPrint). Dua grafik:
distribusi keparahan (bar) dan matriks risiko (keparahan × prioritas).
"""
from __future__ import annotations

from html import escape

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]
_SEV_COLOR = {
    "critical": "#b91c1c",
    "high": "#dc2626",
    "medium": "#d97706",
    "low": "#ca8a04",
    "info": "#16a34a",
}
_SEV_LABEL = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}


def severity_bar_svg(counts: dict[str, int], *, width: int = 460) -> str:
    """Bar horizontal distribusi keparahan (urut critical→info)."""
    rows = [(s, counts.get(s, 0)) for s in _SEV_ORDER if counts.get(s, 0)]
    if not rows:
        return '<svg width="10" height="10" xmlns="http://www.w3.org/2000/svg"></svg>'
    row_h, gap, label_w, pad = 24, 8, 78, 10
    max_v = max(v for _, v in rows) or 1
    bar_max = width - label_w - pad * 2 - 40
    height = pad * 2 + len(rows) * row_h + (len(rows) - 1) * gap
    parts = [
        (
            f'<svg width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            'font-family="sans-serif" font-size="12">'
        )
    ]
    y = pad
    for sev, val in rows:
        bar_w = max(2, int(bar_max * val / max_v))
        color = _SEV_COLOR[sev]
        parts.append(
            f'<text x="{pad}" y="{y + row_h - 7}" fill="#334155">'
            f"{_SEV_LABEL[sev]}</text>"
        )
        parts.append(
            f'<rect x="{pad + label_w}" y="{y}" width="{bar_w}" height="{row_h - 4}" '
            f'rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{pad + label_w + bar_w + 6}" y="{y + row_h - 7}" '
            f'fill="#334155" font-weight="bold">{val}</text>'
        )
        y += row_h + gap
    parts.append("</svg>")
    return "".join(parts)


def matrix_from(items: list[tuple[str, int | None]]) -> dict[tuple[str, int], int]:
    """Hitung sel matriks (keparahan, prioritas)→jumlah dari daftar temuan."""
    cells: dict[tuple[str, int], int] = {}
    for sev, prio in items:
        s = (sev or "info").lower()
        p = prio if prio in (1, 2, 3, 4) else 4
        cells[(s, p)] = cells.get((s, p), 0) + 1
    return cells


def risk_matrix_svg(cells: dict[tuple[str, int], int]) -> str:
    """Matriks risiko: baris keparahan (critical atas) × kolom prioritas P1–P4."""
    cell_w, cell_h, head = 62, 34, 26
    left = 82
    cols = [1, 2, 3, 4]
    width = left + len(cols) * cell_w + 12
    height = head + len(_SEV_ORDER) * cell_h + 12
    parts = [
        (
            f'<svg width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            'font-family="sans-serif" font-size="12">'
        )
    ]
    # Header kolom prioritas.
    for i, p in enumerate(cols):
        x = left + i * cell_w
        parts.append(
            f'<text x="{x + cell_w // 2}" y="{head - 8}" text-anchor="middle" '
            f'fill="#334155" font-weight="bold">P{p}</text>'
        )
    # Baris keparahan.
    for r, sev in enumerate(_SEV_ORDER):
        y = head + r * cell_h
        parts.append(
            f'<text x="8" y="{y + cell_h // 2 + 4}" fill="#334155">'
            f"{_SEV_LABEL[sev]}</text>"
        )
        for i, p in enumerate(cols):
            x = left + i * cell_w
            n = cells.get((sev, p), 0)
            fill = _SEV_COLOR[sev] if n else "#f1f5f9"
            txt_color = "#ffffff" if n else "#94a3b8"
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 4}" height="{cell_h - 4}" '
                f'rx="4" fill="{fill}"/>'
            )
            parts.append(
                f'<text x="{x + (cell_w - 4) // 2}" y="{y + cell_h // 2 + 4}" '
                f'text-anchor="middle" fill="{txt_color}" font-weight="bold">{n}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _esc(s: str) -> str:  # dipakai html_writer; disatukan agar konsisten
    return escape(s or "")

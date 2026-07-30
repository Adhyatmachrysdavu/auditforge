"""Parsing balasan LLM menjadi field terstruktur (tahan-banting).

Model gratis kerap membungkus JSON dengan teks/pagar kode ```json atau
memotongnya. Fungsi di sini mengekstrak field yang diminta walau JSON tak
sempurna, agar hasil AI tak hilang. Dipakai bersama oleh naratif temuan (D10)
dan ringkasan eksekutif (D11).
"""
from __future__ import annotations

import json
import re

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _field(name: str, text: str) -> str:
    """Ekstrak nilai string sebuah kunci JSON walau objek belum tertutup (terpotong)."""
    m = re.search(rf'"{name}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if not m:
        return ""
    try:
        return str(json.loads(f'"{m.group(1)}"')).strip()
    except json.JSONDecodeError:
        return m.group(1).strip()


def extract_json_fields(
    reply: str, keys: tuple[str, ...], *, fallback_key: str | None = None
) -> dict[str, str]:
    """Ambil `keys` dari balasan LLM secara tahan-banting.

    Urutan: (1) buang pagar kode, (2) coba JSON penuh, (3) regex per-field bila
    JSON terpotong, (4) fallback — taruh seluruh balasan pada `fallback_key`
    agar output tak hilang. Selalu mengembalikan semua `keys` (default "").
    """
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^json\s*", "", text, flags=re.IGNORECASE).strip()
    candidate = text
    m = _JSON_RE.search(text)
    if m:
        candidate = m.group(0)
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return {k: str(data.get(k, "")).strip() for k in keys}
    except (json.JSONDecodeError, TypeError):
        pass
    fields = {k: _field(k, candidate) for k in keys}
    if any(fields.values()):
        return fields
    out = {k: "" for k in keys}
    if fallback_key:
        out[fallback_key] = reply.strip()
    return out

"""Perbandingan versi naratif (Modul 2) — deterministik, tanpa DB.

Membandingkan draf AI dengan naratif final auditor **per bagian**
(`description`, `impact`, `recommendation`), bukan sebagai diff baris mentah.
Yang ingin diketahui auditor adalah "bagian mana yang saya ubah dari draf AI",
dan pembacanya adalah manusia — bukan mesin patch.

`changed_ratio` juga menjadi bahan bukti indikator proposal *"maksimal 30%
kalimat memerlukan penyuntingan berat"*. Karena itu rasio keseluruhan
ditimbang panjang kata, bukan dirata-ratakan per bagian: satu kalimat pendek
yang diganti total tidak boleh terlihat sebesar satu paragraf panjang yang
dirombak.
"""
from __future__ import annotations

import difflib
import re

SECTIONS: tuple[str, ...] = ("description", "impact", "recommendation")

_WORD_RE = re.compile(r"\S+")


def _text(source: object, key: str) -> str:
    """Ambil satu bagian naratif dengan aman; apa pun selain dict dianggap kosong."""
    if not isinstance(source, dict):
        return ""
    return str(source.get(key, "") or "").strip()


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _diff_section(before: str, after: str) -> dict[str, object]:
    b, a = _words(before), _words(after)
    matcher = difflib.SequenceMatcher(a=b, b=a, autojunk=False)

    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(b[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(a[j1:j2])

    # 1 - ratio() = proporsi ketidaksamaan. Dua teks kosong dianggap identik.
    changed = 0.0 if not b and not a else round(1.0 - matcher.ratio(), 4)

    return {
        "before": before,
        "after": after,
        "added": added,
        "removed": removed,
        "changed_ratio": changed,
        # Dipakai untuk menimbang rasio keseluruhan; tidak untuk ditampilkan.
        "_weight": max(len(b), len(a)),
    }


def diff_narrative(before: dict | None, after: dict | None) -> dict[str, object]:
    """Bandingkan draf AI (`before`) dengan naratif final auditor (`after`)."""
    sections: dict[str, object] = {}
    total_weight = 0
    weighted_change = 0.0

    for name in SECTIONS:
        result = _diff_section(_text(before, name), _text(after, name))
        weight = int(result.pop("_weight"))
        total_weight += weight
        weighted_change += float(result["changed_ratio"]) * weight
        sections[name] = result

    overall = round(weighted_change / total_weight, 4) if total_weight else 0.0
    return {"sections": sections, "overall_changed_ratio": overall}

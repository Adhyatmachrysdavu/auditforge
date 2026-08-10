"""Syarat dan isi entri Basis Pengetahuan (Modul 3) — deterministik, tanpa DB.

Naratif yang disalin adalah **naratif efektif**, mengikuti aturan yang sama
dengan `reporting/report_data.py` dan `review_diff.py`: `final or draft`.
`final_narrative` yang kosong berarti auditor **menerima draf AI apa adanya**,
bukan tidak punya naratif — membacanya mentah-mentah akan membuang naskah yang
justru sudah disetujui manusia.

`auditor_edited` merekam bedanya agar auditor tahu bobot tiap rujukan; ia
**tidak** dipakai untuk menyaring entri.
"""
from __future__ import annotations

SECTIONS: tuple[str, ...] = ("description", "impact", "recommendation")


def _section(source: object, key: str) -> str:
    """Ambil satu bagian naratif dengan aman; apa pun selain dict dianggap kosong."""
    if not isinstance(source, dict):
        return ""
    return str(source.get(key, "") or "").strip()


def _has_text(source: object) -> bool:
    return any(_section(source, name) for name in SECTIONS)


def effective_narrative(finding: object) -> dict[str, str]:
    """Naratif yang benar-benar berlaku: suntingan auditor menang atas draf AI."""
    final = getattr(finding, "final_narrative", None)
    draft = getattr(finding, "ai_draft", None)
    source = final if _has_text(final) else draft
    return {name: _section(source, name) for name in SECTIONS}


def is_auditor_edited(finding: object) -> bool:
    """True bila naskahnya diketik auditor, bukan draf AI yang diterima apa adanya."""
    return _has_text(getattr(finding, "final_narrative", None))


def should_create_entry(
    *,
    status: str,
    kb_shareable: bool,
    narrative: dict[str, str],
    already_exists: bool,
) -> tuple[bool, str]:
    """Boleh membuat entri KB? Kembalikan (boleh, alasan bila tidak).

    Alasannya dikembalikan sebagai data agar pemanggil dapat mencatat mengapa
    sebuah persetujuan tidak menghasilkan entri, alih-alih diam saja.
    """
    if status != "approved":
        return False, f"Hanya temuan yang disetujui masuk Basis Pengetahuan (status: {status})."
    if not kb_shareable:
        return False, "Penugasan ini menolak berbagi ke Basis Pengetahuan."
    if not _has_text(narrative):
        return False, "Naratif kosong; tidak ada yang dapat dijadikan rujukan."
    if already_exists:
        return False, "Entri untuk temuan ini sudah ada."
    return True, ""

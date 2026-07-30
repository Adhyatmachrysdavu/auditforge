"""Pengayaan temuan (D8) — deterministik, tanpa AI.

Tiga fungsi:
1. **CWE → OWASP Top 10 2021** — memetakan CWE ke kategori OWASP (A01–A10).
2. **CVSS v3.1** — band severity dari skor + hitung skor dari vektor (lib `cvss`).
3. **Penautan CVE** — ekstrak `CVE-xxxx-xxxx` dari teks + backfill skor/CWE/vektor
   dari basis referensi lokal (`_CVE_DB`, dapat diperluas via berkas JSON).

Dijalankan **sebelum** deduplikasi agar CWE hasil backfill ikut menyatukan temuan.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.models.enums import Severity

# --------------------------------------------------------------------------- #
# 1. CWE → OWASP Top 10 2021
# --------------------------------------------------------------------------- #
# Subset representatif dari pemetaan resmi OWASP Top 10 2021 (CWE tersering).
_OWASP_2021: dict[str, set[int]] = {
    "A01:2021 – Broken Access Control": {
        22, 23, 35, 59, 200, 201, 219, 264, 275, 276, 284, 285, 352, 359,
        377, 425, 441, 497, 538, 540, 548, 552, 566, 601, 639, 651, 668,
        862, 863, 913, 922, 1275,
    },
    "A02:2021 – Cryptographic Failures": {
        261, 296, 310, 311, 312, 319, 321, 322, 323, 324, 325, 326, 327,
        328, 329, 330, 331, 335, 336, 337, 338, 340, 347, 523, 720, 757,
        759, 760, 780, 818, 916,
    },
    "A03:2021 – Injection": {
        20, 74, 75, 77, 78, 79, 80, 83, 87, 88, 89, 90, 91, 93, 94, 95, 96,
        97, 98, 99, 100, 113, 116, 138, 184, 470, 471, 564, 610, 643, 644,
        652, 917,
    },
    "A04:2021 – Insecure Design": {
        73, 183, 209, 213, 235, 256, 257, 266, 269, 280, 316, 419, 430, 434,
        444, 451, 472, 501, 522, 525, 539, 579, 598, 602, 642, 646, 650, 653,
        656, 657, 799, 807, 840, 841, 927, 1021, 1173,
    },
    "A05:2021 – Security Misconfiguration": {
        2, 11, 13, 15, 16, 260, 315, 520, 526, 537, 541, 547, 611, 614, 756,
        776, 942, 1004, 1032, 1174,
    },
    "A06:2021 – Vulnerable and Outdated Components": {937, 1035, 1104},
    "A07:2021 – Identification and Authentication Failures": {
        255, 259, 287, 288, 290, 294, 295, 297, 300, 302, 304, 306, 307, 346,
        384, 521, 613, 620, 640, 798, 940, 1216,
    },
    "A08:2021 – Software and Data Integrity Failures": {
        345, 353, 426, 494, 502, 565, 784, 829, 830, 915,
    },
    "A09:2021 – Security Logging and Monitoring Failures": {117, 223, 532, 778},
    "A10:2021 – Server-Side Request Forgery (SSRF)": {918},
}
# Inversi: nomor CWE → label OWASP.
_CWE_TO_OWASP: dict[int, str] = {
    cwe: label for label, cwes in _OWASP_2021.items() for cwe in cwes
}


def _cwe_number(cwe: str | None) -> int | None:
    if not cwe:
        return None
    m = re.search(r"(\d+)", cwe)
    return int(m.group(1)) if m else None


def owasp_for_cwe(cwe: str | None) -> str | None:
    """Kategori OWASP Top 10 2021 untuk sebuah CWE (None bila tak dipetakan)."""
    n = _cwe_number(cwe)
    return _CWE_TO_OWASP.get(n) if n is not None else None


# --------------------------------------------------------------------------- #
# 2. CVSS v3.1
# --------------------------------------------------------------------------- #
def severity_from_cvss(score: float | None) -> Severity | None:
    """Band kualitatif CVSS v3.1 dari skor dasar."""
    if score is None:
        return None
    if score <= 0.0:
        return Severity.info
    if score < 4.0:
        return Severity.low
    if score < 7.0:
        return Severity.medium
    if score < 9.0:
        return Severity.high
    return Severity.critical


_VECTOR_RE = re.compile(r"CVSS:3\.[01]/[A-Z:/]+", re.IGNORECASE)


def find_cvss_vector(*texts: str | None) -> str | None:
    """Temukan string vektor CVSS v3.x pada teks (references/description/raw)."""
    for t in texts:
        if not t:
            continue
        m = _VECTOR_RE.search(t)
        if m:
            return m.group(0).upper()
    return None


def score_from_vector(vector: str | None) -> float | None:
    """Hitung base score dari vektor CVSS v3.x (None bila vektor tak valid)."""
    if not vector:
        return None
    try:
        from cvss import CVSS3

        return float(CVSS3(vector).base_score)
    except Exception:  # noqa: BLE001 — vektor rusak → lewati saja
        return None


# --------------------------------------------------------------------------- #
# 3. Penautan CVE
# --------------------------------------------------------------------------- #
_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)

# Basis referensi lokal minimal (pengganti feed NVD penuh; dapat diperluas via
# berkas JSON, lihat `_load_cve_file`). Cukup untuk demo penautan & backfill.
_CVE_DB: dict[str, dict[str, object]] = {
    "CVE-2021-44228": {  # Log4Shell
        "cvss": 10.0,
        "cwe": "CWE-502",
        "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    },
    "CVE-2014-0160": {  # Heartbleed
        "cvss": 7.5,
        "cwe": "CWE-125",
        "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
    },
    "CVE-2017-5638": {  # Apache Struts RCE
        "cvss": 10.0,
        "cwe": "CWE-20",
        "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    },
}

# Berkas opsional untuk menambah/menimpa basis CVE tanpa ubah kode.
_CVE_FILE = Path(__file__).resolve().parents[2] / "datasets" / "reference" / "cve_min.json"


def _load_cve_file() -> None:
    if _CVE_FILE.exists():
        try:
            extra = json.loads(_CVE_FILE.read_text(encoding="utf-8"))
            for k, v in extra.items():
                _CVE_DB[k.upper()] = v
        except (json.JSONDecodeError, OSError):
            pass


_load_cve_file()


def extract_cves(*texts: str | None) -> list[str]:
    """Kumpulkan ID CVE unik dari beberapa teks (huruf besar, urut kemunculan)."""
    seen: dict[str, None] = {}
    for t in texts:
        if not t:
            continue
        for m in _CVE_RE.finditer(t):
            seen.setdefault(m.group(0).upper(), None)
    return list(seen)


# --------------------------------------------------------------------------- #
# Orkestrasi
# --------------------------------------------------------------------------- #
@dataclass
class Enrichment:
    """Hasil pengayaan satu temuan."""

    cwe: str | None = None
    cvss_score: float | None = None
    cvss_vector: str | None = None
    severity: Severity | None = None
    owasp: str | None = None
    cves: list[str] = field(default_factory=list)


def enrich(
    *,
    title: str | None = None,
    description: str | None = None,
    references: list[str] | None = None,
    cwe: str | None = None,
    cvss_score: float | None = None,
) -> Enrichment:
    """Gabungkan CVE, CVSS v3.1, dan OWASP untuk satu temuan.

    Prioritas skor: skor dari perkakas → vektor pada teks → basis CVE.
    Backfill CWE dari basis CVE bila temuan belum punya CWE.
    """
    ref_text = " ".join(references or [])
    cves = extract_cves(title, description, ref_text)

    out_cwe = cwe
    out_score = cvss_score
    vector = find_cvss_vector(ref_text, description)

    # Backfill dari basis CVE (skor/CWE/vektor) untuk CVE yang dikenal.
    for cid in cves:
        info = _CVE_DB.get(cid)
        if not info:
            continue
        cvss_val = info.get("cvss")
        if out_score is None and isinstance(cvss_val, (int, float)):
            out_score = float(cvss_val)
        if not out_cwe and info.get("cwe"):
            out_cwe = str(info["cwe"])
        if not vector and info.get("vector"):
            vector = str(info["vector"])

    # Vektor → skor (bila skor masih kosong).
    if out_score is None and vector:
        out_score = score_from_vector(vector)

    return Enrichment(
        cwe=out_cwe,
        cvss_score=out_score,
        cvss_vector=vector,
        severity=severity_from_cvss(out_score),
        owasp=owasp_for_cwe(out_cwe),
        cves=cves,
    )

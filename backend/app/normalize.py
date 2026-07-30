"""Normalisasi keparahan lintas-perkakas, *fingerprint*, dan deduplikasi temuan.

Tahap D7. Deterministik (tanpa AI): menyeragamkan severity, menghitung sidik
jari stabil per temuan, lalu menggabungkan temuan identik (mis. satu target
yang dipindai beberapa perkakas menghasilkan duplikat lintas-perkakas).

Prinsip merge:
- **severity** → ambil yang tertinggi (paling parah menang).
- **cvss_score** → ambil yang tertinggi (None-aman).
- **cwe** → isi bila salah satu punya, pertahankan yang sudah ada.
- **sources** → kumpulan perkakas/berkas asal yang berkontribusi.
- **occurrences** → berapa temuan mentah yang tergabung ke satu temuan bersih.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.models.enums import Severity
from app.parsers.base import UnifiedFinding

# Satu asal yang berkontribusi ke sebuah temuan (perkakas + id berkas unggah).
SourceRef = dict[str, object]

# Urutan kanonik keparahan (indeks besar = lebih parah).
SEVERITY_ORDER: list[Severity] = [
    Severity.info,
    Severity.low,
    Severity.medium,
    Severity.high,
    Severity.critical,
]
_SEVERITY_RANK: dict[str, int] = {s.value: i for i, s in enumerate(SEVERITY_ORDER)}


def severity_rank(severity: str | Severity) -> int:
    """Peringkat numerik severity (tak dikenal → dianggap `info`)."""
    val = severity.value if isinstance(severity, Severity) else str(severity)
    return _SEVERITY_RANK.get(val.lower(), 0)


def _as_value(s: str | Severity) -> str:
    return s.value if isinstance(s, Severity) else str(s)


def max_severity(a: str | Severity, b: str | Severity) -> str:
    """Kembalikan severity yang lebih parah di antara dua nilai (sebagai string)."""
    return _as_value(a) if severity_rank(a) >= severity_rank(b) else _as_value(b)


def _norm_target(target: str | None) -> str:
    """Seragamkan target: buang skema, huruf kecil, buang query/fragment & slash akhir."""
    if not target:
        return ""
    t = target.strip().lower()
    t = re.sub(r"^[a-z]+://", "", t)  # buang skema (http://, https://, …)
    t = t.split("?", 1)[0].split("#", 1)[0]  # buang query & fragment
    t = t.rstrip("/")
    return t


def _norm_title(title: str) -> str:
    """Seragamkan judul: huruf kecil, buang non-alfanumerik, ringkas spasi."""
    t = title.strip().lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _norm_cwe(cwe: str | None) -> str:
    """Seragamkan CWE ke bentuk `cwe-<n>` bila memungkinkan."""
    if not cwe:
        return ""
    m = re.search(r"(\d+)", cwe)
    return f"cwe-{m.group(1)}" if m else cwe.strip().lower()


def compute_fingerprint(uf: UnifiedFinding) -> str:
    """Sidik jari stabil untuk deduplikasi.

    Sinyal utama = CWE bila ada (lintas-perkakas lebih tahan karena judul berbeda),
    jika tidak jatuh ke judul ter-normalisasi; digabung dengan target ter-normalisasi.
    """
    primary = _norm_cwe(uf.cwe) or _norm_title(uf.title)
    target = _norm_target(uf.target)
    basis = f"{primary}||{target}"
    # SHA-1 dipakai sebagai kunci dedup deterministik, bukan untuk keamanan.
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


@dataclass
class DedupedFinding:
    """Hasil gabungan satu kelompok temuan identik."""

    fingerprint: str
    title: str
    description: str
    severity: str
    cwe: str | None
    cvss_score: float | None
    occurrences: int = 1
    sources: list[SourceRef] = field(default_factory=list)


def merge_into(acc: DedupedFinding, uf: UnifiedFinding, source: SourceRef) -> None:
    """Gabungkan `uf` ke akumulator `acc` (severity/cvss tertinggi menang)."""
    if severity_rank(uf.severity) > severity_rank(acc.severity):
        acc.severity = uf.severity.value
        acc.title = uf.title[:300]
        acc.description = uf.to_description()
    if uf.cvss_score is not None and (acc.cvss_score is None or uf.cvss_score > acc.cvss_score):
        acc.cvss_score = uf.cvss_score
    if not acc.cwe and uf.cwe:
        acc.cwe = uf.cwe
    acc.occurrences += 1
    if source not in acc.sources:
        acc.sources.append(source)


def dedupe_findings(
    findings: list[UnifiedFinding],
) -> list[DedupedFinding]:
    """Gabungkan daftar `UnifiedFinding` menjadi temuan unik per *fingerprint*.

    Mempertahankan urutan kemunculan pertama. Dipakai untuk uji + penggabungan
    dalam satu berkas; penggabungan lintas-berkas dilakukan di worker terhadap DB.
    """
    groups: dict[str, DedupedFinding] = {}
    order: list[str] = []
    for uf in findings:
        fp = compute_fingerprint(uf)
        source: SourceRef = {"tool": uf.tool.value}
        if fp not in groups:
            groups[fp] = DedupedFinding(
                fingerprint=fp,
                title=uf.title[:300],
                description=uf.to_description(),
                severity=uf.severity.value,
                cwe=uf.cwe,
                cvss_score=uf.cvss_score,
                occurrences=1,
                sources=[source],
            )
            order.append(fp)
        else:
            merge_into(groups[fp], uf, source)
    return [groups[fp] for fp in order]

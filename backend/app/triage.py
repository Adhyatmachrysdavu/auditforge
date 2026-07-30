"""Triase deterministik (D11) — prioritas temuan tanpa LLM (dapat diuji penuh).

Prioritas dihitung dari sinyal objektif yang bisa diaudit: keparahan, skor CVSS,
jumlah kemunculan (korroborasi lintas-perkakas/berkas), dan keberadaan CVE publik
(indikasi eksploit kemungkinan tersedia). Hasilnya rank P1–P4 + skor + kode alasan.

Selaras prinsip AuditForge "deterministik-first": prioritas awal dihitung mesin
agar konsisten & dapat dijelaskan; AI hanya membuat draf naratif/ringkasan, dan
auditor tetap pengambil keputusan akhir (boleh menimpa prioritas).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Bobot dasar per label keparahan (sebelum bonus CVSS/kemunculan/CVE).
_SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 100.0,
    "high": 70.0,
    "medium": 40.0,
    "low": 15.0,
    "info": 5.0,
}

# Ambang skor → prioritas. Dipilih agar label keparahan memetakan wajar:
# critical→P1, high→P2, medium→P3, low/info→P4; bonus dapat menaikkan (eskalasi).
_P1_MIN = 90.0
_P2_MIN = 60.0
_P3_MIN = 30.0


@dataclass(frozen=True)
class Triage:
    priority: int  # 1..4 (1 = paling mendesak)
    score: float
    reasons: list[str] = field(default_factory=list)  # kode alasan (dilokalkan di UI)

    @property
    def rank(self) -> str:
        return f"P{self.priority}"


def priority_score(
    severity: str,
    *,
    cvss_score: float | None = None,
    occurrences: int = 1,
    cve: list[str] | None = None,
) -> tuple[float, list[str]]:
    """Hitung skor prioritas mentah + kode alasan dari sinyal objektif temuan."""
    reasons: list[str] = []
    sev = (severity or "info").lower()
    score = _SEVERITY_WEIGHT.get(sev, 5.0)
    reasons.append(f"severity:{sev}")

    if cvss_score is not None:
        score += cvss_score * 3.0  # kontribusi 0..30
        if cvss_score >= 9.0:
            reasons.append("cvss:critical")
        elif cvss_score >= 7.0:
            reasons.append("cvss:high")

    if occurrences and occurrences > 1:
        score += min(occurrences - 1, 5) * 4.0  # korroborasi, maksimum +20
        reasons.append(f"recurrence:{occurrences}")

    if cve:
        score += 15.0  # eksploit publik kemungkinan tersedia
        reasons.append(f"cve:{len(cve)}")

    return score, reasons


def rank_for_score(score: float) -> int:
    """Petakan skor mentah ke prioritas 1..4."""
    if score >= _P1_MIN:
        return 1
    if score >= _P2_MIN:
        return 2
    if score >= _P3_MIN:
        return 3
    return 4


def triage(
    severity: str,
    *,
    cvss_score: float | None = None,
    occurrences: int = 1,
    cve: list[str] | None = None,
) -> Triage:
    """Triase satu temuan → Triage(priority, score, reasons)."""
    score, reasons = priority_score(
        severity, cvss_score=cvss_score, occurrences=occurrences, cve=cve
    )
    return Triage(priority=rank_for_score(score), score=round(score, 1), reasons=reasons)

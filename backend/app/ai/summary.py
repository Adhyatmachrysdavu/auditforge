"""Ringkasan eksekutif per-penugasan berbasis LLM (D11).

`build_summary_payload()` menyusun agregat deterministik dari temuan (jumlah per
keparahan & prioritas, temuan prioritas teratas, kategori OWASP) menjadi teks
ringkas — bagian ini murni Python & dapat diuji tanpa LLM. `posture()` menilai
postur keamanan secara deterministik. `generate_executive_summary()` meminta LLM
merangkai ringkasan naratif untuk pembaca manajemen. Masking otomatis ditangani
`llm.draft()`. AI hanya membuat DRAF; auditor menyunting & menyetujui.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.ai import llm
from app.ai.parsing import extract_json_fields
from app.ai.prompts import SUMMARY_PROMPT_VERSION, summary_prompts
from app.ai.providers import get_provider

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]
_SEV_RANK = {s: i for i, s in enumerate(_SEV_ORDER)}


@dataclass
class SummaryFinding:
    """Masukan ringan untuk agregasi (dilepas dari model DB agar mudah diuji)."""

    title: str
    severity: str
    priority: int | None = None
    cvss_score: float | None = None
    owasp: str | None = None
    cve: list[str] = field(default_factory=list)


@dataclass
class ExecutiveSummary:
    overview: str
    key_risks: str
    recommendations: str
    posture: str
    model: str
    prompt_version: str = SUMMARY_PROMPT_VERSION

    def as_dict(self) -> dict[str, str]:
        return {
            "overview": self.overview,
            "key_risks": self.key_risks,
            "recommendations": self.recommendations,
            "posture": self.posture,
        }


def posture(findings: list[SummaryFinding]) -> str:
    """Kode postur keamanan deterministik (dilokalkan di UI)."""
    if not findings:
        return "clean"
    sevs = {(f.severity or "").lower() for f in findings}
    prios = {f.priority for f in findings if f.priority}
    if "critical" in sevs or 1 in prios:
        return "critical"
    if "high" in sevs:
        return "elevated"
    if "medium" in sevs:
        return "moderate"
    return "low"


def _sort_key(f: SummaryFinding) -> tuple[int, int, float]:
    """Urutkan: prioritas naik (P1 dulu) → keparahan → CVSS turun."""
    prio = f.priority if f.priority else 9
    sev = _SEV_RANK.get((f.severity or "").lower(), 99)
    return (prio, sev, -(f.cvss_score or 0.0))


def build_summary_payload(
    *,
    engagement_name: str,
    client_name: str,
    findings: list[SummaryFinding],
    top_n: int = 6,
) -> str:
    """Rangkai agregat temuan menjadi teks ringkas & deterministik untuk prompt."""
    lines = [f"Penugasan: {engagement_name}", f"Klien: {client_name}"]
    lines.append(f"Total temuan (setelah dedup): {len(findings)}")

    sev_counts = {s: 0 for s in _SEV_ORDER}
    for f in findings:
        s = (f.severity or "info").lower()
        sev_counts[s] = sev_counts.get(s, 0) + 1
    lines.append(
        "Per keparahan: "
        + ", ".join(f"{s}={sev_counts[s]}" for s in _SEV_ORDER if sev_counts[s])
    )

    prio_counts: dict[int, int] = {}
    for f in findings:
        if f.priority:
            prio_counts[f.priority] = prio_counts.get(f.priority, 0) + 1
    if prio_counts:
        lines.append(
            "Per prioritas: "
            + ", ".join(f"P{p}={prio_counts[p]}" for p in sorted(prio_counts))
        )

    n_cve = sum(1 for f in findings if f.cve)
    if n_cve:
        lines.append(f"Temuan dengan CVE publik: {n_cve}")

    owasp = sorted({f.owasp for f in findings if f.owasp})
    if owasp:
        lines.append("Kategori OWASP: " + "; ".join(owasp))

    top = sorted(findings, key=_sort_key)[:top_n]
    if top:
        lines.append("Temuan prioritas teratas:")
        for f in top:
            rank = f"P{f.priority}" if f.priority else "-"
            cvss = f"CVSS {f.cvss_score}" if f.cvss_score is not None else "CVSS -"
            lines.append(f"- [{rank} · {f.severity} · {cvss}] {f.title}")

    return "\n".join(lines)


def generate_executive_summary(
    payload: str,
    *,
    posture_code: str,
    lang: str = "id",
    max_tokens: int = 1200,
) -> ExecutiveSummary:
    """Panggil LLM (dengan masking otomatis) → ringkasan eksekutif terstruktur."""
    system, user = summary_prompts(payload, lang=lang)
    reply = llm.draft(user, system=system, max_tokens=max_tokens)
    parts = extract_json_fields(
        reply, ("overview", "key_risks", "recommendations"), fallback_key="overview"
    )
    provider = get_provider()
    return ExecutiveSummary(
        overview=parts["overview"],
        key_risks=parts["key_risks"],
        recommendations=parts["recommendations"],
        posture=posture_code,
        model=provider.model,
    )

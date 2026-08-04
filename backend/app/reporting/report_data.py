"""Perakitan data laporan (D15) — deterministik, dapat diuji tanpa DOCX.

Mengambil temuan yang telah ditinjau lalu menyusun struktur laporan: metadata +
ringkasan eksekutif (bila ada) + daftar temuan terurut prioritas. Naratif memakai
`final_narrative` (suntingan auditor) bila ada, jika tidak `ai_draft`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]
_SEV_RANK = {s: i for i, s in enumerate(_SEV_ORDER)}


@dataclass
class ReportFinding:
    finding_id: int
    title: str
    severity: str
    status: str
    priority: int | None
    cwe: str | None
    owasp: str | None
    cvss_score: float | None
    cve: list[str]
    tools: list[str]
    occurrences: int
    description: str
    impact: str
    recommendation: str
    edited: bool
    evidence: list[str] = field(default_factory=list)  # data URI gambar (D16)


@dataclass
class ReportData:
    org_name: str
    report_title: str
    engagement_name: str
    client_name: str
    generated_at: str
    posture: str | None
    summary_overview: str
    summary_key_risks: str
    summary_recommendations: str
    severity_counts: dict[str, int]
    # Peringatan bila ringkasan eksekutif dibuat saat jumlah temuan masih berbeda.
    # Tanpa ini laporan bisa membuka dengan "terdapat 4 temuan" lalu menampilkan
    # tabel berisi 3 — membantah dirinya sendiri di depan klien.
    summary_stale_note: str | None = None
    # --- Modul 2: kelengkapan penugasan yang dijanjikan proposal ---
    period: str | None = None
    scope: str | None = None
    findings: list[ReportFinding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.findings)


def _narrative(f: object) -> dict[str, str]:
    """Naratif efektif: final (auditor) menang atas draf AI; aman bila kosong."""
    final = getattr(f, "final_narrative", None)
    draft = getattr(f, "ai_draft", None)
    n = final or draft or {}
    return {
        "description": str(n.get("description", "") if isinstance(n, dict) else "").strip(),
        "impact": str(n.get("impact", "") if isinstance(n, dict) else "").strip(),
        "recommendation": str(
            n.get("recommendation", "") if isinstance(n, dict) else ""
        ).strip(),
    }


def _sort_key(f: object) -> tuple[int, int, float]:
    prio = getattr(f, "priority", None) or 9
    sev = _SEV_RANK.get((getattr(f, "severity", "") or "").lower(), 99)
    return (prio, sev, -(getattr(f, "cvss_score", None) or 0.0))


def _tools_of(f: object) -> list[str]:
    srcs = getattr(f, "sources", None) or []
    tools = {s.get("tool") for s in srcs if isinstance(s, dict) and s.get("tool")}
    return sorted(t for t in tools if t)


def build_report_data(
    engagement: object,
    findings: list[object],
    *,
    org_name: str,
    report_title: str,
    include: str = "approved",
    exec_summary: dict[str, object] | None = None,
    summary_finding_count: int | None = None,
) -> ReportData:
    """Susun `ReportData`. `include`: 'approved' (default) atau 'all'.

    `summary_finding_count` adalah jumlah temuan pada saat ringkasan eksekutif
    disusun AI. Bila kini berbeda, laporan memuat peringatan bahwa ringkasan
    perlu dibuat ulang — ringkasan adalah snapshot dan tidak ikut berubah saat
    temuan bertambah atau statusnya berpindah.
    """
    selected = (
        list(findings)
        if include == "all"
        else [f for f in findings if getattr(f, "status", "") == "approved"]
    )
    selected.sort(key=_sort_key)

    sev_counts = {s: 0 for s in _SEV_ORDER}
    for f in selected:
        s = (getattr(f, "severity", "info") or "info").lower()
        sev_counts[s] = sev_counts.get(s, 0) + 1

    es = exec_summary or {}
    report_findings: list[ReportFinding] = []
    for f in selected:
        n = _narrative(f)
        report_findings.append(
            ReportFinding(
                finding_id=getattr(f, "id", 0) or 0,
                title=getattr(f, "title", ""),
                severity=getattr(f, "severity", "info"),
                status=getattr(f, "status", ""),
                priority=getattr(f, "priority", None),
                cwe=getattr(f, "cwe", None),
                owasp=getattr(f, "owasp", None),
                cvss_score=getattr(f, "cvss_score", None),
                cve=list(getattr(f, "cve", None) or []),
                tools=_tools_of(f),
                occurrences=getattr(f, "occurrences", 1) or 1,
                description=n["description"],
                impact=n["impact"],
                recommendation=n["recommendation"],
                edited=bool(getattr(f, "narrative_edited", False)),
            )
        )

    # Ringkasan hanya bisa dinyatakan basi bila ia memang ada DAN jumlah temuan
    # saat pembuatannya tercatat. Ringkasan lama (sebelum kolom pencatat ada)
    # tidak boleh dituduh basi hanya karena angkanya tak diketahui.
    stale_note: str | None = None
    current_count = len(findings)
    if es and summary_finding_count is not None and summary_finding_count != current_count:
        stale_note = (
            f"Ringkasan eksekutif ini disusun saat penugasan memiliki "
            f"{summary_finding_count} temuan; kini terdapat {current_count}. "
            f"Buat ulang ringkasan agar sesuai dengan isi laporan."
        )

    # Periode dicetak sebagai satu kalimat agar kop laporan tetap ringkas.
    ps = getattr(engagement, "period_start", None)
    pe = getattr(engagement, "period_end", None)
    period = f"{ps} — {pe}" if ps and pe else (str(ps) if ps else None)

    return ReportData(
        org_name=org_name,
        report_title=report_title,
        engagement_name=getattr(engagement, "name", ""),
        client_name=getattr(engagement, "client_name", ""),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        posture=(str(es["posture"]) if isinstance(es, dict) and es.get("posture") else None),
        summary_overview=str(es.get("overview", "")).strip() if isinstance(es, dict) else "",
        summary_key_risks=str(es.get("key_risks", "")).strip() if isinstance(es, dict) else "",
        summary_recommendations=(
            str(es.get("recommendations", "")).strip() if isinstance(es, dict) else ""
        ),
        severity_counts={k: v for k, v in sev_counts.items() if v},
        findings=report_findings,
        summary_stale_note=stale_note,
        period=period,
        scope=getattr(engagement, "scope", None),
    )

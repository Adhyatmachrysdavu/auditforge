"""Evaluasi terukur per-penugasan (D17) — deterministik, dapat diuji.

Mengubah temuan sebuah penugasan menjadi metrik yang mengkuantifikasi nilai
AuditForge untuk bab evaluasi KP:

- **Efisiensi dedup**: berapa banyak temuan mentah (lintas perkakas/berkas) yang
  digabung → duplikat yang tak perlu ditulis ulang auditor.
- **Cakupan AI**: porsi temuan yang sudah punya draf naratif AI (penulisan manual
  yang dihindari) + porsi yang disunting auditor (bukti pengawasan manusia).
- **Kemajuan review**: porsi temuan yang sudah diputuskan (disetujui/ditolak/FP).
- Distribusi keparahan / prioritas / status.
"""
from __future__ import annotations

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]
_DECIDED = {"approved", "rejected", "false_positive"}


def _pct(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def evaluate_engagement(findings: list[object]) -> dict[str, object]:
    """Hitung metrik evaluasi dari daftar temuan (duck-typed)."""
    total = len(findings)
    raw = sum(int(getattr(f, "occurrences", 1) or 1) for f in findings)
    duplicates_merged = raw - total

    with_ai = sum(1 for f in findings if getattr(f, "ai_generated", False))
    edited = sum(1 for f in findings if getattr(f, "narrative_edited", False))
    decided = sum(1 for f in findings if getattr(f, "status", "") in _DECIDED)
    approved = sum(1 for f in findings if getattr(f, "status", "") == "approved")

    sev_dist: dict[str, int] = {s: 0 for s in _SEV_ORDER}
    prio_dist: dict[str, int] = {}
    status_dist: dict[str, int] = {}
    tools: set[str] = set()
    for f in findings:
        s = (getattr(f, "severity", "info") or "info").lower()
        sev_dist[s] = sev_dist.get(s, 0) + 1
        p = getattr(f, "priority", None)
        if p:
            prio_dist[f"P{p}"] = prio_dist.get(f"P{p}", 0) + 1
        st = getattr(f, "status", "") or "draft"
        status_dist[st] = status_dist.get(st, 0) + 1
        for src in getattr(f, "sources", None) or []:
            if isinstance(src, dict) and src.get("tool"):
                tools.add(str(src["tool"]))

    return {
        "total_findings": total,
        "raw_findings": raw,
        "duplicates_merged": duplicates_merged,
        "dedup_reduction": _pct(duplicates_merged, raw),
        "ai_drafts": with_ai,
        "ai_coverage": _pct(with_ai, total),
        "edited_by_auditor": edited,
        # Pembagi = total temuan (bukan draf AI): auditor bisa menulis naratif
        # manual tanpa draf AI (D13), jadi with_ai bisa 0 padahal ada suntingan.
        "edited_ratio": _pct(edited, total),
        "decided": decided,
        "approved": approved,
        "review_progress": _pct(decided, total),
        "tools_used": sorted(tools),
        "severity_distribution": {k: v for k, v in sev_dist.items() if v},
        "priority_distribution": prio_dist,
        "status_distribution": status_dist,
    }

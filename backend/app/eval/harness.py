"""Orkestrasi eval harness (D12).

Menjalankan pipeline deterministik NYATA (fungsi produksi yang sama) atas golden
set berlabel, lalu menghitung metrik. Tak memanggil LLM — aman dijalankan di CI
tanpa jaringan/kredensial. Naratif dievaluasi opsional (butuh draf kandidat).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.enrichment import enrich
from app.eval.metrics import PRF, cluster_prf, narrative_score
from app.models.enums import ScanTool, Severity
from app.normalize import compute_fingerprint
from app.parsers.base import UnifiedFinding

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval_data"

# Ambang lulus (gating). Golden set dirancang lolos pada 1.0; ambang memberi
# ruang bila golden diperluas nanti.
DEDUP_F1_MIN = 0.90
ENRICH_ACC_MIN = 0.95


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))
    return data


def _to_tool(v: str | None) -> ScanTool:
    try:
        return ScanTool(v) if v else ScanTool.unknown
    except ValueError:
        return ScanTool.unknown


def _to_sev(v: str | None) -> Severity:
    try:
        return Severity(v) if v else Severity.info
    except ValueError:
        return Severity.info


def run_dedup_eval(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Presisi dedup: bangun temuan, enrich (backfill CWE), fingerprint, kelompokkan.

    Mereplikasi urutan worker: pengayaan sebelum sidik jari agar CWE hasil
    backfill ikut menyatukan temuan lintas-perkakas.
    """
    data = data or _load("dedup_cases.json")
    cases = data["cases"]
    gold = [c["gold_cluster"] for c in cases]
    pred: list[str] = []
    for c in cases:
        uf = UnifiedFinding(
            title=c["title"],
            description=c.get("description"),
            severity=_to_sev(c.get("severity")),
            tool=_to_tool(c.get("tool")),
            target=c.get("target"),
            cwe=c.get("cwe"),
            cvss_score=c.get("cvss_score"),
            references=c.get("references", []),
        )
        e = enrich(
            title=uf.title,
            description=uf.description,
            references=uf.references,
            cwe=uf.cwe,
            cvss_score=uf.cvss_score,
        )
        if e.cwe:
            uf.cwe = e.cwe
        pred.append(compute_fingerprint(uf))

    prf: PRF = cluster_prf(gold, pred)
    return {
        "n": len(cases),
        "gold_clusters": len(set(gold)),
        "pred_clusters": len(set(pred)),
        "precision": prf.precision,
        "recall": prf.recall,
        "f1": prf.f1,
        "tp": prf.tp,
        "fp": prf.fp,
        "fn": prf.fn,
        "passed": prf.f1 >= DEDUP_F1_MIN,
    }


def run_enrichment_eval(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Akurasi pengayaan per-field (cwe/owasp/score/severity) atas golden set."""
    data = data or _load("enrichment_cases.json")
    cases = data["cases"]
    checks = 0
    correct = 0
    failures: list[dict[str, Any]] = []
    for c in cases:
        e = enrich(
            title=c.get("title"),
            description=c.get("description"),
            references=c.get("references", []),
            cwe=c.get("cwe"),
            cvss_score=c.get("cvss_score"),
        )
        got = {
            "expected_cwe": e.cwe,
            "expected_owasp": e.owasp,
            "expected_score": e.cvss_score,
            "expected_severity": e.severity.value if e.severity else None,
        }
        for key, want in c.items():
            if key not in got:
                continue
            checks += 1
            actual = got[key]
            ok = (
                abs(actual - want) < 0.1
                if key == "expected_score"
                and isinstance(actual, (int, float))
                and isinstance(want, (int, float))
                else actual == want
            )
            if ok:
                correct += 1
            else:
                failures.append(
                    {"case": c.get("name"), "field": key, "want": want, "got": actual}
                )
    accuracy = round(correct / checks, 4) if checks else 1.0
    return {
        "cases": len(cases),
        "checks": checks,
        "correct": correct,
        "accuracy": accuracy,
        "failures": failures,
        "passed": accuracy >= ENRICH_ACC_MIN,
    }


def run_narrative_eval(
    candidates: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Skor naratif AI vs rujukan auditor (§6.4).

    `candidates`: peta indeks-kasus → draf {description,impact,recommendation}
    (mis. hasil `generate_narrative`). Tanpa kandidat → status menunggu (skip),
    karena penilaian butuh draf AI dan/atau golden auditor yang lengkap.
    """
    data = _load("narrative_golden.json")
    cases = data["cases"]
    if not candidates:
        return {
            "status": "skipped",
            "reason": "belum ada draf kandidat / golden auditor (lihat §6.4)",
            "golden_cases": len(cases),
        }
    scored: list[dict[str, Any]] = []
    for idx, cand in candidates.items():
        if idx < 0 or idx >= len(cases):
            continue
        s = narrative_score(cand, cases[idx]["reference"])
        scored.append({"index": idx, **s})
    mean_overlap = (
        round(sum(s["overlap"] for s in scored) / len(scored), 4) if scored else 0.0
    )
    return {"status": "scored", "scored": scored, "mean_overlap": mean_overlap}


def evaluate() -> dict[str, Any]:
    """Jalankan seluruh evaluasi deterministik → laporan ringkas + status lulus."""
    dedup = run_dedup_eval()
    enrich_r = run_enrichment_eval()
    narrative = run_narrative_eval()
    passed = bool(dedup["passed"] and enrich_r["passed"])
    return {
        "dedup": dedup,
        "enrichment": enrich_r,
        "narrative": narrative,
        "passed": passed,
    }

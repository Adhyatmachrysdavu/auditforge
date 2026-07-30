"""Uji unit D12 — metrik eval + harness atas golden set nyata (tanpa LLM)."""
from __future__ import annotations

from app.eval.harness import (
    DEDUP_F1_MIN,
    ENRICH_ACC_MIN,
    evaluate,
    run_dedup_eval,
    run_enrichment_eval,
    run_narrative_eval,
)
from app.eval.metrics import cluster_prf, jaccard, narrative_score


# ---------------- metrik pairwise ----------------
def test_prf_perfect_grouping():
    prf = cluster_prf(["a", "a", "b"], ["x", "x", "y"])
    assert prf.precision == 1.0 and prf.recall == 1.0 and prf.f1 == 1.0


def test_prf_over_merge_lowers_precision():
    # gold: {0,1} & {2}; pred menggabung semua → 1 FP pasangan (0,2)&(1,2)
    prf = cluster_prf(["a", "a", "b"], ["x", "x", "x"])
    assert prf.fp == 2 and prf.fn == 0
    assert prf.recall == 1.0 and prf.precision < 1.0


def test_prf_under_merge_lowers_recall():
    # gold menggabung {0,1}; pred memisah → 1 FN pasangan
    prf = cluster_prf(["a", "a"], ["x", "y"])
    assert prf.fn == 1 and prf.fp == 0
    assert prf.precision == 1.0 and prf.recall == 0.0


def test_prf_all_unique_is_one():
    prf = cluster_prf(["a", "b", "c"], ["x", "y", "z"])
    assert prf.precision == 1.0 and prf.recall == 1.0


# ---------------- naratif ----------------
def test_jaccard_identical_and_disjoint():
    assert jaccard("sql injection here", "sql injection here") == 1.0
    assert jaccard("alpha beta", "gamma delta") == 0.0


def test_narrative_score_structure_and_overlap():
    cand = {"description": "reflected xss in search", "impact": "", "recommendation": "encode output"}
    ref = {"description": "reflected xss in search", "impact": "steal session", "recommendation": "encode output"}
    s = narrative_score(cand, ref)
    assert s["per_field"]["description"] == 1.0
    assert s["per_field"]["recommendation"] == 1.0
    assert s["structure"] == round(2 / 3, 4)  # impact kosong


# ---------------- harness atas golden nyata ----------------
def test_dedup_eval_golden_is_perfect():
    r = run_dedup_eval()
    # 8 temuan mentah → 5 kelompok emas; pipeline harus mencocokkan tepat.
    assert r["gold_clusters"] == 5
    assert r["pred_clusters"] == 5
    assert r["f1"] == 1.0 and r["fp"] == 0 and r["fn"] == 0
    assert r["passed"] and r["f1"] >= DEDUP_F1_MIN


def test_enrichment_eval_golden_is_accurate():
    r = run_enrichment_eval()
    assert r["failures"] == []
    assert r["accuracy"] == 1.0 and r["accuracy"] >= ENRICH_ACC_MIN
    assert r["passed"]


def test_narrative_eval_skips_without_candidates():
    r = run_narrative_eval()
    assert r["status"] == "skipped" and r["golden_cases"] >= 2


def test_narrative_eval_scores_candidate():
    # Kandidat = salinan rujukan kasus 0 → overlap sempurna.
    from app.eval.harness import _load

    ref0 = _load("narrative_golden.json")["cases"][0]["reference"]
    r = run_narrative_eval({0: dict(ref0)})
    assert r["status"] == "scored" and r["mean_overlap"] == 1.0


def test_evaluate_overall_passes():
    rep = evaluate()
    assert rep["passed"] is True
    assert rep["dedup"]["passed"] and rep["enrichment"]["passed"]

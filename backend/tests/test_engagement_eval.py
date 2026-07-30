"""Uji unit D17 — metrik evaluasi per-penugasan (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.eval.engagement_eval import evaluate_engagement


def _f(**kw):
    base = dict(
        severity="info", status="draft", priority=None, occurrences=1,
        ai_generated=False, narrative_edited=False, sources=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_dedup_reduction():
    # 3 temuan unik, occurrences 3+1+1 = 5 mentah → 2 duplikat digabung → 40%.
    fs = [_f(occurrences=3), _f(occurrences=1), _f(occurrences=1)]
    m = evaluate_engagement(fs)
    assert m["total_findings"] == 3
    assert m["raw_findings"] == 5
    assert m["duplicates_merged"] == 2
    assert m["dedup_reduction"] == 0.4


def test_ai_coverage_and_edit_ratio():
    fs = [
        _f(ai_generated=True, narrative_edited=True),
        _f(ai_generated=True, narrative_edited=False),
        _f(ai_generated=False),
    ]
    m = evaluate_engagement(fs)
    assert m["ai_drafts"] == 2
    assert m["ai_coverage"] == round(2 / 3, 4)
    assert m["edited_by_auditor"] == 1
    assert m["edited_ratio"] == round(1 / 3, 4)  # 1 dari 3 temuan disunting auditor


def test_edited_without_ai_draft_no_divzero():
    # Regresi: auditor menulis naratif manual tanpa draf AI (with_ai=0).
    # Dulu edited/with_ai → "2/0" & 0%; kini edited/total terdefinisi.
    fs = [
        _f(ai_generated=False, narrative_edited=True),
        _f(ai_generated=False, narrative_edited=True),
        _f(ai_generated=False),
    ]
    m = evaluate_engagement(fs)
    assert m["ai_drafts"] == 0
    assert m["edited_by_auditor"] == 2
    assert m["edited_ratio"] == round(2 / 3, 4)


def test_review_progress_and_distributions():
    fs = [
        _f(status="approved", severity="critical", priority=1),
        _f(status="rejected", severity="high", priority=2),
        _f(status="draft", severity="low", priority=4),
    ]
    m = evaluate_engagement(fs)
    assert m["decided"] == 2 and m["approved"] == 1
    assert m["review_progress"] == round(2 / 3, 4)
    assert m["severity_distribution"] == {"critical": 1, "high": 1, "low": 1}
    assert m["priority_distribution"] == {"P1": 1, "P2": 1, "P4": 1}
    assert m["status_distribution"] == {"approved": 1, "rejected": 1, "draft": 1}


def test_tools_used_from_sources():
    fs = [
        _f(sources=[{"tool": "nuclei"}, {"tool": "zap"}]),
        _f(sources=[{"tool": "zap"}]),
    ]
    m = evaluate_engagement(fs)
    assert m["tools_used"] == ["nuclei", "zap"]


def test_empty_engagement():
    m = evaluate_engagement([])
    assert m["total_findings"] == 0
    assert m["dedup_reduction"] == 0.0
    assert m["ai_coverage"] == 0.0

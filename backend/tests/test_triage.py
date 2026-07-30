"""Uji unit D11 — triase deterministik (tanpa LLM)."""
from __future__ import annotations

from app.triage import priority_score, rank_for_score, triage


def test_critical_is_p1():
    t = triage("critical")
    assert t.priority == 1 and t.rank == "P1"


def test_high_is_p2():
    assert triage("high").priority == 2


def test_medium_is_p3():
    assert triage("medium").priority == 3


def test_low_and_info_are_p4():
    assert triage("low").priority == 4
    assert triage("info").priority == 4


def test_cvss_escalates_high_to_p1():
    # high (70) + cvss 8.0 (24) = 94 → P1
    t = triage("high", cvss_score=8.0)
    assert t.priority == 1
    assert "cvss:high" in t.reasons


def test_cve_and_recurrence_escalate_medium():
    # medium (40) + cve (15) + 3× (8) + cvss7 (21) = 84 → P2 (naik dari P3)
    t = triage("medium", cvss_score=7.0, occurrences=3, cve=["CVE-2021-1"])
    assert t.priority <= 2
    assert any(r.startswith("cve:") for r in t.reasons)
    assert any(r.startswith("recurrence:") for r in t.reasons)


def test_recurrence_bonus_capped():
    # Bonus kemunculan dibatasi +20 (min(occ-1,5)*4).
    s_big, _ = priority_score("info", occurrences=100)
    s_cap, _ = priority_score("info", occurrences=6)
    assert s_big == s_cap


def test_unknown_severity_defaults_low():
    t = triage("tidak-dikenal")
    assert t.priority == 4
    assert t.reasons[0] == "severity:tidak-dikenal"


def test_rank_boundaries():
    assert rank_for_score(90.0) == 1
    assert rank_for_score(89.9) == 2
    assert rank_for_score(60.0) == 2
    assert rank_for_score(30.0) == 3
    assert rank_for_score(29.9) == 4


def test_score_is_rounded():
    t = triage("high", cvss_score=7.3)
    assert t.score == round(t.score, 1)

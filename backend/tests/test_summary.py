"""Uji unit D11 — agregasi ringkasan eksekutif + postur (LLM di-stub)."""
from __future__ import annotations

import app.ai.summary as summary
from app.ai.summary import (
    SummaryFinding,
    build_summary_payload,
    generate_executive_summary,
    posture,
)


def _f(title, severity, **kw):
    return SummaryFinding(title=title, severity=severity, **kw)


def test_posture_empty_is_clean():
    assert posture([]) == "clean"


def test_posture_critical_wins():
    fs = [_f("a", "low"), _f("b", "critical")]
    assert posture(fs) == "critical"


def test_posture_priority_one_is_critical():
    assert posture([_f("a", "high", priority=1)]) == "critical"


def test_posture_elevated_and_moderate():
    assert posture([_f("a", "high")]) == "elevated"
    assert posture([_f("a", "medium"), _f("b", "low")]) == "moderate"
    assert posture([_f("a", "low"), _f("b", "info")]) == "low"


def test_payload_contains_aggregates():
    fs = [
        _f("SQLi", "critical", priority=1, cvss_score=9.8, owasp="A03:2021 – Injection",
           cve=["CVE-2021-1"]),
        _f("XSS", "high", priority=2, cvss_score=7.1, owasp="A03:2021 – Injection"),
        _f("Info leak", "low", priority=4),
    ]
    p = build_summary_payload(
        engagement_name="Pentest Q3", client_name="ACME", findings=fs
    )
    assert "Pentest Q3" in p
    assert "ACME" in p
    assert "Total temuan (setelah dedup): 3" in p
    assert "critical=1" in p and "high=1" in p and "low=1" in p
    assert "P1=1" in p and "P2=1" in p
    assert "Temuan dengan CVE publik: 1" in p
    assert "A03:2021 – Injection" in p
    # Temuan prioritas teratas terurut P1 dulu.
    top_idx = p.index("Temuan prioritas teratas:")
    assert p.index("SQLi") > top_idx
    assert p.index("SQLi") < p.index("Info leak")


def test_top_n_limits_list():
    fs = [_f(f"t{i}", "medium", priority=3) for i in range(10)]
    p = build_summary_payload(
        engagement_name="E", client_name="C", findings=fs, top_n=4
    )
    assert p.count("- [P3 ") == 4


def test_generate_executive_summary_stub(monkeypatch):
    monkeypatch.setattr(
        summary.llm, "draft",
        lambda *a, **k: '{"overview":"o","key_risks":"k","recommendations":"r"}',
    )

    class P:
        model = "stub-model"

    monkeypatch.setattr(summary, "get_provider", lambda: P())
    es = generate_executive_summary("payload apa saja", posture_code="elevated")
    assert es.overview == "o" and es.key_risks == "k" and es.recommendations == "r"
    assert es.posture == "elevated"
    assert es.model == "stub-model"
    assert es.prompt_version == "summary-v1"
    assert es.as_dict()["overview"] == "o"

"""Uji unit D15 — perakitan data laporan + render DOCX (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.reporting.docx_writer import render_docx
from app.reporting.report_data import build_report_data


def _f(**kw):
    base = dict(
        title="T", severity="info", status="approved", priority=4, cwe=None, owasp=None,
        cvss_score=None, cve=[], sources=[], occurrences=1, ai_draft=None,
        final_narrative=None, narrative_edited=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _eng():
    return SimpleNamespace(name="Pentest Q3", client_name="ACME")


def test_include_approved_only():
    fs = [
        _f(title="A", status="approved", severity="critical", priority=1),
        _f(title="B", status="draft", severity="high", priority=2),
        _f(title="C", status="rejected", severity="high", priority=2),
    ]
    d = build_report_data(_eng(), fs, org_name="Org", report_title="Judul")
    assert [f.title for f in d.findings] == ["A"]
    assert d.total == 1


def test_include_all():
    fs = [_f(title="A", status="approved"), _f(title="B", status="draft")]
    d = build_report_data(_eng(), fs, org_name="O", report_title="J", include="all")
    assert d.total == 2


def test_sort_by_priority_then_severity():
    fs = [
        _f(title="low", status="approved", severity="low", priority=4),
        _f(title="crit", status="approved", severity="critical", priority=1),
        _f(title="high", status="approved", severity="high", priority=2),
    ]
    d = build_report_data(_eng(), fs, org_name="O", report_title="J")
    assert [f.title for f in d.findings] == ["crit", "high", "low"]


def test_final_narrative_wins_over_ai_draft():
    f = _f(
        status="approved",
        ai_draft={"description": "ai", "impact": "ai", "recommendation": "ai"},
        final_narrative={"description": "human", "impact": "h", "recommendation": "r"},
        narrative_edited=True,
    )
    d = build_report_data(_eng(), [f], org_name="O", report_title="J")
    assert d.findings[0].description == "human"
    assert d.findings[0].edited is True


def test_ai_draft_used_when_no_final():
    f = _f(status="approved", ai_draft={"description": "ai", "impact": "", "recommendation": ""})
    d = build_report_data(_eng(), [f], org_name="O", report_title="J")
    assert d.findings[0].description == "ai"


def test_severity_counts_and_exec_summary():
    fs = [
        _f(status="approved", severity="critical"),
        _f(status="approved", severity="low"),
    ]
    es = {"overview": "o", "key_risks": "k", "recommendations": "r", "posture": "critical"}
    d = build_report_data(_eng(), fs, org_name="O", report_title="J", exec_summary=es)
    assert d.severity_counts == {"critical": 1, "low": 1}
    assert d.posture == "critical" and d.summary_overview == "o"


def test_render_docx_returns_valid_zip():
    fs = [_f(title="X", status="approved", severity="high", priority=2,
             ai_draft={"description": "d", "impact": "i", "recommendation": "r"})]
    d = build_report_data(_eng(), fs, org_name="Org", report_title="Judul")
    blob = render_docx(d, accent="#1E5F9F", lang="id")
    assert isinstance(blob, bytes) and len(blob) > 1000
    assert blob[:2] == b"PK"  # DOCX = arsip ZIP


def test_render_docx_english_and_empty():
    d = build_report_data(_eng(), [], org_name="Org", report_title="Report")
    blob = render_docx(d, lang="en")
    assert blob[:2] == b"PK"


def test_render_html_contains_charts_and_findings():
    from app.reporting.html_writer import render_html

    fs = [_f(title="XSS", status="approved", severity="high", priority=2,
             ai_draft={"description": "d", "impact": "i", "recommendation": "r"})]
    d = build_report_data(_eng(), fs, org_name="Org", report_title="Judul")
    html = render_html(d, accent="#1E5F9F", lang="id")
    assert "<!doctype html>" in html.lower()
    assert "<svg" in html  # grafik tersemat
    assert "XSS" in html and "Judul" in html
    assert "Matriks Risiko" in html  # label ID

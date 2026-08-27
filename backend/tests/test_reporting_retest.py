"""Uji unit R4 — kolom remediasi pada laporan (tanpa DB, tanpa LLM)."""
from __future__ import annotations

from types import SimpleNamespace

from app.reporting.report_data import build_report_data


def _temuan(**kw):
    dasar = dict(
        id=1, title="Log4Shell", severity="critical", status="approved", priority=1,
        cwe="CWE-502", owasp=None, cvss_score=9.8, cve=[], sources=[],
        occurrences=1, ai_draft=None, final_narrative=None, narrative_edited=False,
        rounds_seen=[1], remediation_status=None, remediation_confirmed_round=None,
    )
    dasar.update(kw)
    return SimpleNamespace(**dasar)


def _eng():
    return SimpleNamespace(
        name="Audit Contoh", client_name="PT Contoh", scope=None,
        period_start=None, period_end=None,
    )


def test_putaran_satu_tidak_memunculkan_kolom_remediasi():
    data = build_report_data(
        _eng(), [_temuan()], org_name="X", report_title="Y", current_round=1
    )
    assert data.current_round == 1
    assert data.findings[0].remediation is None


def test_status_yang_ditegaskan_tercetak():
    f = _temuan(remediation_status="fixed", remediation_confirmed_round=2)
    data = build_report_data(
        _eng(), [f], org_name="X", report_title="Y", current_round=2
    )
    assert data.findings[0].remediation == "fixed"
    assert data.remediation_counts["fixed"] == 1


def test_usulan_tidak_pernah_tercetak():
    # rounds_seen [1] pada putaran 2 berarti usulan "fixed", tetapi belum
    # ditegaskan siapa pun — laporan tak boleh menyebutnya tertutup.
    data = build_report_data(
        _eng(), [_temuan()], org_name="X", report_title="Y", current_round=2
    )
    assert data.findings[0].remediation is None
    assert data.remediation_counts["fixed"] == 0


def test_penegasan_kedaluwarsa_tidak_tercetak():
    f = _temuan(rounds_seen=[1, 3], remediation_status="fixed",
                remediation_confirmed_round=2)
    data = build_report_data(
        _eng(), [f], org_name="X", report_title="Y", current_round=3
    )
    assert data.findings[0].remediation is None

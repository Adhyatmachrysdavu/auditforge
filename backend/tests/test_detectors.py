"""Uji unit D17 — pustaka deteksi kerentanan deterministik berbasis plugin.

Murni (tanpa DB/infra/AI): `pytest tests/test_detectors.py`.
"""
from __future__ import annotations

from app.detectors import run_detectors
from app.detectors.csrf import CsrfDetector
from app.detectors.lfi import LfiDetector
from app.detectors.sqli import SqliDetector


def test_sqli_detects_mysql_error():
    m = SqliDetector().detect("Response: You have an error in your SQL syntax near '1")
    assert m is not None
    assert m.cwe == "CWE-89"


def test_sqli_no_match_on_clean_text():
    assert SqliDetector().detect("Reflected XSS on the search parameter.") is None


def test_lfi_detects_path_traversal():
    m = LfiDetector().detect("GET /download?file=../../../../etc/passwd")
    assert m is not None
    assert m.cwe == "CWE-22"


def test_lfi_detects_php_wrapper():
    assert LfiDetector().detect("param=php://filter/convert.base64-encode/resource=index").cwe == "CWE-22"


def test_csrf_matches_real_zap_alert_wording():
    # Cuplikan asli dari datasets/fixtures/zap-sample.json.
    m = CsrfDetector().detect("Absence of Anti-CSRF Tokens")
    assert m is not None
    assert m.cwe == "CWE-352"


def test_csrf_no_match_on_unrelated_text():
    assert CsrfDetector().detect("Directory listing is enabled on /uploads/") is None


def test_registry_runs_all_and_aggregates():
    matches = run_detectors(
        "Login form vulnerable", "Absence of Anti-CSRF Tokens; also ../../etc/passwd works"
    )
    ids = {m.detector_id for m in matches}
    assert ids == {"CSRF", "LFI"}


def test_registry_empty_text_returns_empty():
    assert run_detectors(None, "", None) == []


def test_registry_one_broken_detector_does_not_block_others(monkeypatch):
    def boom(self, text):  # noqa: ARG001
        raise RuntimeError("regex meledak")

    monkeypatch.setattr(SqliDetector, "detect", boom)
    matches = run_detectors("Absence of Anti-CSRF Tokens")
    assert {m.detector_id for m in matches} == {"CSRF"}

"""Uji unit D7 — normalisasi severity, fingerprint, dan deduplikasi.

Murni (tanpa DB/infra): `pytest tests/test_normalize.py`.
"""
from __future__ import annotations

from app.models.enums import ScanTool, Severity
from app.normalize import (
    compute_fingerprint,
    dedupe_findings,
    max_severity,
    severity_rank,
)
from app.parsers.base import UnifiedFinding


def uf(**kw) -> UnifiedFinding:
    base = {"title": "Cross-Site Scripting", "target": "https://app.local/search"}
    base.update(kw)
    return UnifiedFinding(**base)


# ---------- normalisasi severity ----------

def test_severity_order_monotonic():
    ranks = [severity_rank(s) for s in ("info", "low", "medium", "high", "critical")]
    assert ranks == sorted(ranks)
    assert ranks == [0, 1, 2, 3, 4]


def test_severity_rank_case_insensitive_and_unknown():
    assert severity_rank("CRITICAL") == severity_rank(Severity.critical)
    assert severity_rank("bogus") == 0  # tak dikenal → info


def test_max_severity_picks_worse():
    assert max_severity("low", "high") == "high"
    assert max_severity(Severity.critical, "medium") == "critical"
    assert max_severity("info", "info") == "info"


# ---------- fingerprint ----------

def test_fingerprint_stable():
    assert compute_fingerprint(uf()) == compute_fingerprint(uf())


def test_same_cwe_and_target_across_tools_collide():
    # Judul & perkakas beda, tapi CWE + target sama → satu isu (dedup lintas-perkakas).
    a = uf(title="XSS in search parameter", tool=ScanTool.zap, cwe="CWE-79")
    b = uf(title="Reflected Cross Site Scripting", tool=ScanTool.burp, cwe="79")
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_target_normalization_ignores_scheme_and_trailing_slash():
    a = uf(target="https://app.local/search/", cwe="CWE-79")
    b = uf(target="http://app.local/search", cwe="CWE-79")
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_different_target_differs():
    a = uf(target="https://app.local/search", cwe="CWE-79")
    b = uf(target="https://app.local/login", cwe="CWE-79")
    assert compute_fingerprint(a) != compute_fingerprint(b)


def test_no_cwe_falls_back_to_title():
    a = uf(title="Directory Listing", target="https://app.local/backup", cwe=None)
    b = uf(title="directory   listing", target="https://app.local/backup", cwe=None)
    assert compute_fingerprint(a) == compute_fingerprint(b)


# ---------- deduplikasi ----------

def test_dedupe_merges_and_keeps_max_severity():
    findings = [
        uf(tool=ScanTool.zap, cwe="CWE-79", severity=Severity.medium, cvss_score=6.1),
        uf(tool=ScanTool.burp, cwe="CWE-79", severity=Severity.high, cvss_score=7.4,
           title="Reflected XSS"),
        uf(tool=ScanTool.nuclei, cwe="CWE-89", severity=Severity.critical,
           target="https://app.local/item", title="SQL Injection"),
    ]
    result = dedupe_findings(findings)
    assert len(result) == 2  # dua XSS tergabung, SQLi terpisah

    xss = next(r for r in result if r.cwe and "79" in r.cwe)
    assert xss.severity == "high"          # tertinggi menang
    assert xss.cvss_score == 7.4           # cvss tertinggi menang
    assert xss.occurrences == 2
    assert {s["tool"] for s in xss.sources} == {"zap", "burp"}


def test_dedupe_preserves_first_seen_order():
    findings = [
        uf(cwe="CWE-89", target="https://app.local/a", title="SQLi"),
        uf(cwe="CWE-79", target="https://app.local/b", title="XSS"),
    ]
    result = dedupe_findings(findings)
    assert [r.cwe for r in result] == ["CWE-89", "CWE-79"]

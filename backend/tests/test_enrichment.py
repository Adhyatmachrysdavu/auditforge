"""Uji unit D8 — pengayaan (CWE→OWASP, CVSS v3.1, penautan CVE).

Murni (tanpa DB/infra): `pytest tests/test_enrichment.py`.
"""
from __future__ import annotations

from app.enrichment import (
    enrich,
    extract_cves,
    find_cvss_vector,
    owasp_for_cwe,
    score_from_vector,
    severity_from_cvss,
)
from app.models.enums import Severity


# ---------- CWE → OWASP ----------

def test_owasp_injection():
    assert owasp_for_cwe("CWE-79").startswith("A03")   # XSS → Injection
    assert owasp_for_cwe("89").startswith("A03")        # SQLi (tanpa prefix)


def test_owasp_various_categories():
    assert owasp_for_cwe("CWE-200").startswith("A01")   # info exposure
    assert owasp_for_cwe("CWE-327").startswith("A02")   # crypto
    assert owasp_for_cwe("CWE-502").startswith("A08")   # deserialization
    assert owasp_for_cwe("CWE-918").startswith("A10")   # SSRF


def test_owasp_unknown_returns_none():
    assert owasp_for_cwe(None) is None
    assert owasp_for_cwe("CWE-99999") is None


# ---------- CVSS v3.1 band ----------

def test_severity_bands():
    assert severity_from_cvss(0.0) == Severity.info
    assert severity_from_cvss(3.9) == Severity.low
    assert severity_from_cvss(4.0) == Severity.medium
    assert severity_from_cvss(7.0) == Severity.high
    assert severity_from_cvss(9.8) == Severity.critical
    assert severity_from_cvss(None) is None


def test_score_from_vector():
    v = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
    assert score_from_vector(v) == 10.0
    assert score_from_vector("bukan vektor") is None
    assert score_from_vector(None) is None


def test_find_vector_in_text():
    txt = "Detail: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N end"
    assert find_cvss_vector(txt).startswith("CVSS:3.1/")


# ---------- CVE ----------

def test_extract_cves_dedup_and_upper():
    cves = extract_cves("cve-2021-44228 dan CVE-2021-44228", "juga CVE-2014-0160")
    assert cves == ["CVE-2021-44228", "CVE-2014-0160"]


# ---------- orkestrasi enrich() ----------

def test_enrich_backfills_from_known_cve():
    # Temuan tanpa CWE/CVSS, tapi menyebut Log4Shell → backfill dari basis CVE.
    e = enrich(
        title="Apache Log4j2 RCE",
        description="Terkait CVE-2021-44228 pada endpoint login.",
        references=["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
        cwe=None,
        cvss_score=None,
    )
    assert e.cves == ["CVE-2021-44228"]
    assert e.cwe == "CWE-502"
    assert e.cvss_score == 10.0
    assert e.severity == Severity.critical
    assert e.owasp.startswith("A08")
    assert e.cvss_vector.startswith("CVSS:3.1/")


def test_enrich_keeps_tool_score_and_maps_owasp():
    # Perkakas sudah beri skor; enrich menghormatinya + petakan OWASP dari CWE.
    e = enrich(title="Reflected XSS", cwe="CWE-79", cvss_score=6.1)
    assert e.cvss_score == 6.1
    assert e.severity == Severity.medium
    assert e.owasp.startswith("A03")
    assert e.cves == []


def test_enrich_computes_score_from_vector_in_references():
    e = enrich(
        title="Some issue",
        references=["Vector CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"],
        cwe="CWE-89",
    )
    assert e.cvss_score == 10.0
    assert e.severity == Severity.critical

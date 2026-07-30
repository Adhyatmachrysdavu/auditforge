"""Uji unit D10 — parsing naratif tahan-banting + build_payload (LLM di-stub)."""
from __future__ import annotations

import app.ai.narrative as narrative
from app.ai.narrative import _parse, build_payload, generate_narrative


def test_parse_clean_json():
    r = _parse('{"description": "d", "impact": "i", "recommendation": "r"}')
    assert r == {"description": "d", "impact": "i", "recommendation": "r"}


def test_parse_json_in_code_fence():
    reply = '```json\n{"description":"d","impact":"i","recommendation":"r"}\n```'
    assert _parse(reply)["description"] == "d"


def test_parse_json_embedded_in_prose():
    reply = (
        'Tentu, ini hasilnya:\n'
        '{"description":"d","impact":"i","recommendation":"r"} Semoga membantu.'
    )
    r = _parse(reply)
    assert r["impact"] == "i"
    assert r["recommendation"] == "r"


def test_parse_fallback_non_json():
    reply = "Ini bukan JSON sama sekali."
    r = _parse(reply)
    assert r["description"] == reply
    assert r["impact"] == ""
    assert r["recommendation"] == ""


def test_build_payload_includes_fields():
    p = build_payload(
        title="XSS", severity="high", cwe="CWE-79",
        owasp="A03:2021 – Injection", cvss_score=7.4, cve=["CVE-2020-1"],
    )
    assert "Judul: XSS" in p
    assert "Keparahan: high" in p
    assert "CWE-79" in p
    assert "A03" in p
    assert "7.4" in p
    assert "CVE-2020-1" in p


def test_generate_narrative_uses_llm_and_provider_model(monkeypatch):
    monkeypatch.setattr(
        narrative.llm, "draft",
        lambda *a, **k: '{"description":"d","impact":"i","recommendation":"r"}',
    )

    class P:
        model = "stub-model"

    monkeypatch.setattr(narrative, "get_provider", lambda: P())
    n = generate_narrative("payload apa saja")
    assert n.description == "d" and n.impact == "i" and n.recommendation == "r"
    assert n.model == "stub-model"
    assert n.prompt_version == "narrative-v1"
    assert n.as_dict() == {"description": "d", "impact": "i", "recommendation": "r"}

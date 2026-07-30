"""Pembuatan naratif temuan berbasis LLM (D10).

`generate_narrative()` menyusun draf {description, impact, recommendation} untuk
sebuah temuan. Masking otomatis ditangani oleh `llm.draft()`. Output di-parse
sebagai JSON secara tahan-banting (model gratis kadang membungkus JSON dengan
teks lain); bila gagal, seluruh balasan dijadikan `description` agar tak hilang.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ai import llm
from app.ai.parsing import extract_json_fields
from app.ai.prompts import NARRATIVE_PROMPT_VERSION, narrative_prompts
from app.ai.providers import get_provider


@dataclass
class FindingNarrative:
    description: str
    impact: str
    recommendation: str
    model: str
    prompt_version: str = NARRATIVE_PROMPT_VERSION

    def as_dict(self) -> dict[str, str]:
        return {
            "description": self.description,
            "impact": self.impact,
            "recommendation": self.recommendation,
        }


def build_payload(
    *,
    title: str,
    severity: str,
    description: str | None = None,
    cwe: str | None = None,
    owasp: str | None = None,
    cvss_score: float | None = None,
    cve: list[str] | None = None,
) -> str:
    """Rangkai konteks temuan menjadi teks ringkas untuk prompt."""
    lines = [f"Judul: {title}", f"Keparahan: {severity}"]
    if cwe:
        lines.append(f"CWE: {cwe}")
    if owasp:
        lines.append(f"OWASP: {owasp}")
    if cvss_score is not None:
        lines.append(f"CVSS: {cvss_score}")
    if cve:
        lines.append("CVE: " + ", ".join(cve))
    if description:
        lines.append(f"Detail: {description}")
    return "\n".join(lines)


def _parse(reply: str) -> dict[str, str]:
    """Ambil {description, impact, recommendation} dari balasan LLM (tahan-banting)."""
    return extract_json_fields(
        reply, ("description", "impact", "recommendation"), fallback_key="description"
    )


def generate_narrative(
    payload: str, *, lang: str = "id", max_tokens: int = 1000
) -> FindingNarrative:
    """Panggil LLM (dengan masking otomatis) → naratif terstruktur."""
    system, user = narrative_prompts(payload, lang=lang)
    reply = llm.draft(user, system=system, max_tokens=max_tokens)
    parts = _parse(reply)
    provider = get_provider()
    return FindingNarrative(
        description=parts["description"],
        impact=parts["impact"],
        recommendation=parts["recommendation"],
        model=provider.model,
    )

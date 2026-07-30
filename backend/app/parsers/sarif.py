"""Parser SARIF 2.1.0 (JSON) — keluaran SAST (Semgrep, CodeQL, dll.)."""
from __future__ import annotations

import json
from typing import Any, ClassVar

from app.models.enums import ScanTool, Severity
from app.parsers.base import BaseParser, UnifiedFinding

_LEVEL = {
    "error": Severity.high,
    "warning": Severity.medium,
    "note": Severity.low,
    "none": Severity.info,
}


def _sev_from_score(score: float | None) -> Severity | None:
    if score is None:
        return None
    if score >= 9.0:
        return Severity.critical
    if score >= 7.0:
        return Severity.high
    if score >= 4.0:
        return Severity.medium
    if score > 0.0:
        return Severity.low
    return Severity.info


def _cwe_from_tags(tags: list[Any]) -> str | None:
    for t in tags:
        s = str(t)
        if s.upper().startswith("CWE-"):
            return s.upper()
    return None


class SarifParser(BaseParser):
    tool: ClassVar[ScanTool] = ScanTool.sarif

    @classmethod
    def sniff(cls, filename: str, content: bytes) -> bool:
        if content.lstrip()[:1] != b"{":
            return False
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return False
        return isinstance(data, dict) and "runs" in data

    def parse(self, content: bytes) -> list[UnifiedFinding]:
        data = json.loads(content)
        findings: list[UnifiedFinding] = []
        for run in data.get("runs", []):
            driver = (run.get("tool") or {}).get("driver") or {}
            rules = {r.get("id"): r for r in driver.get("rules", []) if r.get("id")}
            for res in run.get("results", []):
                findings.append(self._one(res, rules))
        return findings

    @staticmethod
    def _one(res: dict, rules: dict[str, dict]) -> UnifiedFinding:
        rule = rules.get(res.get("ruleId"), {})
        props = rule.get("properties") or {}
        try:
            score = float(props["security-severity"]) if "security-severity" in props else None
        except (TypeError, ValueError):
            score = None
        severity = _sev_from_score(score) or _LEVEL.get(
            str(res.get("level", "warning")).lower(), Severity.medium
        )

        target = None
        locs = res.get("locations") or []
        if locs:
            phys = locs[0].get("physicalLocation") or {}
            uri = (phys.get("artifactLocation") or {}).get("uri")
            line = (phys.get("region") or {}).get("startLine")
            if uri:
                target = f"{uri}:{line}" if line else uri

        title = (
            rule.get("name")
            or (rule.get("shortDescription") or {}).get("text")
            or res.get("ruleId")
            or "Temuan SARIF"
        )
        return UnifiedFinding(
            title=str(title),
            description=(res.get("message") or {}).get("text"),
            severity=severity,
            tool=ScanTool.sarif,
            target=target,
            cwe=_cwe_from_tags(props.get("tags") or []),
            cvss_score=score,
            raw={"ruleId": res.get("ruleId")},
        )

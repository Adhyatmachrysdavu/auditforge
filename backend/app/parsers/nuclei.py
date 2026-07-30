"""Parser keluaran Nuclei (JSONL — satu objek JSON per baris)."""
from __future__ import annotations

import json
from typing import ClassVar

from app.models.enums import ScanTool, Severity
from app.parsers.base import BaseParser, UnifiedFinding
from app.parsers.util import as_list, first, first_json_line, to_float

_SEV = {
    "info": Severity.info,
    "informational": Severity.info,
    "unknown": Severity.info,
    "low": Severity.low,
    "medium": Severity.medium,
    "high": Severity.high,
    "critical": Severity.critical,
}


class NucleiParser(BaseParser):
    tool: ClassVar[ScanTool] = ScanTool.nuclei

    @classmethod
    def sniff(cls, filename: str, content: bytes) -> bool:
        if filename.lower().endswith(".jsonl"):
            return True
        line = first_json_line(content)
        return bool(
            line
            and ("template-id" in line or "templateID" in line or "template_id" in line)
            and "info" in line
        )

    def parse(self, content: bytes) -> list[UnifiedFinding]:
        findings: list[UnifiedFinding] = []
        for raw in content.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            findings.append(self._one(rec))
        return findings

    def _one(self, rec: dict) -> UnifiedFinding:
        info = rec.get("info") or {}
        classification = info.get("classification") or {}
        return UnifiedFinding(
            title=info.get("name")
            or rec.get("template-id")
            or rec.get("templateID")
            or "Temuan Nuclei",
            description=info.get("description"),
            severity=_SEV.get(str(info.get("severity", "info")).lower(), Severity.info),
            tool=ScanTool.nuclei,
            target=rec.get("matched-at") or rec.get("host") or rec.get("url"),
            cwe=first(classification.get("cwe-id")),
            cvss_score=to_float(classification.get("cvss-score")),
            references=as_list(info.get("reference")),
            raw=rec,
        )

"""Parser keluaran Burp Suite (XML export)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import ClassVar

from app.models.enums import ScanTool, Severity
from app.parsers.base import BaseParser, UnifiedFinding
from app.parsers.util import strip_html

_SEV = {
    "information": Severity.info,
    "informational": Severity.info,
    "info": Severity.info,
    "low": Severity.low,
    "medium": Severity.medium,
    "high": Severity.high,
}
_CWE_RE = re.compile(r"CWE-\d+", re.IGNORECASE)


class BurpParser(BaseParser):
    tool: ClassVar[ScanTool] = ScanTool.burp

    @classmethod
    def sniff(cls, filename: str, content: bytes) -> bool:
        head = content[:4096]
        return b"burpVersion" in head or (b"<issues" in head and b"<issue" in head)

    def parse(self, content: bytes) -> list[UnifiedFinding]:
        root = ET.fromstring(content)
        findings: list[UnifiedFinding] = []
        for issue in root.iter("issue"):

            def txt(tag: str) -> str | None:
                el = issue.find(tag)
                return el.text if el is not None else None

            host = txt("host") or ""
            path = txt("path") or ""
            classif = txt("vulnerabilityClassifications") or ""
            cwe_match = _CWE_RE.search(classif)
            desc = strip_html(txt("issueDetail")) or strip_html(txt("issueBackground"))
            findings.append(
                UnifiedFinding(
                    title=txt("name") or "Temuan Burp",
                    description=desc,
                    severity=_SEV.get(
                        str(txt("severity") or "").strip().lower(), Severity.info
                    ),
                    tool=ScanTool.burp,
                    target=(host + path) or None,
                    cwe=cwe_match.group(0).upper() if cwe_match else None,
                    raw={"name": txt("name"), "severity": txt("severity")},
                )
            )
        return findings

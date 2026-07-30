"""Parser keluaran OWASP ZAP (JSON atau XML)."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import ClassVar

from app.models.enums import ScanTool, Severity
from app.parsers.base import BaseParser, UnifiedFinding
from app.parsers.util import strip_html

# ZAP riskcode: 0=info, 1=low, 2=medium, 3=high (tak ada "critical").
_RISK = {
    "0": Severity.info,
    "1": Severity.low,
    "2": Severity.medium,
    "3": Severity.high,
}


def _cwe(value: str | None) -> str | None:
    if value and str(value) not in ("-1", "0", ""):
        return f"CWE-{value}"
    return None


def _refs(value: str | None) -> list[str]:
    text = strip_html(value) or ""
    return [line.strip() for line in text.splitlines() if line.strip()]


class ZapParser(BaseParser):
    tool: ClassVar[ScanTool] = ScanTool.zap

    @classmethod
    def sniff(cls, filename: str, content: bytes) -> bool:
        head = content.lstrip()[:1]
        if head == b"{":
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return False
            return isinstance(data, dict) and "site" in data
        return b"OWASPZAPReport" in content[:4096] or b"alertitem" in content[:4096]

    def parse(self, content: bytes) -> list[UnifiedFinding]:
        if content.lstrip()[:1] == b"{":
            return self._parse_json(content)
        return self._parse_xml(content)

    def _parse_json(self, content: bytes) -> list[UnifiedFinding]:
        data = json.loads(content)
        findings: list[UnifiedFinding] = []
        for site in data.get("site", []):
            site_name = site.get("@name") or site.get("@host")
            for alert in site.get("alerts", []):
                instances = alert.get("instances") or []
                target = instances[0].get("uri") if instances else site_name
                findings.append(
                    UnifiedFinding(
                        title=alert.get("name") or alert.get("alert") or "Temuan ZAP",
                        description=strip_html(alert.get("desc")),
                        severity=_RISK.get(str(alert.get("riskcode", "0")), Severity.info),
                        tool=ScanTool.zap,
                        target=target,
                        cwe=_cwe(alert.get("cweid")),
                        references=_refs(alert.get("reference")),
                        raw=alert,
                    )
                )
        return findings

    def _parse_xml(self, content: bytes) -> list[UnifiedFinding]:
        root = ET.fromstring(content)
        findings: list[UnifiedFinding] = []
        for site in root.iter("site"):
            site_name = site.get("name")
            for item in site.iter("alertitem"):

                def txt(tag: str) -> str | None:
                    el = item.find(tag)
                    return el.text if el is not None else None

                uris = [u.text for u in item.iter("uri") if u.text]
                findings.append(
                    UnifiedFinding(
                        title=txt("alert") or txt("name") or "Temuan ZAP",
                        description=strip_html(txt("desc")),
                        severity=_RISK.get(str(txt("riskcode") or "0"), Severity.info),
                        tool=ScanTool.zap,
                        target=uris[0] if uris else site_name,
                        cwe=_cwe(txt("cweid")),
                        references=_refs(txt("reference")),
                        raw={"alert": txt("alert"), "cweid": txt("cweid")},
                    )
                )
        return findings

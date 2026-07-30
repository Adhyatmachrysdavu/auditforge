"""Parser keluaran Nmap (XML, hasil `-oX`).

Menghasilkan temuan: setiap port terbuka + setiap hasil skrip NSE (port/host).
Nmap tak punya tingkat keparahan, jadi port = info; skrip = info, dinaikkan ke
medium bila outputnya mengindikasikan kerentanan.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import ClassVar

from app.models.enums import ScanTool, Severity
from app.parsers.base import BaseParser, UnifiedFinding

_CVE_RE = re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)
_VULN_HINTS = ("vuln", "vulnerable", "cve-", "exploit")


def _host_label(host: ET.Element) -> str:
    for addr in host.iter("address"):
        if addr.get("addr"):
            return addr.get("addr", "host")
    hn = host.find("hostnames/hostname")
    if hn is not None and hn.get("name"):
        return hn.get("name", "host")
    return "host"


def _script_severity(script_id: str, output: str) -> Severity:
    text = f"{script_id} {output}".lower()
    return Severity.medium if any(h in text for h in _VULN_HINTS) else Severity.info


class NmapParser(BaseParser):
    tool: ClassVar[ScanTool] = ScanTool.nmap

    @classmethod
    def sniff(cls, filename: str, content: bytes) -> bool:
        return b"<nmaprun" in content[:4096]

    def parse(self, content: bytes) -> list[UnifiedFinding]:
        root = ET.fromstring(content)
        findings: list[UnifiedFinding] = []
        for host in root.iter("host"):
            label = _host_label(host)
            for port in host.iter("port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue
                portid = port.get("portid", "?")
                proto = port.get("protocol", "tcp")
                svc = port.find("service")
                svc_name = svc.get("name") if svc is not None else None
                product = " ".join(
                    v
                    for v in (
                        svc.get("product") if svc is not None else None,
                        svc.get("version") if svc is not None else None,
                    )
                    if v
                )
                target = f"{label}:{portid}/{proto}"
                title = f"Port terbuka {portid}/{proto}"
                if svc_name:
                    title += f" — {svc_name}"
                findings.append(
                    UnifiedFinding(
                        title=title,
                        description=f"Layanan: {svc_name or 'tak dikenal'}"
                        + (f" ({product})" if product else ""),
                        severity=Severity.info,
                        tool=ScanTool.nmap,
                        target=target,
                        raw={"portid": portid, "protocol": proto, "service": svc_name},
                    )
                )
                for script in port.iter("script"):
                    findings.append(self._script_finding(script, target))
            for hs in host.findall("hostscript/script"):
                findings.append(self._script_finding(hs, label))
        return findings

    @staticmethod
    def _script_finding(script: ET.Element, target: str) -> UnifiedFinding:
        sid = script.get("id", "script")
        output = (script.get("output") or "").strip()
        refs = list(dict.fromkeys(m.group(0).upper() for m in _CVE_RE.finditer(output)))
        return UnifiedFinding(
            title=f"Nmap script: {sid}",
            description=output or None,
            severity=_script_severity(sid, output),
            tool=ScanTool.nmap,
            target=target,
            references=refs,
            raw={"script": sid},
        )

"""Registry parser — pemilihan berdasarkan perkakas eksplisit atau deteksi otomatis."""
from __future__ import annotations

from app.models.enums import ScanTool
from app.parsers.base import BaseParser, UnifiedFinding
from app.parsers.burp import BurpParser
from app.parsers.nmap import NmapParser
from app.parsers.nuclei import NucleiParser
from app.parsers.sarif import SarifParser
from app.parsers.zap import ZapParser

_PARSERS: list[type[BaseParser]] = [
    NucleiParser,
    ZapParser,
    NmapParser,
    BurpParser,
    SarifParser,
]
_BY_TOOL: dict[ScanTool, type[BaseParser]] = {p.tool: p for p in _PARSERS}


def select_parser(tool: str | None, filename: str, content: bytes) -> BaseParser | None:
    """Pilih parser: utamakan `tool` eksplisit, jika tidak cocok → deteksi otomatis."""
    if tool:
        try:
            t = ScanTool(tool)
        except ValueError:
            t = ScanTool.unknown
        if t in _BY_TOOL:
            return _BY_TOOL[t]()
    for cls in _PARSERS:
        try:
            if cls.sniff(filename, content):
                return cls()
        except Exception:  # noqa: BLE001 — deteksi gagal → coba parser berikutnya
            continue
    return None


__all__ = ["select_parser", "BaseParser", "UnifiedFinding"]

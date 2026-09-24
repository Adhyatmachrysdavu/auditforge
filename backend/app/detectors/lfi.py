"""Detektor Local File Inclusion / Path Traversal (CWE-22) — penanda pada evidensi."""
from __future__ import annotations

import re

from app.detectors.base import BaseDetector, DetectorMatch

# Urutan `../` berulang (traversal), berkas sistem khas yang sering jadi target
# pembuktian (POC) LFI di Linux/Windows, dan skema wrapper PHP yang jadi vektor
# LFI-ke-RCE klasik.
_LFI_RE = re.compile(
    r"(?:\.\./){2,}|"
    r"\betc/passwd\b|\bwin\.ini\b|\bboot\.ini\b|"
    r"\bphp://filter\b|\bphp://input\b|\bfile://",
    re.IGNORECASE,
)


class LfiDetector(BaseDetector):
    id = "LFI"
    label = "Local File Inclusion / Path Traversal"
    cwe = "CWE-22"

    def detect(self, text: str) -> DetectorMatch | None:
        m = _LFI_RE.search(text)
        if not m:
            return None
        return DetectorMatch(
            detector_id=self.id, label=self.label, cwe=self.cwe, evidence=m.group(0)
        )

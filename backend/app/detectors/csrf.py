"""Detektor CSRF (CWE-352) — penanda ketiadaan token anti-CSRF pada evidensi.

Pola dicocokkan dengan cara perkakas menuliskannya (mis. ZAP: "Absence of
Anti-CSRF Tokens" — lihat `datasets/fixtures/zap-sample.json`), bukan dengan
mencoba menebak dari cookie/header, agar tak berisik pada temuan tak terkait.
"""
from __future__ import annotations

import re

from app.detectors.base import BaseDetector, DetectorMatch

_CSRF_RE = re.compile(
    r"(?i)\b(?:absence of|no|missing|lack of)\b[^.\n]{0,20}\banti-csrf\b|"
    r"\b(?:absence of|no|missing|lack of)\b[^.\n]{0,10}\bcsrf tokens?\b"
)


class CsrfDetector(BaseDetector):
    id = "CSRF"
    label = "Cross-Site Request Forgery"
    cwe = "CWE-352"

    def detect(self, text: str) -> DetectorMatch | None:
        m = _CSRF_RE.search(text)
        if not m:
            return None
        return DetectorMatch(
            detector_id=self.id, label=self.label, cwe=self.cwe, evidence=m.group(0)
        )

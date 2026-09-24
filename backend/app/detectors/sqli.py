"""Detektor SQL Injection (CWE-89) — penanda pesan galat basis data pada evidensi."""
from __future__ import annotations

import re

from app.detectors.base import BaseDetector, DetectorMatch

# Pesan galat khas yang bocor dari MySQL/PostgreSQL/MSSQL/Oracle/SQLite saat
# input tak disanitasi menembus query — pola umum di tulisan bug-bounty & OWASP
# Testing Guide utk deteksi SQLi berbasis galat (error-based).
_SQL_ERROR_RE = re.compile(
    r"(?i)\byou have an error in your sql syntax\b|"
    r"\bwarning:\s*mysqli?_|"
    r"\bunclosed quotation mark after the character string\b|"
    r"\bquoted string not properly terminated\b|"
    r"\bpg_query\(\)\s*:|"
    r"\bsqlstate\[\d+\]|"
    r"\bora-\d{5}\b|"
    r"\bsqlite3?\.OperationalError\b|"
    r"\bmicrosoft ole db provider for odbc drivers\b"
)


class SqliDetector(BaseDetector):
    id = "SQLI"
    label = "SQL Injection"
    cwe = "CWE-89"

    def detect(self, text: str) -> DetectorMatch | None:
        m = _SQL_ERROR_RE.search(text)
        if not m:
            return None
        return DetectorMatch(
            detector_id=self.id, label=self.label, cwe=self.cwe, evidence=m.group(0)
        )

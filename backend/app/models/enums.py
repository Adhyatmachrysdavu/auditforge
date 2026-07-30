"""Nilai enumerasi domain.

Disimpan sebagai kolom String di DB (migrasi lebih sederhana), namun divalidasi
di lapisan aplikasi lewat enum ini.
"""
from __future__ import annotations

import enum


class RoleName(str, enum.Enum):
    admin = "admin"
    auditor = "auditor"
    analyst = "analyst"


class EngagementStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    reporting = "reporting"
    closed = "closed"


class ScanTool(str, enum.Enum):
    nmap = "nmap"
    nuclei = "nuclei"
    zap = "zap"
    burp = "burp"
    sarif = "sarif"
    unknown = "unknown"


class UploadStatus(str, enum.Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    parsed = "parsed"
    failed = "failed"


class Severity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    false_positive = "false_positive"

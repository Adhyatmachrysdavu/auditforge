"""Alur review temuan (D13) — mesin status deterministik + aturan peran.

Prinsip AuditForge: AI hanya membuat DRAF; **auditor** pengambil keputusan akhir.
Modul ini murni (tanpa I/O) sehingga transisi & batas persetujuan dapat diuji
penuh, lalu dipakai oleh router.

Status (lihat `FindingStatus`): draft → in_review → approved / rejected /
false_positive, dengan kemungkinan dibuka kembali (reopen) ke in_review.
"""
from __future__ import annotations

from app.models.enums import FindingStatus, RoleName

# Transisi yang diizinkan: status sekarang → himpunan status tujuan.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    FindingStatus.draft.value: {
        FindingStatus.in_review.value,
    },
    FindingStatus.in_review.value: {
        FindingStatus.approved.value,
        FindingStatus.rejected.value,
        FindingStatus.false_positive.value,
        FindingStatus.draft.value,  # kembalikan ke draf untuk revisi
    },
    FindingStatus.approved.value: {
        FindingStatus.in_review.value,  # buka kembali
    },
    FindingStatus.rejected.value: {
        FindingStatus.in_review.value,
    },
    FindingStatus.false_positive.value: {
        FindingStatus.in_review.value,
    },
}

# Keputusan final yang HANYA boleh dilakukan auditor/admin (batas persetujuan).
APPROVAL_STATES: set[str] = {
    FindingStatus.approved.value,
    FindingStatus.rejected.value,
    FindingStatus.false_positive.value,
}

# Peran yang boleh menyunting naratif & mengajukan ke review.
EDITOR_ROLES: set[str] = {RoleName.analyst.value, RoleName.auditor.value, RoleName.admin.value}
# Peran yang boleh mengambil keputusan final.
APPROVER_ROLES: set[str] = {RoleName.auditor.value, RoleName.admin.value}


def is_valid_status(value: str) -> bool:
    return value in {s.value for s in FindingStatus}


def can_transition(current: str, target: str) -> bool:
    """True bila perpindahan `current`→`target` diizinkan mesin status."""
    if current == target:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, set())


def role_allows_transition(role: str, target: str) -> bool:
    """True bila `role` berwenang memindahkan status ke `target`.

    Keputusan final (approved/rejected/false_positive) → hanya auditor/admin.
    Transisi lain (ajukan review, kembalikan ke draf) → editor (termasuk analis).
    """
    if target in APPROVAL_STATES:
        return role in APPROVER_ROLES
    return role in EDITOR_ROLES

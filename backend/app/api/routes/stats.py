"""Statistik ringkas untuk dasbor."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.engagement import Engagement
from app.models.enums import Severity
from app.models.finding import Finding
from app.models.scan_upload import ScanUpload
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
def overview(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    engagements = db.scalar(select(func.count()).select_from(Engagement)) or 0
    uploads = db.scalar(select(func.count()).select_from(ScanUpload)) or 0
    findings = db.scalar(select(func.count()).select_from(Finding)) or 0

    rows = db.execute(
        select(Finding.severity, func.count()).group_by(Finding.severity)
    ).all()
    counts = {sev: cnt for sev, cnt in rows}
    # Urutan tetap (kritis→info) + isi 0 untuk yang tak ada.
    by_severity = {s.value: counts.get(s.value, 0) for s in [
        Severity.critical, Severity.high, Severity.medium, Severity.low, Severity.info
    ]}

    return {
        "engagements": engagements,
        "uploads": uploads,
        "findings": findings,
        "by_severity": by_severity,
    }

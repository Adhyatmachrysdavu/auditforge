"""Statistik ringkas untuk dasbor."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.eval.timing import timing_summary
from app.models.engagement import Engagement
from app.models.enums import Severity
from app.models.finding import Finding, FindingRevision
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


@router.get("/timing")
def timing_overview(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    """Agregat waktu penyusunan lintas penugasan (Modul 1) untuk halaman /reports.

    Seluruh revisi diambil dalam satu kueri lalu dikelompokkan di memori, agar
    tidak memicu satu kueri per penugasan.
    """
    rows = db.execute(
        select(Finding.engagement_id, FindingRevision.action, FindingRevision.created_at)
        .join(Finding, FindingRevision.finding_id == Finding.id)
        .order_by(FindingRevision.created_at)
    ).all()

    by_eng: dict[int, list[object]] = {}
    for eid, action, created_at in rows:
        by_eng.setdefault(eid, []).append(
            SimpleNamespace(action=action, created_at=created_at)
        )

    items: list[dict] = []
    for e in db.scalars(select(Engagement).order_by(Engagement.id)).all():
        summary = timing_summary(by_eng.get(e.id, []), baseline_hours=e.baseline_hours)
        items.append(
            {
                "engagement_id": e.id,
                "name": e.name,
                "client_name": e.client_name,
                "status": e.status,
                **summary,
            }
        )

    measured = [i for i in items if i["saved_ratio"] is not None]
    avg = (
        round(sum(float(i["saved_ratio"]) for i in measured) / len(measured), 4)
        if measured
        else None
    )
    return {
        "items": items,
        "engagements_measured": len(measured),
        "avg_saved_ratio": avg,
    }

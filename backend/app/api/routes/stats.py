"""Statistik ringkas untuk dasbor."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import needs_engagement_filter
from app.api.deps import get_current_user
from app.db.session import get_db
from app.eval.timing import aggregate_timing, timing_summary
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.enums import Severity
from app.models.finding import Finding, FindingRevision
from app.models.scan_upload import ScanUpload
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


def _accessible_ids(db: Session, user: User) -> list[int] | None:
    """Id penugasan yang boleh dilihat pengguna, atau None bila tak perlu disaring.

    `None` berarti admin — lihat semua. Daftar **kosong** berarti pengguna bukan
    anggota penugasan mana pun, dan hasilnya harus nol; itu bedanya fail-closed
    dengan fail-open pada penyaringan berbasis daftar.
    """
    if not needs_engagement_filter(user.role.name):
        return None
    return list(
        db.scalars(
            select(EngagementMember.engagement_id).where(
                EngagementMember.user_id == user.id
            )
        ).all()
    )


@router.get("")
def overview(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    eng_ids = _accessible_ids(db, user)

    q_eng = select(func.count()).select_from(Engagement)
    q_up = select(func.count()).select_from(ScanUpload)
    q_find = select(func.count()).select_from(Finding)
    q_sev = select(Finding.severity, func.count()).group_by(Finding.severity)
    if eng_ids is not None:
        q_eng = q_eng.where(Engagement.id.in_(eng_ids))
        q_up = q_up.where(ScanUpload.engagement_id.in_(eng_ids))
        q_find = q_find.where(Finding.engagement_id.in_(eng_ids))
        q_sev = q_sev.where(Finding.engagement_id.in_(eng_ids))

    engagements = db.scalar(q_eng) or 0
    uploads = db.scalar(q_up) or 0
    findings = db.scalar(q_find) or 0

    counts = {sev: cnt for sev, cnt in db.execute(q_sev).all()}
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
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Agregat waktu penyusunan lintas penugasan (Modul 1) untuk halaman /reports.

    Seluruh revisi diambil dalam satu kueri lalu dikelompokkan di memori, agar
    tidak memicu satu kueri per penugasan. Hanya penugasan yang boleh diakses
    pengguna yang ikut dihitung.
    """
    eng_ids = _accessible_ids(db, user)

    q_rev = (
        select(
            Finding.engagement_id,
            FindingRevision.action,
            FindingRevision.created_at,
            FindingRevision.author_id,
        )
        .select_from(FindingRevision)
        .join(Finding, FindingRevision.finding_id == Finding.id)
        .order_by(FindingRevision.created_at)
    )
    q_eng = select(Engagement).order_by(Engagement.id)
    if eng_ids is not None:
        q_rev = q_rev.where(Finding.engagement_id.in_(eng_ids))
        q_eng = q_eng.where(Engagement.id.in_(eng_ids))

    # `author_id` wajib ikut: itu yang memisahkan kerja auditor dari draf worker AI.
    by_eng: dict[int, list[object]] = {}
    for eid, action, created_at, author_id in db.execute(q_rev).all():
        by_eng.setdefault(eid, []).append(
            SimpleNamespace(action=action, created_at=created_at, author_id=author_id)
        )

    items: list[dict] = []
    for e in db.scalars(q_eng).all():
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

    return {"items": items, **aggregate_timing(items)}

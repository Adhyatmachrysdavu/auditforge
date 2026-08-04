"""Pusat Ingest — aktivitas penyerapan berkas lintas penugasan.

Data yang ditampilkan seluruhnya sudah tersimpan di `ScanUpload`; selama ini
hanya tidak pernah ditanyakan lintas penugasan. Tanpa halaman ini, berkas yang
gagal hanya dapat ditemukan dengan membuka tab Berkas pada tiap penugasan satu
per satu.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import needs_engagement_filter
from app.api.deps import get_current_user
from app.db.session import get_db
from app.ingest.rules import can_reparse
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.enums import UploadStatus
from app.models.scan_upload import ScanUpload
from app.models.user import User

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("")
def list_ingest(
    status: str | None = None,
    engagement_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Aktivitas ingest terbaru lintas penugasan, terbaru lebih dulu.

    Hanya penugasan yang boleh diakses pengguna. Daftar id kosong berarti nol
    hasil, bukan seluruh data — itu bedanya fail-closed dengan fail-open pada
    penyaringan berbasis daftar.
    """
    eng_ids: list[int] | None = None
    if needs_engagement_filter(user.role.name):
        eng_ids = list(
            db.scalars(
                select(EngagementMember.engagement_id).where(
                    EngagementMember.user_id == user.id
                )
            ).all()
        )

    q = (
        select(ScanUpload, Engagement.name)
        .join(Engagement, ScanUpload.engagement_id == Engagement.id)
        .order_by(ScanUpload.created_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    if status:
        q = q.where(ScanUpload.status == status)
    if engagement_id is not None:
        q = q.where(ScanUpload.engagement_id == engagement_id)
    if eng_ids is not None:
        q = q.where(ScanUpload.engagement_id.in_(eng_ids))

    items = []
    for up, eng_name in db.execute(q).all():
        ok, _reason = can_reparse(
            status=up.status, has_storage_key=bool(up.storage_key)
        )
        items.append(
            {
                "upload_id": up.id,
                "engagement_id": up.engagement_id,
                "engagement_name": eng_name,
                "filename": up.filename,
                "tool": up.tool,
                "status": up.status,
                "error": up.error,
                # uploaded_by kosong = diserap otomatis oleh watcher (R3).
                "source": "manual" if up.uploaded_by else "watcher",
                "can_reparse": ok,
                "created_at": up.created_at.isoformat() if up.created_at else None,
            }
        )

    since = datetime.now(UTC) - timedelta(days=1)
    q_today = (
        select(func.count())
        .select_from(ScanUpload)
        .where(ScanUpload.created_at >= since)
    )
    q_failed = (
        select(func.count())
        .select_from(ScanUpload)
        .where(ScanUpload.status == UploadStatus.failed.value)
    )
    q_total = select(func.count()).select_from(ScanUpload)
    if eng_ids is not None:
        q_today = q_today.where(ScanUpload.engagement_id.in_(eng_ids))
        q_failed = q_failed.where(ScanUpload.engagement_id.in_(eng_ids))
        q_total = q_total.where(ScanUpload.engagement_id.in_(eng_ids))

    today = db.scalar(q_today) or 0
    failed = db.scalar(q_failed) or 0
    total = db.scalar(q_total) or 0

    return {
        "items": items,
        "summary": {"today": today, "failed": failed, "total": total},
    }

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

from app.api.deps import get_current_user
from app.db.session import get_db
from app.ingest.rules import can_reparse
from app.models.engagement import Engagement
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
    _: User = Depends(get_current_user),
) -> dict:
    """Aktivitas ingest terbaru lintas penugasan, terbaru lebih dulu."""
    # TODO(Modul 2): saring berdasarkan keanggotaan tim setelah engagement_members ada.
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
    today = db.scalar(
        select(func.count())
        .select_from(ScanUpload)
        .where(ScanUpload.created_at >= since)
    ) or 0
    failed = db.scalar(
        select(func.count())
        .select_from(ScanUpload)
        .where(ScanUpload.status == UploadStatus.failed.value)
    ) or 0
    total = db.scalar(select(func.count()).select_from(ScanUpload)) or 0

    return {
        "items": items,
        "summary": {"today": today, "failed": failed, "total": total},
    }

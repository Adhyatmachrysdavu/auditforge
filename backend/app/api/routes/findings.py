"""Pencarian temuan lintas penugasan (Modul 3).

Berbeda dengan Basis Pengetahuan yang sengaja lintas klien, pencarian ini
**disaring keanggotaan**: seorang analis hanya menemukan temuan pada penugasan
yang memang menjadi tanggung jawabnya. Daftar id kosong berarti nol hasil,
bukan seluruh data — itu bedanya fail-closed dengan fail-open.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import needs_engagement_filter
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.finding import Finding
from app.models.user import User
from app.schemas.knowledge import FindingSearchOut

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("")
def search_findings(
    q: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    cwe: str | None = None,
    owasp: str | None = None,
    engagement_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Cari temuan pada seluruh penugasan yang boleh diakses pengguna."""
    stmt = (
        select(Finding, Engagement)
        .join(Engagement, Finding.engagement_id == Engagement.id)
        .order_by(Finding.priority.asc().nulls_last(), Finding.id.desc())
    )

    if needs_engagement_filter(user.role.name):
        eng_ids = list(
            db.scalars(
                select(EngagementMember.engagement_id).where(
                    EngagementMember.user_id == user.id
                )
            ).all()
        )
        stmt = stmt.where(Finding.engagement_id.in_(eng_ids))

    if engagement_id is not None:
        stmt = stmt.where(Finding.engagement_id == engagement_id)
    if severity:
        stmt = stmt.where(Finding.severity == severity.strip().lower())
    if status:
        stmt = stmt.where(Finding.status == status.strip().lower())
    if cwe:
        stmt = stmt.where(Finding.cwe == cwe.strip().upper())
    if owasp:
        stmt = stmt.where(Finding.owasp == owasp.strip())
    if q:
        stmt = stmt.where(Finding.title.ilike(f"%{q.strip()}%"))

    rows = db.execute(stmt.limit(max(1, min(limit, 500)))).all()
    return {
        "items": [
            FindingSearchOut(
                id=f.id,
                engagement_id=f.engagement_id,
                engagement_name=e.name,
                client_name=e.client_name,
                title=f.title,
                severity=f.severity,
                status=f.status,
                priority=f.priority,
                cwe=f.cwe,
                owasp=f.owasp,
                cvss_score=f.cvss_score,
            )
            for f, e in rows
        ]
    }

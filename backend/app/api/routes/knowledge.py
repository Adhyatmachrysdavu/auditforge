"""Basis Pengetahuan Temuan (Modul 3) — rujukan naratif lintas penugasan.

Tiga pengaman menyertai keputusan menyimpan naratif secara utuh:

1. Hanya **auditor/admin** yang boleh membuka (router ini).
2. `engagements.kb_shareable` menentukan apakah sebuah penugasan boleh menjadi
   rujukan (dijaga saat entri dibuat, lihat `engagements._sync_knowledge_entry`).
3. **Akses baca dicatat.** `AuditMiddleware` hanya mencatat mutasi, jadi route di
   sini menulis `AuditLog` sendiri. Bila klien bertanya siapa saja yang pernah
   melihat temuan mereka, jawabannya tersedia.
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.knowledge.matching import normalize_title, rank_matches
from app.models.audit_log import AuditLog
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.knowledge_entry import KnowledgeEntry
from app.models.user import User
from app.schemas.knowledge import KnowledgeEntryOut, KnowledgeSuggestion

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_KB_ROLES = ("auditor", "admin")


def _log_read(
    db: Session, request: Request, user: User, *, detail: str, entity_id: str | None
) -> None:
    """Catat akses baca ke jejak audit; middleware hanya mencatat mutasi."""
    db.add(
        AuditLog(
            user_id=user.id,
            action="read",
            method="GET",
            path=request.url.path,
            entity="knowledge",
            entity_id=entity_id,
            status_code=200,
            ip=request.client.host if request.client else None,
            detail=detail,
        )
    )
    db.commit()


def _to_out(entry: KnowledgeEntry, eng: Engagement | None) -> KnowledgeEntryOut:
    return KnowledgeEntryOut(
        id=entry.id,
        source_finding_id=entry.source_finding_id,
        source_engagement_id=entry.source_engagement_id,
        source_engagement_name=eng.name if eng else "—",
        source_client_name=eng.client_name if eng else "—",
        title=entry.title,
        cwe=entry.cwe,
        owasp=entry.owasp,
        severity=entry.severity,
        narrative=entry.narrative or {},
        auditor_edited=bool(entry.auditor_edited),
        usage_count=entry.usage_count or 0,
        created_at=entry.created_at,
    )


def _engagement_map(db: Session, entries: list[KnowledgeEntry]) -> dict[int, Engagement]:
    """Ambil seluruh penugasan asal dalam satu kueri, bukan satu per entri."""
    ids = {e.source_engagement_id for e in entries}
    if not ids:
        return {}
    return {
        e.id: e
        for e in db.scalars(select(Engagement).where(Engagement.id.in_(ids))).all()
    }


@router.get("")
def list_knowledge(
    request: Request,
    q: str | None = None,
    cwe: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_KB_ROLES)),
) -> dict:
    """Telusuri Basis Pengetahuan. Akses baca dicatat pada jejak audit."""
    stmt = select(KnowledgeEntry).order_by(
        KnowledgeEntry.usage_count.desc(), KnowledgeEntry.id.desc()
    )
    if cwe:
        stmt = stmt.where(KnowledgeEntry.cwe == cwe.strip().upper())
    if q:
        # Cocokkan pada judul ternormalisasi agar "example.com:443" pada kueri
        # tidak menghalangi kecocokan.
        needle = normalize_title(q)
        if needle:
            stmt = stmt.where(KnowledgeEntry.title_norm.ilike(f"%{needle}%"))
        else:
            stmt = stmt.where(KnowledgeEntry.title.ilike(f"%{q.strip()}%"))
    entries = list(db.scalars(stmt.limit(max(1, min(limit, 200)))).all())
    engs = _engagement_map(db, entries)

    _log_read(
        db, request, user,
        detail=f"telusur basis pengetahuan q={q or ''} cwe={cwe or ''} hasil={len(entries)}",
        entity_id=None,
    )
    return {"items": [_to_out(e, engs.get(e.source_engagement_id)) for e in entries]}


@router.get("/suggest")
def suggest_knowledge(
    request: Request,
    finding_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_KB_ROLES)),
) -> dict:
    """Entri paling mirip untuk satu temuan, memakai pencocokan deterministik."""
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Temuan tak ditemukan")

    target = SimpleNamespace(cwe=f.cwe, title_norm=normalize_title(f.title))
    # Entri dari temuan itu sendiri bukan saran yang berguna.
    candidates = list(
        db.scalars(
            select(KnowledgeEntry).where(KnowledgeEntry.source_finding_id != finding_id)
        ).all()
    )
    ranked = rank_matches(target, candidates, limit=max(1, min(limit, 20)))
    engs = _engagement_map(db, [c for c, _ in ranked])

    _log_read(
        db, request, user,
        detail=f"saran basis pengetahuan untuk temuan {finding_id}, {len(ranked)} hasil",
        entity_id=str(finding_id),
    )
    return {
        "items": [
            KnowledgeSuggestion(
                entry=_to_out(c, engs.get(c.source_engagement_id)), score=score
            )
            for c, score in ranked
        ]
    }

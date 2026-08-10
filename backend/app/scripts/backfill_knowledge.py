"""Isi Basis Pengetahuan dari temuan yang sudah disetujui (Modul 3).

Idempoten: dijalankan berulang kali tidak menggandakan entri, karena syaratnya
sama dengan jalur runtime — keduanya memakai `app.knowledge.entries`.

Sengaja **tidak** ditaruh di dalam migrasi: aturan naratif efektif
(`final or draft`) hanya boleh punya satu sumber kebenaran. Menuliskannya ulang
dalam SQL menciptakan salinan kedua yang dapat menyimpang diam-diam.

    docker exec auditforge-api-1 python -m app.scripts.backfill_knowledge
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.knowledge.entries import (
    effective_narrative,
    is_auditor_edited,
    should_create_entry,
)
from app.knowledge.matching import normalize_title
from app.models.engagement import Engagement
from app.models.finding import Finding, FindingRevision
from app.models.knowledge_entry import KnowledgeEntry


def _approver_id(db: Session, finding_id: int) -> int | None:
    """Siapa yang menyetujui temuan ini, menurut riwayat revisinya.

    Bila tak ditemukan, kembalikan None. Mengarang penulis akan merusak
    keterlacakan yang justru menjadi inti modul ini.
    """
    return db.scalar(
        select(FindingRevision.author_id)
        .where(
            FindingRevision.finding_id == finding_id,
            FindingRevision.action == "approve",
        )
        .order_by(FindingRevision.id.desc())
        .limit(1)
    )


def run() -> dict[str, int]:
    db = SessionLocal()
    try:
        sudah_ada = set(db.scalars(select(KnowledgeEntry.source_finding_id)).all())
        engagements = {e.id: e for e in db.scalars(select(Engagement)).all()}
        rows = db.scalars(
            select(Finding).where(Finding.status == "approved").order_by(Finding.id)
        ).all()

        dibuat = dilewati = 0
        for f in rows:
            eng = engagements.get(f.engagement_id)
            if eng is None:
                dilewati += 1
                continue
            narrative = effective_narrative(f)
            ok, _alasan = should_create_entry(
                status=f.status,
                kb_shareable=bool(eng.kb_shareable),
                narrative=narrative,
                already_exists=f.id in sudah_ada,
            )
            if not ok:
                dilewati += 1
                continue
            db.add(
                KnowledgeEntry(
                    source_finding_id=f.id,
                    source_engagement_id=eng.id,
                    title=f.title,
                    title_norm=normalize_title(f.title),
                    cwe=f.cwe,
                    owasp=f.owasp,
                    severity=f.severity,
                    narrative=narrative,
                    auditor_edited=is_auditor_edited(f),
                    created_by=_approver_id(db, f.id),
                )
            )
            sudah_ada.add(f.id)
            dibuat += 1

        db.commit()
        return {"diperiksa": len(rows), "dibuat": dibuat, "dilewati": dilewati}
    finally:
        db.close()


if __name__ == "__main__":
    hasil = run()
    print(
        f"Basis Pengetahuan: {hasil['dibuat']} entri baru, "
        f"{hasil['dilewati']} dilewati, dari {hasil['diperiksa']} temuan disetujui."
    )

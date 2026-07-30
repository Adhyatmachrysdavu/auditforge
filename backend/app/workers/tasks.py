"""Task Celery: parsing → pengayaan (D8) → deduplikasi (D7) → simpan temuan."""
from __future__ import annotations

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import get_bytes, put_bytes
from app.db.session import SessionLocal
from app.enrichment import enrich
from app.ingest.watcher import iter_inbox_files, move_result
from app.models.engagement import Engagement
from app.models.enums import UploadStatus
from app.models.finding import Finding, FindingRevision
from app.models.scan_upload import ScanUpload
from app.normalize import SourceRef, compute_fingerprint, severity_rank
from app.parsers import select_parser
from app.parsers.base import UnifiedFinding
from app.triage import triage
from app.workers.celery_app import celery_app


def _apply_triage(row: Finding) -> None:
    """Hitung prioritas deterministik (D11) dari keadaan temuan saat ini."""
    t = triage(
        row.severity,
        cvss_score=row.cvss_score,
        occurrences=row.occurrences or 1,
        cve=row.cve or [],
    )
    row.priority = t.priority
    row.priority_score = t.score


def _enrich_finding(uf: UnifiedFinding) -> None:
    """Terapkan pengayaan D8 ke `uf` di tempat (sebelum fingerprint & dedup).

    Backfill CWE/CVSS dari CVE, naikkan severity sesuai band CVSS v3.1, dan
    simpan OWASP/vektor/CVE pada `uf.raw` untuk dipindahkan ke baris temuan.
    """
    e = enrich(
        title=uf.title,
        description=uf.description,
        references=uf.references,
        cwe=uf.cwe,
        cvss_score=uf.cvss_score,
    )
    if e.cwe:
        uf.cwe = e.cwe
    if e.cvss_score is not None:
        uf.cvss_score = e.cvss_score
    # Severity dari CVSS hanya menaikkan (jangan turunkan label perkakas).
    if e.severity is not None and severity_rank(e.severity) > severity_rank(uf.severity):
        uf.severity = e.severity
    uf.raw["_owasp"] = e.owasp
    uf.raw["_cvss_vector"] = e.cvss_vector
    uf.raw["_cves"] = e.cves


def _ingest_findings(
    db: Session, engagement_id: int, upload_id: int, findings: list[UnifiedFinding]
) -> dict:
    """Simpan temuan dengan deduplikasi terhadap temuan yang sudah ada di engagement.

    Sidik jari sama → gabung (severity/cvss tertinggi menang, catat asal, naikkan
    `occurrences`). Sidik jari baru → buat baris baru. Menggabungkan lintas-berkas
    dan lintas-perkakas dalam satu engagement.
    """
    # Muat sidik jari yang sudah ada di engagement ini agar dedup lintas-berkas jalan.
    existing: dict[str, Finding] = {}
    for f in db.scalars(
        select(Finding).where(
            Finding.engagement_id == engagement_id, Finding.fingerprint.is_not(None)
        )
    ).all():
        existing.setdefault(f.fingerprint, f)  # type: ignore[arg-type]

    created = 0
    merged = 0
    for uf in findings:
        _enrich_finding(uf)  # D8: pengayaan sebelum fingerprint & dedup
        fp = compute_fingerprint(uf)
        source: SourceRef = {"tool": uf.tool.value, "upload_id": upload_id}
        cves = uf.raw.get("_cves") or []
        row = existing.get(fp)
        if row is None:
            row = Finding(
                engagement_id=engagement_id,
                source_upload_id=upload_id,
                title=uf.title[:300],
                description=uf.to_description(),
                severity=uf.severity.value,
                cwe=uf.cwe,
                cvss_score=uf.cvss_score,
                owasp=uf.raw.get("_owasp"),
                cvss_vector=uf.raw.get("_cvss_vector"),
                cve=list(cves),
                fingerprint=fp,
                occurrences=1,
                sources=[source],
                ai_generated=False,
            )
            db.add(row)
            existing[fp] = row
            created += 1
        else:
            # Gabung: severity & cvss tertinggi menang; catat asal; naikkan occurrences.
            if severity_rank(uf.severity) > severity_rank(row.severity):
                row.severity = uf.severity.value
                row.title = uf.title[:300]
                row.description = uf.to_description()
            if uf.cvss_score is not None and (
                row.cvss_score is None or uf.cvss_score > row.cvss_score
            ):
                row.cvss_score = uf.cvss_score
            if not row.cwe and uf.cwe:
                row.cwe = uf.cwe
            if not row.owasp and uf.raw.get("_owasp"):
                row.owasp = uf.raw.get("_owasp")
            if not row.cvss_vector and uf.raw.get("_cvss_vector"):
                row.cvss_vector = uf.raw.get("_cvss_vector")
            union = [*(row.cve or []), *(c for c in cves if c not in (row.cve or []))]
            if union != (row.cve or []):
                row.cve = union  # reassign → deteksi perubahan
            row.occurrences = (row.occurrences or 1) + 1
            if source not in (row.sources or []):
                row.sources = [*(row.sources or []), source]  # reassign → deteksi perubahan
            merged += 1

    # D11: triase deterministik atas keadaan akhir tiap temuan di engagement.
    for row in existing.values():
        _apply_triage(row)

    return {"created": created, "merged": merged}


@celery_app.task(name="auditforge.generate_narrative")
def generate_narrative(finding_id: int, lang: str = "id") -> dict:
    """Susun draf naratif AI untuk satu temuan, simpan ke `ai_draft` (D10).

    Masking otomatis di `llm.draft`. Gagal → status dilaporkan, tak meng-crash worker.
    """
    from app.ai.narrative import build_payload
    from app.ai.narrative import generate_narrative as gen
    from app.ai.prompts import NARRATIVE_PROMPT_VERSION

    db = SessionLocal()
    try:
        f = db.get(Finding, finding_id)
        if f is None:
            return {"error": "finding tak ditemukan", "finding_id": finding_id}
        payload = build_payload(
            title=f.title,
            severity=f.severity,
            description=f.description,
            cwe=f.cwe,
            owasp=f.owasp,
            cvss_score=f.cvss_score,
            cve=f.cve or [],
        )
        try:
            narr = gen(payload, lang=lang)
        except Exception as exc:  # noqa: BLE001 — laporkan, jangan crash
            return {"error": f"{type(exc).__name__}: {exc}"[:300], "finding_id": finding_id}

        f.ai_draft = narr.as_dict()
        f.ai_generated = True
        f.ai_model = narr.model[:64]
        f.ai_prompt_version = NARRATIVE_PROMPT_VERSION
        # D13: catat asal draf pada riwayat revisi (penulis = AI → author_id None).
        db.add(
            FindingRevision(
                finding_id=f.id,
                action="ai_draft",
                status=f.status,
                narrative=narr.as_dict(),
                note=f"AI · {narr.model[:64]} · {NARRATIVE_PROMPT_VERSION}",
                author_id=None,
            )
        )
        db.commit()
        return {"finding_id": finding_id, "model": narr.model, "ok": True}
    finally:
        db.close()


@celery_app.task(name="auditforge.generate_exec_summary")
def generate_exec_summary(engagement_id: int, lang: str = "id") -> dict:
    """Susun draf ringkasan eksekutif AI untuk satu penugasan (D11).

    Agregasi temuan deterministik → LLM (dengan masking). Gagal → dilaporkan,
    tak meng-crash worker. AI hanya membuat draf; auditor menyunting & menyetujui.
    """
    from app.ai.prompts import SUMMARY_PROMPT_VERSION
    from app.ai.summary import (
        SummaryFinding,
        build_summary_payload,
        generate_executive_summary,
        posture,
    )
    from app.models.engagement import Engagement

    db = SessionLocal()
    try:
        eng = db.get(Engagement, engagement_id)
        if eng is None:
            return {"error": "penugasan tak ditemukan", "engagement_id": engagement_id}
        rows = db.scalars(
            select(Finding).where(Finding.engagement_id == engagement_id)
        ).all()
        sfs = [
            SummaryFinding(
                title=f.title,
                severity=f.severity,
                priority=f.priority,
                cvss_score=f.cvss_score,
                owasp=f.owasp,
                cve=f.cve or [],
            )
            for f in rows
        ]
        payload = build_summary_payload(
            engagement_name=eng.name, client_name=eng.client_name, findings=sfs
        )
        try:
            es = generate_executive_summary(
                payload, posture_code=posture(sfs), lang=lang
            )
        except Exception as exc:  # noqa: BLE001 — laporkan, jangan crash
            return {
                "error": f"{type(exc).__name__}: {exc}"[:300],
                "engagement_id": engagement_id,
            }

        eng.exec_summary = es.as_dict()
        eng.exec_summary_generated = True
        eng.exec_summary_model = es.model[:64]
        eng.exec_summary_prompt_version = SUMMARY_PROMPT_VERSION
        db.commit()
        return {"engagement_id": engagement_id, "model": es.model, "ok": True}
    finally:
        db.close()


@celery_app.task(name="auditforge.parse_upload")
def parse_upload(upload_id: int) -> dict:
    """Unduh berkas dari MinIO, jalankan parser, simpan temuan ke DB."""
    db = SessionLocal()
    try:
        upload = db.get(ScanUpload, upload_id)
        if upload is None:
            return {"error": "upload tak ditemukan", "upload_id": upload_id}

        upload.status = UploadStatus.parsing.value
        db.commit()

        try:
            content = get_bytes(upload.storage_key or "")
            parser = select_parser(upload.tool, upload.filename, content)
            if parser is None:
                upload.status = UploadStatus.failed.value
                upload.error = "Format berkas tak dikenali oleh parser mana pun."
                db.commit()
                return {"error": "parser tak dikenali", "upload_id": upload_id}

            findings = parser.parse(content)
            stats = _ingest_findings(db, upload.engagement_id, upload.id, findings)
            upload.tool = parser.tool.value  # tulis-balik perkakas terdeteksi (auto/unknown)
            upload.status = UploadStatus.parsed.value
            upload.error = None
            db.commit()
            return {
                "upload_id": upload_id,
                "tool": parser.tool.value,
                "findings": len(findings),
                "created": stats["created"],
                "merged": stats["merged"],
            }
        except Exception as exc:  # noqa: BLE001 — tandai gagal, jangan buang traceback diam-diam
            db.rollback()
            upload.status = UploadStatus.failed.value
            upload.error = f"{type(exc).__name__}: {exc}"[:1000]
            db.commit()
            return {"error": str(exc), "upload_id": upload_id}
    finally:
        db.close()


def _ingest_watched_file(db: Session, engagement_id: int, path: str, name: str) -> bool:
    """Serap satu berkas dari folder terpantau: MinIO → ScanUpload → parse.

    Mengembalikan True bila penguraian berhasil. Mengikuti konvensi unggah manual
    (kunci `uploads/<eid>/...`, `tool="unknown"` → parser auto-sniff) agar temuan
    masuk pipeline dedup/enrichment/triase yang sama.
    """
    with open(path, "rb") as fh:
        content = fh.read()
    safe = name.replace("/", "_").replace("\\", "_")
    key = f"uploads/{engagement_id}/{uuid.uuid4().hex}_{safe}"
    put_bytes(key, content)
    upload = ScanUpload(
        engagement_id=engagement_id,
        filename=safe,
        tool="unknown",  # deteksi perkakas otomatis via sniff() saat parse
        storage_key=key,
        uploaded_by=None,  # None = ingest otomatis (bukan aksi pengguna)
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    result = parse_upload(upload.id)
    return "error" not in result


@celery_app.task(name="auditforge.scan_inbox")
def scan_inbox() -> dict[str, object]:
    """Pindai folder terpantau (R3) dan serap berkas baru secara otomatis.

    Auditor/skrip cukup menaruh berkas di `<watch_dir>/inbox/<engagement_id>/`;
    task periodik (Celery beat) ini yang memicu penguraian, sehingga tak perlu
    unggah manual lewat UI. Berkas dipindah ke `processed/` atau `failed/`.
    """
    settings = get_settings()
    base = settings.watch_dir
    if not settings.watch_enabled or not base or not os.path.isdir(base):
        return {"skipped": "watcher nonaktif / folder tak ada", "base": base}

    db = SessionLocal()
    processed = failed = 0
    try:
        for eid, path in iter_inbox_files(
            base, settle_seconds=settings.watch_settle_seconds
        ):
            if db.get(Engagement, eid) is None:
                move_result(path, base, eid, ok=False)  # penugasan tak ada → failed
                failed += 1
                continue
            try:
                ok = _ingest_watched_file(db, eid, str(path), path.name)
            except Exception:  # noqa: BLE001 — satu berkas gagal tak boleh menghentikan pindaian
                db.rollback()
                ok = False
            move_result(path, base, eid, ok=ok)
            processed += int(ok)
            failed += int(not ok)
        return {"processed": processed, "failed": failed}
    finally:
        db.close()

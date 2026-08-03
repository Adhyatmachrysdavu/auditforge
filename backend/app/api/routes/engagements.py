"""Router penugasan: engagement + unggah berkas scan + daftar temuan."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.storage import get_bytes, put_bytes, remove_object
from app.db.session import get_db
from app.eval.engagement_eval import evaluate_engagement
from app.eval.timing import timing_summary
from app.models.engagement import Engagement
from app.models.enums import ScanTool
from app.models.finding import Finding, FindingAttachment, FindingRevision
from app.models.scan_upload import ScanUpload
from app.models.user import User
from app.reporting.branding import load_branding
from app.reporting.docx_writer import render_docx
from app.reporting.html_writer import render_html
from app.reporting.pdf_writer import render_pdf
from app.reporting.report_data import ReportData, build_report_data
from app.review import can_transition, is_valid_status, role_allows_transition
from app.schemas.engagement import (
    AttachmentOut,
    BaselineIn,
    EngagementCreate,
    EngagementDetailOut,
    EngagementOut,
    FindingDetailOut,
    FindingOut,
    FindingRevisionOut,
    NarrativeEditIn,
    NarrativeJobOut,
    ScanUploadOut,
    StatusChangeIn,
    SummaryJobOut,
    TriageResultOut,
)
from app.triage import triage
from app.workers.tasks import generate_exec_summary, generate_narrative, parse_upload

router = APIRouter(prefix="/engagements", tags=["engagements"])


def _get_engagement(db: Session, engagement_id: int) -> Engagement:
    eng = db.get(Engagement, engagement_id)
    if eng is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Penugasan tak ditemukan")
    return eng


def _engagement_out(e: Engagement) -> EngagementOut:
    return EngagementOut(
        id=e.id,
        name=e.name,
        client_name=e.client_name,
        description=e.description,
        status=e.status,
        created_by=e.created_by,
    )


@router.post("", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
def create_engagement(
    payload: EngagementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EngagementOut:
    eng = Engagement(
        name=payload.name,
        client_name=payload.client_name,
        description=payload.description,
        created_by=user.id,
    )
    db.add(eng)
    db.commit()
    db.refresh(eng)
    return _engagement_out(eng)


@router.get("", response_model=list[EngagementOut])
def list_engagements(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[EngagementOut]:
    return [_engagement_out(e) for e in db.scalars(select(Engagement)).all()]


@router.get("/{engagement_id}", response_model=EngagementDetailOut)
def get_engagement(
    engagement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EngagementDetailOut:
    e = _get_engagement(db, engagement_id)
    return EngagementDetailOut(
        id=e.id,
        name=e.name,
        client_name=e.client_name,
        description=e.description,
        status=e.status,
        created_by=e.created_by,
        exec_summary_generated=e.exec_summary_generated,
        exec_summary_model=e.exec_summary_model,
        exec_summary_prompt_version=e.exec_summary_prompt_version,
        exec_summary=e.exec_summary,
        baseline_hours=e.baseline_hours,
        baseline_note=e.baseline_note,
    )


@router.post(
    "/{engagement_id}/uploads",
    response_model=ScanUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_scan(
    engagement_id: int,
    file: UploadFile = File(...),
    tool: str = Form("unknown"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanUploadOut:
    _get_engagement(db, engagement_id)
    content = await file.read()

    safe_name = (file.filename or "berkas").replace("/", "_").replace("\\", "_")
    tool_val = tool if tool in {t.value for t in ScanTool} else ScanTool.unknown.value
    key = f"uploads/{engagement_id}/{uuid.uuid4().hex}_{safe_name}"
    put_bytes(key, content, content_type=file.content_type or "application/octet-stream")

    upload = ScanUpload(
        engagement_id=engagement_id,
        filename=safe_name,
        tool=tool_val,
        storage_key=key,
        uploaded_by=user.id,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    # Parsing berjalan asinkron di worker Celery.
    parse_upload.delay(upload.id)

    return ScanUploadOut(
        id=upload.id,
        engagement_id=upload.engagement_id,
        filename=upload.filename,
        tool=upload.tool,
        status=upload.status,
    )


@router.get("/{engagement_id}/uploads", response_model=list[ScanUploadOut])
def list_uploads(
    engagement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ScanUploadOut]:
    _get_engagement(db, engagement_id)
    rows = db.scalars(
        select(ScanUpload).where(ScanUpload.engagement_id == engagement_id)
    ).all()
    return [
        ScanUploadOut(
            id=u.id,
            engagement_id=u.engagement_id,
            filename=u.filename,
            tool=u.tool,
            status=u.status,
            error=u.error,
        )
        for u in rows
    ]


@router.get("/{engagement_id}/findings", response_model=list[FindingOut])
def list_findings(
    engagement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[FindingOut]:
    _get_engagement(db, engagement_id)
    rows = db.scalars(
        select(Finding).where(Finding.engagement_id == engagement_id).order_by(Finding.id)
    ).all()
    out: list[FindingOut] = []
    for f in rows:
        srcs = f.sources or []
        tools = sorted({s.get("tool") for s in srcs if s.get("tool")})
        out.append(
            FindingOut(
                id=f.id,
                engagement_id=f.engagement_id,
                source_upload_id=f.source_upload_id,
                title=f.title,
                severity=f.severity,
                status=f.status,
                cwe=f.cwe,
                cvss_score=f.cvss_score,
                owasp=f.owasp,
                cve=f.cve or [],
                occurrences=f.occurrences or 1,
                tools=tools,
                ai_generated=f.ai_generated,
                priority=f.priority,
                priority_score=f.priority_score,
            )
        )
    return out


def _get_finding(db: Session, engagement_id: int, finding_id: int) -> Finding:
    f = db.get(Finding, finding_id)
    if f is None or f.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Temuan tak ditemukan"
        )
    return f


def _finding_detail(f: Finding) -> FindingDetailOut:
    tools = sorted({s.get("tool") for s in (f.sources or []) if s.get("tool")})
    return FindingDetailOut(
        id=f.id,
        engagement_id=f.engagement_id,
        source_upload_id=f.source_upload_id,
        title=f.title,
        severity=f.severity,
        status=f.status,
        cwe=f.cwe,
        cvss_score=f.cvss_score,
        owasp=f.owasp,
        cve=f.cve or [],
        occurrences=f.occurrences or 1,
        tools=tools,
        ai_generated=f.ai_generated,
        priority=f.priority,
        priority_score=f.priority_score,
        description=f.description,
        cvss_vector=f.cvss_vector,
        ai_model=f.ai_model,
        ai_prompt_version=f.ai_prompt_version,
        ai_draft=f.ai_draft,
        final_narrative=f.final_narrative,
        narrative_edited=f.narrative_edited,
        reviewed_by=f.reviewed_by,
        reviewed_at=f.reviewed_at,
    )


@router.get("/{engagement_id}/findings/{finding_id}", response_model=FindingDetailOut)
def get_finding(
    engagement_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FindingDetailOut:
    _get_engagement(db, engagement_id)
    f = _get_finding(db, engagement_id, finding_id)
    return _finding_detail(f)


@router.post("/{engagement_id}/generate-narratives", response_model=NarrativeJobOut)
def generate_narratives(
    engagement_id: int,
    only_missing: bool = True,
    lang: str = "id",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> NarrativeJobOut:
    """Antrekan pembuatan draf naratif AI untuk temuan (async, per-temuan)."""
    _get_engagement(db, engagement_id)
    rows = db.scalars(
        select(Finding).where(Finding.engagement_id == engagement_id)
    ).all()
    queued = skipped = 0
    for f in rows:
        if only_missing and f.ai_generated:
            skipped += 1
            continue
        generate_narrative.delay(f.id, lang)
        queued += 1
    return NarrativeJobOut(queued=queued, skipped=skipped)


@router.post("/{engagement_id}/exec-summary", response_model=SummaryJobOut)
def queue_exec_summary(
    engagement_id: int,
    lang: str = "id",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SummaryJobOut:
    """Antrekan pembuatan draf ringkasan eksekutif AI untuk penugasan (async)."""
    _get_engagement(db, engagement_id)
    n = db.scalar(
        select(func.count()).select_from(Finding).where(
            Finding.engagement_id == engagement_id
        )
    )
    generate_exec_summary.delay(engagement_id, lang)
    return SummaryJobOut(queued=True, findings=int(n or 0))


@router.post("/{engagement_id}/triage", response_model=TriageResultOut)
def recompute_triage(
    engagement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TriageResultOut:
    """Hitung ulang prioritas deterministik semua temuan (sinkron, cepat)."""
    _get_engagement(db, engagement_id)
    rows = db.scalars(
        select(Finding).where(Finding.engagement_id == engagement_id)
    ).all()
    for f in rows:
        t = triage(
            f.severity,
            cvss_score=f.cvss_score,
            occurrences=f.occurrences or 1,
            cve=f.cve or [],
        )
        f.priority = t.priority
        f.priority_score = t.score
    db.commit()
    return TriageResultOut(triaged=len(rows))


# --------------------------------------------------------------------------- #
# D13: review temuan — editor naratif, alur status, riwayat versi
# --------------------------------------------------------------------------- #
_ACTION_FOR_STATUS = {
    "in_review": "submit",
    "approved": "approve",
    "rejected": "reject",
    "false_positive": "false_positive",
    "draft": "reopen",
}


def _add_revision(
    db: Session,
    f: Finding,
    *,
    action: str,
    note: str | None,
    author_id: int | None,
    narrative: dict | None = None,
) -> None:
    db.add(
        FindingRevision(
            finding_id=f.id,
            action=action,
            status=f.status,
            narrative=narrative,
            note=note,
            author_id=author_id,
        )
    )


@router.put(
    "/{engagement_id}/findings/{finding_id}/narrative", response_model=FindingDetailOut
)
def edit_narrative(
    engagement_id: int,
    finding_id: int,
    payload: NarrativeEditIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "auditor", "admin")),
) -> FindingDetailOut:
    """Simpan naratif final hasil suntingan auditor (menang atas draf AI).

    Menandai `narrative_edited` dan mencatat revisi. Tak mengubah status.
    """
    _get_engagement(db, engagement_id)
    f = _get_finding(db, engagement_id, finding_id)
    narrative = {
        "description": payload.description.strip(),
        "impact": payload.impact.strip(),
        "recommendation": payload.recommendation.strip(),
    }
    f.final_narrative = narrative
    f.narrative_edited = True
    _add_revision(
        db, f, action="edit", note=payload.note, author_id=user.id, narrative=narrative
    )
    db.commit()
    db.refresh(f)
    return _finding_detail(f)


@router.post(
    "/{engagement_id}/findings/{finding_id}/status", response_model=FindingDetailOut
)
def change_status(
    engagement_id: int,
    finding_id: int,
    payload: StatusChangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FindingDetailOut:
    """Pindahkan status temuan mengikuti mesin status + batas persetujuan peran."""
    _get_engagement(db, engagement_id)
    f = _get_finding(db, engagement_id, finding_id)
    target = payload.status
    if not is_valid_status(target):
        raise HTTPException(status_code=422, detail=f"Status tak dikenal: {target}")
    if not can_transition(f.status, target):
        raise HTTPException(
            status_code=409,
            detail=f"Transisi tak diizinkan: {f.status} → {target}",
        )
    if not role_allows_transition(user.role.name, target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keputusan ini memerlukan peran auditor.",
        )
    f.status = target
    f.reviewed_by = user.id
    f.reviewed_at = datetime.now(UTC)
    _add_revision(
        db, f, action=_ACTION_FOR_STATUS.get(target, target),
        note=payload.note, author_id=user.id,
    )
    db.commit()
    db.refresh(f)
    return _finding_detail(f)


@router.get(
    "/{engagement_id}/findings/{finding_id}/revisions",
    response_model=list[FindingRevisionOut],
)
def list_revisions(
    engagement_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[FindingRevisionOut]:
    """Riwayat revisi naratif & status temuan (terbaru dahulu)."""
    _get_engagement(db, engagement_id)
    _get_finding(db, engagement_id, finding_id)
    rows = db.scalars(
        select(FindingRevision)
        .where(FindingRevision.finding_id == finding_id)
        .order_by(FindingRevision.id.desc())
    ).all()
    return [
        FindingRevisionOut(
            id=r.id,
            action=r.action,
            status=r.status,
            narrative=r.narrative,
            note=r.note,
            author_id=r.author_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# D14: lampiran bukti temuan (screenshot/PoC) di MinIO
# --------------------------------------------------------------------------- #
_MAX_EVIDENCE_BYTES = 20 * 1024 * 1024  # 20 MB per berkas


def _attachment_out(a: FindingAttachment) -> AttachmentOut:
    return AttachmentOut(
        id=a.id,
        finding_id=a.finding_id,
        filename=a.filename,
        content_type=a.content_type,
        size=a.size,
        uploaded_by=a.uploaded_by,
        created_at=a.created_at,
    )


@router.get(
    "/{engagement_id}/findings/{finding_id}/attachments",
    response_model=list[AttachmentOut],
)
def list_attachments(
    engagement_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AttachmentOut]:
    _get_engagement(db, engagement_id)
    _get_finding(db, engagement_id, finding_id)
    rows = db.scalars(
        select(FindingAttachment)
        .where(FindingAttachment.finding_id == finding_id)
        .order_by(FindingAttachment.id.desc())
    ).all()
    return [_attachment_out(a) for a in rows]


@router.post(
    "/{engagement_id}/findings/{finding_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    engagement_id: int,
    finding_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "auditor", "admin")),
) -> AttachmentOut:
    """Unggah lampiran bukti sebuah temuan ke MinIO."""
    _get_engagement(db, engagement_id)
    f = _get_finding(db, engagement_id, finding_id)
    content = await file.read()
    if len(content) > _MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=413, detail="Berkas terlalu besar (maks 20 MB).")
    safe_name = (file.filename or "bukti").replace("/", "_").replace("\\", "_")
    key = f"evidence/{engagement_id}/{finding_id}/{uuid.uuid4().hex}_{safe_name}"
    put_bytes(key, content, content_type=file.content_type or "application/octet-stream")
    att = FindingAttachment(
        finding_id=f.id,
        filename=safe_name,
        storage_key=key,
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
        uploaded_by=user.id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return _attachment_out(att)


@router.get(
    "/{engagement_id}/findings/{finding_id}/attachments/{attachment_id}/download",
)
def download_attachment(
    engagement_id: int,
    finding_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Unduh berkas lampiran (stream byte dari MinIO)."""
    _get_engagement(db, engagement_id)
    _get_finding(db, engagement_id, finding_id)
    a = db.get(FindingAttachment, attachment_id)
    if a is None or a.finding_id != finding_id:
        raise HTTPException(status_code=404, detail="Lampiran tak ditemukan")
    data = get_bytes(a.storage_key)
    return Response(
        content=data,
        media_type=a.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{a.filename}"'},
    )


@router.delete(
    "/{engagement_id}/findings/{finding_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_attachment(
    engagement_id: int,
    finding_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("analyst", "auditor", "admin")),
) -> Response:
    """Hapus lampiran bukti (baris DB + objek MinIO)."""
    _get_engagement(db, engagement_id)
    _get_finding(db, engagement_id, finding_id)
    a = db.get(FindingAttachment, attachment_id)
    if a is None or a.finding_id != finding_id:
        raise HTTPException(status_code=404, detail="Lampiran tak ditemukan")
    remove_object(a.storage_key)
    db.delete(a)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# D15: generator laporan DOCX (letterhead brand runtime)
# --------------------------------------------------------------------------- #
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MAX_EVIDENCE_IMAGES = 5  # batasi gambar per temuan agar laporan tak membengkak


def _evidence_uris(db: Session, finding_id: int) -> list[str]:
    """Data URI untuk lampiran gambar sebuah temuan (untuk disematkan ke laporan)."""
    rows = db.scalars(
        select(FindingAttachment)
        .where(FindingAttachment.finding_id == finding_id)
        .order_by(FindingAttachment.id)
    ).all()
    uris: list[str] = []
    for a in rows:
        if not (a.content_type or "").startswith("image/"):
            continue
        if len(uris) >= _MAX_EVIDENCE_IMAGES:
            break
        try:
            b64 = base64.b64encode(get_bytes(a.storage_key)).decode("ascii")
        except Exception:  # noqa: BLE001,S112 — lewati bukti yang gagal diambil
            continue
        uris.append(f"data:{a.content_type};base64,{b64}")
    return uris


def _assemble_report(
    db: Session, engagement_id: int, include: str, *, with_evidence: bool
) -> tuple[ReportData, object]:
    """Susun ReportData + branding; sematkan bukti gambar bila diminta."""
    eng = _get_engagement(db, engagement_id)
    findings = db.scalars(
        select(Finding).where(Finding.engagement_id == engagement_id)
    ).all()
    brand = load_branding()
    data = build_report_data(
        eng,
        list(findings),
        org_name=brand.org_name,
        report_title=brand.report_title,
        include="all" if include == "all" else "approved",
        exec_summary=eng.exec_summary,
    )
    if with_evidence:
        for rf in data.findings:
            rf.evidence = _evidence_uris(db, rf.finding_id)
    return data, brand


def _safe_name(name: str | None) -> str:
    return (name or "laporan").replace("/", "_").replace("\\", "_").replace('"', "")


@router.get("/{engagement_id}/evaluation")
def engagement_evaluation(
    engagement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Metrik evaluasi terukur (efisiensi dedup, cakupan AI, kemajuan review) — D17."""
    _get_engagement(db, engagement_id)
    rows = db.scalars(
        select(Finding).where(Finding.engagement_id == engagement_id)
    ).all()
    return evaluate_engagement(list(rows))


@router.get("/{engagement_id}/timing")
def engagement_timing(
    engagement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Metrik waktu penyusunan laporan (Modul 1) dari jejak revisi temuan."""
    eng = _get_engagement(db, engagement_id)
    rows = db.scalars(
        select(FindingRevision)
        .join(Finding, FindingRevision.finding_id == Finding.id)
        .where(Finding.engagement_id == engagement_id)
        .order_by(FindingRevision.created_at)
    ).all()
    return timing_summary(list(rows), baseline_hours=eng.baseline_hours)


@router.put("/{engagement_id}/baseline")
def set_engagement_baseline(
    engagement_id: int,
    payload: BaselineIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("auditor", "admin")),
) -> dict:
    """Isi angka pembanding waktu penyusunan manual (Modul 1).

    Hanya auditor/admin: angka ini menjadi dasar klaim penghematan pada laporan
    evaluasi, sehingga bukan pekerjaan analisis harian.
    """
    eng = _get_engagement(db, engagement_id)
    eng.baseline_hours = payload.baseline_hours
    eng.baseline_note = payload.baseline_note
    db.commit()
    return {
        "baseline_hours": eng.baseline_hours,
        "baseline_note": eng.baseline_note,
    }


@router.get("/{engagement_id}/report.docx")
def download_report_docx(
    engagement_id: int,
    include: str = "approved",
    lang: str = "id",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Unduh laporan DOCX (default: hanya temuan disetujui; `include=all` untuk semua)."""
    data, brand = _assemble_report(db, engagement_id, include, with_evidence=False)
    blob = render_docx(data, accent=brand.accent, lang=lang)
    return Response(
        content=blob,
        media_type=_DOCX_MIME,
        headers={
            "Content-Disposition": (
                f'attachment; filename="AuditForge_{_safe_name(data.engagement_name)}.docx"'
            )
        },
    )


@router.get("/{engagement_id}/report.html")
def preview_report_html(
    engagement_id: int,
    include: str = "approved",
    lang: str = "id",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Pratinjau laporan sebagai HTML (charts + bukti gambar tersemat)."""
    data, brand = _assemble_report(db, engagement_id, include, with_evidence=True)
    html = render_html(data, accent=brand.accent, lang=lang)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/{engagement_id}/report.pdf")
def download_report_pdf(
    engagement_id: int,
    include: str = "approved",
    lang: str = "id",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Unduh laporan PDF (WeasyPrint) — charts house-style + bukti gambar tersemat."""
    data, brand = _assemble_report(db, engagement_id, include, with_evidence=True)
    html = render_html(data, accent=brand.accent, lang=lang)
    blob = render_pdf(html)
    return Response(
        content=blob,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="AuditForge_{_safe_name(data.engagement_name)}.pdf"'
            )
        },
    )

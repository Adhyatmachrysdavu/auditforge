"""Router administrasi — konfigurasi LLM runtime (D9/R2). Hanya untuk admin."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.config_store import load_llm_config, save_llm_config
from app.ai.llm import preview_masked
from app.ai.providers import AINotConfigured, get_provider
from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.reporting.branding import load_branding, save_branding

router = APIRouter(prefix="/admin", tags=["admin"])

_admin_only = require_roles("admin")


def _mask_key(key: str | None) -> str:
    """Tampilkan key secara aman: awalan + **** + 4 karakter terakhir."""
    if not key:
        return ""
    if len(key) <= 12:
        return "****"
    return f"{key[:9]}****{key[-4:]}"


class LlmConfigOut(BaseModel):
    format: str
    base_url: str
    model: str
    api_key_set: bool
    api_key_masked: str


class LlmConfigUpdate(BaseModel):
    format: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # kosong/absen → tak mengubah key yang ada
    model: str | None = None


class LlmTestResult(BaseModel):
    status: str
    provider: str
    model: str
    detail: str | None = None


def _current_out() -> LlmConfigOut:
    cfg = load_llm_config()
    return LlmConfigOut(
        format=cfg.format,
        base_url=cfg.base_url,
        model=cfg.model,
        api_key_set=bool(cfg.api_key),
        api_key_masked=_mask_key(cfg.api_key),
    )


@router.get("/llm", response_model=LlmConfigOut)
def get_llm_config(_: User = Depends(_admin_only)) -> LlmConfigOut:
    """Konfigurasi LLM efektif (key tak pernah dikembalikan utuh)."""
    return _current_out()


@router.put("/llm", response_model=LlmConfigOut)
def update_llm_config(
    payload: LlmConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_admin_only),
) -> LlmConfigOut:
    """Simpan konfigurasi LLM ke DB (menimpa `.env`). Berlaku tanpa restart."""
    # Key kosong ("") diperlakukan sebagai "jangan ubah".
    api_key = payload.api_key or None
    save_llm_config(
        db,
        format=payload.format,
        base_url=payload.base_url,
        api_key=api_key,
        model=payload.model,
    )
    return _current_out()


@router.post("/llm/test", response_model=LlmTestResult)
def test_llm_connection(_: User = Depends(_admin_only)) -> LlmTestResult:
    """Uji koneksi ke LLM aktif (ping). Melaporkan status sebagai data, tak crash."""
    provider = get_provider()
    try:
        reply = provider.ping()
        return LlmTestResult(
            status="ok", provider=provider.name, model=provider.model, detail=reply[:200]
        )
    except AINotConfigured as exc:
        return LlmTestResult(
            status="unconfigured", provider=provider.name, model=provider.model,
            detail=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 — laporkan sebagai status
        return LlmTestResult(
            status="error", provider=provider.name, model=provider.model, detail=str(exc)
        )


# --------------------------------------------------------------------------- #
# D15: branding/letterhead laporan
# --------------------------------------------------------------------------- #
class BrandingOut(BaseModel):
    org_name: str
    report_title: str
    accent: str


class BrandingUpdate(BaseModel):
    org_name: str | None = None
    report_title: str | None = None
    accent: str | None = None


@router.get("/branding", response_model=BrandingOut)
def get_branding(_: User = Depends(_admin_only)) -> BrandingOut:
    """Branding/letterhead laporan yang berlaku (DB → .env)."""
    b = load_branding()
    return BrandingOut(org_name=b.org_name, report_title=b.report_title, accent=b.accent)


@router.put("/branding", response_model=BrandingOut)
def update_branding(
    payload: BrandingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_admin_only),
) -> BrandingOut:
    """Simpan branding laporan ke DB (menimpa `.env`). Berlaku tanpa restart."""
    save_branding(
        db,
        org_name=payload.org_name or None,
        report_title=payload.report_title or None,
        accent=payload.accent or None,
    )
    b = load_branding()
    return BrandingOut(org_name=b.org_name, report_title=b.report_title, accent=b.accent)


# --------------------------------------------------------------------------- #
# D17: transparansi masking + pelihat jejak audit
# --------------------------------------------------------------------------- #
class MaskingPreviewIn(BaseModel):
    text: str = Field(max_length=20000)


class MaskingPreviewOut(BaseModel):
    masked: str


@router.post("/masking-preview", response_model=MaskingPreviewOut)
def masking_preview(
    payload: MaskingPreviewIn, _: User = Depends(_admin_only)
) -> MaskingPreviewOut:
    """Tampilkan versi tersamar dari teks — bukti apa yang keluar ke LLM (tanpa memanggil LLM)."""
    return MaskingPreviewOut(masked=preview_masked(payload.text))


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    action: str
    method: str
    path: str
    status_code: int | None
    created_at: datetime | None = None


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(_admin_only),
) -> list[AuditLogOut]:
    """Jejak audit terbaru (aksi mutasi tercatat middleware) — hanya admin."""
    limit = max(1, min(limit, 200))
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    ).all()
    return [
        AuditLogOut(
            id=r.id,
            user_id=r.user_id,
            action=r.action,
            method=r.method,
            path=r.path,
            status_code=r.status_code,
            created_at=r.created_at,
        )
        for r in rows
    ]

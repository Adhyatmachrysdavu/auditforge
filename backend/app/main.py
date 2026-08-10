"""Titik masuk API AuditForge (FastAPI).

Sprint 1 / D1: endpoint health + pemeriksaan akses AI. Modul domain (parser,
enrichment, review, report) menyusul pada sprint berikutnya.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.ai.providers import AINotConfigured, get_provider
from app.api.routes import admin as admin_routes
from app.api.routes import auth as auth_routes
from app.api.routes import engagements as engagement_routes
from app.api.routes import findings as findings_routes
from app.api.routes import ingest as ingest_routes
from app.api.routes import knowledge as knowledge_routes
from app.api.routes import stats as stats_routes
from app.api.routes import users as users_routes
from app.core.audit import AuditMiddleware
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version=__version__)

# Izinkan frontend (dev) memanggil API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Jejak audit: catat semua aksi mutasi ke tabel audit_logs.
app.add_middleware(AuditMiddleware)

# Router domain.
app.include_router(auth_routes.router)
app.include_router(users_routes.router)
app.include_router(engagement_routes.router)
app.include_router(findings_routes.router)
app.include_router(knowledge_routes.router)
app.include_router(ingest_routes.router)
app.include_router(stats_routes.router)
app.include_router(admin_routes.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}


@app.get("/health/ai")
def health_ai() -> dict[str, str]:
    """Memverifikasi akses ke provider AI aktif (Anthropic/Ollama).

    Tidak pernah menggagalkan proses: status dilaporkan sebagai data, bukan error.
    """
    provider = get_provider()
    try:
        reply = provider.ping()
        return {
            "status": "ok",
            "provider": provider.name,
            "model": provider.model,
            "reply": reply,
        }
    except AINotConfigured as exc:
        return {"status": "unconfigured", "provider": provider.name, "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 — laporkan sebagai status, jangan crash
        return {
            "status": "error",
            "provider": provider.name,
            "model": provider.model,
            "detail": str(exc),
        }

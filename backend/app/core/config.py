"""Konfigurasi aplikasi.

Nilai dibaca dari environment (dan berkas .env). Tidak ada rahasia yang
di-hardcode di dalam kode.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AuditForge"
    environment: str = "development"

    # Basis data & broker
    database_url: str = "postgresql+psycopg://auditforge:auditforge@postgres:5432/auditforge"
    redis_url: str = "redis://redis:6379/0"

    # Penyimpanan objek
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "auditforge"
    minio_secret_key: str = "auditforge-secret"
    minio_bucket: str = "auditforge"
    minio_secure: bool = False

    # Kecerdasan buatan — LLM agnostik (D9)
    #   ai_format: "openai" (OpenAI-compatible: OpenRouter/Ollama/OpenAI) | "anthropic" (Claude)
    ai_format: str = "openai"
    ai_base_url: str = "https://openrouter.ai/api/v1"
    ai_api_key: str | None = None
    ai_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Provider lama (fallback via ai_provider bila ai_format tak dipakai)
    ai_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3"

    # Keamanan / autentikasi (JWT). GANTI secret_key di produksi lewat env.
    secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 jam

    # Branding laporan / letterhead (D15) — dapat ditimpa runtime via app_settings.
    brand_org_name: str = "PT Suryasoft Konsultama"
    brand_report_title: str = "Laporan Audit Keamanan"
    brand_accent: str = "#1E5F9F"

    # Auto-ingest folder terpantau (R3). Watcher (Celery beat) memindai
    #   <watch_dir>/inbox/<engagement_id>/*  → parsing otomatis (deteksi perkakas
    #   via sniff), lalu berkas dipindah ke processed/ atau failed/.
    watch_enabled: bool = True
    watch_dir: str = "/watch"
    watch_interval_seconds: float = 30.0  # frekuensi pemindaian beat
    watch_settle_seconds: float = 5.0  # abaikan berkas yang baru ditulis (hindari parsial)

    # Kredensial admin awal (dipakai skrip seed sekali). Ganti di produksi.
    seed_admin_email: str = "admin@auditforge.local"
    seed_admin_password: str = "admin12345"
    seed_admin_name: str = "Administrator"


@lru_cache
def get_settings() -> Settings:
    return Settings()

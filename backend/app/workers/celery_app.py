"""Aplikasi Celery untuk proses latar (parsing berkas, pemanggilan AI, dll.)."""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "auditforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(task_track_started=True)

# Auto-ingest (R3): jadwal beat memindai folder terpantau secara berkala.
# Jadwal hanya berlaku bila proses `celery beat` dijalankan (service `beat`).
if settings.watch_enabled:
    celery_app.conf.beat_schedule = {
        "scan-inbox": {
            "task": "auditforge.scan_inbox",
            "schedule": settings.watch_interval_seconds,
        }
    }


@celery_app.task(name="auditforge.ping")
def ping() -> str:
    """Task sanity-check: memastikan worker & broker menyala."""
    return "pong"

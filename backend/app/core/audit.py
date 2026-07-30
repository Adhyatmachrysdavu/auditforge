"""Middleware jejak audit.

Mencatat setiap aksi mutasi (POST/PUT/PATCH/DELETE) ke tabel `audit_logs`:
metode, path, kode status, IP, dan pengguna (bila token bearer valid).
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.method in _MUTATING:
            self._record(request, response.status_code)
        return response

    @staticmethod
    def _record(request: Request, status_code: int) -> None:
        user_id = _user_id_from_header(request.headers.get("authorization", ""))
        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=request.method.lower(),
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    ip=request.client.host if request.client else None,
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001 — audit tak boleh menggagalkan request
            db.rollback()
        finally:
            db.close()


def _user_id_from_header(authorization: str) -> int | None:
    if not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = decode_access_token(authorization.split(" ", 1)[1])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except Exception:  # noqa: BLE001 — token tak valid → anonim
        return None

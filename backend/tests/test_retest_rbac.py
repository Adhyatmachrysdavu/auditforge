"""Uji unit R4 — gerbang peran pada endpoint retest (tanpa DB, tanpa jaringan).

KENAPA INI ADA. Spec bagian 10 menuntut satu penolakan yang harus tetap berlaku:
analis dilarang menegaskan remediasi. Penolakan itu hidup di lapisan route, yang
tak disentuh satu pun tes lain, dan hanya pernah dibuktikan sekali secara manual.
Bila `require_roles("auditor", "admin")` suatu saat berubah keliru, tak ada yang
menangkapnya: seluruh tes tetap hijau dan endpoint-nya tetap membalas 200.

Yang diuji di sini bukan deklarasinya, melainkan perilakunya. Dependency-nya
diambil dari pohon route FastAPI yang sesungguhnya lalu dipanggil langsung
dengan pengguna palsu, sehingga penggantian dependency maupun pelonggaran daftar
peran sama-sama membuat tes ini jatuh.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.engagements import router

# Endpoint retest yang keputusannya milik auditor, bukan analis.
JALUR_RETEST = [
    ("POST", "/engagements/{engagement_id}/rounds"),
    ("PATCH", "/engagements/{engagement_id}/findings/{finding_id}/remediation"),
]


def _penjaga_peran(metode: str, jalur: str):
    """Ambil dependency `require_roles` yang benar-benar terpasang di route."""
    for route in router.routes:
        if getattr(route, "path", None) == jalur and metode in getattr(route, "methods", set()):
            penjaga = [
                d.call
                for d in route.dependant.dependencies
                if getattr(d.call, "__name__", "") == "checker"
            ]
            assert penjaga, f"{metode} {jalur} tak punya penjaga peran sama sekali"
            assert len(penjaga) == 1, f"{metode} {jalur} punya lebih dari satu penjaga peran"
            return penjaga[0]
    raise AssertionError(f"route {metode} {jalur} tak ditemukan")


def _pengguna(peran: str):
    return SimpleNamespace(id=1, role=SimpleNamespace(name=peran))


@pytest.mark.parametrize(("metode", "jalur"), JALUR_RETEST)
def test_analis_ditolak(metode: str, jalur: str):
    penjaga = _penjaga_peran(metode, jalur)
    with pytest.raises(HTTPException) as exc:
        penjaga(_pengguna("analyst"))
    assert exc.value.status_code == 403


@pytest.mark.parametrize(("metode", "jalur"), JALUR_RETEST)
@pytest.mark.parametrize("peran", ["auditor", "admin"])
def test_auditor_dan_admin_lolos(metode: str, jalur: str, peran: str):
    penjaga = _penjaga_peran(metode, jalur)
    assert penjaga(_pengguna(peran)).role.name == peran


@pytest.mark.parametrize(("metode", "jalur"), JALUR_RETEST)
def test_peran_tak_dikenal_ditolak(metode: str, jalur: str):
    # Fail-closed: peran asing tak pernah lolos, termasuk yang kosong.
    penjaga = _penjaga_peran(metode, jalur)
    for peran in ("", "superuser", "viewer"):
        with pytest.raises(HTTPException) as exc:
            penjaga(_pengguna(peran))
        assert exc.value.status_code == 403

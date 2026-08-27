"""Uji unit R4 — penandaan putaran saat ingest (tanpa DB sungguhan)."""
from __future__ import annotations

from app.workers.tasks import tandai_putaran


def test_putaran_baru_ditambahkan():
    assert tandai_putaran([1], 2) == [1, 2]


def test_putaran_yang_sama_tidak_digandakan():
    # Dua berkas dalam satu putaran tidak boleh menghasilkan [2, 2].
    assert tandai_putaran([1, 2], 2) == [1, 2]


def test_daftar_kosong_terisi():
    assert tandai_putaran([], 1) == [1]
    assert tandai_putaran(None, 3) == [3]


def test_hasil_selalu_urut_dan_unik():
    assert tandai_putaran([3, 1, 3], 2) == [1, 2, 3]


def test_mengembalikan_daftar_baru_bukan_daftar_yang_sama():
    # Penting: SQLAlchemy hanya mendeteksi perubahan bila kolom ditugaskan
    # ulang dengan objek baru, bukan dimutasi di tempat.
    awal = [1]
    hasil = tandai_putaran(awal, 2)
    assert hasil is not awal
    assert awal == [1]

# Verifikasi Remediasi (Retest) Berbasis Putaran — Rencana Implementasi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auditor dapat membuka putaran retest pada penugasan yang sama, memasukkan hasil pemindaian ulang, lalu menegaskan mana temuan yang tertutup, masih terbuka, atau kambuh — dan status yang ditegaskan itu tercetak di laporan.

**Architecture:** Satu kerentanan tetap satu baris `findings`. Tiap penampakan dicap nomor putaran di `findings.rounds_seen`, sehingga ketidakhadiran di putaran terbaru dapat dibaca tanpa menduplikasi temuan. Usulan status dihitung ulang tiap kali dibaca oleh modul murni `app/retest.py`; yang tersimpan hanya keputusan auditor.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · pytest · Next.js 14 · TypeScript

**Spec:** `docs/superpowers/specs/2026-08-18-retest-putaran-design.md`

## Global Constraints

- **Docstring dan komentar berbahasa Indonesia**; identifier, tipe, dan nama field API berbahasa Inggris. Jangan menerjemahkan prosa Indonesia yang sudah ada, jangan mengganti nama simbol menjadi Indonesia.
- **Seluruh tes murni**: tanpa DB, Redis, MinIO, maupun LLM. Tidak ada `conftest.py`. Baris ORM dipalsukan dengan `types.SimpleNamespace` (lihat `backend/tests/test_reporting.py`).
- **Tag requirement `R4`** pada modul dan tes baru, mengikuti kebiasaan repo (`D7` dedup, `D11` triase, `R3` auto-ingest).
- **Kolom daftar ditugaskan ulang, bukan dimutasi**: `row.rounds_seen = [...]`, agar SQLAlchemy mendeteksi perubahan.
- **Setiap teks UI baru wajib ada di kedua lokal** `id` dan `en` pada `frontend/src/i18n/messages.ts`. Tipe `MessageKey` membuat `tsc` gagal bila satu lokal terlewat.
- **Nilai status remediasi**: `not_tested`, `open`, `fixed`, `recurring`. Disimpan sebagai `String(20)`, divalidasi di lapisan aplikasi.
- **Gerbang wajib hijau sebelum tiap commit terakhir tugas**: `docker exec auditforge-api-1 python -m pytest -q` dan `docker exec auditforge-web-1 npx tsc --noEmit`.
- **Setelah mengubah kode task Celery, restart kontainer `worker` dan `beat`** — keduanya tidak hot-reload.
- Migrasi dijalankan dengan `docker exec auditforge-api-1 alembic upgrade head`.

---

### Task 1: Modul murni `app/retest.py`

Jantung fitur. Tanpa DB, tanpa LLM, dapat diuji sepenuhnya sendiri. Dikerjakan lebih dulu supaya tugas berikutnya tinggal memanggilnya.

**Files:**
- Create: `backend/app/retest.py`
- Test: `backend/tests/test_retest.py`

**Interfaces:**
- Consumes: tidak ada.
- Produces:
  - `STATUS_NOT_TESTED = "not_tested"`, `STATUS_OPEN = "open"`, `STATUS_FIXED = "fixed"`, `STATUS_RECURRING = "recurring"`
  - `VALID_STATUSES: frozenset[str]`
  - `propose(rounds_seen: list[int] | None, current_round: int) -> str`
  - `is_new_in_round(rounds_seen: list[int] | None, current_round: int) -> bool`
  - `is_stale(confirmed_status: str | None, confirmed_round: int | None, rounds_seen: list[int] | None, current_round: int) -> bool`
  - `effective_status(confirmed_status: str | None, confirmed_round: int | None, rounds_seen: list[int] | None, current_round: int) -> str | None`
  - `summarize(rows: Iterable[object], current_round: int) -> dict[str, int]`

> Catatan penyempurnaan terhadap spec bagian 4: `summarize` menerima `current_round` sebagai argumen kedua. Tanpa itu ia tak dapat memanggil `effective_status`.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_retest.py`:

```python
"""Uji unit R4 — verifikasi remediasi berbasis putaran (tanpa DB, tanpa LLM)."""
from __future__ import annotations

from types import SimpleNamespace

from app.retest import (
    STATUS_FIXED,
    STATUS_NOT_TESTED,
    STATUS_OPEN,
    STATUS_RECURRING,
    effective_status,
    is_new_in_round,
    is_stale,
    propose,
    summarize,
)


def test_putaran_satu_belum_ada_pembanding():
    assert propose([1], 1) == STATUS_NOT_TESTED


def test_rounds_seen_kosong_dianggap_belum_diuji():
    # Data lama sebelum kolom ini ada; jangan menyimpulkan apa pun.
    assert propose([], 3) == STATUS_NOT_TESTED
    assert propose(None, 3) == STATUS_NOT_TESTED


def test_tak_terlihat_di_putaran_berjalan_berarti_tertutup():
    assert propose([1], 2) == STATUS_FIXED


def test_masih_terlihat_berarti_terbuka():
    assert propose([1, 2], 2) == STATUS_OPEN


def test_temuan_baru_di_putaran_belakangan_juga_terbuka():
    # Pertama terlihat di putaran 2; tak ada putaran terlewat sebelum itu.
    assert propose([2], 2) == STATUS_OPEN


def test_putaran_terlewat_di_tengah_berarti_kambuh():
    assert propose([1, 3], 3) == STATUS_RECURRING


def test_terlihat_berturut_turut_bukan_kambuh():
    assert propose([1, 2, 3], 3) == STATUS_OPEN


def test_baru_di_putaran_ini():
    assert is_new_in_round([2, 3], 2) is True
    assert is_new_in_round([1, 2], 2) is False
    assert is_new_in_round([], 2) is False


def test_penegasan_dibantah_putaran_berikutnya_jadi_kedaluwarsa():
    # Ditegaskan tertutup di putaran 2, lalu terlihat lagi di putaran 3.
    assert is_stale(STATUS_FIXED, 2, [1, 3], 3) is True
    assert effective_status(STATUS_FIXED, 2, [1, 3], 3) is None


def test_penegasan_yang_masih_sejalan_tidak_kedaluwarsa():
    assert is_stale(STATUS_OPEN, 2, [1, 2, 3], 3) is False
    assert effective_status(STATUS_OPEN, 2, [1, 2, 3], 3) == STATUS_OPEN


def test_penegasan_pada_putaran_berjalan_tidak_pernah_kedaluwarsa():
    assert is_stale(STATUS_FIXED, 3, [1], 3) is False


def test_belum_ditegaskan_bukan_kedaluwarsa_dan_tak_berlaku():
    assert is_stale(None, None, [1, 2], 2) is False
    assert effective_status(None, None, [1, 2], 2) is None


def test_summarize_hanya_menghitung_status_yang_berlaku():
    rows = [
        # ditegaskan tertutup di putaran 2, masih sejalan
        SimpleNamespace(remediation_status=STATUS_FIXED, remediation_confirmed_round=2,
                        rounds_seen=[1]),
        # ditegaskan terbuka, masih sejalan
        SimpleNamespace(remediation_status=STATUS_OPEN, remediation_confirmed_round=2,
                        rounds_seen=[1, 2]),
        # belum ditegaskan → tidak dihitung
        SimpleNamespace(remediation_status=None, remediation_confirmed_round=None,
                        rounds_seen=[1, 2]),
    ]
    assert summarize(rows, 2) == {
        STATUS_FIXED: 1,
        STATUS_OPEN: 1,
        STATUS_RECURRING: 0,
        STATUS_NOT_TESTED: 0,
    }
```

- [ ] **Step 2: Jalankan tes untuk memastikan ia gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_retest.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retest'`

- [ ] **Step 3: Tulis implementasi minimal**

Buat `backend/app/retest.py`:

```python
"""R4 — verifikasi remediasi (retest) berbasis putaran.

Deterministik dan murni: tanpa basis data, tanpa LLM. Usulan status TIDAK
disimpan, melainkan dihitung ulang tiap kali dibaca, sehingga tak mungkin
basi. Yang tersimpan di basis data hanya keputusan auditor.

Desain: docs/superpowers/specs/2026-08-18-retest-putaran-design.md
"""
from __future__ import annotations

from collections.abc import Iterable

STATUS_NOT_TESTED = "not_tested"
STATUS_OPEN = "open"
STATUS_FIXED = "fixed"
STATUS_RECURRING = "recurring"

VALID_STATUSES = frozenset(
    {STATUS_NOT_TESTED, STATUS_OPEN, STATUS_FIXED, STATUS_RECURRING}
)


def _bersih(rounds_seen: list[int] | None) -> list[int]:
    """Urutkan dan buang duplikat. JSON dari DB bisa memuat apa saja."""
    return sorted({int(r) for r in (rounds_seen or [])})


def propose(rounds_seen: list[int] | None, current_round: int) -> str:
    """Usulan status remediasi dari riwayat penampakan.

    Ini USULAN, bukan penetapan. Ketidakhadiran sebuah temuan di putaran
    terbaru bukan bukti ia sudah diperbaiki: cakupan pemindaian bisa berbeda,
    target bisa sedang mati, atau perkakas kebetulan tak mendeteksi.
    """
    rounds = _bersih(rounds_seen)
    if current_round <= 1 or not rounds:
        return STATUS_NOT_TESTED
    if current_round not in rounds:
        return STATUS_FIXED
    # Terlihat di putaran berjalan. Kambuh bila ada putaran yang terlewat
    # antara penampakan pertama dan sekarang.
    awal = rounds[0]
    terlewat = any(r not in rounds for r in range(awal + 1, current_round))
    return STATUS_RECURRING if terlewat else STATUS_OPEN


def is_new_in_round(rounds_seen: list[int] | None, current_round: int) -> bool:
    """True bila temuan ini pertama kali terlihat pada putaran berjalan.

    Bukan status tersendiri — temuan baru memang terbuka — melainkan penanda
    tampilan agar auditor tahu mana yang muncul akibat perbaikan yang keliru.
    """
    rounds = _bersih(rounds_seen)
    return bool(rounds) and rounds[0] == current_round


def is_stale(
    confirmed_status: str | None,
    confirmed_round: int | None,
    rounds_seen: list[int] | None,
    current_round: int,
) -> bool:
    """True bila penegasan lama sudah dibantah putaran yang lebih baru.

    Penegasan tidak pernah dihapus — ia benar pada saat diberikan, dan
    menghapus keputusan manusia diam-diam merusak keterlacakan.
    """
    if not confirmed_status:
        return False
    if confirmed_round is None or confirmed_round >= current_round:
        return False
    return propose(rounds_seen, current_round) != confirmed_status


def effective_status(
    confirmed_status: str | None,
    confirmed_round: int | None,
    rounds_seen: list[int] | None,
    current_round: int,
) -> str | None:
    """Status yang berlaku untuk laporan. None = belum ditegaskan atau kedaluwarsa."""
    if not confirmed_status:
        return None
    if is_stale(confirmed_status, confirmed_round, rounds_seen, current_round):
        return None
    return confirmed_status


def summarize(rows: Iterable[object], current_round: int) -> dict[str, int]:
    """Hitung temuan per status yang BERLAKU. Usulan tak pernah ikut terhitung."""
    counts = {
        STATUS_FIXED: 0,
        STATUS_OPEN: 0,
        STATUS_RECURRING: 0,
        STATUS_NOT_TESTED: 0,
    }
    for r in rows:
        st = effective_status(
            getattr(r, "remediation_status", None),
            getattr(r, "remediation_confirmed_round", None),
            getattr(r, "rounds_seen", None),
            current_round,
        )
        if st in counts:
            counts[st] += 1
    return counts
```

- [ ] **Step 4: Jalankan tes untuk memastikan ia lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_retest.py -q`
Expected: PASS, 13 tes

- [ ] **Step 5: Jalankan seluruh suite**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS, 235 tes (222 sebelumnya + 13 baru)

- [ ] **Step 6: Commit**

```bash
git add backend/app/retest.py backend/tests/test_retest.py
git commit -m "feat(retest): modul murni R4 untuk usulan status remediasi

Menghitung usulan dari riwayat penampakan per putaran, tanpa menyimpannya.
Penegasan auditor yang dibantah putaran berikutnya ditandai kedaluwarsa,
tidak dihapus."
```

---

### Task 2: Kolom basis data dan migrasi

**Files:**
- Modify: `backend/app/models/engagement.py`
- Modify: `backend/app/models/scan_upload.py`
- Modify: `backend/app/models/finding.py`
- Create: `backend/alembic/versions/a9f3c7d21e08_retest_putaran.py`

**Interfaces:**
- Consumes: konstanta status dari Task 1 (hanya sebagai acuan nilai, tidak diimpor oleh model).
- Produces:
  - `Engagement.current_round: int`
  - `ScanUpload.round: int`
  - `Finding.rounds_seen: list[int]`, `Finding.remediation_status: str | None`, `Finding.remediation_note: str | None`, `Finding.remediation_confirmed_round: int | None`, `Finding.remediation_confirmed_by: int | None`, `Finding.remediation_confirmed_at: datetime | None`

- [ ] **Step 1: Tambahkan kolom pada `Engagement`**

Di `backend/app/models/engagement.py`, tepat setelah blok `kb_shareable`, tambahkan:

```python
    # --- R4: verifikasi remediasi (retest) ---
    # Putaran yang sedang berjalan. 1 = audit awal; 2 dan seterusnya = retest.
    # Dinaikkan hanya lewat tindakan sadar auditor, bukan otomatis dari waktu.
    current_round: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
```

`Integer` sudah diimpor di berkas ini; periksa baris `from sqlalchemy import ...` dan tambahkan bila belum.

- [ ] **Step 2: Tambahkan kolom pada `ScanUpload`**

Di `backend/app/models/scan_upload.py`, setelah `content_hash`, tambahkan:

```python
    # --- R4 --- Putaran saat berkas ini masuk, dicap dari engagement.current_round.
    # Dicap saat masuk, bukan dibaca belakangan: putaran bisa sudah berpindah
    # ketika seseorang menelusuri riwayat.
    round: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
```

Tambahkan `Integer` pada impor `sqlalchemy` di berkas ini.

- [ ] **Step 3: Tambahkan kolom pada `Finding`**

Di `backend/app/models/finding.py`, setelah blok `# --- D13: review & persetujuan ---` dan sebelum `created_at`, tambahkan:

```python
    # --- R4: verifikasi remediasi (retest) ---
    # Putaran tempat temuan ini pernah terlihat, mis. [1, 3]. Inilah yang
    # membuat ketidakhadiran terbaca tanpa menduplikasi temuan.
    rounds_seen: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Keputusan auditor. None = belum ditegaskan; usulan sistem TIDAK disimpan.
    remediation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    remediation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Putaran saat penegasan diberikan. Dipakai menandai penegasan yang sudah
    # dibantah putaran berikutnya.
    remediation_confirmed_round: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    remediation_confirmed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    remediation_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 4: Tulis migrasi**

Buat `backend/alembic/versions/a9f3c7d21e08_retest_putaran.py`:

```python
"""verifikasi remediasi berbasis putaran (R4)

Revision ID: a9f3c7d21e08
Revises: d4b7e2c81f95
Create Date: 2026-08-18 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9f3c7d21e08'
down_revision: str | None = 'd4b7e2c81f95'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'engagements',
        sa.Column('current_round', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'scan_uploads',
        sa.Column('round', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column('findings', sa.Column('rounds_seen', sa.JSON(), nullable=True))
    op.add_column(
        'findings', sa.Column('remediation_status', sa.String(length=20), nullable=True)
    )
    op.add_column('findings', sa.Column('remediation_note', sa.Text(), nullable=True))
    op.add_column(
        'findings', sa.Column('remediation_confirmed_round', sa.Integer(), nullable=True)
    )
    op.add_column(
        'findings', sa.Column('remediation_confirmed_by', sa.Integer(), nullable=True)
    )
    op.add_column(
        'findings',
        sa.Column('remediation_confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_findings_remediation_confirmed_by',
        'findings', 'users',
        ['remediation_confirmed_by'], ['id'],
    )
    # Temuan lama diisi [1], BUKAN daftar kosong. Daftar kosong terbaca
    # "belum diuji" selamanya, sehingga penugasan lama tak akan pernah
    # menghasilkan usulan yang benar begitu putaran kedua dibuka.
    op.execute("UPDATE findings SET rounds_seen = '[1]' WHERE rounds_seen IS NULL")


def downgrade() -> None:
    op.drop_constraint(
        'fk_findings_remediation_confirmed_by', 'findings', type_='foreignkey'
    )
    op.drop_column('findings', 'remediation_confirmed_at')
    op.drop_column('findings', 'remediation_confirmed_by')
    op.drop_column('findings', 'remediation_confirmed_round')
    op.drop_column('findings', 'remediation_note')
    op.drop_column('findings', 'remediation_status')
    op.drop_column('findings', 'rounds_seen')
    op.drop_column('scan_uploads', 'round')
    op.drop_column('engagements', 'current_round')
```

- [ ] **Step 5: Jalankan migrasi dan periksa hasilnya**

Run:
```bash
docker exec auditforge-api-1 alembic upgrade head
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c "\d findings" | grep -E "rounds_seen|remediation"
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -tAc "SELECT DISTINCT rounds_seen::text FROM findings"
```
Expected: enam kolom remediasi/`rounds_seen` muncul, dan seluruh temuan lama bernilai `[1]`.

- [ ] **Step 6: Pastikan suite tetap hijau**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS, 235 tes

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/ backend/alembic/versions/a9f3c7d21e08_retest_putaran.py
git commit -m "feat(retest): kolom putaran dan status remediasi

Temuan lama diisi rounds_seen [1], bukan daftar kosong, agar penugasan yang
sudah ada langsung terbaca benar begitu putaran kedua dibuka."
```

---

### Task 3: Pipeline menandai putaran saat ingest

**Files:**
- Modify: `backend/app/workers/tasks.py` (fungsi `_ingest_findings`, dan titik pembuatan `ScanUpload` pada auto-ingest)
- Test: `backend/tests/test_retest_ingest.py` (create)

**Interfaces:**
- Consumes: `Finding.rounds_seen` (Task 2).
- Produces: `_ingest_findings(db, engagement_id, upload_id, findings, current_round)` — parameter kelima baru, wajib.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_retest_ingest.py`:

```python
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
```

- [ ] **Step 2: Jalankan tes untuk memastikan ia gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_retest_ingest.py -q`
Expected: FAIL — `ImportError: cannot import name 'tandai_putaran'`

- [ ] **Step 3: Tambahkan helper murni di `tasks.py`**

Di `backend/app/workers/tasks.py`, tepat sebelum `def _ingest_findings(`, tambahkan:

```python
def tandai_putaran(rounds_seen: list[int] | None, current_round: int) -> list[int]:
    """Sisipkan putaran berjalan, kembalikan daftar BARU yang urut dan unik.

    Mengembalikan daftar baru, bukan memutasi yang lama, karena SQLAlchemy
    hanya mendeteksi perubahan kolom JSON bila kolomnya ditugaskan ulang.
    """
    return sorted({int(r) for r in (rounds_seen or [])} | {int(current_round)})
```

- [ ] **Step 4: Jalankan tes untuk memastikan ia lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_retest_ingest.py -q`
Expected: PASS, 5 tes

- [ ] **Step 5: Pakai helper itu di `_ingest_findings`**

Ubah tanda tangan fungsi:

```python
def _ingest_findings(
    db: Session,
    engagement_id: int,
    upload_id: int,
    findings: list[UnifiedFinding],
    current_round: int,
) -> dict:
```

Pada baris pembuatan `source`, tambahkan nomor putaran:

```python
        source: SourceRef = {
            "tool": uf.tool.value,
            "upload_id": upload_id,
            "round": current_round,
        }
```

Pada cabang `if row is None:` (pembuatan `Finding` baru), tambahkan satu argumen:

```python
                rounds_seen=[current_round],
```

Pada cabang `else:` (penggabungan), tambahkan sebagai baris pertama di dalam blok:

```python
            # R4: catat putaran ini sebelum apa pun yang lain. Penggabungan
            # lintas putaran memang diinginkan — yang tak boleh hilang adalah
            # jejak putaran mana saja temuan ini terlihat.
            row.rounds_seen = tandai_putaran(row.rounds_seen, current_round)
```

- [ ] **Step 6: Teruskan putaran dari pemanggilnya**

Di `parse_upload`, sebelum memanggil `_ingest_findings`, ambil putaran penugasan dan cap berkasnya:

```python
            eng = db.get(Engagement, upload.engagement_id)
            putaran = int(getattr(eng, "current_round", 1) or 1)
            upload.round = putaran
            stats = _ingest_findings(
                db, upload.engagement_id, upload.id, findings, putaran
            )
```

Pastikan `Engagement` sudah diimpor di berkas ini; tambahkan `from app.models.engagement import Engagement` bila belum.

- [ ] **Step 7: Jalankan seluruh suite**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS, 240 tes

- [ ] **Step 8: Restart worker dan beat, lalu uji ingest sungguhan**

Run:
```bash
docker compose restart worker beat
mkdir -p datasets/watch/inbox/21
cp datasets/fixtures/nuclei-sample.jsonl datasets/watch/inbox/21/
sleep 60
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -tAc \
  "SELECT id, rounds_seen::text FROM findings WHERE engagement_id = 21 ORDER BY id"
```
Expected: temuan baru bernilai `[1]`, dan berkasnya pindah ke `datasets/watch/processed/21/`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/workers/tasks.py backend/tests/test_retest_ingest.py
git commit -m "feat(retest): tandai putaran pada tiap penampakan saat ingest

Dedup tetap menggabungkan lintas putaran — itu memang diinginkan karena satu
kerentanan tetap satu baris. Yang ditambahkan adalah jejak putaran, sehingga
ketidakhadiran di putaran terbaru tetap terbaca."
```

---

### Task 4: Endpoint putaran dan penegasan remediasi

**Files:**
- Modify: `backend/app/schemas/engagement.py`
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `app.retest.propose`, `effective_status`, `VALID_STATUSES` (Task 1); kolom dari Task 2.
- Produces:
  - `POST /engagements/{id}/rounds` → `{"current_round": int}`
  - `PATCH /engagements/{id}/findings/{fid}/remediation` → `FindingDetailOut`
  - `FindingOut` bertambah `rounds_seen: list[int]`, `remediation_status: str | None`, `remediation_proposal: str`, `remediation_stale: bool`
  - `EngagementDetailOut` bertambah `current_round: int`

- [ ] **Step 1: Tambahkan field skema**

Di `backend/app/schemas/engagement.py`, pada `class FindingOut`, tambahkan setelah `priority_score`:

```python
    # --- R4: verifikasi remediasi ---
    rounds_seen: list[int] = []
    remediation_status: str | None = None
    # Dihitung, hanya-baca. Tak pernah disimpan agar tak mungkin basi.
    remediation_proposal: str = "not_tested"
    # True bila penegasan lama sudah dibantah putaran berikutnya.
    remediation_stale: bool = False
```

Pada `class EngagementDetailOut` (dan `EngagementOut` bila keduanya dipakai daftar penugasan), tambahkan:

```python
    current_round: int = 1
```

Tambahkan pula skema masukan baru di akhir berkas:

```python
class RemediationIn(BaseModel):
    """Penegasan status remediasi oleh auditor."""

    status: str
    note: str | None = Field(default=None, max_length=1000)
```

- [ ] **Step 2: Serialisasikan field baru**

Di `backend/app/api/routes/engagements.py`, tambahkan impor:

```python
from app.retest import VALID_STATUSES, STATUS_NOT_TESTED, is_stale, propose
```

Pada `list_findings`, ambil putaran penugasan sekali di luar perulangan lalu isi keempat field baru:

```python
    eng = _get_engagement(db, engagement_id, user)
    putaran = int(getattr(eng, "current_round", 1) or 1)
```

dan di dalam `FindingOut(...)` tambahkan:

```python
                rounds_seen=f.rounds_seen or [],
                remediation_status=f.remediation_status,
                remediation_proposal=propose(f.rounds_seen, putaran),
                remediation_stale=is_stale(
                    f.remediation_status,
                    f.remediation_confirmed_round,
                    f.rounds_seen,
                    putaran,
                ),
```

Ubah `_finding_detail(f)` menjadi `_finding_detail(f, current_round)` dan tambahkan keempat field yang sama. Perbarui setiap pemanggilnya agar meneruskan putaran penugasan.

- [ ] **Step 3: Endpoint membuka putaran baru**

Tambahkan setelah endpoint `save_engagement_details`:

```python
@router.post("/{engagement_id}/rounds")
def start_round(
    engagement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("auditor", "admin")),
) -> dict[str, int]:
    """Buka putaran berikutnya. Analis tak boleh — ini keputusan audit."""
    eng = _get_engagement(db, engagement_id, user)
    eng.current_round = int(eng.current_round or 1) + 1
    db.commit()
    return {"current_round": eng.current_round}
```

- [ ] **Step 4: Endpoint penegasan remediasi**

Tambahkan setelah endpoint perubahan status temuan:

```python
@router.patch(
    "/{engagement_id}/findings/{finding_id}/remediation",
    response_model=FindingDetailOut,
)
def confirm_remediation(
    engagement_id: int,
    finding_id: int,
    payload: RemediationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("auditor", "admin")),
) -> FindingDetailOut:
    """Tegaskan status remediasi. Hanya auditor/admin, sejalan dengan persetujuan temuan."""
    eng = _get_engagement(db, engagement_id, user)
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status remediasi tak dikenal: {payload.status}",
        )
    f = _get_finding(db, engagement_id, finding_id)
    putaran = int(eng.current_round or 1)
    f.remediation_status = payload.status
    f.remediation_note = payload.note
    f.remediation_confirmed_round = putaran
    f.remediation_confirmed_by = user.id
    f.remediation_confirmed_at = utcnow()
    db.add(
        FindingRevision(
            finding_id=f.id,
            action="remediation",
            status=f.status,
            narrative=None,
            note=f"remediasi: {payload.status}"
            + (f" — {payload.note}" if payload.note else ""),
            author_id=user.id,
        )
    )
    db.commit()
    db.refresh(f)
    return _finding_detail(f, putaran)
```

Pastikan `utcnow`, `FindingRevision`, dan `RemediationIn` sudah diimpor di berkas ini.

- [ ] **Step 5: Sertakan `current_round` pada detail penugasan**

Pada helper yang membangun `EngagementDetailOut` (sekitar baris 185), tambahkan:

```python
        current_round=e.current_round or 1,
```

- [ ] **Step 6: Uji manual keempat jalur**

Run:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=admin@auditforge.local&password=admin12345' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST http://localhost:8000/engagements/21/rounds -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/engagements/21/findings/173/remediation \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"fixed","note":"diverifikasi manual"}' | head -c 300

ANALIS=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=analis@auditforge.local&password=analis12345' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -o /dev/null -w "analis buka putaran: %{http_code}\n" \
  -X POST http://localhost:8000/engagements/21/rounds -H "Authorization: Bearer $ANALIS"
```
Expected: `{"current_round": 2}`; penegasan membalas 200; analis membalas **403**.

Ganti `173` dengan id temuan yang ada di penugasan 21.

- [ ] **Step 7: Jalankan seluruh suite dan cek asap**

Run:
```bash
docker exec auditforge-api-1 python -m pytest -q
./scripts/smoke.sh
```
Expected: 240 tes PASS; 43 cek asap lulus.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/engagement.py backend/app/api/routes/engagements.py
git commit -m "feat(retest): endpoint buka putaran dan tegaskan status remediasi

Usulan ikut pada payload temuan sebagai field hitung, tidak disimpan.
Penegasan hanya untuk auditor/admin dan tercatat di riwayat temuan."
```

---

### Task 5: Kolom remediasi pada laporan

**Files:**
- Modify: `backend/app/reporting/report_data.py`
- Modify: `backend/app/reporting/html_writer.py`
- Modify: `backend/app/reporting/docx_writer.py`
- Modify: `backend/app/api/routes/engagements.py` (pemanggil `build_report_data`)
- Test: `backend/tests/test_reporting_retest.py` (create)

**Interfaces:**
- Consumes: `app.retest.effective_status`, `summarize` (Task 1).
- Produces: `ReportFinding.remediation: str | None`; `ReportData.current_round: int`, `ReportData.remediation_counts: dict[str, int]`; `build_report_data(..., current_round: int = 1)`.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_reporting_retest.py`:

```python
"""Uji unit R4 — kolom remediasi pada laporan (tanpa DB, tanpa LLM)."""
from __future__ import annotations

from types import SimpleNamespace

from app.reporting.report_data import build_report_data


def _temuan(**kw):
    dasar = dict(
        id=1, title="Log4Shell", severity="critical", status="approved", priority=1,
        cwe="CWE-502", owasp=None, cvss_score=9.8, cve=[], sources=[],
        occurrences=1, ai_draft=None, final_narrative=None, narrative_edited=False,
        rounds_seen=[1], remediation_status=None, remediation_confirmed_round=None,
    )
    dasar.update(kw)
    return SimpleNamespace(**dasar)


def _eng():
    return SimpleNamespace(
        name="Audit Contoh", client_name="PT Contoh", scope=None,
        period_start=None, period_end=None,
    )


def test_putaran_satu_tidak_memunculkan_kolom_remediasi():
    data = build_report_data(
        _eng(), [_temuan()], org_name="X", report_title="Y", current_round=1
    )
    assert data.current_round == 1
    assert data.findings[0].remediation is None


def test_status_yang_ditegaskan_tercetak():
    f = _temuan(remediation_status="fixed", remediation_confirmed_round=2)
    data = build_report_data(
        _eng(), [f], org_name="X", report_title="Y", current_round=2
    )
    assert data.findings[0].remediation == "fixed"
    assert data.remediation_counts["fixed"] == 1


def test_usulan_tidak_pernah_tercetak():
    # rounds_seen [1] pada putaran 2 berarti usulan "fixed", tetapi belum
    # ditegaskan siapa pun — laporan tak boleh menyebutnya tertutup.
    data = build_report_data(
        _eng(), [_temuan()], org_name="X", report_title="Y", current_round=2
    )
    assert data.findings[0].remediation is None
    assert data.remediation_counts["fixed"] == 0


def test_penegasan_kedaluwarsa_tidak_tercetak():
    f = _temuan(rounds_seen=[1, 3], remediation_status="fixed",
                remediation_confirmed_round=2)
    data = build_report_data(
        _eng(), [f], org_name="X", report_title="Y", current_round=3
    )
    assert data.findings[0].remediation is None
```

- [ ] **Step 2: Jalankan tes untuk memastikan ia gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_reporting_retest.py -q`
Expected: FAIL — `TypeError: build_report_data() got an unexpected keyword argument 'current_round'`

- [ ] **Step 3: Perluas `report_data.py`**

Tambahkan impor:

```python
from app.retest import effective_status, summarize
```

Pada `class ReportFinding`, tambahkan field terakhir:

```python
    # R4: status remediasi yang BERLAKU. None = belum ditegaskan, kedaluwarsa,
    # atau penugasan ini belum pernah diretest.
    remediation: str | None = None
```

Pada `class ReportData`, tambahkan:

```python
    current_round: int = 1
    remediation_counts: dict[str, int] = field(default_factory=dict)
```

Pada `build_report_data`, tambahkan parameter kata kunci `current_round: int = 1`, lalu di dalam perulangan pembuatan `ReportFinding` tambahkan:

```python
                remediation=(
                    effective_status(
                        getattr(f, "remediation_status", None),
                        getattr(f, "remediation_confirmed_round", None),
                        getattr(f, "rounds_seen", None),
                        current_round,
                    )
                    if current_round > 1
                    else None
                ),
```

Sebelum `return`, isi kedua field baru:

```python
    remediation_counts = summarize(selected, current_round) if current_round > 1 else {}
```

dan teruskan `current_round=current_round, remediation_counts=remediation_counts` ke konstruktor `ReportData`.

- [ ] **Step 4: Jalankan tes untuk memastikan ia lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_reporting_retest.py -q`
Expected: PASS, 4 tes

- [ ] **Step 5: Render kolomnya di HTML**

Di `backend/app/reporting/html_writer.py`, pada baris label (sekitar baris 33) tambahkan pasangan dwibahasa:

```python
        "remediation": "Remediasi", "rem_fixed": "Tertutup",
        "rem_open": "Masih terbuka", "rem_recurring": "Kambuh",
```

(dan padanan Inggrisnya pada kamus `en`: `"Remediation"`, `"Closed"`, `"Still open"`, `"Recurring"`).

Pada template Jinja2 tiap temuan, tepat setelah baris prioritas, tambahkan:

```jinja
      {% if data.current_round > 1 and f.remediation %}
        · <span class="rem rem-{{ f.remediation }}">{{ L['rem_' + f.remediation] }}</span>
      {% endif %}
```

Pada bagian ringkasan, tepat setelah distribusi severity, tambahkan:

```jinja
    {% if data.current_round > 1 %}
      <p>{{ data.remediation_counts.get('fixed', 0) }} dari {{ data.total }}
         temuan telah tertutup dan diverifikasi (Putaran {{ data.current_round }}).</p>
    {% endif %}
```

- [ ] **Step 6: Render kolomnya di DOCX**

Di `backend/app/reporting/docx_writer.py`, pada bagian yang menulis metadata tiap temuan (baris berisi severity dan prioritas), tambahkan sesudahnya:

```python
        if data.current_round > 1 and f.remediation:
            doc.add_paragraph(f"Remediasi: {LABEL_REMEDIASI[f.remediation]}")
```

dan di dekat konstanta berkas tersebut:

```python
# R4 — label status remediasi untuk laporan DOCX.
LABEL_REMEDIASI = {
    "fixed": "Tertutup",
    "open": "Masih terbuka",
    "recurring": "Kambuh",
    "not_tested": "Belum diuji",
}
```

- [ ] **Step 7: Teruskan `current_round` dari route**

Di `backend/app/api/routes/engagements.py`, pada `_assemble_report` (atau fungsi yang memanggil `build_report_data`), tambahkan argumen:

```python
        current_round=int(getattr(eng, "current_round", 1) or 1),
```

- [ ] **Step 8: Uji ketiga format sungguhan**

Run:
```bash
docker exec auditforge-api-1 python -m pytest -q
./scripts/smoke.sh
curl -s -o /tmp/r.html -w "html=%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" http://localhost:8000/engagements/17/report.html
grep -c "Remediasi" /tmp/r.html
```
Expected: 244 tes PASS; 43 cek asap lulus; penugasan 17 masih di Putaran 1 sehingga hasil `grep` adalah **0**.

- [ ] **Step 9: Commit**

```bash
git add backend/app/reporting/ backend/app/api/routes/engagements.py backend/tests/test_reporting_retest.py
git commit -m "feat(retest): kolom status remediasi pada laporan

Hanya status yang berlaku yang tercetak; usulan dan penegasan kedaluwarsa
tidak. Kolomnya baru muncul bila current_round > 1, sehingga laporan
penugasan yang belum diretest identik dengan sebelumnya."
```

---

### Task 6: Antarmuka

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/app/engagements/[id]/page.tsx`
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- Consumes: endpoint dan field dari Task 4.
- Produces: `api.startRound(id)`, `api.setRemediation(id, findingId, status, note)`; tipe `Finding` bertambah empat field.

- [ ] **Step 1: Perluas klien API**

Di `frontend/src/lib/api.ts`, pada `interface Finding`, tambahkan:

```typescript
  rounds_seen: number[];
  remediation_status: string | null;
  remediation_proposal: string;
  remediation_stale: boolean;
```

Pada `interface EngagementDetail`, tambahkan `current_round: number;`.

Tambahkan dua fungsi di dekat `saveEngagementDetails`:

```typescript
export function startRound(id: number): Promise<{ current_round: number }> {
  return req(`/engagements/${id}/rounds`, { method: "POST" });
}

export function setRemediation(
  id: number,
  findingId: number,
  status: string,
  note?: string,
): Promise<FindingDetail> {
  return req<FindingDetail>(`/engagements/${id}/findings/${findingId}/remediation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note: note || null }),
  });
}
```

- [ ] **Step 2: Tambahkan teks di kedua lokal**

Di `frontend/src/i18n/messages.ts`, pada kamus `id`:

```typescript
    "retest.round": "Putaran",
    "retest.newRound": "Mulai Putaran Baru",
    "retest.newRoundAsk": "Buka putaran baru? Berkas yang masuk setelah ini akan dihitung sebagai putaran berikutnya.",
    "retest.column": "Remediasi",
    "retest.proposalTag": "usulan",
    "retest.confirm": "Tegaskan",
    "retest.note": "Alasan (opsional)",
    "retest.stale": "Ditegaskan pada putaran sebelumnya, tetapi keadaannya sudah berubah. Tegaskan ulang.",
    "retest.seenIn": "Terlihat di putaran",
    "retest.notSeenIn": "Tak terlihat di Putaran",
    "retest.newHere": "baru di putaran ini",
    "retest.st.not_tested": "Belum diuji",
    "retest.st.open": "Masih terbuka",
    "retest.st.fixed": "Tertutup",
    "retest.st.recurring": "Kambuh",
```

dan padanannya pada kamus `en`:

```typescript
    "retest.round": "Round",
    "retest.newRound": "Start New Round",
    "retest.newRoundAsk": "Start a new round? Files arriving after this count towards the next round.",
    "retest.column": "Remediation",
    "retest.proposalTag": "proposed",
    "retest.confirm": "Confirm",
    "retest.note": "Reason (optional)",
    "retest.stale": "Confirmed in an earlier round, but the situation has changed. Please confirm again.",
    "retest.seenIn": "Seen in round",
    "retest.notSeenIn": "Not seen in Round",
    "retest.newHere": "new in this round",
    "retest.st.not_tested": "Not tested",
    "retest.st.open": "Still open",
    "retest.st.fixed": "Closed",
    "retest.st.recurring": "Recurring",
```

- [ ] **Step 3: Tombol putaran di kepala penugasan**

Di `frontend/src/app/engagements/[id]/page.tsx`, pada bagian kepala yang menampilkan nama penugasan, tambahkan:

```tsx
{eng && (
  <span className="badge wait">
    {t("retest.round")} {eng.current_round ?? 1}
  </span>
)}
{canApprove && (
  <button
    className="btn secondary"
    onClick={() => {
      if (!window.confirm(t("retest.newRoundAsk"))) return;
      api
        .startRound(id)
        .then(() => refresh())
        .catch((err) =>
          setError(err instanceof ApiError ? err.message : String(err)),
        );
    }}
  >
    {t("retest.newRound")}
  </button>
)}
```

`canApprove` sudah ada di berkas ini dan bernilai benar untuk auditor/admin.

- [ ] **Step 4: Kolom Remediasi pada tabel temuan**

Tambahkan `<th>{t("retest.column")}</th>` pada baris kepala tabel, dan pada tiap baris:

```tsx
<td>
  {f.remediation_status && !f.remediation_stale ? (
    <span className={`badge rem-${f.remediation_status}`}>
      {t(`retest.st.${f.remediation_status}` as MessageKey)}
    </span>
  ) : (eng?.current_round ?? 1) > 1 ? (
    <span className="badge wait" title={t("retest.proposalTag")}>
      {t(`retest.st.${f.remediation_proposal}` as MessageKey)} ·{" "}
      {t("retest.proposalTag")}
    </span>
  ) : (
    <span className="muted">—</span>
  )}
</td>
```

- [ ] **Step 5: Penapis status remediasi**

Di dekat deretan tombol penapis severity yang sudah ada, tambahkan:

```tsx
{(eng?.current_round ?? 1) > 1 && (
  <div className="filter-row">
    {["all", "fixed", "open", "recurring"].map((s) => (
      <button
        key={s}
        className={`btn chip${remFilter === s ? " active" : ""}`}
        onClick={() => setRemFilter(s)}
      >
        {s === "all" ? t("find.all") : t(`retest.st.${s}` as MessageKey)}
      </button>
    ))}
  </div>
)}
```

Tambahkan state `const [remFilter, setRemFilter] = useState("all");`, dan saring
daftar temuan sebelum dirender:

```tsx
const shown = findings.filter((f) => {
  if (remFilter === "all") return true;
  const berlaku =
    f.remediation_status && !f.remediation_stale
      ? f.remediation_status
      : f.remediation_proposal;
  return berlaku === remFilter;
});
```

Pakai `shown` menggantikan `findings` pada tabel dan kanban. Penapis memakai
status **berlaku**, bukan status tersimpan, supaya "tampilkan yang tertutup"
sejalan dengan apa yang mata pengguna lihat di kolom Remediasi.

- [ ] **Step 6: Garis waktu dan tombol penegasan di panel detail**

Pada panel detail temuan, sesudah blok riwayat, tambahkan:

```tsx
{(eng?.current_round ?? 1) > 1 && detail && (
  <section className="card">
    <h4 style={{ marginTop: 0 }}>{t("retest.column")}</h4>
    <p className="muted">
      {detail.rounds_seen?.length
        ? `${t("retest.seenIn")} ${detail.rounds_seen.join(", ")}` +
          (Math.min(...detail.rounds_seen) === eng?.current_round
            ? ` · ${t("retest.newHere")}`
            : "")
        : `${t("retest.notSeenIn")} ${eng?.current_round}`}
    </p>
    {detail.remediation_stale && (
      <div className="alert warn">{t("retest.stale")}</div>
    )}
    <div className="form-row">
      {["fixed", "open", "recurring"].map((s) => (
        <button
          key={s}
          className="btn secondary"
          onClick={() =>
            api
              .setRemediation(id, detail.id, s, remNote || undefined)
              .then(() => {
                setRemNote("");
                return refresh();
              })
              .catch((err) =>
                setError(err instanceof ApiError ? err.message : String(err)),
              )
          }
        >
          {t("retest.confirm")}: {t(`retest.st.${s}` as MessageKey)}
        </button>
      ))}
    </div>
    <label className="field">
      <span>{t("retest.note")}</span>
      <input value={remNote} onChange={(e) => setRemNote(e.target.value)} />
    </label>
  </section>
)}
```

Tambahkan state `const [remNote, setRemNote] = useState("");` bersama state lain di bagian atas komponen, dan kosongkan di `toggleDetail` bersama `diff` — panel yang menyisakan isi temuan sebelumnya adalah cacat yang sudah pernah terjadi dua kali di berkas ini.

- [ ] **Step 7: Warna lencana**

Di `frontend/src/app/globals.css`, dekat kelas `.badge` yang sudah ada, tambahkan:

```css
/* R4 — status remediasi. Warnanya sengaja berbeda dari severity supaya tak
   terbaca sebagai tingkat keparahan. */
.badge.rem-fixed { background: #dcfce7; color: #166534; }
.badge.rem-open { background: #fef3c7; color: #92400e; }
.badge.rem-recurring { background: #fee2e2; color: #991b1b; }
```

- [ ] **Step 8: Typecheck dan periksa di peramban**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: senyap.

Lalu buka `http://localhost:3000/engagements/21` setelah `Ctrl+Shift+R`, dan periksa berurutan: lencana Putaran tampil di kepala; tombol Mulai Putaran Baru ada untuk admin dan **tidak ada** untuk analis; kolom Remediasi menampilkan `—` selama Putaran 1; setelah putaran dibuka ia menampilkan usulan redup; menegaskan salah satu status mengubahnya jadi lencana biasa; dan berpindah antar temuan tidak menyisakan catatan alasan temuan sebelumnya.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(retest): antarmuka putaran dan penegasan remediasi

Usulan tampil redup dan berlabel 'usulan' supaya tak tertukar dengan
keputusan auditor. Penegasan yang kedaluwarsa memunculkan peringatan yang
meminta penegasan ulang."
```

---

### Task 7: Gerbang dan penutup

**Files:**
- Modify: `scripts/smoke.sh`
- Modify: `FLOW.md`

**Interfaces:**
- Consumes: seluruh tugas sebelumnya.
- Produces: tidak ada.

- [ ] **Step 1: Tambahkan cek asap**

Di `scripts/smoke.sh`, di dalam blok `if [ -n "$FID" ]; then`, sesudah baris
`cek 200 GET "/knowledge/suggest?finding_id=$FID"`, tambahkan:

```bash
        # R4: payload temuan wajib memuat usulan remediasi. Field ini dihitung,
        # jadi ketiadaannya berarti serialisasinya putus — dan itu tak akan
        # membuat satu pun endpoint membalas selain 200.
        if curl -s "$BASE/engagements/$EID/findings" -H "Authorization: Bearer $TOKEN"             | grep -q '"remediation_proposal"'; then
            LULUS=$((LULUS + 1))
            printf '  [32mok[0m   payload temuan memuat remediation_proposal
'
        else
            GAGAL=$((GAGAL + 1))
            printf '  [31mGAGAL[0m payload temuan tanpa remediation_proposal
'
        fi
```

Lalu di bagian "Penolakan yang harus tetap berlaku", sesudah cek DELETE yang ada,
tambahkan di dalam blok `if [ -n "$EID" ]`:

```bash
    if [ -n "$FID" ]; then
        cek 400 PATCH "/engagements/$EID/findings/$FID/remediation" '{"status":"ngawur"}'
    fi
```

Status yang tak dikenal harus ditolak 400, bukan disimpan apa adanya — kolomnya
`String(20)` tanpa batasan di basis data, sehingga lapisan aplikasi satu-satunya
yang menjaga.

- [ ] **Step 2: Perbarui FLOW.md**

Tambahkan bagian ini sesudah langkah peninjauan temuan:

```markdown
## Memverifikasi perbaikan klien (retest)

Setelah klien menyatakan temuan sudah diperbaiki, verifikasinya dilakukan
sebagai **putaran baru** di penugasan yang sama, bukan penugasan baru.

1. Buka: penugasan yang bersangkutan. Di kepala halaman tertulis **Putaran 1**.
2. Tekan **Mulai Putaran Baru**. Sejak saat itu setiap berkas yang masuk
   dihitung sebagai Putaran 2, termasuk yang datang lewat folder terpantau.
3. Masukkan hasil pemindaian ulang, lewat tab **Berkas** atau folder terpantau
   seperti biasa.
4. Buka: tab **Temuan**. Kolom **Remediasi** kini terisi usulan sistem.

Usulan itu **bukan keputusan**. Lencana yang berbunyi "tak terlihat di Putaran 2"
hanya menyatakan bahwa pemindaian ulang tidak menemukannya lagi — bisa saja
cakupannya berbeda, targetnya sedang mati, atau perkakasnya kebetulan tak
mendeteksi. Karena itu ia tampil redup dan berlabel "usulan".

5. Buka satu temuan, periksa garis waktunya, lalu tekan **Tegaskan** dengan
   status yang menurut Anda benar. Isi alasannya bila Anda menimpa usulan.

Hanya status yang sudah ditegaskan yang tercetak di laporan. Bila sebuah temuan
yang pernah Anda tegaskan tertutup muncul lagi di putaran berikutnya, penegasan
lama ditandai perlu ditegaskan ulang dan sementara itu tidak ikut tercetak.
```

- [ ] **Step 3: Jalankan seluruh gerbang**

Run:
```bash
docker exec auditforge-api-1 python -m pytest -q
docker exec auditforge-web-1 npx tsc --noEmit
./scripts/smoke.sh
```
Expected: 244 tes PASS; `tsc` senyap; cek asap lulus seluruhnya tanpa satu pun GAGAL.

- [ ] **Step 4: Periksa kriteria selesai spec bagian 11 satu per satu**

Jalankan skenario penuh pada penugasan uji: buka Putaran 2, masukkan berkas yang memuat sebagian temuan lama, dan pastikan keempat status muncul benar. Lalu buka Putaran 3 dengan berkas yang memuat kembali temuan yang tadi ditegaskan tertutup, dan pastikan peringatan kedaluwarsa muncul serta temuan itu hilang dari laporan.

Bandingkan pula laporan penugasan 17 yang masih di Putaran 1 dengan hasil sebelum fitur ini ada — keduanya harus identik.

- [ ] **Step 5: Commit dan push**

```bash
git add scripts/smoke.sh FLOW.md
git commit -m "test(smoke): jaga payload remediasi; FLOW.md memuat alur retest"
git push origin main
```

---

## Catatan Penyempurnaan terhadap Spec

Tiga hal ditetapkan di rencana ini yang di spec masih longgar. Bila salah satunya ditolak saat tinjauan, spec dan rencana harus diperbarui bersama.

1. `summarize` menerima `current_round` sebagai argumen kedua; tanpa itu ia tak dapat memanggil `effective_status`.
2. `_ingest_findings` mendapat parameter kelima `current_round` yang **wajib**, bukan bernilai bawaan, agar pemanggil yang lupa meneruskannya gagal keras alih-alih diam-diam mencap semua ke putaran 1.
3. Penegasan dicatat sebagai `FindingRevision` beraksi `remediation`, sehingga terbaca di panel riwayat yang sudah ada tanpa komponen baru.

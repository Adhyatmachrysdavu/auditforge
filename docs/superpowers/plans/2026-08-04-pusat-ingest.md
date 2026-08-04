# Pusat Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Melengkapi auto-ingest (R3) dengan halaman aktivitas lintas penugasan, kemampuan mengurai ulang berkas gagal, dan penolakan berkas duplikat — sehingga otomatisasi benar-benar mengurangi pekerjaan auditor, bukan memindahkannya.

**Architecture:** Seluruh keputusan ditempatkan pada satu modul murni (`app/ingest/rules.py`) yang tidak menyentuh basis data, mengikuti pola `review.py` dan `ingest/watcher.py`. Tidak ada model baru — data halaman `/ingest` sudah tersimpan di `ScanUpload`, yang kurang hanya satu kolom hash. Endpoint urai ulang diletakkan di bawah `/engagements/{id}/...` agar ikut terlindungi ketika Modul 2 memasang pembatasan keanggotaan.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest · Next.js 14 App Router, TypeScript, Phosphor Icons

## Global Constraints

- Seluruh tes baru **murni**: tanpa DB, Redis, MinIO, LLM, tanpa `conftest.py`. Objek palsu memakai `types.SimpleNamespace`.
- Docstring dan komentar dalam **Bahasa Indonesia**; identifier dan nama field API dalam Bahasa Inggris.
- Setiap teks UI baru wajib ditambahkan ke **kedua** locale pada `frontend/src/i18n/messages.ts`; tipe `MessageKey` membuat `tsc` gagal bila terlewat.
- Perkakas dev tidak ada di image: `docker exec auditforge-api-1 pip install -e ".[dev]"` bila `pytest` hilang.
- Jangan menjalankan `npm run lint` — tanpa konfigurasi ESLint, `next lint` berhenti di wizard interaktif. `tsc --noEmit` adalah satu-satunya gerbang frontend.
- Jangan menyentuh `triage.py`, masking, RBAC persetujuan, maupun pipeline deterministik.
- Alembic head saat ini: **`a7c4e9b2f130`**.
- Suite saat ini: **137 tes lulus**.

---

## File Structure

| Berkas | Tanggung jawab |
|---|---|
| `backend/app/ingest/rules.py` | **Baru.** Dua keputusan murni: boleh diurai ulang? duplikat? |
| `backend/tests/test_ingest_rules.py` | **Baru.** Tes modul di atas |
| `backend/alembic/versions/b3d8f1c05a92_scan_upload_content_hash.py` | **Baru.** Kolom hash |
| `backend/app/models/scan_upload.py` | Tambah `content_hash` |
| `backend/app/api/routes/engagements.py` | Dedup saat unggah manual + endpoint urai ulang |
| `backend/app/workers/tasks.py` | Dedup pada jalur watcher |
| `backend/app/api/routes/ingest.py` | **Baru.** `GET /ingest` lintas penugasan |
| `backend/app/main.py` | Daftarkan router baru |
| `frontend/src/lib/api.ts` | Tipe + fungsi klien |
| `frontend/src/i18n/messages.ts` | Kunci ID + EN |
| `frontend/src/components/AppShell.tsx` | Item sidebar baru |
| `frontend/src/app/ingest/page.tsx` | **Baru.** Halaman Pusat Ingest |
| `frontend/src/app/engagements/[id]/page.tsx` | Tombol Urai Ulang di tab Berkas |

---

### Task 1: Modul murni aturan ingest

**Files:**
- Create: `backend/app/ingest/rules.py`
- Test: `backend/tests/test_ingest_rules.py`

**Interfaces:**
- Consumes: tidak ada (task pertama)
- Produces:
  - `can_reparse(*, status: str, has_storage_key: bool) -> tuple[bool, str]` — `(boleh, alasan)`; `alasan` kosong bila boleh
  - `is_duplicate(*, content_hash: str | None, parsed_hashes: set[str]) -> bool`
  - `sha256_of(content: bytes) -> str`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_ingest_rules.py`:

```python
"""Uji unit aturan ingest — urai ulang & deteksi duplikat (tanpa DB)."""
from __future__ import annotations

from app.ingest.rules import can_reparse, is_duplicate, sha256_of


def test_reparse_allowed_for_failed_with_file():
    ok, reason = can_reparse(status="failed", has_storage_key=True)
    assert ok is True
    assert reason == ""


def test_reparse_rejected_when_file_missing():
    ok, reason = can_reparse(status="failed", has_storage_key=False)
    assert ok is False
    assert "penyimpanan" in reason.lower()


def test_reparse_rejected_for_parsed():
    # Mengulang berkas yang sudah berhasil akan menaikkan occurrences tiap
    # temuan — dan angka itu ikut menentukan prioritas triase.
    ok, reason = can_reparse(status="parsed", has_storage_key=True)
    assert ok is False
    assert "gagal" in reason.lower()


def test_reparse_rejected_while_parsing():
    # Menghindari dua task parse berjalan atas berkas yang sama.
    ok, reason = can_reparse(status="parsing", has_storage_key=True)
    assert ok is False
    assert reason != ""


def test_reparse_rejected_for_uploaded():
    ok, _ = can_reparse(status="uploaded", has_storage_key=True)
    assert ok is False


def test_duplicate_when_hash_already_parsed():
    assert is_duplicate(content_hash="abc", parsed_hashes={"abc", "def"}) is True


def test_not_duplicate_when_hash_unseen():
    assert is_duplicate(content_hash="xyz", parsed_hashes={"abc"}) is False


def test_not_duplicate_when_hash_missing():
    # Berkas lama tanpa hash tak boleh dianggap duplikat.
    assert is_duplicate(content_hash=None, parsed_hashes={"abc"}) is False
    assert is_duplicate(content_hash="", parsed_hashes={"abc"}) is False


def test_not_duplicate_against_empty_set():
    # Himpunan kosong = belum ada berkas yang BERHASIL diurai. Berkas yang dulu
    # gagal tidak masuk himpunan ini, sehingga boleh dikirim ulang — inilah yang
    # membuat berkas lama bisa hidup lagi saat parser baru ditambahkan.
    assert is_duplicate(content_hash="abc", parsed_hashes=set()) is False


def test_sha256_stable_and_differentiating():
    assert sha256_of(b"halo") == sha256_of(b"halo")
    assert sha256_of(b"halo") != sha256_of(b"halo ")
    assert len(sha256_of(b"halo")) == 64
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_ingest_rules.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingest.rules'`

- [ ] **Step 3: Tulis implementasi minimal**

Buat `backend/app/ingest/rules.py`:

```python
"""Aturan keputusan ingest — deterministik, tanpa DB.

Dua keputusan yang menentukan apakah sebuah berkas boleh diproses:

1. **Boleh diurai ulang?** Hanya berkas yang gagal dan berkas mentahnya masih
   ada. Mengulang berkas yang sudah berhasil menaikkan `occurrences` setiap
   temuan di dalamnya; deduplikasi mencegah baris ganda, tetapi tidak mencegah
   angka kemunculan menjadi keliru — padahal angka itu ikut menentukan
   prioritas triase.

2. **Duplikat?** Berkas dengan isi yang sama ditolak **hanya bila** berkas
   sebelumnya sudah BERHASIL diurai. Kata "berhasil" itu inti aturannya: berkas
   yang dulu gagal harus tetap boleh dikirim ulang, sebab kegagalannya bisa
   disebabkan parser yang belum ada. Tanpa pengecualian ini, menambah parser
   baru tidak akan pernah membuat berkas lama dapat masuk.
"""
from __future__ import annotations

import hashlib

_REPARSEABLE = "failed"


def sha256_of(content: bytes) -> str:
    """Sidik jari isi berkas untuk deteksi duplikat."""
    return hashlib.sha256(content).hexdigest()


def can_reparse(*, status: str, has_storage_key: bool) -> tuple[bool, str]:
    """(boleh, alasan). `alasan` kosong bila boleh."""
    if status != _REPARSEABLE:
        return False, (
            f"Hanya berkas gagal yang dapat diurai ulang "
            f"(status saat ini: {status})."
        )
    if not has_storage_key:
        return False, "Berkas mentah tidak lagi tersedia di penyimpanan."
    return True, ""


def is_duplicate(*, content_hash: str | None, parsed_hashes: set[str]) -> bool:
    """True bila isi berkas ini sudah pernah BERHASIL diurai di penugasan yang sama."""
    if not content_hash:
        return False  # berkas lama tanpa hash: jangan pernah dianggap duplikat
    return content_hash in parsed_hashes
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_ingest_rules.py -q`
Expected: PASS — 10 passed

- [ ] **Step 5: Pastikan tes lama tidak rusak**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 147 passed (137 lama + 10 baru)

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/rules.py backend/tests/test_ingest_rules.py
git commit -m "feat(ingest): aturan urai ulang & deteksi duplikat berkas

Urai ulang hanya untuk berkas gagal: mengulang yang sudah berhasil menaikkan
occurrences tiap temuan, dan angka itu ikut menentukan prioritas triase.
Duplikat hanya ditolak bila berkas sebelumnya BERHASIL diurai — tanpa
pengecualian itu, menambah parser baru tak akan pernah membuat berkas lama
bisa masuk."
```

---

### Task 2: Kolom hash dan penolakan duplikat

**Files:**
- Create: `backend/alembic/versions/b3d8f1c05a92_scan_upload_content_hash.py`
- Modify: `backend/app/models/scan_upload.py`
- Modify: `backend/app/api/routes/engagements.py`
- Modify: `backend/app/workers/tasks.py`

**Interfaces:**
- Consumes: `sha256_of`, `is_duplicate` (Task 1)
- Produces: `ScanUpload.content_hash: str | None`; unggah manual duplikat → `409`; watcher duplikat → berkas pindah ke `processed/` tanpa `ScanUpload` baru

- [ ] **Step 1: Buat migrasi**

Buat `backend/alembic/versions/b3d8f1c05a92_scan_upload_content_hash.py`:

```python
"""sidik jari isi berkas pada scan_uploads

Revision ID: b3d8f1c05a92
Revises: a7c4e9b2f130
Create Date: 2026-08-04 05:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3d8f1c05a92'
down_revision: str | None = 'a7c4e9b2f130'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: berkas yang masuk sebelum kolom ini ada tidak punya hash, dan
    # tidak boleh dianggap duplikat karenanya. Terindeks karena setiap ingest
    # melakukan satu pencarian terhadapnya.
    op.add_column(
        'scan_uploads', sa.Column('content_hash', sa.String(length=64), nullable=True)
    )
    op.create_index(
        'ix_scan_uploads_content_hash', 'scan_uploads', ['content_hash']
    )


def downgrade() -> None:
    op.drop_index('ix_scan_uploads_content_hash', table_name='scan_uploads')
    op.drop_column('scan_uploads', 'content_hash')
```

- [ ] **Step 2: Tambah kolom pada model**

Di `backend/app/models/scan_upload.py`, tambahkan setelah baris `error`:

```python
    # Sidik jari isi berkas (SHA-256) untuk menolak unggahan ganda. Kosong pada
    # berkas yang masuk sebelum kolom ini ada.
    content_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
```

- [ ] **Step 3: Jalankan migrasi**

Run: `docker exec auditforge-api-1 alembic upgrade head`
Expected: `Running upgrade a7c4e9b2f130 -> b3d8f1c05a92`

Verifikasi:
Run: `docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c "\d scan_uploads" | grep content_hash`
Expected: satu baris `content_hash | character varying(64)`

- [ ] **Step 4: Tolak duplikat pada unggah manual**

Di `backend/app/api/routes/engagements.py`, tambahkan impor setelah `from app.eval.timing import timing_summary`:

```python
from app.ingest.rules import can_reparse, is_duplicate, sha256_of
```

Lalu di fungsi `upload_scan`, tepat setelah `content = await file.read()`, sisipkan:

```python
    # Tolak berkas yang isinya sudah pernah BERHASIL diurai di penugasan ini.
    # Yang dulu gagal tidak masuk himpunan ini, jadi tetap boleh dikirim ulang.
    content_hash = sha256_of(content)
    parsed_hashes = set(
        db.scalars(
            select(ScanUpload.content_hash).where(
                ScanUpload.engagement_id == engagement_id,
                ScanUpload.status == UploadStatus.parsed.value,
                ScanUpload.content_hash.is_not(None),
            )
        ).all()
    )
    if is_duplicate(content_hash=content_hash, parsed_hashes=parsed_hashes):
        existing = db.scalar(
            select(ScanUpload).where(
                ScanUpload.engagement_id == engagement_id,
                ScanUpload.content_hash == content_hash,
                ScanUpload.status == UploadStatus.parsed.value,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Berkas dengan isi identik sudah diserap "
                f"(unggahan #{existing.id if existing else '?'})."
            ),
        )
```

Lalu pada pembuatan objek `ScanUpload` di fungsi yang sama, tambahkan satu argumen:

```python
        uploaded_by=user.id,
        content_hash=content_hash,
    )
```

Tambahkan `UploadStatus` ke impor enum bila belum ada:

```python
from app.models.enums import ScanTool, UploadStatus
```

- [ ] **Step 5: Lewati duplikat pada jalur watcher**

Di `backend/app/workers/tasks.py`, tambahkan impor setelah `from app.ingest.watcher import iter_inbox_files, move_result`:

```python
from app.ingest.rules import is_duplicate, sha256_of
```

Lalu di `_ingest_watched_file`, ganti isi fungsi dari pembacaan berkas sampai pembuatan `ScanUpload` menjadi:

```python
    with open(path, "rb") as fh:
        content = fh.read()

    # Berkas identik yang sudah berhasil diserap: pindahkan ke processed/ tanpa
    # memproses ulang. Ini bukan kegagalan, jadi jangan masuk failed/.
    content_hash = sha256_of(content)
    parsed_hashes = set(
        db.scalars(
            select(ScanUpload.content_hash).where(
                ScanUpload.engagement_id == engagement_id,
                ScanUpload.status == UploadStatus.parsed.value,
                ScanUpload.content_hash.is_not(None),
            )
        ).all()
    )
    if is_duplicate(content_hash=content_hash, parsed_hashes=parsed_hashes):
        return True

    safe = name.replace("/", "_").replace("\\", "_")
    key = f"uploads/{engagement_id}/{uuid.uuid4().hex}_{safe}"
    put_bytes(key, content)
    upload = ScanUpload(
        engagement_id=engagement_id,
        filename=safe,
        tool="unknown",  # deteksi perkakas otomatis via sniff() saat parse
        storage_key=key,
        uploaded_by=None,  # None = ingest otomatis (bukan aksi pengguna)
        content_hash=content_hash,
    )
```

Sisa fungsi (mulai `db.add(upload)`) tidak berubah.

- [ ] **Step 6: Restart worker dan beat**

Kode task Celery tidak hot-reload.

Run: `docker compose restart worker beat`
Expected: keduanya `Started`

- [ ] **Step 7: Uji manual penolakan duplikat**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
# Unggah pertama → 201
curl -s -o /dev/null -w "unggah-1: %{http_code}\n" -X POST http://localhost:8000/engagements/17/uploads -H "Authorization: Bearer $TOKEN" -F "file=@datasets/fixtures/zap-sample.json"
sleep 5
# Unggah kedua dengan berkas sama → 409
curl -s -w "\nunggah-2: %{http_code}\n" -X POST http://localhost:8000/engagements/17/uploads -H "Authorization: Bearer $TOKEN" -F "file=@datasets/fixtures/zap-sample.json"
```
Expected: yang pertama `201`, yang kedua `409` beserta nomor unggahan aslinya.

- [ ] **Step 8: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 147 passed

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/b3d8f1c05a92_scan_upload_content_hash.py backend/app/models/scan_upload.py backend/app/api/routes/engagements.py backend/app/workers/tasks.py
git commit -m "feat(ingest): tolak berkas duplikat lewat sidik jari isi

Hash dihitung di kedua jalur masuk. Unggah manual duplikat dibalas 409 beserta
nomor unggahan aslinya; jalur watcher memindahkan berkas ke processed/ tanpa
memproses ulang karena duplikat bukan kegagalan. Kolom nullable, berkas lama
tanpa hash tak pernah dianggap duplikat."
```

---

### Task 3: Endpoint urai ulang

**Files:**
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `can_reparse` (Task 1, sudah diimpor di Task 2); `ScanUploadOut` yang sudah ada
- Produces: `POST /engagements/{engagement_id}/uploads/{upload_id}/reparse` → `ScanUploadOut`

- [ ] **Step 1: Tambah endpoint**

Di `backend/app/api/routes/engagements.py`, sisipkan tepat setelah fungsi `list_uploads`:

```python
@router.post(
    "/{engagement_id}/uploads/{upload_id}/reparse", response_model=ScanUploadOut
)
def reparse_upload(
    engagement_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("analyst", "auditor", "admin")),
) -> ScanUploadOut:
    """Urai ulang berkas yang gagal, memakai berkas mentah yang masih tersimpan.

    Bukan keputusan persetujuan melainkan pemrosesan berkas, sehingga analis
    juga berwenang — setara dengan hak mengunggah yang sudah dimilikinya.
    """
    _get_engagement(db, engagement_id)
    upload = db.get(ScanUpload, upload_id)
    if upload is None or upload.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unggahan tak ditemukan"
        )

    ok, reason = can_reparse(
        status=upload.status, has_storage_key=bool(upload.storage_key)
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

    upload.status = UploadStatus.uploaded.value
    upload.error = None
    db.commit()
    db.refresh(upload)
    parse_upload.delay(upload.id)

    return ScanUploadOut(
        id=upload.id,
        engagement_id=upload.engagement_id,
        filename=upload.filename,
        tool=upload.tool,
        status=upload.status,
        error=upload.error,
    )
```

- [ ] **Step 2: Verifikasi endpoint terdaftar**

Run:
```bash
docker exec auditforge-api-1 python -c "
from app.main import app
print([r for r in app.openapi()['paths'] if 'reparse' in r])
"
```
Expected: `['/engagements/{engagement_id}/uploads/{upload_id}/reparse']`

- [ ] **Step 3: Uji penolakan pada berkas yang sudah parsed**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -w "\nstatus: %{http_code}\n" -X POST http://localhost:8000/engagements/17/uploads/110/reparse -H "Authorization: Bearer $TOKEN"
```
Expected: `409` dengan pesan "Hanya berkas gagal yang dapat diurai ulang (status saat ini: parsed)."

- [ ] **Step 4: Uji jalur berhasil**

Berkas `broken-sample.xml` memang rusak, sehingga gagal lagi tidak membuktikan apa pun. Buat kasus yang benar-benar bisa berhasil: ambil unggahan yang sudah `parsed` lalu tandai `failed` di basis data.

```bash
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c "update scan_uploads set status='failed', error='uji urai ulang' where id=110;"
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -X POST http://localhost:8000/engagements/17/uploads/110/reparse -H "Authorization: Bearer $TOKEN"
sleep 6
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c "select id,status,error from scan_uploads where id=110;"
```
Expected: status kembali `parsed`, `error` kosong.

- [ ] **Step 5: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 147 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/engagements.py
git commit -m "feat(api): endpoint urai ulang berkas gagal

Berkas mentah tetap tersimpan di MinIO, jadi mengurai ulang cukup memanggil
task yang sudah ada. Diletakkan di bawah /engagements/{id} agar ikut terlindungi
saat Modul 2 memasang pembatasan keanggotaan. Analis juga berwenang: ini
pemrosesan berkas, bukan keputusan persetujuan."
```

---

### Task 4: Endpoint aktivitas ingest lintas penugasan

**Files:**
- Create: `backend/app/api/routes/ingest.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `can_reparse` (Task 1); `ScanUpload.content_hash` (Task 2)
- Produces: `GET /ingest` → `{"items": [...], "summary": {"today": int, "failed": int, "total": int}}`; setiap elemen `items` berisi `upload_id`, `engagement_id`, `engagement_name`, `filename`, `tool`, `status`, `error`, `source`, `can_reparse`, `created_at`

- [ ] **Step 1: Buat router**

Buat `backend/app/api/routes/ingest.py`:

```python
"""Pusat Ingest — aktivitas penyerapan berkas lintas penugasan.

Data yang ditampilkan seluruhnya sudah tersimpan di `ScanUpload`; selama ini
hanya tidak pernah ditanyakan lintas penugasan. Tanpa halaman ini, berkas yang
gagal hanya dapat ditemukan dengan membuka tab Berkas pada tiap penugasan satu
per satu.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.ingest.rules import can_reparse
from app.models.engagement import Engagement
from app.models.enums import UploadStatus
from app.models.scan_upload import ScanUpload
from app.models.user import User

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("")
def list_ingest(
    status: str | None = None,
    engagement_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Aktivitas ingest terbaru lintas penugasan, terbaru lebih dulu."""
    # TODO(Modul 2): saring berdasarkan keanggotaan tim setelah engagement_members ada.
    q = (
        select(ScanUpload, Engagement.name)
        .join(Engagement, ScanUpload.engagement_id == Engagement.id)
        .order_by(ScanUpload.created_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    if status:
        q = q.where(ScanUpload.status == status)
    if engagement_id is not None:
        q = q.where(ScanUpload.engagement_id == engagement_id)

    items = []
    for up, eng_name in db.execute(q).all():
        ok, _reason = can_reparse(
            status=up.status, has_storage_key=bool(up.storage_key)
        )
        items.append(
            {
                "upload_id": up.id,
                "engagement_id": up.engagement_id,
                "engagement_name": eng_name,
                "filename": up.filename,
                "tool": up.tool,
                "status": up.status,
                "error": up.error,
                # uploaded_by kosong = diserap otomatis oleh watcher (R3).
                "source": "manual" if up.uploaded_by else "watcher",
                "can_reparse": ok,
                "created_at": up.created_at.isoformat() if up.created_at else None,
            }
        )

    since = datetime.now(UTC) - timedelta(days=1)
    today = db.scalar(
        select(func.count())
        .select_from(ScanUpload)
        .where(ScanUpload.created_at >= since)
    ) or 0
    failed = db.scalar(
        select(func.count())
        .select_from(ScanUpload)
        .where(ScanUpload.status == UploadStatus.failed.value)
    ) or 0
    total = db.scalar(select(func.count()).select_from(ScanUpload)) or 0

    return {
        "items": items,
        "summary": {"today": today, "failed": failed, "total": total},
    }
```

- [ ] **Step 2: Daftarkan router**

Di `backend/app/main.py`, tambahkan impor setelah `from app.api.routes import engagements as engagement_routes`:

```python
from app.api.routes import ingest as ingest_routes
```

Lalu setelah `app.include_router(engagement_routes.router)`:

```python
app.include_router(ingest_routes.router)
```

- [ ] **Step 3: Verifikasi keluaran**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s "http://localhost:8000/ingest?status=failed" -H "Authorization: Bearer $TOKEN" | python -c "
import sys,json
d=json.load(sys.stdin)
print('gagal ditampilkan:', len(d['items']))
print('ringkasan        :', d['summary'])
for i in d['items'][:3]:
    print(' -', i['engagement_id'], i['filename'], i['source'], 'reparse:', i['can_reparse'])
"
```
Expected: enam hingga tujuh berkas gagal dari beberapa penugasan berbeda, `can_reparse: True` pada yang berkasnya masih ada, dan `summary.failed` bernilai sama dengan jumlah baris berstatus `failed`.

- [ ] **Step 4: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 147 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/ingest.py backend/app/main.py
git commit -m "feat(api): endpoint aktivitas ingest lintas penugasan

Router terpisah, bukan ditambahkan ke engagements.py yang sudah ~710 baris —
cakupannya memang berbeda. Kolom source diturunkan dari uploaded_by; konvensi
None untuk ingest otomatis sudah dipakai _ingest_watched_file."
```

---

### Task 5: Halaman Pusat Ingest

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/app/ingest/page.tsx`

**Interfaces:**
- Consumes: `GET /ingest` (Task 4); `POST /engagements/{eid}/uploads/{uid}/reparse` (Task 3)
- Produces: halaman `/ingest`; fungsi klien `getIngest`, `reparseUpload`

- [ ] **Step 1: Tambah tipe dan fungsi klien**

Di `frontend/src/lib/api.ts`, sisipkan sebelum komentar `// ---------- D17: transparansi masking`:

```ts
// ---------- Pusat Ingest ----------
export interface IngestItem {
  upload_id: number;
  engagement_id: number;
  engagement_name: string;
  filename: string;
  tool: string;
  status: string;
  error: string | null;
  /** "manual" bila diunggah pengguna, "watcher" bila diserap otomatis (R3). */
  source: string;
  can_reparse: boolean;
  created_at: string | null;
}
export interface IngestOverview {
  items: IngestItem[];
  summary: { today: number; failed: number; total: number };
}
export const getIngest = (status?: string) =>
  req<IngestOverview>(`/ingest${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const reparseUpload = (engagementId: number, uploadId: number) =>
  req<ScanUpload>(`/engagements/${engagementId}/uploads/${uploadId}/reparse`, {
    method: "POST",
  });
```

- [ ] **Step 2: Tambah kunci terjemahan ke KEDUA locale**

Di `frontend/src/i18n/messages.ts`, pada blok `id`, sisipkan setelah `"nav.admin": "Administrasi",`:

```ts
    "nav.ingest": "Ingest",
    "ingest.subtitle": "Aktivitas penyerapan berkas dari seluruh penugasan.",
    "ingest.today": "Masuk 24 jam terakhir",
    "ingest.failed": "Gagal belum ditangani",
    "ingest.total": "Total berkas",
    "ingest.colTime": "Waktu",
    "ingest.colEngagement": "Penugasan",
    "ingest.colFile": "Berkas",
    "ingest.colTool": "Perkakas",
    "ingest.colSource": "Asal",
    "ingest.colStatus": "Status",
    "ingest.colAction": "Aksi",
    "ingest.reparse": "Urai Ulang",
    "ingest.reparsing": "Mengurai…",
    "ingest.empty": "Belum ada aktivitas ingest.",
    "ingest.filterAll": "Semua",
    "ingest.filterFailed": "Gagal saja",
    "ingest.sourceManual": "manual",
    "ingest.sourceWatcher": "otomatis",
```

Pada blok `en`, sisipkan setelah `"nav.admin": "Administration",` padanannya:

```ts
    "nav.ingest": "Ingest",
    "ingest.subtitle": "File ingestion activity across all engagements.",
    "ingest.today": "Last 24 hours",
    "ingest.failed": "Unresolved failures",
    "ingest.total": "Total files",
    "ingest.colTime": "Time",
    "ingest.colEngagement": "Engagement",
    "ingest.colFile": "File",
    "ingest.colTool": "Tool",
    "ingest.colSource": "Source",
    "ingest.colStatus": "Status",
    "ingest.colAction": "Action",
    "ingest.reparse": "Re-parse",
    "ingest.reparsing": "Parsing…",
    "ingest.empty": "No ingestion activity yet.",
    "ingest.filterAll": "All",
    "ingest.filterFailed": "Failed only",
    "ingest.sourceManual": "manual",
    "ingest.sourceWatcher": "automatic",
```

- [ ] **Step 3: Tambah item sidebar**

Di `frontend/src/components/AppShell.tsx`, tambahkan `Path` ke daftar impor ikon Phosphor yang sudah ada, lalu sisipkan satu entri pada array navigasi antara `/reports` dan `/admin`:

```tsx
  { href: "/ingest", icon: <Path size={18} />, key: "nav.ingest" },
```

- [ ] **Step 4: Buat halaman**

Buat `frontend/src/app/ingest/page.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowClockwise } from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function IngestPage() {
  const { t } = useI18n();
  const [data, setData] = useState<api.IngestOverview | null>(null);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .getIngest(onlyFailed ? "failed" : undefined)
      .then((d) => {
        setData(d);
        setLoadFailed(false);
      })
      .catch((err) => {
        setLoadFailed(true);
        setError(err instanceof ApiError ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [onlyFailed]);

  useEffect(load, [load]);

  async function reparse(item: api.IngestItem) {
    setBusyId(item.upload_id);
    setError(null);
    try {
      await api.reparseUpload(item.engagement_id, item.upload_id);
      // Parsing berjalan asinkron di worker; beri jeda sebelum memuat ulang.
      setTimeout(load, 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  const items = data?.items ?? [];

  return (
    <AppShell title={t("nav.ingest")}>
      <section className="card">
        <p className="muted" style={{ marginTop: 0 }}>{t("ingest.subtitle")}</p>
        <div className="form-row">
          <div className="field">
            <span>{t("ingest.today")}</span>
            <strong className="mono">{data?.summary.today ?? 0}</strong>
          </div>
          <div className="field">
            <span>{t("ingest.failed")}</span>
            <strong className="mono">{data?.summary.failed ?? 0}</strong>
          </div>
          <div className="field">
            <span>{t("ingest.total")}</span>
            <strong className="mono">{data?.summary.total ?? 0}</strong>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            className={onlyFailed ? "btn secondary" : "btn"}
            onClick={() => setOnlyFailed(false)}
          >
            {t("ingest.filterAll")}
          </button>
          <button
            className={onlyFailed ? "btn" : "btn secondary"}
            onClick={() => setOnlyFailed(true)}
          >
            {t("ingest.filterFailed")}
          </button>
        </div>
        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="card">
        {loading ? (
          <p className="muted">…</p>
        ) : loadFailed ? (
          <p className="muted">{t("ingest.empty")}</p>
        ) : items.length === 0 ? (
          <p className="muted">{t("ingest.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("ingest.colTime")}</th>
                  <th>{t("ingest.colEngagement")}</th>
                  <th>{t("ingest.colFile")}</th>
                  <th>{t("ingest.colTool")}</th>
                  <th>{t("ingest.colSource")}</th>
                  <th>{t("ingest.colStatus")}</th>
                  <th>{t("ingest.colAction")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.upload_id}>
                    <td className="mono">{fmtTime(it.created_at)}</td>
                    <td>
                      <Link className="link" href={`/engagements/${it.engagement_id}`}>
                        #{it.engagement_id} {it.engagement_name}
                      </Link>
                    </td>
                    <td>{it.filename}</td>
                    <td className="mono">{it.tool}</td>
                    <td className="mono">
                      {it.source === "manual"
                        ? t("ingest.sourceManual")
                        : t("ingest.sourceWatcher")}
                    </td>
                    <td>
                      <span
                        className={`badge ${it.status === "parsed" ? "ok" : it.status === "failed" ? "err" : "wait"}`}
                        title={it.error ?? ""}
                      >
                        {it.status}
                      </span>
                    </td>
                    <td>
                      {it.can_reparse && (
                        <button
                          className="btn secondary"
                          disabled={busyId === it.upload_id}
                          onClick={() => reparse(it)}
                        >
                          <ArrowClockwise size={14} />{" "}
                          {busyId === it.upload_id
                            ? t("ingest.reparsing")
                            : t("ingest.reparse")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
```

- [ ] **Step 5: Typecheck**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: tanpa keluaran. Bila muncul galat kunci terjemahan, ada kunci yang belum ditambahkan ke salah satu locale.

- [ ] **Step 6: Verifikasi di peramban**

Buka `http://localhost:3000/ingest` setelah masuk sebagai `admin@auditforge.local`.
Expected: item **Ingest** muncul di sidebar; tabel memuat aktivitas dari beberapa penugasan; penyaring **Gagal saja** menyisakan berkas gagal; tombol **Urai Ulang** hanya muncul pada baris gagal; arahkan kursor ke badge status gagal untuk melihat pesan galatnya.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/i18n/messages.ts frontend/src/components/AppShell.tsx frontend/src/app/ingest/page.tsx
git commit -m "feat(web): halaman Pusat Ingest

Aktivitas ingest seluruh penugasan dalam satu tabel, dengan penyaring gagal dan
tombol Urai Ulang di tempat. Sebelumnya berkas gagal hanya bisa ditemukan
dengan membuka tab Berkas tiap penugasan satu per satu."
```

---

### Task 6: Tombol Urai Ulang di tab Berkas penugasan

**Files:**
- Modify: `frontend/src/app/engagements/[id]/page.tsx`

**Interfaces:**
- Consumes: `reparseUpload` (Task 5); kunci `ingest.reparse` dan `ingest.reparsing` (Task 5)
- Produces: tidak ada yang bergantung padanya

- [ ] **Step 1: Tambah state dan handler**

Di `frontend/src/app/engagements/[id]/page.tsx`, tambahkan satu state bersama state lain di komponen utama:

```tsx
  const [reparsingId, setReparsingId] = useState<number | null>(null);
```

Lalu tambahkan handler di dekat fungsi pemuatan berkas yang sudah ada:

```tsx
  async function handleReparse(uploadId: number) {
    setReparsingId(uploadId);
    setError(null);
    try {
      await api.reparseUpload(id, uploadId);
      // Parsing asinkron di worker; beri jeda sebelum memuat ulang daftar berkas.
      setTimeout(() => void refresh(), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setReparsingId(null);
    }
  }
```

Fungsi pemuat ulang pada berkas ini bernama `refresh` (didefinisikan sebagai
`useCallback` di sekitar baris 135, memuat engagement + uploads + findings + evaluasi +
timing sekaligus). Letakkan `handleReparse` setelah definisi `refresh` agar ia sudah
terdeklarasi saat dipanggil.

- [ ] **Step 2: Tambah tombol pada baris berstatus failed**

Pada tabel daftar berkas di tab **Berkas**, tambahkan satu sel di akhir tiap baris:

```tsx
                    <td>
                      {u.status === "failed" && (
                        <button
                          className="btn secondary"
                          disabled={reparsingId === u.id}
                          onClick={() => handleReparse(u.id)}
                        >
                          <ArrowClockwise size={14} />{" "}
                          {reparsingId === u.id
                            ? t("ingest.reparsing")
                            : t("ingest.reparse")}
                        </button>
                      )}
                    </td>
```

Tambahkan `ArrowClockwise` ke daftar impor Phosphor pada berkas ini, dan satu `<th />` kosong pada baris kepala tabel berkas agar jumlah kolomnya cocok.

- [ ] **Step 3: Typecheck**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: tanpa keluaran

- [ ] **Step 4: Verifikasi di peramban**

Buka `http://localhost:3000/engagements/17` → tab **Berkas**.
Expected: baris `broken-sample.xml` (status `failed`) menampilkan tombol **Urai Ulang**; baris berstatus `parsed` tidak. Menekannya membuat status berpindah ke `parsing` lalu kembali `failed` — berkas itu memang rusak, dan itulah perilaku yang benar.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/engagements/[id]/page.tsx
git commit -m "feat(web): tombol urai ulang di tab Berkas penugasan

Auditor yang sudah berada di dalam sebuah penugasan tak perlu berpindah ke
halaman Ingest hanya untuk mencoba ulang satu berkas."
```

---

## Verifikasi Akhir

- [ ] `docker exec auditforge-api-1 python -m pytest -q` → 147 passed
- [ ] `docker exec auditforge-web-1 npx tsc --noEmit` → bersih
- [ ] `/ingest` menampilkan berkas gagal dari beberapa penugasan sekaligus
- [ ] Unggah berkas identik yang sudah berhasil diserap → `409`
- [ ] Taruh berkas identik di `datasets/watch/inbox/17/` → berpindah ke `processed/`, tidak ada `ScanUpload` baru
- [ ] Urai ulang berkas `parsed` → ditolak `409`
- [ ] `docker exec auditforge-api-1 alembic downgrade -1 && docker exec auditforge-api-1 alembic upgrade head` berjalan tanpa galat

## Yang Belum Dikerjakan Plan Ini

| Bagian spec | Alasan |
|---|---|
| Notifikasi in-app + email | Spec terpisah, dibangun setelah ini — bagian inilah yang menghasilkan peristiwanya |
| Penyaringan `GET /ingest` berdasarkan keanggotaan tim | Berasal dari Modul 2 spec penyelarasan-proposal; ditandai `TODO(Modul 2)` di kode |
| Kolom `source` untuk jalur agent | Direncanakan spec `remote-scan-ingest`; halaman ini sudah menampilkan kolom Asal dan tinggal membacanya |
| Pengisian mundur hash berkas lama | Mengunduh puluhan berkas dari MinIO demi manfaat nol |

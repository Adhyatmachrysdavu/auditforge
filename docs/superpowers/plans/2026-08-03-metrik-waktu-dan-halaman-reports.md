# Metrik Waktu Penyusunan + Halaman /reports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengukur waktu penyusunan laporan dari jejak revisi yang sudah terekam, lalu menyajikannya di halaman `/reports` yang saat ini masih *stub* — sehingga indikator keberhasilan proposal ("penurunan waktu penyusunan laporan minimal 50%") dapat dibuktikan dengan data.

**Architecture:** Seluruh perhitungan deterministik dan ditempatkan pada satu modul murni (`app/eval/timing.py`) yang tidak menyentuh basis data, mengikuti pola `app/eval/engagement_eval.py` yang sudah ada. Lapisan route hanya mengambil baris `FindingRevision` lalu meneruskannya. Angka pembanding (*baseline* manual) diisi manusia melalui endpoint terpisah; bila kosong, sistem menampilkan waktu aktual tanpa mengklaim penghematan apa pun.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest · Next.js 14 App Router, TypeScript, Phosphor Icons

## Global Constraints

- Seluruh tes baru **murni**: tanpa DB, Redis, MinIO, LLM, dan tanpa `conftest.py`. Objek palsu memakai `types.SimpleNamespace` (lihat `tests/test_engagement_eval.py`).
- Docstring dan komentar ditulis dalam **Bahasa Indonesia**; identifier dan nama field API dalam Bahasa Inggris.
- Setiap teks UI baru wajib ditambahkan ke **kedua** locale pada `frontend/src/i18n/messages.ts` (tipe `MessageKey` menjaga sinkronisasi).
- Perkakas dev tidak ada di image: jalankan `docker exec auditforge-api-1 pip install -e ".[dev]"` sekali sebelum memakai pytest.
- Jangan menyentuh `triage.py`, masking, RBAC persetujuan, maupun pipeline deterministik yang sudah berjalan.
- Ambang jeda kerja aktif: **1800 detik (30 menit)**.
- Alembic head saat ini: **`c9f2a6b3d5e8`**.

---

## File Structure

| Berkas | Tanggung jawab |
|---|---|
| `backend/app/eval/timing.py` | **Baru.** Seluruh logika perhitungan waktu. Murni, tanpa DB |
| `backend/tests/test_timing.py` | **Baru.** Tes untuk modul di atas |
| `backend/alembic/versions/f1a2b3c4d5e6_engagement_baseline.py` | **Baru.** Dua kolom baseline |
| `backend/app/models/engagement.py` | Tambah 2 kolom |
| `backend/app/schemas/engagement.py` | Tambah `BaselineIn`, perluas `EngagementDetailOut` |
| `backend/app/api/routes/engagements.py` | Tambah `GET .../timing` dan `PUT .../baseline` |
| `backend/app/api/routes/stats.py` | Tambah `GET /stats/timing` |
| `frontend/src/lib/api.ts` | Tipe + fungsi klien |
| `frontend/src/i18n/messages.ts` | Kunci ID + EN |
| `frontend/src/app/reports/page.tsx` | **Tulis ulang** dari *stub* |

---

### Task 1: Modul murni perhitungan waktu

**Files:**
- Create: `backend/app/eval/timing.py`
- Test: `backend/tests/test_timing.py`

**Interfaces:**
- Consumes: tidak ada (task pertama)
- Produces:
  - `active_work_seconds(timestamps: Iterable[datetime], *, gap_seconds: float = 1800.0) -> float`
  - `timing_summary(events: list[object], *, baseline_hours: float | None = None, gap_seconds: float = 1800.0) -> dict[str, object]`
  - `DEFAULT_GAP_SECONDS: float = 1800.0`
  - `events` bersifat *duck-typed*: setiap elemen memiliki atribut `.action` (str) dan `.created_at` (datetime)
  - Kunci keluaran `timing_summary`: `event_count`, `first_at`, `last_at`, `calendar_seconds`, `active_seconds`, `active_hours`, `events_by_action`, `baseline_hours`, `saved_hours`, `saved_ratio`

**Catatan penyimpangan dari spec:** spec menyebut "waktu per tahap (ingest / draf AI / review)". Pembagian itu tidak dapat dihitung secara jujur dari data yang ada — sebuah revisi `edit` tidak memberi tahu berapa lama auditor benar-benar mengetik. Sebagai gantinya dikeluarkan `events_by_action` (jumlah peristiwa per jenis aksi), yang faktual dan tidak mengarang. Bila kelak pembagian waktu per tahap benar-benar dibutuhkan, ia memerlukan instrumentasi baru di sisi UI, bukan pengolahan ulang data lama.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_timing.py`:

```python
"""Uji unit Modul 1 — pengukuran waktu penyusunan laporan (tanpa DB)."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.eval.timing import active_work_seconds, timing_summary

T0 = datetime(2026, 8, 1, 9, 0, 0)


def _ev(action: str, minutes: float):
    """Peristiwa revisi palsu (duck-typed seperti FindingRevision)."""
    return SimpleNamespace(action=action, created_at=T0 + timedelta(minutes=minutes))


def test_active_work_ignores_long_gaps():
    # 0 → +10 mnt (600 dtk, dihitung) → +5 jam (jeda panjang, dibuang)
    #   → +5 jam 10 mnt (600 dtk, dihitung). Total 1200 dtk.
    stamps = [
        T0,
        T0 + timedelta(minutes=10),
        T0 + timedelta(hours=5),
        T0 + timedelta(hours=5, minutes=10),
    ]
    assert active_work_seconds(stamps) == 1200.0


def test_active_work_empty_and_single():
    assert active_work_seconds([]) == 0.0
    assert active_work_seconds([T0]) == 0.0


def test_active_work_unsorted_input():
    # Urutan masukan tak boleh memengaruhi hasil.
    stamps = [T0 + timedelta(minutes=10), T0, T0 + timedelta(minutes=20)]
    assert active_work_seconds(stamps) == 1200.0


def test_summary_without_baseline_claims_nothing():
    # Tanpa baseline, sistem melaporkan waktu aktual tapi TIDAK mengklaim penghematan.
    evs = [_ev("ai_draft", 0), _ev("edit", 10), _ev("approve", 20)]
    m = timing_summary(evs)
    assert m["active_seconds"] == 1200.0
    assert m["active_hours"] == 0.33
    assert m["baseline_hours"] is None
    assert m["saved_hours"] is None
    assert m["saved_ratio"] is None


def test_summary_with_baseline_computes_saving():
    evs = [_ev("ai_draft", 0), _ev("edit", 10), _ev("approve", 20)]
    m = timing_summary(evs, baseline_hours=8.0)
    assert m["active_hours"] == 0.33
    assert m["saved_hours"] == 7.67
    assert m["saved_ratio"] == 0.9588


def test_summary_baseline_zero_no_divzero():
    # Baseline 0 tak masuk akal → diperlakukan seperti tidak ada, bukan pembagian nol.
    evs = [_ev("edit", 0), _ev("approve", 5)]
    m = timing_summary(evs, baseline_hours=0.0)
    assert m["saved_ratio"] is None
    assert m["saved_hours"] is None


def test_summary_counts_actions_and_bounds():
    evs = [_ev("ai_draft", 0), _ev("edit", 5), _ev("edit", 10), _ev("approve", 15)]
    m = timing_summary(evs)
    assert m["event_count"] == 4
    assert m["events_by_action"] == {"ai_draft": 1, "edit": 2, "approve": 1}
    assert m["first_at"] == T0.isoformat()
    assert m["last_at"] == (T0 + timedelta(minutes=15)).isoformat()
    assert m["calendar_seconds"] == 900.0


def test_summary_empty_events():
    m = timing_summary([])
    assert m["event_count"] == 0
    assert m["first_at"] is None
    assert m["last_at"] is None
    assert m["active_seconds"] == 0.0
    assert m["calendar_seconds"] == 0.0
    assert m["events_by_action"] == {}
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_timing.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.eval.timing'`

- [ ] **Step 3: Tulis implementasi minimal**

Buat `backend/app/eval/timing.py`:

```python
"""Pengukuran waktu penyusunan laporan (Modul 1) — deterministik, tanpa DB.

Indikator keberhasilan proposal menuntut bukti "penurunan waktu penyusunan
laporan minimal 50%". Data waktunya sudah terekam sejak awal di
`FindingRevision` (kolom `action` + `created_at`), sehingga metrik dapat
dihitung mundur untuk penugasan yang sudah berjalan.

Yang dihitung adalah **waktu kerja aktif**, bukan waktu kalender: selisih
antar-peristiwa yang lebih panjang dari ambang jeda dianggap istirahat dan
tidak dijumlahkan. Tanpa pembatasan itu angka akan mencakup malam dan akhir
pekan sehingga tak dapat dipertahankan saat ditanya.

Bila `baseline_hours` tidak diisi, modul ini melaporkan waktu aktual tetapi
tidak mengklaim penghematan apa pun — lebih baik kosong daripada mengarang.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

DEFAULT_GAP_SECONDS = 1800.0  # 30 menit


def active_work_seconds(
    timestamps: Iterable[datetime], *, gap_seconds: float = DEFAULT_GAP_SECONDS
) -> float:
    """Jumlah selisih antar-peristiwa berurutan yang lebih pendek dari `gap_seconds`."""
    ts = sorted(timestamps)
    total = 0.0
    for earlier, later in zip(ts, ts[1:]):
        delta = (later - earlier).total_seconds()
        if 0 < delta < gap_seconds:
            total += delta
    return total


def timing_summary(
    events: list[object],
    *,
    baseline_hours: float | None = None,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
) -> dict[str, object]:
    """Ringkas jejak revisi menjadi metrik waktu (duck-typed: `.action`, `.created_at`)."""
    stamps = sorted(
        s for s in (getattr(e, "created_at", None) for e in events)
        if isinstance(s, datetime)
    )

    by_action: dict[str, int] = {}
    for e in events:
        a = str(getattr(e, "action", "") or "unknown")
        by_action[a] = by_action.get(a, 0) + 1

    active = active_work_seconds(stamps, gap_seconds=gap_seconds)
    calendar = (stamps[-1] - stamps[0]).total_seconds() if len(stamps) >= 2 else 0.0
    active_hours = round(active / 3600, 2)

    saved_hours: float | None = None
    saved_ratio: float | None = None
    # Baseline <= 0 diperlakukan seperti tidak ada: tak ada yang bisa dibandingkan.
    if baseline_hours is not None and baseline_hours > 0:
        saved_hours = round(baseline_hours - active_hours, 2)
        saved_ratio = round(saved_hours / baseline_hours, 4)

    return {
        "event_count": len(events),
        "first_at": stamps[0].isoformat() if stamps else None,
        "last_at": stamps[-1].isoformat() if stamps else None,
        "calendar_seconds": round(calendar, 2),
        "active_seconds": round(active, 2),
        "active_hours": active_hours,
        "events_by_action": by_action,
        "baseline_hours": baseline_hours,
        "saved_hours": saved_hours,
        "saved_ratio": saved_ratio,
    }
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_timing.py -q`
Expected: PASS — 8 passed

- [ ] **Step 5: Pastikan tes lama tidak rusak**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 117 passed (109 lama + 8 baru)

- [ ] **Step 6: Commit**

```bash
git add backend/app/eval/timing.py backend/tests/test_timing.py
git commit -m "feat(eval): hitung waktu kerja aktif penyusunan laporan

Waktu kerja aktif, bukan waktu kalender: jeda > 30 menit dianggap istirahat
dan tidak dijumlahkan, supaya angkanya tidak mencakup malam dan akhir pekan.
Tanpa baseline, sistem melaporkan waktu aktual tanpa mengklaim penghematan."
```

---

### Task 2: Kolom baseline pada penugasan

**Files:**
- Create: `backend/alembic/versions/f1a2b3c4d5e6_engagement_baseline.py`
- Modify: `backend/app/models/engagement.py`
- Modify: `backend/app/schemas/engagement.py`

**Interfaces:**
- Consumes: tidak ada
- Produces:
  - `Engagement.baseline_hours: float | None`, `Engagement.baseline_note: str | None`
  - `BaselineIn` (Pydantic) dengan field `baseline_hours: float | None` dan `baseline_note: str | None`
  - `EngagementDetailOut` bertambah field `baseline_hours` dan `baseline_note`

- [ ] **Step 1: Buat migrasi**

Buat `backend/alembic/versions/f1a2b3c4d5e6_engagement_baseline.py`:

```python
"""engagement baseline waktu penyusunan (Modul 1)

Revision ID: f1a2b3c4d5e6
Revises: c9f2a6b3d5e8
Create Date: 2026-08-03 14:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: str | None = 'c9f2a6b3d5e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('engagements', sa.Column('baseline_hours', sa.Float(), nullable=True))
    op.add_column('engagements', sa.Column('baseline_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('engagements', 'baseline_note')
    op.drop_column('engagements', 'baseline_hours')
```

- [ ] **Step 2: Tambah kolom pada model**

Di `backend/app/models/engagement.py`, ubah baris impor SQLAlchemy agar menyertakan `Float`:

```python
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
```

Lalu tambahkan dua kolom di akhir kelas `Engagement`, setelah `exec_summary`:

```python
    # --- Modul 1: baseline pembanding waktu penyusunan manual ---
    # Diisi manusia; sistem tak punya cara mengetahuinya sendiri. Kosong = tak
    # ada klaim penghematan.
    baseline_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Tambah skema**

Di `backend/app/schemas/engagement.py`, tambahkan kelas baru setelah `EngagementDetailOut`:

```python
class BaselineIn(BaseModel):
    """Angka pembanding waktu penyusunan manual (Modul 1)."""

    baseline_hours: float | None = Field(default=None, ge=0)
    baseline_note: str | None = None
```

Lalu tambahkan dua field ke `EngagementDetailOut`:

```python
class EngagementDetailOut(EngagementOut):
    # --- D11: ringkasan eksekutif AI ---
    exec_summary_generated: bool = False
    exec_summary_model: str | None = None
    exec_summary_prompt_version: str | None = None
    exec_summary: dict | None = None
    # --- Modul 1: baseline waktu ---
    baseline_hours: float | None = None
    baseline_note: str | None = None
```

- [ ] **Step 4: Jalankan migrasi**

Run: `docker exec auditforge-api-1 alembic upgrade head`
Expected: `Running upgrade c9f2a6b3d5e8 -> f1a2b3c4d5e6`

- [ ] **Step 5: Verifikasi kolom ada**

Run: `docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c "\d engagements" | grep baseline`
Expected: dua baris — `baseline_hours | double precision` dan `baseline_note | text`

- [ ] **Step 6: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 117 passed

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/f1a2b3c4d5e6_engagement_baseline.py backend/app/models/engagement.py backend/app/schemas/engagement.py
git commit -m "feat(db): kolom baseline waktu penyusunan pada penugasan

Angka pembanding diisi manusia karena sistem tak punya cara mengetahui berapa
lama laporan disusun secara manual. Keduanya nullable, data lama tak terpengaruh."
```

---

### Task 3: Endpoint timing dan baseline per penugasan

**Files:**
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `timing_summary` (Task 1); `BaselineIn`, kolom `baseline_hours`/`baseline_note` (Task 2)
- Produces:
  - `GET /engagements/{id}/timing` → objek hasil `timing_summary`
  - `PUT /engagements/{id}/baseline` → `{"baseline_hours": float|null, "baseline_note": str|null}`

Catatan: `require_roles` dan `FindingRevision` **sudah** ter-impor di berkas ini (baris 12 dan 18); tidak perlu ditambahkan.

- [ ] **Step 1: Tambah impor**

Di `backend/app/api/routes/engagements.py`, tepat setelah baris `from app.eval.engagement_eval import evaluate_engagement`:

```python
from app.eval.timing import timing_summary
```

Lalu tambahkan `BaselineIn` ke daftar impor dari `app.schemas.engagement` (urutkan menaik — `BaselineIn` mendahului `EngagementCreate`):

```python
from app.schemas.engagement import (
    AttachmentOut,
    BaselineIn,
    EngagementCreate,
    ...
)
```

- [ ] **Step 2: Tambah kedua endpoint**

Sisipkan tepat setelah fungsi `engagement_evaluation` (berakhir di sekitar baris 650):

```python
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
```

- [ ] **Step 3: Sertakan baseline pada detail penugasan**

Pada fungsi `get_engagement` (sekitar baris 91–109), tambahkan dua argumen terakhir saat membangun `EngagementDetailOut`, tepat setelah `exec_summary=e.exec_summary,`:

```python
        exec_summary=e.exec_summary,
        baseline_hours=e.baseline_hours,
        baseline_note=e.baseline_note,
    )
```

- [ ] **Step 4: Verifikasi endpoint hidup**

Run:
```bash
docker exec auditforge-api-1 python -c "from app.main import app; print([r.path for r in app.routes if 'timing' in r.path or 'baseline' in r.path])"
```
Expected: `['/engagements/{engagement_id}/timing', '/engagements/{engagement_id}/baseline']`

- [ ] **Step 5: Uji manual terhadap data nyata**

Penugasan #17 memiliki riwayat revisi dari pengujian sebelumnya.

Run:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s http://localhost:8000/engagements/17/timing -H "Authorization: Bearer $TOKEN"
```
Expected: JSON berisi `event_count`, `active_seconds`, dan `saved_ratio: null` (baseline belum diisi)

- [ ] **Step 6: Uji pengisian baseline**

Run:
```bash
curl -s -X PUT http://localhost:8000/engagements/17/baseline -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"baseline_hours": 8, "baseline_note": "rata-rata penugasan serupa"}'
curl -s http://localhost:8000/engagements/17/timing -H "Authorization: Bearer $TOKEN"
```
Expected: panggilan pertama mengembalikan baseline yang tersimpan; panggilan kedua kini memuat `saved_hours` dan `saved_ratio` bernilai angka, bukan `null`

- [ ] **Step 7: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 117 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/routes/engagements.py
git commit -m "feat(api): endpoint metrik waktu dan baseline per penugasan

GET .../timing menghitung dari jejak revisi yang sudah ada, jadi penugasan lama
langsung punya angka. PUT .../baseline dibatasi auditor/admin karena angka itu
menjadi dasar klaim penghematan."
```

---

### Task 4: Agregat waktu lintas penugasan

**Files:**
- Modify: `backend/app/api/routes/stats.py`

**Interfaces:**
- Consumes: `timing_summary` (Task 1); kolom baseline (Task 2)
- Produces: `GET /stats/timing` → `{"items": [...], "engagements_measured": int, "avg_saved_ratio": float|null}`; setiap elemen `items` berisi seluruh kunci `timing_summary` ditambah `engagement_id`, `name`, `client_name`, `status`

- [ ] **Step 1: Tulis ulang bagian impor**

Ganti blok impor `backend/app/api/routes/stats.py` menjadi:

```python
"""Statistik ringkas untuk dasbor."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.eval.timing import timing_summary
from app.models.engagement import Engagement
from app.models.enums import Severity
from app.models.finding import Finding, FindingRevision
from app.models.scan_upload import ScanUpload
from app.models.user import User
```

- [ ] **Step 2: Tambah endpoint agregat**

Sisipkan di akhir `backend/app/api/routes/stats.py`:

```python
@router.get("/timing")
def timing_overview(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    """Agregat waktu penyusunan lintas penugasan (Modul 1) untuk halaman /reports.

    Seluruh revisi diambil dalam satu kueri lalu dikelompokkan di memori, agar
    tidak memicu satu kueri per penugasan.
    """
    rows = db.execute(
        select(Finding.engagement_id, FindingRevision.action, FindingRevision.created_at)
        .join(Finding, FindingRevision.finding_id == Finding.id)
        .order_by(FindingRevision.created_at)
    ).all()

    by_eng: dict[int, list[object]] = {}
    for eid, action, created_at in rows:
        by_eng.setdefault(eid, []).append(
            SimpleNamespace(action=action, created_at=created_at)
        )

    items: list[dict] = []
    for e in db.scalars(select(Engagement).order_by(Engagement.id)).all():
        summary = timing_summary(by_eng.get(e.id, []), baseline_hours=e.baseline_hours)
        items.append(
            {
                "engagement_id": e.id,
                "name": e.name,
                "client_name": e.client_name,
                "status": e.status,
                **summary,
            }
        )

    measured = [i for i in items if i["saved_ratio"] is not None]
    avg = (
        round(sum(float(i["saved_ratio"]) for i in measured) / len(measured), 4)
        if measured
        else None
    )
    return {
        "items": items,
        "engagements_measured": len(measured),
        "avg_saved_ratio": avg,
    }
```

- [ ] **Step 3: Verifikasi keluaran**

Run:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s http://localhost:8000/stats/timing -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -30
```
Expected: `items` memuat seluruh penugasan; `engagements_measured` bernilai 1 (hanya #17 yang punya baseline dari Task 3); `avg_saved_ratio` berupa angka

- [ ] **Step 4: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 117 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/stats.py
git commit -m "feat(api): agregat waktu penyusunan lintas penugasan

Satu kueri untuk seluruh revisi lalu dikelompokkan di memori, bukan satu kueri
per penugasan. Penugasan tanpa baseline tetap tampil tapi tak ikut dirata-rata."
```

---

### Task 5: Halaman /reports

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/app/reports/page.tsx` (tulis ulang penuh)

**Interfaces:**
- Consumes: `GET /stats/timing` (Task 4); `downloadReportDocx`, `downloadReportPdf`, `previewReport` yang sudah ada di `lib/api.ts`
- Produces: halaman `/reports` yang berfungsi

- [ ] **Step 1: Tambah tipe dan fungsi klien**

Di `frontend/src/lib/api.ts`, sisipkan tepat sebelum komentar `// ---------- D17: transparansi masking`:

```ts
// ---------- Modul 1: metrik waktu penyusunan ----------
export interface Timing {
  event_count: number;
  first_at: string | null;
  last_at: string | null;
  calendar_seconds: number;
  active_seconds: number;
  active_hours: number;
  events_by_action: Record<string, number>;
  baseline_hours: number | null;
  saved_hours: number | null;
  saved_ratio: number | null;
}
export interface TimingRow extends Timing {
  engagement_id: number;
  name: string;
  client_name: string;
  status: string;
}
export interface TimingOverview {
  items: TimingRow[];
  engagements_measured: number;
  avg_saved_ratio: number | null;
}
export const getTiming = (id: number) => req<Timing>(`/engagements/${id}/timing`);
export const getTimingOverview = () => req<TimingOverview>("/stats/timing");
export const setBaseline = (
  id: number,
  baseline_hours: number | null,
  baseline_note: string | null
) =>
  req<{ baseline_hours: number | null; baseline_note: string | null }>(
    `/engagements/${id}/baseline`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ baseline_hours, baseline_note }),
    }
  );
```

- [ ] **Step 2: Tambah kunci terjemahan ke KEDUA locale**

Di `frontend/src/i18n/messages.ts`, pada blok `id`, sisipkan setelah baris `"report.hint": ...`:

```ts
    "reports.subtitle": "Laporan seluruh penugasan beserta waktu penyusunannya.",
    "reports.avgSaved": "Rata-rata penghematan waktu",
    "reports.measured": "Penugasan terukur",
    "reports.totalEngagements": "Total penugasan",
    "reports.colEngagement": "Penugasan",
    "reports.colClient": "Klien",
    "reports.colActive": "Waktu aktif",
    "reports.colBaseline": "Baseline",
    "reports.colSaved": "Hemat",
    "reports.colActions": "Laporan",
    "reports.noBaseline": "belum diisi",
    "reports.empty": "Belum ada penugasan.",
    "reports.hours": "jam",
```

Pada blok `en`, sisipkan setelah baris `"report.hint": ...` padanannya:

```ts
    "reports.subtitle": "All engagements with their report preparation time.",
    "reports.avgSaved": "Average time saved",
    "reports.measured": "Measured engagements",
    "reports.totalEngagements": "Total engagements",
    "reports.colEngagement": "Engagement",
    "reports.colClient": "Client",
    "reports.colActive": "Active time",
    "reports.colBaseline": "Baseline",
    "reports.colSaved": "Saved",
    "reports.colActions": "Report",
    "reports.noBaseline": "not set",
    "reports.empty": "No engagements yet.",
    "reports.hours": "h",
```

- [ ] **Step 3: Tulis ulang halaman**

Ganti seluruh isi `frontend/src/app/reports/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { FileDoc, FilePdf, Eye } from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

function pct(v: number | null): string {
  return v === null ? "—" : `${Math.round(v * 100)}%`;
}

export default function ReportsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<api.TimingOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTimingOverview()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  const items = data?.items ?? [];

  return (
    <AppShell title={t("nav.reports")}>
      <section className="card">
        <p className="muted" style={{ marginTop: 0 }}>{t("reports.subtitle")}</p>
        <div className="form-row">
          <div className="field">
            <span>{t("reports.avgSaved")}</span>
            <strong className="mono">{pct(data?.avg_saved_ratio ?? null)}</strong>
          </div>
          <div className="field">
            <span>{t("reports.measured")}</span>
            <strong className="mono">{data?.engagements_measured ?? 0}</strong>
          </div>
          <div className="field">
            <span>{t("reports.totalEngagements")}</span>
            <strong className="mono">{items.length}</strong>
          </div>
        </div>
        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="card">
        {items.length === 0 ? (
          <p className="muted">{t("reports.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t("reports.colEngagement")}</th>
                  <th>{t("reports.colClient")}</th>
                  <th>{t("reports.colActive")}</th>
                  <th>{t("reports.colBaseline")}</th>
                  <th>{t("reports.colSaved")}</th>
                  <th>{t("reports.colActions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.engagement_id}>
                    <td className="mono">{r.engagement_id}</td>
                    <td>{r.name}</td>
                    <td>{r.client_name}</td>
                    <td className="mono">
                      {r.active_hours} {t("reports.hours")}
                    </td>
                    <td className="mono">
                      {r.baseline_hours === null ? (
                        <span className="muted">{t("reports.noBaseline")}</span>
                      ) : (
                        `${r.baseline_hours} ${t("reports.hours")}`
                      )}
                    </td>
                    <td className="mono">{pct(r.saved_ratio)}</td>
                    <td>
                      <button
                        className="btn ghost"
                        onClick={() => api.previewReport(r.engagement_id)}
                      >
                        <Eye size={14} /> {t("report.preview")}
                      </button>{" "}
                      <button
                        className="btn ghost"
                        onClick={() => api.downloadReportDocx(r.engagement_id)}
                      >
                        <FileDoc size={14} /> DOCX
                      </button>{" "}
                      <button
                        className="btn ghost"
                        onClick={() => api.downloadReportPdf(r.engagement_id)}
                      >
                        <FilePdf size={14} /> PDF
                      </button>
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

- [ ] **Step 4: Typecheck**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: tanpa keluaran error. Bila muncul galat kunci terjemahan, berarti ada kunci yang belum ditambahkan ke salah satu locale — perbaiki di `messages.ts`.

- [ ] **Step 5: Verifikasi di peramban**

Buka `http://localhost:3000/reports` setelah masuk sebagai `admin@auditforge.local`.
Expected: tabel berisi 17 penugasan; kolom Baseline menampilkan "belum diisi" untuk sebagian besar, dan penugasan #17 menampilkan angka beserta persentase penghematan; tombol Pratinjau/DOCX/PDF berfungsi.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/i18n/messages.ts frontend/src/app/reports/page.tsx
git commit -m "feat(web): halaman /reports menggantikan stub

Pusat laporan lintas penugasan plus metrik waktu penyusunan. Penugasan tanpa
baseline menampilkan 'belum diisi', bukan 0% — tidak mengklaim yang tak terukur."
```

---

## Verifikasi Akhir

- [ ] `docker exec auditforge-api-1 python -m pytest -q` → 117 passed
- [ ] `docker exec auditforge-web-1 npx tsc --noEmit` → bersih
- [ ] `http://localhost:3000/reports` menampilkan data nyata, bukan "coming soon"
- [ ] Penugasan tanpa baseline menampilkan "belum diisi", **bukan** 0%
- [ ] `docker exec auditforge-api-1 alembic downgrade -1 && docker exec auditforge-api-1 alembic upgrade head` berjalan tanpa galat

## Yang Belum Dikerjakan Plan Ini

| Bagian spec | Alasan |
|---|---|
| Grafik batang waktu aktual vs baseline | Tabel sudah menyampaikan angka yang sama; grafik dapat ditambahkan setelah bentuk datanya terbukti dipakai |
| Penyaringan berdasarkan keanggotaan tim | Berasal dari Modul 2 spec yang sama; endpoint ini akan ikut tersaring saat Modul 2 dikerjakan |
| Formulir pengisian baseline di UI | Endpoint `PUT .../baseline` sudah tersedia dan teruji lewat curl. Formulirnya wajar diletakkan di tab Ringkasan halaman penugasan, bukan di `/reports` |

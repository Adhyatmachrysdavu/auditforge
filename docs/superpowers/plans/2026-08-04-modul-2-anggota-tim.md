# Modul 2 — Anggota Tim, Pembatasan Akses, dan Diff Naratif

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Melengkapi modul "Pengelolaan Penugasan" yang dijanjikan proposal — periode, cakupan, dan anggota tim — dengan pembatasan akses berbasis keanggotaan, plus perbandingan versi naratif AI-vs-auditor.

**Architecture:** Dua keputusan ditempatkan di modul murni tanpa DB (`app/access.py`, `app/review_diff.py`), mengikuti pola `review.py`. Pembatasan akses dipasang pada satu titik: `_get_engagement()` yang sudah dipanggil 18 dari 21 route di `engagements.py`. Migrasi mengisi keanggotaan dalam transaksi yang sama dengan pembuatan tabelnya, lalu memverifikasi hasilnya — kalau ada penugasan yang masih yatim, migrasi gagal keras alih-alih mengunci pengguna diam-diam.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest, `difflib` (pustaka standar) · Next.js 14 App Router, TypeScript

## Global Constraints

- Seluruh tes baru **murni**: tanpa DB, Redis, MinIO, LLM, tanpa `conftest.py`. Objek palsu memakai `types.SimpleNamespace`.
- Docstring dan komentar dalam **Bahasa Indonesia**; identifier dan nama field API dalam Bahasa Inggris.
- Setiap teks UI baru wajib ada di **kedua** locale pada `frontend/src/i18n/messages.ts`; tipe `MessageKey` membuat `tsc` gagal bila terlewat.
- Jangan menjalankan `npm run lint` — tanpa konfigurasi ESLint, `next lint` berhenti di wizard interaktif.
- Jangan menyentuh `triage.py`, masking, alur status persetujuan, maupun pipeline deterministik.
- Alembic head saat ini: **`b3d8f1c05a92`**.
- Suite saat ini: **153 tes lulus**.
- Aturan akses **fail-closed**: admin melihat semua; selain admin hanya penugasan tempat ia terdaftar sebagai anggota.
- Pengelolaan keanggotaan dibatasi **auditor dan admin**. Menghapus anggota terakhir ditolak `409`.

---

## File Structure

| Berkas | Tanggung jawab |
|---|---|
| `backend/app/access.py` | **Baru.** Satu keputusan murni: boleh akses atau tidak |
| `backend/tests/test_access.py` | **Baru.** Tes modul di atas |
| `backend/app/review_diff.py` | **Baru.** Perbandingan naratif per bagian |
| `backend/tests/test_review_diff.py` | **Baru.** Tes modul di atas |
| `backend/app/models/engagement_member.py` | **Baru.** Tabel keanggotaan |
| `backend/app/models/engagement.py` | Kolom periode, cakupan, `kb_shareable` |
| `backend/alembic/versions/c5e1a90f4b26_engagement_members.py` | **Baru.** Migrasi + pengisian + verifikasi |
| `backend/app/schemas/engagement.py` | Skema anggota, periode/cakupan, diff |
| `backend/app/api/routes/engagements.py` | Pembatasan akses + endpoint anggota + endpoint diff |
| `backend/app/api/routes/stats.py` | Saring agregat |
| `backend/app/api/routes/ingest.py` | Saring aktivitas ingest |
| `backend/app/reporting/report_data.py` | Periode & cakupan di kop laporan |
| `frontend/src/lib/api.ts` | Tipe + fungsi klien |
| `frontend/src/i18n/messages.ts` | Kunci ID + EN |
| `frontend/src/app/engagements/[id]/page.tsx` | Tab **Tim** + tab **Perbandingan** |

---

### Task 1: Keputusan akses (modul murni)

**Files:**
- Create: `backend/app/access.py`
- Test: `backend/tests/test_access.py`

**Interfaces:**
- Consumes: tidak ada
- Produces: `can_access_engagement(*, role: str, is_member: bool) -> bool`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_access.py`:

```python
"""Uji unit Modul 2 — keputusan akses penugasan (tanpa DB)."""
from __future__ import annotations

from app.access import can_access_engagement


def test_admin_sees_everything_without_membership():
    assert can_access_engagement(role="admin", is_member=False) is True


def test_member_can_access():
    assert can_access_engagement(role="auditor", is_member=True) is True
    assert can_access_engagement(role="analyst", is_member=True) is True


def test_non_member_denied_even_as_auditor():
    # Peran tinggi tidak memberi akses ke penugasan yang bukan miliknya.
    assert can_access_engagement(role="auditor", is_member=False) is False


def test_non_member_analyst_denied():
    assert can_access_engagement(role="analyst", is_member=False) is False


def test_unknown_role_denied():
    # Fail-closed: peran yang tak dikenal tidak pernah lolos tanpa keanggotaan.
    assert can_access_engagement(role="", is_member=False) is False
    assert can_access_engagement(role="superuser", is_member=False) is False
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_access.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.access'`

- [ ] **Step 3: Tulis implementasi**

Buat `backend/app/access.py`:

```python
"""Keputusan akses penugasan (Modul 2) — deterministik, tanpa DB.

Aturannya sengaja hanya satu kalimat: administrator melihat seluruh penugasan;
siapa pun selain itu hanya melihat penugasan tempat ia terdaftar sebagai
anggota tim. Peran tinggi tidak memberi jalan pintas — seorang auditor tetap
tidak dapat membuka penugasan klien yang bukan garapannya.

Bersifat *fail-closed*: apa pun yang tidak secara eksplisit diizinkan, ditolak.
"""
from __future__ import annotations

ADMIN_ROLE = "admin"


def can_access_engagement(*, role: str, is_member: bool) -> bool:
    """True bila pengguna berperan `role` boleh membuka penugasan tersebut."""
    if role == ADMIN_ROLE:
        return True
    return bool(is_member)
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_access.py -q`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/access.py backend/tests/test_access.py
git commit -m "feat(access): keputusan akses penugasan berbasis keanggotaan

Fail-closed dan hanya satu aturan: admin melihat semua, selain itu hanya
penugasan tempat ia terdaftar. Peran tinggi tidak memberi jalan pintas —
auditor tetap tak bisa membuka penugasan klien yang bukan garapannya."
```

---

### Task 2: Perbandingan naratif (modul murni)

**Files:**
- Create: `backend/app/review_diff.py`
- Test: `backend/tests/test_review_diff.py`

**Interfaces:**
- Consumes: tidak ada
- Produces:
  - `SECTIONS: tuple[str, ...]` = `("description", "impact", "recommendation")`
  - `diff_narrative(before: dict | None, after: dict | None) -> dict[str, object]`
  - Keluaran: `{"sections": {<nama>: {"before": str, "after": str, "added": list[str], "removed": list[str], "changed_ratio": float}}, "overall_changed_ratio": float}`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_review_diff.py`:

```python
"""Uji unit Modul 2 — perbandingan naratif AI vs auditor (tanpa DB)."""
from __future__ import annotations

from app.review_diff import SECTIONS, diff_narrative


def test_identical_narrative_has_zero_change():
    n = {"description": "Ada kerentanan", "impact": "Data bocor", "recommendation": "Tambal"}
    d = diff_narrative(n, dict(n))
    assert d["overall_changed_ratio"] == 0.0
    for s in SECTIONS:
        assert d["sections"][s]["changed_ratio"] == 0.0
        assert d["sections"][s]["added"] == []
        assert d["sections"][s]["removed"] == []


def test_detects_added_and_removed_words():
    before = {"description": "Ada kerentanan lama", "impact": "", "recommendation": ""}
    after = {"description": "Ada kerentanan kritis", "impact": "", "recommendation": ""}
    d = diff_narrative(before, after)
    sec = d["sections"]["description"]
    assert "kritis" in sec["added"]
    assert "lama" in sec["removed"]
    assert 0.0 < sec["changed_ratio"] <= 1.0


def test_missing_draft_counts_as_fully_written_by_auditor():
    # Tak ada draf AI: seluruh isi naratif ditulis manusia → perubahan penuh.
    after = {"description": "Ditulis auditor", "impact": "Dampak", "recommendation": "Saran"}
    d = diff_narrative(None, after)
    assert d["overall_changed_ratio"] == 1.0
    assert d["sections"]["description"]["before"] == ""


def test_both_empty_is_not_a_change():
    d = diff_narrative(None, None)
    assert d["overall_changed_ratio"] == 0.0
    for s in SECTIONS:
        assert d["sections"][s]["changed_ratio"] == 0.0


def test_ignores_unknown_keys_and_non_dict_input():
    # Naratif lama bisa memuat kunci lain; hanya tiga bagian resmi yang dibandingkan.
    before = {"description": "A", "catatan": "abaikan"}
    after = {"description": "B", "catatan": "abaikan juga"}
    d = diff_narrative(before, after)
    assert set(d["sections"].keys()) == set(SECTIONS)
    # Masukan yang bukan dict tidak boleh meledak.
    assert diff_narrative("bukan dict", None)["overall_changed_ratio"] == 0.0


def test_overall_ratio_weighted_by_length_not_section_count():
    # Satu bagian panjang yang tak berubah tidak boleh tertutup oleh satu
    # bagian pendek yang berubah total.
    long_same = " ".join(["kata"] * 40)
    before = {"description": long_same, "impact": "x", "recommendation": ""}
    after = {"description": long_same, "impact": "y", "recommendation": ""}
    d = diff_narrative(before, after)
    assert d["sections"]["impact"]["changed_ratio"] == 1.0
    assert d["overall_changed_ratio"] < 0.2
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_review_diff.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.review_diff'`

- [ ] **Step 3: Tulis implementasi**

Buat `backend/app/review_diff.py`:

```python
"""Perbandingan versi naratif (Modul 2) — deterministik, tanpa DB.

Membandingkan draf AI dengan naratif final auditor **per bagian**
(`description`, `impact`, `recommendation`), bukan sebagai diff baris mentah.
Yang ingin diketahui auditor adalah "bagian mana yang saya ubah dari draf AI",
dan pembacanya adalah manusia — bukan mesin patch.

`changed_ratio` juga menjadi bahan bukti indikator proposal *"maksimal 30%
kalimat memerlukan penyuntingan berat"*. Karena itu rasio keseluruhan
ditimbang panjang kata, bukan dirata-ratakan per bagian: satu kalimat pendek
yang diganti total tidak boleh terlihat sebesar satu paragraf panjang yang
dirombak.
"""
from __future__ import annotations

import difflib
import re

SECTIONS: tuple[str, ...] = ("description", "impact", "recommendation")

_WORD_RE = re.compile(r"\S+")


def _text(source: object, key: str) -> str:
    """Ambil satu bagian naratif dengan aman; apa pun selain dict dianggap kosong."""
    if not isinstance(source, dict):
        return ""
    return str(source.get(key, "") or "").strip()


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _diff_section(before: str, after: str) -> dict[str, object]:
    b, a = _words(before), _words(after)
    matcher = difflib.SequenceMatcher(a=b, b=a, autojunk=False)

    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(b[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(a[j1:j2])

    # 1 - ratio() = proporsi ketidaksamaan. Dua teks kosong dianggap identik.
    changed = 0.0 if not b and not a else round(1.0 - matcher.ratio(), 4)

    return {
        "before": before,
        "after": after,
        "added": added,
        "removed": removed,
        "changed_ratio": changed,
        # Dipakai untuk menimbang rasio keseluruhan; tidak untuk ditampilkan.
        "_weight": max(len(b), len(a)),
    }


def diff_narrative(
    before: dict | None, after: dict | None
) -> dict[str, object]:
    """Bandingkan draf AI (`before`) dengan naratif final auditor (`after`)."""
    sections: dict[str, object] = {}
    total_weight = 0
    weighted_change = 0.0

    for name in SECTIONS:
        result = _diff_section(_text(before, name), _text(after, name))
        weight = int(result.pop("_weight"))
        total_weight += weight
        weighted_change += float(result["changed_ratio"]) * weight
        sections[name] = result

    overall = round(weighted_change / total_weight, 4) if total_weight else 0.0
    return {"sections": sections, "overall_changed_ratio": overall}
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_review_diff.py -q`
Expected: PASS — 6 passed

- [ ] **Step 5: Pastikan tes lama tidak rusak**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 164 passed (153 lama + 5 + 6)

- [ ] **Step 6: Commit**

```bash
git add backend/app/review_diff.py backend/tests/test_review_diff.py
git commit -m "feat(review): perbandingan naratif AI vs auditor per bagian

Rasio keseluruhan ditimbang panjang kata, bukan dirata-ratakan per bagian —
satu kalimat pendek yang diganti total tak boleh terlihat sebesar paragraf
panjang yang dirombak. Rasio ini jadi bahan bukti indikator proposal soal
porsi kalimat yang perlu penyuntingan berat."
```

---

### Task 3: Tabel keanggotaan, kolom penugasan, dan migrasi berisi pengisian

**Files:**
- Create: `backend/app/models/engagement_member.py`
- Create: `backend/alembic/versions/c5e1a90f4b26_engagement_members.py`
- Modify: `backend/app/models/engagement.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: tidak ada
- Produces:
  - `EngagementMember` dengan kolom `id`, `engagement_id`, `user_id`, `role_in_team`, `added_by`, `created_at`
  - `Engagement.scope: str | None`, `Engagement.period_start: date | None`, `Engagement.period_end: date | None`, `Engagement.kb_shareable: bool`

**Ini task paling berisiko dalam rencana ini.** Basis data memuat 18 penugasan dan tak satu pun punya anggota. Bila pembatasan akses aktif tanpa pengisian, setiap pengguna non-admin kehilangan akses ke seluruh data seketika. Karena itu pengisian berada di dalam migrasi yang sama, dan migrasi memverifikasi hasilnya sendiri.

- [ ] **Step 1: Buat model keanggotaan**

Buat `backend/app/models/engagement_member.py`:

```python
"""Keanggotaan tim pada sebuah penugasan (Modul 2).

Keanggotaan inilah yang menentukan siapa boleh membuka sebuah penugasan —
lihat `app/access.py`. Administrator tidak perlu terdaftar; ia melihat semua.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class EngagementMember(Base):
    __tablename__ = "engagement_members"
    __table_args__ = (
        UniqueConstraint("engagement_id", "user_id", name="uq_engagement_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 'lead' | 'member' — keterangan peran di dalam tim, bukan RBAC aplikasi.
    role_in_team: Mapped[str] = mapped_column(String(20), default="member")
    added_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

- [ ] **Step 2: Daftarkan model dan tambah kolom penugasan**

Di `backend/app/models/__init__.py`, tambahkan impor mengikuti pola yang sudah ada di berkas itu agar Alembic dan SQLAlchemy mengenali tabelnya:

```python
from app.models.engagement_member import EngagementMember  # noqa: F401
```

Di `backend/app/models/engagement.py`, ubah baris impor SQLAlchemy agar menyertakan `Date`:

```python
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
```

Lalu tambahkan empat kolom di akhir kelas `Engagement`:

```python
    # --- Modul 2: kelengkapan penugasan (modul "Pengelolaan Penugasan" di proposal) ---
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Boleh menjadi rujukan Basis Pengetahuan (Modul 3). Sebagian NDA melarang
    # data klien dipakai untuk keperluan lain sekalipun internal.
    kb_shareable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=sa_true()
    )
```

Tambahkan pula impor yang dibutuhkan di bagian atas berkas:

```python
from datetime import date, datetime
from sqlalchemy import true as sa_true
```

- [ ] **Step 3: Buat migrasi berisi pengisian dan verifikasi**

Buat `backend/alembic/versions/c5e1a90f4b26_engagement_members.py`:

```python
"""anggota tim + periode & cakupan penugasan (Modul 2)

Revision ID: c5e1a90f4b26
Revises: b3d8f1c05a92
Create Date: 2026-08-04 07:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c5e1a90f4b26'
down_revision: str | None = 'b3d8f1c05a92'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('engagements', sa.Column('scope', sa.Text(), nullable=True))
    op.add_column('engagements', sa.Column('period_start', sa.Date(), nullable=True))
    op.add_column('engagements', sa.Column('period_end', sa.Date(), nullable=True))
    op.add_column(
        'engagements',
        sa.Column(
            'kb_shareable', sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )

    op.create_table(
        'engagement_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_in_team', sa.String(length=20), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['added_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engagement_id', 'user_id', name='uq_engagement_member'),
    )
    op.create_index(
        'ix_engagement_members_engagement_id', 'engagement_members', ['engagement_id']
    )
    op.create_index('ix_engagement_members_user_id', 'engagement_members', ['user_id'])

    # --- Pengisian: WAJIB berada di migrasi yang sama ---
    # Tanpa ini, pembatasan akses langsung mengunci setiap pengguna non-admin
    # dari seluruh penugasan yang sudah ada.
    conn = op.get_bind()

    # 1. Pembuat penugasan menjadi `lead`.
    conn.execute(
        sa.text(
            """
            INSERT INTO engagement_members
                (engagement_id, user_id, role_in_team, added_by, created_at)
            SELECT e.id, e.created_by, 'lead', NULL, NOW()
            FROM engagements e
            WHERE e.created_by IS NOT NULL
            """
        )
    )

    # 2. Penugasan tanpa pembuat jatuh ke seluruh administrator.
    conn.execute(
        sa.text(
            """
            INSERT INTO engagement_members
                (engagement_id, user_id, role_in_team, added_by, created_at)
            SELECT e.id, u.id, 'lead', NULL, NOW()
            FROM engagements e
            CROSS JOIN users u
            JOIN roles r ON r.id = u.role_id
            WHERE e.created_by IS NULL AND r.name = 'admin'
            """
        )
    )

    # 3. Verifikasi: tidak boleh ada penugasan tanpa anggota. Lebih baik migrasi
    #    gagal keras di sini daripada mengunci pengguna diam-diam.
    orphans = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM engagements e
            WHERE NOT EXISTS (
                SELECT 1 FROM engagement_members m WHERE m.engagement_id = e.id
            )
            """
        )
    ).scalar()
    if orphans:
        raise RuntimeError(
            f"{orphans} penugasan tidak memperoleh anggota tim. "
            "Migrasi dibatalkan agar tidak ada pengguna yang terkunci."
        )


def downgrade() -> None:
    op.drop_index('ix_engagement_members_user_id', table_name='engagement_members')
    op.drop_index(
        'ix_engagement_members_engagement_id', table_name='engagement_members'
    )
    op.drop_table('engagement_members')
    op.drop_column('engagements', 'kb_shareable')
    op.drop_column('engagements', 'period_end')
    op.drop_column('engagements', 'period_start')
    op.drop_column('engagements', 'scope')
```

- [ ] **Step 4: Jalankan migrasi**

Run: `docker exec auditforge-api-1 alembic upgrade head`
Expected: `Running upgrade b3d8f1c05a92 -> c5e1a90f4b26` tanpa `RuntimeError`

- [ ] **Step 5: Verifikasi tidak ada penugasan yatim**

Run:
```bash
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c "
select (select count(*) from engagements) as penugasan,
       (select count(*) from engagement_members) as baris_anggota,
       (select count(*) from engagements e where not exists
          (select 1 from engagement_members m where m.engagement_id = e.id)) as yatim;"
```
Expected: `yatim` bernilai **0**, dan `baris_anggota` minimal sama dengan jumlah penugasan.

- [ ] **Step 6: Uji downgrade lalu upgrade lagi**

Run:
```bash
docker exec auditforge-api-1 alembic downgrade -1
docker exec auditforge-api-1 alembic upgrade head
```
Expected: keduanya berhasil, dan pemeriksaan pada Step 5 tetap menghasilkan `yatim = 0`.

- [ ] **Step 7: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 164 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/engagement_member.py backend/app/models/engagement.py backend/app/models/__init__.py backend/alembic/versions/c5e1a90f4b26_engagement_members.py
git commit -m "feat(db): tabel anggota tim + periode & cakupan penugasan

Pengisian keanggotaan berada di dalam migrasi yang sama, bukan skrip terpisah
yang bisa lupa dijalankan: created_by jadi lead, penugasan tanpa pembuat jatuh
ke seluruh admin. Migrasi memverifikasi sendiri tak ada penugasan yatim dan
gagal keras bila ada — lebih baik daripada mengunci pengguna diam-diam."
```

---

### Task 4: Pasang pembatasan akses

**Files:**
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `can_access_engagement` (Task 1); `EngagementMember` (Task 3)
- Produces: `_get_engagement(db, engagement_id, user)` — signature bertambah satu argumen; melempar `404` bila tidak ada **atau** pengguna tidak berhak

Menyembunyikan penugasan yang tak berhak di balik `404` (bukan `403`) disengaja: `403` memberi tahu bahwa penugasan dengan nomor itu ada, dan nama klien sering dapat ditebak dari nomor berurutan.

- [ ] **Step 1: Ubah helper**

Di `backend/app/api/routes/engagements.py`, tambahkan impor:

```python
from app.access import can_access_engagement
from app.models.engagement_member import EngagementMember
```

Ganti fungsi `_get_engagement` menjadi:

```python
def _is_member(db: Session, engagement_id: int, user_id: int) -> bool:
    """True bila pengguna terdaftar sebagai anggota tim penugasan tersebut."""
    return db.scalar(
        select(EngagementMember.id).where(
            EngagementMember.engagement_id == engagement_id,
            EngagementMember.user_id == user_id,
        )
    ) is not None


def _get_engagement(db: Session, engagement_id: int, user: User) -> Engagement:
    """Ambil penugasan yang boleh diakses `user`, atau 404.

    Penugasan yang ada tetapi bukan hak pengguna sengaja dibalas 404, bukan 403:
    403 membocorkan bahwa penugasan bernomor itu ada, dan nama klien kerap dapat
    ditebak dari nomor yang berurutan.
    """
    eng = db.get(Engagement, engagement_id)
    if eng is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Penugasan tak ditemukan"
        )
    allowed = can_access_engagement(
        role=user.role.name,
        is_member=_is_member(db, engagement_id, user.id),
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Penugasan tak ditemukan"
        )
    return eng
```

- [ ] **Step 2: Perbarui seluruh pemanggil**

Run untuk melihat daftarnya:
```bash
grep -n "_get_engagement(db, engagement_id)" backend/app/api/routes/engagements.py
```

Setiap baris yang muncul harus menjadi `_get_engagement(db, engagement_id, user)`. Pada route yang parameternya masih bernama `_` (mis. `_: User = Depends(get_current_user)` atau `_: User = Depends(require_roles(...))`), ubah namanya menjadi `user` supaya bisa diteruskan.

Verifikasi tidak ada yang tersisa:
```bash
grep -c "_get_engagement(db, engagement_id)$" backend/app/api/routes/engagements.py
```
Expected: `0`

- [ ] **Step 3: Saring daftar penugasan**

Ganti isi `list_engagements` menjadi:

```python
@router.get("", response_model=list[EngagementOut])
def list_engagements(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[EngagementOut]:
    """Hanya penugasan yang boleh diakses pengguna. Admin melihat semua."""
    q = select(Engagement)
    if user.role.name != "admin":
        q = q.join(
            EngagementMember, EngagementMember.engagement_id == Engagement.id
        ).where(EngagementMember.user_id == user.id)
    return [_engagement_out(e) for e in db.scalars(q).all()]
```

- [ ] **Step 4: Pembuat penugasan otomatis menjadi anggota**

Di `create_engagement`, tepat setelah `db.refresh(eng)` dan sebelum `return`:

```python
    # Tanpa ini pembuatnya sendiri langsung kehilangan akses ke penugasan yang
    # baru saja ia buat.
    db.add(
        EngagementMember(
            engagement_id=eng.id,
            user_id=user.id,
            role_in_team="lead",
            added_by=user.id,
        )
    )
    db.commit()
```

- [ ] **Step 5: Verifikasi admin masih bisa membuka semuanya**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s http://localhost:8000/engagements -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print('penugasan terlihat admin:',len(json.load(sys.stdin)))"
curl -s -o /dev/null -w "buka #18: %{http_code}\n" http://localhost:8000/engagements/18 -H "Authorization: Bearer $TOKEN"
```
Expected: seluruh penugasan terlihat (18), dan `buka #18: 200`.

- [ ] **Step 6: Verifikasi pengguna non-anggota ditolak**

Buat pengguna analis lalu coba membuka penugasan yang bukan miliknya:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -X POST http://localhost:8000/users -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"email":"uji.analis@auditforge.local","full_name":"Uji Analis","password":"analis12345","role":"analyst"}' -o /dev/null -w "buat analis: %{http_code}\n"
ATOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=uji.analis@auditforge.local&password=analis12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s http://localhost:8000/engagements -H "Authorization: Bearer $ATOKEN" | python -c "import sys,json;print('penugasan terlihat analis:',len(json.load(sys.stdin)))"
curl -s -o /dev/null -w "analis buka #18: %{http_code}\n" http://localhost:8000/engagements/18 -H "Authorization: Bearer $ATOKEN"
```
Expected: `penugasan terlihat analis: 0` dan `analis buka #18: 404`.

Payload di atas sudah cocok dengan skema `UserCreate` (`email`, `full_name`, `password` minimal 8 karakter, `role` berisi nama peran), dan `POST /users` memang tersedia di `backend/app/api/routes/users.py`.

- [ ] **Step 7: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 164 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/routes/engagements.py
git commit -m "feat(api): batasi akses penugasan berdasarkan keanggotaan tim

Dipasang di _get_engagement yang sudah dipakai 18 dari 21 route, jadi satu
perubahan menutup hampir seluruh permukaan. Penugasan yang bukan hak pengguna
dibalas 404, bukan 403 — 403 membocorkan bahwa penugasan bernomor itu ada, dan
nama klien kerap bisa ditebak dari nomor berurutan.

Pembuat penugasan otomatis jadi anggota lead, kalau tidak ia langsung kehilangan
akses ke penugasan yang baru saja dibuatnya."
```

---

### Task 5: Endpoint kelola anggota

**Files:**
- Modify: `backend/app/schemas/engagement.py`
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `EngagementMember` (Task 3); `_get_engagement(db, engagement_id, user)` (Task 4)
- Produces:
  - `MemberOut` — `user_id`, `email`, `full_name`, `role`, `role_in_team`
  - `MemberIn` — `user_id`, `role_in_team`
  - `GET /engagements/{id}/members` → `list[MemberOut]` (anggota penugasan)
  - `POST /engagements/{id}/members` → `MemberOut` (auditor, admin)
  - `DELETE /engagements/{id}/members/{user_id}` → `204` (auditor, admin)

- [ ] **Step 1: Tambah skema**

Di `backend/app/schemas/engagement.py`, tambahkan:

```python
class MemberOut(BaseModel):
    """Satu anggota tim penugasan, sudah digabung dengan data penggunanya."""

    user_id: int
    email: str
    full_name: str
    role: str          # peran RBAC aplikasi (admin/auditor/analyst)
    role_in_team: str  # 'lead' | 'member'


class MemberIn(BaseModel):
    user_id: int
    role_in_team: str = "member"
```

- [ ] **Step 2: Tambah ketiga endpoint**

Di `backend/app/api/routes/engagements.py`, sisipkan setelah fungsi `get_engagement`:

```python
def _member_out(m: EngagementMember, u: User) -> MemberOut:
    return MemberOut(
        user_id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role.name,
        role_in_team=m.role_in_team,
    )


@router.get("/{engagement_id}/members", response_model=list[MemberOut])
def list_members(
    engagement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MemberOut]:
    """Daftar anggota tim. Analis anggota boleh melihat, tapi tak boleh mengubah."""
    _get_engagement(db, engagement_id, user)
    rows = db.execute(
        select(EngagementMember, User)
        .join(User, User.id == EngagementMember.user_id)
        .where(EngagementMember.engagement_id == engagement_id)
        .order_by(EngagementMember.id)
    ).all()
    return [_member_out(m, u) for m, u in rows]


@router.post(
    "/{engagement_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    engagement_id: int,
    payload: MemberIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("auditor", "admin")),
) -> MemberOut:
    """Tambah anggota tim.

    Dibatasi auditor/admin: menambahkan seseorang berarti memberinya akses ke
    data kerentanan klien — keputusan kepercayaan, bukan pekerjaan harian.
    """
    _get_engagement(db, engagement_id, user)

    target = db.get(User, payload.user_id)
    if target is None or not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tak ditemukan"
        )

    existing = db.scalar(
        select(EngagementMember).where(
            EngagementMember.engagement_id == engagement_id,
            EngagementMember.user_id == payload.user_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pengguna sudah menjadi anggota penugasan ini.",
        )

    role_in_team = payload.role_in_team if payload.role_in_team in {"lead", "member"} else "member"
    member = EngagementMember(
        engagement_id=engagement_id,
        user_id=payload.user_id,
        role_in_team=role_in_team,
        added_by=user.id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_out(member, target)


@router.delete(
    "/{engagement_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    engagement_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("auditor", "admin")),
) -> Response:
    """Keluarkan anggota dari penugasan.

    Anggota terakhir tidak boleh dikeluarkan: penugasan tanpa anggota hanya
    dapat dibuka admin, dan itu cara termudah kehilangan akses tanpa sadar.
    """
    _get_engagement(db, engagement_id, user)

    member = db.scalar(
        select(EngagementMember).where(
            EngagementMember.engagement_id == engagement_id,
            EngagementMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Anggota tak ditemukan"
        )

    total = db.scalar(
        select(func.count())
        .select_from(EngagementMember)
        .where(EngagementMember.engagement_id == engagement_id)
    ) or 0
    if total <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Anggota terakhir tidak dapat dikeluarkan. "
                "Tambahkan anggota lain lebih dulu."
            ),
        )

    db.delete(member)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Tambahkan `MemberIn` dan `MemberOut` ke daftar impor dari `app.schemas.engagement` (urut menaik).

- [ ] **Step 3: Uji ketiga endpoint**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
echo "--- daftar anggota #18 ---"
curl -s http://localhost:8000/engagements/18/members -H "Authorization: Bearer $TOKEN" | python -m json.tool
AID=$(docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -t -c "select id from users where email='uji.analis@auditforge.local';" | tr -d ' \n')
echo "--- tambah analis (id $AID) ---"
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/engagements/18/members -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"user_id\": $AID, \"role_in_team\": \"member\"}"
echo "--- tambah lagi (harus 409) ---"
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/engagements/18/members -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"user_id\": $AID}"
echo "--- keluarkan analis ---"
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/engagements/18/members/$AID -H "Authorization: Bearer $TOKEN"
```
Expected: daftar memuat admin; tambah `201`; tambah ulang `409`; keluarkan `204`.

- [ ] **Step 4: Uji penjaga anggota terakhir**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
UID=$(curl -s http://localhost:8000/engagements/18/members -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print(json.load(sys.stdin)[0]['user_id'])")
curl -s -w "\nkeluarkan anggota terakhir: %{http_code}\n" -X DELETE http://localhost:8000/engagements/18/members/$UID -H "Authorization: Bearer $TOKEN"
```
Expected: `409` beserta pesan bahwa anggota terakhir tak dapat dikeluarkan.

- [ ] **Step 5: Pastikan tes lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — 164 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/engagement.py backend/app/api/routes/engagements.py
git commit -m "feat(api): endpoint kelola anggota tim penugasan

Menambah anggota dibatasi auditor/admin — memberi orang akses ke data
kerentanan klien adalah keputusan kepercayaan, bukan pekerjaan harian. Analis
anggota tetap boleh melihat daftar rekan setimnya.

Anggota terakhir ditolak 409: penugasan tanpa anggota cuma bisa dibuka admin,
dan itu cara termudah kehilangan akses tanpa sadar."
```

---

### Task 6: Saring agregat dan cetak periode/cakupan di laporan

**Files:**
- Modify: `backend/app/api/routes/stats.py`
- Modify: `backend/app/api/routes/ingest.py`
- Modify: `backend/app/reporting/report_data.py`
- Modify: `backend/app/schemas/engagement.py`
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `EngagementMember` (Task 3)
- Produces: `EngagementDetailOut` bertambah `scope`, `period_start`, `period_end`, `kb_shareable`; `ReportData` bertambah `period` dan `scope`; endpoint `PUT /engagements/{id}/details`

- [ ] **Step 1: Buat helper penyaring bersama**

Di `backend/app/access.py`, tambahkan:

```python
def accessible_engagement_ids_clause(user_role: str) -> bool:
    """True bila daftar penugasan perlu disaring untuk peran ini.

    Dipisah agar route pemanggil tidak menuliskan `role != "admin"` sendiri-sendiri
    dan menyimpang diam-diam.
    """
    return user_role != ADMIN_ROLE
```

- [ ] **Step 2: Saring `/stats` dan `/stats/timing`**

Di `backend/app/api/routes/stats.py`, tambahkan impor:

```python
from app.access import accessible_engagement_ids_clause
from app.models.engagement_member import EngagementMember
```

Di kedua fungsi (`overview` dan `timing_overview`), ubah parameter `_: User = Depends(get_current_user)` menjadi `user: User = Depends(get_current_user)`, lalu hitung daftar id yang boleh diakses di awal fungsi:

```python
    # TODO(Modul 2) dihapus: penyaringan keanggotaan kini terpasang.
    eng_ids: list[int] | None = None
    if accessible_engagement_ids_clause(user.role.name):
        eng_ids = list(
            db.scalars(
                select(EngagementMember.engagement_id).where(
                    EngagementMember.user_id == user.id
                )
            ).all()
        )
```

Lalu tambahkan `.where(Engagement.id.in_(eng_ids))` pada kueri penugasan dan `.where(Finding.engagement_id.in_(eng_ids))` pada kueri temuan/revisi **bila `eng_ids is not None`**. Bila `eng_ids` berupa daftar kosong, hasilnya harus nol — bukan seluruh data.

Hapus komentar `TODO(Modul 2)` yang lama di berkas ini.

- [ ] **Step 3: Saring `/ingest`**

Di `backend/app/api/routes/ingest.py`, terapkan pola yang sama: ubah `_` menjadi `user`, hitung `eng_ids`, tambahkan `.where(ScanUpload.engagement_id.in_(eng_ids))` pada kueri `items` dan pada ketiga kueri ringkasan bila `eng_ids is not None`. Hapus komentar `TODO(Modul 2)` di berkas ini.

- [ ] **Step 4: Tambah endpoint pengisian periode & cakupan**

Di `backend/app/schemas/engagement.py`:

```python
class EngagementDetailsIn(BaseModel):
    """Kelengkapan penugasan (modul "Pengelolaan Penugasan" di proposal)."""

    scope: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    kb_shareable: bool = True
```

Tambahkan `from datetime import date` di bagian atas berkas bila belum ada, dan tambahkan keempat field itu ke `EngagementDetailOut` dengan nilai bawaan.

Di `backend/app/api/routes/engagements.py`, sisipkan setelah `set_engagement_baseline`:

```python
@router.put("/{engagement_id}/details")
def set_engagement_details(
    engagement_id: int,
    payload: EngagementDetailsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("auditor", "admin")),
) -> dict:
    """Isi periode pelaksanaan, cakupan pengujian, dan izin rujukan KB."""
    eng = _get_engagement(db, engagement_id, user)
    if (
        payload.period_start is not None
        and payload.period_end is not None
        and payload.period_end < payload.period_start
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Akhir periode tidak boleh mendahului awal periode.",
        )
    eng.scope = payload.scope
    eng.period_start = payload.period_start
    eng.period_end = payload.period_end
    eng.kb_shareable = payload.kb_shareable
    db.commit()
    return {
        "scope": eng.scope,
        "period_start": eng.period_start.isoformat() if eng.period_start else None,
        "period_end": eng.period_end.isoformat() if eng.period_end else None,
        "kb_shareable": eng.kb_shareable,
    }
```

Sertakan keempat field itu juga saat membangun `EngagementDetailOut` di fungsi `get_engagement`.

- [ ] **Step 5: Cetak periode & cakupan di kop laporan**

Di `backend/app/reporting/report_data.py`, tambahkan dua field ke `ReportData`:

```python
    period: str | None = None
    scope: str | None = None
```

Lalu isi keduanya di dalam `build_report_data`, sebelum `return ReportData(...)`:

```python
    # Periode dicetak sebagai satu kalimat agar kop laporan tetap ringkas.
    ps = getattr(engagement, "period_start", None)
    pe = getattr(engagement, "period_end", None)
    period = f"{ps} — {pe}" if ps and pe else (str(ps) if ps else None)
```

dan tambahkan `period=period, scope=getattr(engagement, "scope", None),` ke pemanggilan `ReportData(...)`.

Di `backend/app/reporting/html_writer.py`, tambahkan dua baris pada blok metadata kop (di dekat baris yang mencetak klien):

```html
  {% if data.period %}<p><span class="lbl">Periode:</span> {{ data.period }}</p>{% endif %}
  {% if data.scope %}<p><span class="lbl">Cakupan:</span> {{ data.scope }}</p>{% endif %}
```

- [ ] **Step 6: Verifikasi penyaringan bekerja**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
ATOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=uji.analis@auditforge.local&password=analis12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
echo "--- admin ---"
curl -s http://localhost:8000/stats -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;d=json.load(sys.stdin);print('penugasan:',d['engagements'],'temuan:',d['findings'])"
curl -s http://localhost:8000/ingest -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print('ingest items:',len(json.load(sys.stdin)['items']))"
echo "--- analis (bukan anggota mana pun) ---"
curl -s http://localhost:8000/stats -H "Authorization: Bearer $ATOKEN" | python -c "import sys,json;d=json.load(sys.stdin);print('penugasan:',d['engagements'],'temuan:',d['findings'])"
curl -s http://localhost:8000/ingest -H "Authorization: Bearer $ATOKEN" | python -c "import sys,json;print('ingest items:',len(json.load(sys.stdin)['items']))"
```
Expected: admin melihat angka penuh; analis melihat **0** di semuanya.

- [ ] **Step 7: Verifikasi periode & cakupan muncul di laporan**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -X PUT http://localhost:8000/engagements/18/details -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"scope":"Aplikasi web internal, tanpa uji DoS","period_start":"2026-08-01","period_end":"2026-08-04","kb_shareable":true}'
curl -s "http://localhost:8000/engagements/18/report.html" -H "Authorization: Bearer $TOKEN" | grep -oE "(Periode|Cakupan):[^<]{0,60}"
```
Expected: kedua baris muncul di kop laporan.

- [ ] **Step 8: Pastikan tidak ada TODO tersisa dan tes lama lulus**

```bash
grep -rn "TODO(Modul 2)" backend/app --include=*.py || echo "bersih"
docker exec auditforge-api-1 python -m pytest -q
```
Expected: `bersih`, dan `164 passed`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/access.py backend/app/api/routes/stats.py backend/app/api/routes/ingest.py backend/app/api/routes/engagements.py backend/app/schemas/engagement.py backend/app/reporting/report_data.py backend/app/reporting/html_writer.py
git commit -m "feat(api): saring agregat per keanggotaan + periode & cakupan di laporan

Menutup kedua TODO(Modul 2) yang menganggur di stats.py dan ingest.py. Daftar
id kosong berarti nol hasil, bukan seluruh data — itu bedanya fail-closed
dengan fail-open pada penyaringan berbasis daftar.

Periode dan cakupan kini tercetak di kop laporan, melengkapi modul
Pengelolaan Penugasan yang dijanjikan proposal."
```

---

### Task 7: Tab Tim di halaman penugasan

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/app/engagements/[id]/page.tsx`

**Interfaces:**
- Consumes: endpoint anggota (Task 5) dan `PUT /engagements/{id}/details` (Task 6)
- Produces: tab `team` pada halaman penugasan

- [ ] **Step 1: Tambah tipe dan fungsi klien**

Di `frontend/src/lib/api.ts`, sisipkan sebelum komentar `// ---------- Pusat Ingest ----------`:

```ts
// ---------- Modul 2: anggota tim & kelengkapan penugasan ----------
export interface Member {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
  role_in_team: string;
}
export interface EngagementDetails {
  scope: string | null;
  period_start: string | null;
  period_end: string | null;
  kb_shareable: boolean;
}
export const listMembers = (id: number) =>
  req<Member[]>(`/engagements/${id}/members`);
export const addMember = (id: number, user_id: number, role_in_team = "member") =>
  req<Member>(`/engagements/${id}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id, role_in_team }),
  });
export const removeMember = (id: number, userId: number) =>
  req<null>(`/engagements/${id}/members/${userId}`, { method: "DELETE" });
export const saveEngagementDetails = (id: number, d: EngagementDetails) =>
  req<EngagementDetails>(`/engagements/${id}/details`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(d),
  });
// Belum ada fungsi apa pun untuk /users di klien ini — dropdown anggota
// membutuhkannya, jadi ditambahkan di sini.
export const listUsers = () => req<User[]>("/users");
```

Antarmuka `User` sudah ada di berkas ini (sekitar baris 55) — pakai yang itu, jangan membuat tipe baru.

Tambahkan pula keempat field ke antarmuka `EngagementDetail` yang sudah ada:

```ts
  scope: string | null;
  period_start: string | null;
  period_end: string | null;
  kb_shareable: boolean;
```

- [ ] **Step 2: Tambah kunci terjemahan ke KEDUA locale**

Pada blok `id`, sisipkan setelah `"tab.summary": "Ringkasan",`:

```ts
    "tab.team": "Tim",
    "team.title": "Anggota Tim",
    "team.hint": "Hanya anggota yang dapat membuka penugasan ini. Administrator selalu bisa.",
    "team.name": "Nama",
    "team.email": "Surel",
    "team.role": "Peran",
    "team.roleInTeam": "Peran di tim",
    "team.add": "Tambah Anggota",
    "team.remove": "Keluarkan",
    "team.empty": "Belum ada anggota.",
    "team.pickUser": "Pilih pengguna",
    "team.forbidden": "Hanya auditor atau admin yang boleh mengubah anggota tim.",
    "team.lastMember": "Anggota terakhir tidak dapat dikeluarkan.",
    "det.title": "Kelengkapan Penugasan",
    "det.scope": "Cakupan pengujian",
    "det.scopePlaceholder": "mis. aplikasi web internal, tanpa uji DoS",
    "det.periodStart": "Mulai",
    "det.periodEnd": "Selesai",
    "det.kbShareable": "Boleh jadi rujukan Basis Pengetahuan",
    "det.save": "Simpan Kelengkapan",
    "det.saved": "Kelengkapan penugasan tersimpan.",
```

Pada blok `en`, sisipkan setelah `"tab.summary": "Summary",` padanannya:

```ts
    "tab.team": "Team",
    "team.title": "Team Members",
    "team.hint": "Only members can open this engagement. Administrators always can.",
    "team.name": "Name",
    "team.email": "Email",
    "team.role": "Role",
    "team.roleInTeam": "Role in team",
    "team.add": "Add Member",
    "team.remove": "Remove",
    "team.empty": "No members yet.",
    "team.pickUser": "Pick a user",
    "team.forbidden": "Only auditors or admins may change team members.",
    "team.lastMember": "The last member cannot be removed.",
    "det.title": "Engagement Details",
    "det.scope": "Testing scope",
    "det.scopePlaceholder": "e.g. internal web app, no DoS testing",
    "det.periodStart": "Start",
    "det.periodEnd": "End",
    "det.kbShareable": "May be referenced by the Knowledge Base",
    "det.save": "Save Details",
    "det.saved": "Engagement details saved.",
```

- [ ] **Step 3: Daftarkan tab baru**

Di `frontend/src/app/engagements/[id]/page.tsx`, ubah deklarasi `TABS` (sekitar baris 487):

```tsx
  const TABS: { key: "files" | "findings" | "summary" | "team"; label: string }[] = [
    { key: "files", label: t("tab.files") },
    { key: "findings", label: `${t("tab.findings")} (${findings.length})` },
    { key: "summary", label: t("tab.summary") },
    { key: "team", label: t("tab.team") },
  ];
```

Perbarui juga tipe state `tab` agar menerima `"team"`.

- [ ] **Step 4: Tambah state, pemuatan, dan isi tab**

Tambahkan state bersama state lain:

```tsx
  const [members, setMembers] = useState<api.Member[]>([]);
  const [allUsers, setAllUsers] = useState<api.User[]>([]);
  const [pickUser, setPickUser] = useState<string>("");
  const [scope, setScope] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [kbShareable, setKbShareable] = useState(true);
  // State pesan tersendiri. `baseMsg` yang sudah ada khusus untuk baseline di
  // tab Ringkasan — memakainya di sini membuat pesan muncul di tab yang salah.
  const [teamMsg, setTeamMsg] = useState<string | null>(null);
```

Tambahkan pemuat yang dipanggil saat tab `team` dibuka:

```tsx
  const loadTeam = useCallback(async () => {
    const [ms, us] = await Promise.all([
      api.listMembers(id),
      api.listUsers().catch(() => [] as api.User[]),
    ]);
    setMembers(ms);
    setAllUsers(us);
  }, [id]);

  useEffect(() => {
    if (tab === "team") void loadTeam();
  }, [tab, loadTeam]);
```

Isi formulir kelengkapan dari `eng` ketika data penugasan termuat:

```tsx
  useEffect(() => {
    if (!eng) return;
    setScope(eng.scope ?? "");
    setPeriodStart(eng.period_start ?? "");
    setPeriodEnd(eng.period_end ?? "");
    setKbShareable(eng.kb_shareable ?? true);
  }, [eng]);
```

Lalu render blok tab, mengikuti pola `{tab === "summary" && (...)}` yang sudah ada:

```tsx
      {tab === "team" && (
        <>
          <section className="card">
            <h3 style={{ marginTop: 0 }}>{t("team.title")}</h3>
            <p className="muted">{t("team.hint")}</p>
            {members.length === 0 ? (
              <p className="muted">{t("team.empty")}</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t("team.name")}</th>
                      <th>{t("team.email")}</th>
                      <th>{t("team.role")}</th>
                      <th>{t("team.roleInTeam")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.user_id}>
                        <td>{m.full_name}</td>
                        <td className="mono">{m.email}</td>
                        <td className="mono">{m.role}</td>
                        <td className="mono">{m.role_in_team}</td>
                        <td>
                          {canApprove && (
                            <button
                              className="btn secondary"
                              onClick={() =>
                                api
                                  .removeMember(id, m.user_id)
                                  .then(() => void loadTeam())
                                  .catch((err) =>
                                    setError(
                                      err instanceof ApiError ? err.message : String(err)
                                    )
                                  )
                              }
                            >
                              {t("team.remove")}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {canApprove && (
              <div className="form-row" style={{ marginTop: 12 }}>
                <label className="field">
                  <span>{t("team.pickUser")}</span>
                  <select value={pickUser} onChange={(e) => setPickUser(e.target.value)}>
                    <option value="">—</option>
                    {allUsers
                      .filter((u) => !members.some((m) => m.user_id === u.id))
                      .map((u) => (
                        <option key={u.id} value={String(u.id)}>
                          {u.full_name} ({u.role})
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  className="btn"
                  disabled={!pickUser}
                  onClick={() =>
                    api
                      .addMember(id, Number(pickUser))
                      .then(() => {
                        setPickUser("");
                        void loadTeam();
                      })
                      .catch((err) =>
                        setError(err instanceof ApiError ? err.message : String(err))
                      )
                  }
                >
                  {t("team.add")}
                </button>
              </div>
            )}
          </section>

          <section className="card">
            <h3 style={{ marginTop: 0 }}>{t("det.title")}</h3>
            <div className="form-row">
              <label className="field">
                <span>{t("det.periodStart")}</span>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                />
              </label>
              <label className="field">
                <span>{t("det.periodEnd")}</span>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                />
              </label>
            </div>
            <label className="field" style={{ marginTop: 8 }}>
              <span>{t("det.scope")}</span>
              <textarea
                rows={3}
                value={scope}
                placeholder={t("det.scopePlaceholder")}
                onChange={(e) => setScope(e.target.value)}
              />
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <input
                type="checkbox"
                checked={kbShareable}
                onChange={(e) => setKbShareable(e.target.checked)}
              />
              <span>{t("det.kbShareable")}</span>
            </label>
            {canApprove && (
              <button
                className="btn"
                style={{ marginTop: 12 }}
                onClick={() =>
                  api
                    .saveEngagementDetails(id, {
                      scope: scope || null,
                      period_start: periodStart || null,
                      period_end: periodEnd || null,
                      kb_shareable: kbShareable,
                    })
                    .then(() => {
                      setTeamMsg(t("det.saved"));
                      void refresh();
                    })
                    .catch((err) =>
                      setError(err instanceof ApiError ? err.message : String(err))
                    )
                }
              >
                {t("det.save")}
              </button>
            )}
            {teamMsg && <div className="alert ok">{teamMsg}</div>}
          </section>
        </>
      )}
```

- [ ] **Step 5: Typecheck**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: tanpa keluaran. Bila muncul galat kunci terjemahan, ada kunci yang belum ditambahkan ke salah satu locale.

- [ ] **Step 6: Verifikasi di peramban**

Buka `http://localhost:3000/engagements/18` → tab **Tim**.
Expected: daftar anggota memuat Administrator; dropdown berisi pengguna yang belum menjadi anggota; tombol **Tambah Anggota** dan **Keluarkan** muncul (kamu login sebagai admin); formulir periode dan cakupan terisi nilai yang tersimpan di Task 6.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/i18n/messages.ts frontend/src/app/engagements/[id]/page.tsx
git commit -m "feat(web): tab Tim berisi anggota, periode, dan cakupan penugasan

Tab tersendiri, bukan disisipkan ke Ringkasan yang sudah memuat ringkasan AI,
baseline, dan metrik waktu. Ketiga isinya sama-sama menjawab modul
Pengelolaan Penugasan di proposal, jadi wajar berada di satu tempat."
```

---

### Task 8: Perbandingan naratif di panel review

**Files:**
- Modify: `backend/app/api/routes/engagements.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/app/engagements/[id]/page.tsx`

**Interfaces:**
- Consumes: `diff_narrative` (Task 2); `_get_engagement(db, engagement_id, user)` (Task 4)
- Produces: `GET /engagements/{id}/findings/{fid}/diff` → keluaran `diff_narrative`

- [ ] **Step 1: Tambah endpoint**

Di `backend/app/api/routes/engagements.py`, tambahkan impor `from app.review_diff import diff_narrative`, lalu sisipkan setelah endpoint riwayat revisi:

```python
@router.get("/{engagement_id}/findings/{finding_id}/diff")
def finding_diff(
    engagement_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Bandingkan draf AI dengan naratif final auditor.

    `overall_changed_ratio` menjadi bahan bukti indikator proposal soal porsi
    kalimat yang memerlukan penyuntingan berat.
    """
    _get_engagement(db, engagement_id, user)
    f = db.get(Finding, finding_id)
    if f is None or f.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Temuan tak ditemukan"
        )
    return diff_narrative(f.ai_draft, f.final_narrative)
```

- [ ] **Step 2: Tambah klien dan terjemahan**

Di `frontend/src/lib/api.ts`:

```ts
export interface DiffSection {
  before: string;
  after: string;
  added: string[];
  removed: string[];
  changed_ratio: number;
}
export interface NarrativeDiff {
  sections: Record<string, DiffSection>;
  overall_changed_ratio: number;
}
export const getFindingDiff = (id: number, findingId: number) =>
  req<NarrativeDiff>(`/engagements/${id}/findings/${findingId}/diff`);
```

Di `frontend/src/i18n/messages.ts`, blok `id`:

```ts
    "diff.tab": "Perbandingan",
    "diff.overall": "Porsi kata yang diubah auditor",
    "diff.added": "Ditambahkan",
    "diff.removed": "Dihapus",
    "diff.none": "Tidak ada perbedaan dari draf AI.",
```

blok `en`:

```ts
    "diff.tab": "Comparison",
    "diff.overall": "Share of words changed by auditor",
    "diff.added": "Added",
    "diff.removed": "Removed",
    "diff.none": "No difference from the AI draft.",
```

- [ ] **Step 3: Tampilkan di panel review**

Di panel review pada `frontend/src/app/engagements/[id]/page.tsx`, di samping tombol **Riwayat** yang sudah ada, tambahkan tombol **Perbandingan** dengan state dan pemuat:

```tsx
  const [diff, setDiff] = useState<api.NarrativeDiff | null>(null);

  async function loadDiff(findingId: number) {
    try {
      setDiff(await api.getFindingDiff(id, findingId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }
```

dan blok tampilannya:

```tsx
  {diff && (
    <div className="card" style={{ marginTop: 12 }}>
      <p className="mono">
        {t("diff.overall")}: {Math.round(diff.overall_changed_ratio * 100)}%
      </p>
      {Object.entries(diff.sections).map(([name, s]) => (
        <div key={name} style={{ marginTop: 8 }}>
          <strong>{name}</strong>{" "}
          <span className="mono">({Math.round(s.changed_ratio * 100)}%)</span>
          {s.added.length === 0 && s.removed.length === 0 ? (
            <p className="muted">{t("diff.none")}</p>
          ) : (
            <>
              {s.added.length > 0 && (
                <p>
                  <span className="badge ok">{t("diff.added")}</span> {s.added.join(" ")}
                </p>
              )}
              {s.removed.length > 0 && (
                <p>
                  <span className="badge err">{t("diff.removed")}</span>{" "}
                  {s.removed.join(" ")}
                </p>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  )}
```

- [ ] **Step 4: Verifikasi dengan data nyata**

Penugasan #18 memiliki satu temuan yang naratifnya sudah disunting auditor.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin@auditforge.local&password=admin12345' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
FID=$(docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -t -c "select id from findings where engagement_id=18 and narrative_edited = true limit 1;" | tr -d ' \n')
curl -s "http://localhost:8000/engagements/18/findings/$FID/diff" -H "Authorization: Bearer $TOKEN" | python -c "
import sys,json
d=json.load(sys.stdin)
print('rasio keseluruhan:', d['overall_changed_ratio'])
for k,v in d['sections'].items():
    print(f\"  {k:16} {v['changed_ratio']:.4f}  +{len(v['added'])} -{len(v['removed'])}\")
"
```
Expected: rasio keseluruhan antara 0 dan 1, dan bagian yang kamu sunting menunjukkan kata yang ditambah/dihapus.

- [ ] **Step 5: Typecheck dan tes**

```bash
docker exec auditforge-web-1 npx tsc --noEmit
docker exec auditforge-api-1 python -m pytest -q
```
Expected: tsc tanpa keluaran; `164 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/engagements.py frontend/src/lib/api.ts frontend/src/i18n/messages.ts frontend/src/app/engagements/[id]/page.tsx
git commit -m "feat(review): perbandingan naratif AI vs auditor di panel review

Menutup janji proposal soal perbandingan versi penyuntingan, dan
overall_changed_ratio menjadi bahan bukti indikator kedua — porsi kalimat yang
memerlukan penyuntingan berat — yang selama ini belum pernah terukur."
```

---

## Verifikasi Akhir

- [ ] `docker exec auditforge-api-1 python -m pytest -q` → 164 passed
- [ ] `docker exec auditforge-web-1 npx tsc --noEmit` → bersih
- [ ] `grep -rn "TODO(Modul 2)" backend/app --include=*.py` → tidak ada hasil
- [ ] Tidak ada penugasan tanpa anggota (kueri pada Task 3 Step 5 → `yatim = 0`)
- [ ] Admin melihat seluruh penugasan; analis bukan anggota melihat **0** di `/engagements`, `/stats`, dan `/ingest`
- [ ] Anggota terakhir tidak dapat dikeluarkan (`409`)
- [ ] Periode dan cakupan tercetak di kop laporan
- [ ] `alembic downgrade -1` lalu `upgrade head` berjalan tanpa galat
- [ ] `FLOW.md` diperbarui: langkah mengisi tim, periode, cakupan, dan membaca Perbandingan

## Yang Belum Dikerjakan Plan Ini

| Bagian | Alasan |
|---|---|
| Modul 3 — Basis Pengetahuan + halaman `/findings` | Spec terpisah, dibangun setelah ini; `kb_shareable` sudah disiapkan di sini |
| Perbandingan dua revisi sembarang (`?from=&to=`) | Spec menyebutnya sebagai varian; perbandingan draf-AI vs final sudah menjawab kebutuhan indikator. Tambahkan bila auditor benar-benar memintanya |
| Notifikasi | Spec tersendiri, belum ditulis |

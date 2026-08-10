# Modul 3 — Basis Pengetahuan Temuan dan Halaman `/findings`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Naratif temuan yang telah disetujui menjadi rujukan yang dapat dicari dan dipakai ulang lintas penugasan, dan halaman `/findings` yang selama ini *stub* berubah menjadi pencarian temuan + Basis Pengetahuan.

**Architecture:** Dua modul murni tanpa DB memikul seluruh keputusan — `knowledge/matching.py` (pencocokan judul lintas klien) dan `knowledge/entries.py` (naratif efektif + syarat pembuatan entri). Tabel `knowledge_entries` menyimpan salinan beku naratif saat temuan disetujui. Dua router baru (`/knowledge`, `/findings`) tipis di atas modul murni itu; satu endpoint penerapan menumpang router `engagements` yang sudah ada. Frontend menambah satu halaman dua-tab.

**Tech Stack:** FastAPI + SQLAlchemy 2 (`Mapped`/`mapped_column`) + Alembic + PostgreSQL; Next.js 14 App Router + TypeScript; pytest murni tanpa infrastruktur.

## Global Constraints

- **Docstring dan komentar berbahasa Indonesia**; identifier, tipe, dan nama field API berbahasa Inggris. Jangan mengubah prosa Indonesia yang sudah ada menjadi Inggris.
- **Seluruh tes harus murni** — tanpa DB, Redis, MinIO, LLM, tanpa `conftest.py`. Palsukan baris ORM dengan `types.SimpleNamespace` (lihat `backend/tests/test_reporting.py`).
- **Tidak ada pemanggilan LLM baru.** Modul 3 sepenuhnya deterministik.
- **Setiap teks UI baru wajib ditambahkan ke KEDUA locale** di `frontend/src/i18n/messages.ts`. Tipe `MessageKey` membuat `tsc` gagal bila satu locale terlewat.
- Gerbang: `docker exec auditforge-api-1 python -m pytest -q` dan `docker exec auditforge-web-1 npx tsc --noEmit`. **Jangan jalankan `npm run lint`** — tidak ada konfigurasi ESLint, `next lint` berhenti di prompt interaktif.
- Dev tools tidak ikut ter-*build*: jalankan `docker exec auditforge-api-1 pip install -e ".[dev]"` sekali di awal, dan ulangi setelah `docker compose build`.
- Setelah mengubah kode Celery task, **restart kontainer `worker` dan `beat`**. Modul 3 tidak menyentuh task, jadi seharusnya tidak perlu.
- Kelas CSS tersedia di `frontend/src/app/globals.css`: `card`, `table`, `table-wrap`, `badge` (+ `ok`/`err`/`wait`), `btn` (+ `secondary`), `alert` (+ `ok`/`err`), `muted`, `mono`, `link`, `field`, `form-row`. **Jangan pakai `btn ghost`** — kelas itu berteks putih, dibuat untuk chrome navy, dan tak terbaca di kartu berlatar terang.
- Titik awal: `main` @ `baeb4f4`. Alembic head saat ini `c5e1a90f4b26`.

---

## Struktur Berkas

| Berkas | Tanggung jawab |
|---|---|
| `backend/app/knowledge/__init__.py` | Paket kosong |
| `backend/app/knowledge/matching.py` | **Murni.** Normalisasi judul lintas klien + skor kemiripan |
| `backend/app/knowledge/entries.py` | **Murni.** Naratif efektif + syarat pembuatan entri KB |
| `backend/app/models/knowledge_entry.py` | Model `KnowledgeEntry` |
| `backend/alembic/versions/d4b7e2c81f95_knowledge_entries.py` | Tabel + indeks |
| `backend/app/scripts/backfill_knowledge.py` | Pengisian mundur, idempoten, memakai modul murni |
| `backend/app/api/routes/knowledge.py` | `GET /knowledge`, `GET /knowledge/suggest` — auditor/admin, akses baca tercatat |
| `backend/app/api/routes/findings.py` | `GET /findings` — pencarian lintas penugasan, disaring keanggotaan |
| `backend/app/schemas/knowledge.py` | Skema Pydantic KB + pencarian temuan |
| `backend/tests/test_knowledge_matching.py` | Tes modul pencocokan |
| `backend/tests/test_knowledge_entries.py` | Tes naratif efektif + syarat entri |
| `frontend/src/app/findings/page.tsx` | Halaman dua tab (menggantikan *stub*) |
| `frontend/src/lib/api.ts` | Tipe + fungsi klien baru |
| `frontend/src/i18n/messages.ts` | Teks ID + EN |
| Modifikasi: `backend/app/models/__init__.py`, `backend/app/main.py`, `backend/app/api/routes/engagements.py`, `frontend/src/components/AppShell.tsx`, `FLOW.md` | |

**Catatan penyimpangan dari spec** — spec §5.2 hasil revisi menempatkan pengisian mundur **di dalam migrasi**. Rencana ini memindahkannya ke `app/scripts/backfill_knowledge.py`. Alasannya: aturan naratif efektif (`final or draft`, termasuk perlakuan atas string kosong dan spasi) hanya boleh punya **satu** sumber kebenaran. Menuliskannya ulang dalam SQL akan menciptakan salinan kedua yang bisa menyimpang — persis kelas cacat yang sudah dua kali terjadi hari ini (`f54c8e1`). Skrip dapat mengimpor modul murni yang sama, idempoten, dan dapat dijalankan ulang. Polanya mengikuti `app/scripts/seed.py` yang sudah ada. Migrasi tetap membuat tabel; Task 8 menjalankan skripnya dan memverifikasi hasilnya.

---

## Task 1: Modul pencocokan judul lintas penugasan

**Files:**
- Create: `backend/app/knowledge/__init__.py`
- Create: `backend/app/knowledge/matching.py`
- Test: `backend/tests/test_knowledge_matching.py`

**Interfaces:**
- Consumes: tidak ada
- Produces:
  - `normalize_title(title: str) -> str`
  - `title_tokens(title_norm: str) -> set[str]`
  - `score_match(*, a_cwe: str | None, a_title_norm: str, b_cwe: str | None, b_title_norm: str) -> float`
  - `rank_matches(target: object, candidates: list, *, limit: int = 5, min_score: float = 0.3) -> list[tuple[object, float]]` — `target` dan tiap `candidate` cukup memiliki atribut `cwe` dan `title_norm`

- [ ] **Step 1: Buat paket**

```bash
mkdir -p backend/app/knowledge
printf '"""Basis Pengetahuan Temuan (Modul 3)."""\n' > backend/app/knowledge/__init__.py
```

- [ ] **Step 2: Tulis tes yang gagal**

Buat `backend/tests/test_knowledge_matching.py`:

```python
"""Uji unit Modul 3 — pencocokan judul temuan lintas penugasan (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.knowledge.matching import (
    normalize_title,
    rank_matches,
    score_match,
    title_tokens,
)


def test_normalize_membuang_host_port_dan_kata_umum():
    assert normalize_title("TLS Version Detection on example.com:443") == "tls version"


def test_normalize_membuang_url_penuh():
    hasil = normalize_title("Cross Site Scripting (Reflected) at http://example.com/search?q=1")
    assert hasil == "cross site scripting reflected"


def test_normalize_membuang_alamat_ip_dan_angka():
    assert normalize_title("Open Port 8080 on 192.168.1.10") == "open port"


def test_normalize_mempertahankan_nama_teknologi():
    # 'log4j2' mengandung angka tetapi bukan angka berdiri sendiri — harus bertahan.
    hasil = normalize_title("Apache Log4j2 Remote Code Execution (Log4Shell)")
    assert "log4j2" in hasil
    assert "log4shell" in hasil


def test_normalize_teks_kosong_aman():
    assert normalize_title("") == ""
    assert normalize_title("   ") == ""
    # Judul yang seluruhnya kata umum menyusut menjadi kosong, bukan meledak.
    assert normalize_title("the a an of") == ""


def test_title_tokens_unik():
    assert title_tokens("tls version tls") == {"tls", "version"}
    assert title_tokens("") == set()


def test_cwe_sama_dan_judul_sama_memberi_skor_penuh():
    s = score_match(
        a_cwe="CWE-79", a_title_norm="cross site scripting",
        b_cwe="CWE-79", b_title_norm="cross site scripting",
    )
    assert s == 1.0


def test_cwe_berbeda_dibatasi_kemiripan_judul_saja():
    # Tanpa kesamaan CWE, skor tak boleh melampaui bobot judul (0.4).
    s = score_match(
        a_cwe="CWE-79", a_title_norm="cross site scripting",
        b_cwe="CWE-89", b_title_norm="cross site scripting",
    )
    assert s == 0.4


def test_cwe_kosong_tidak_dianggap_cocok():
    # Dua temuan tanpa CWE bukan berarti ber-CWE sama.
    s = score_match(
        a_cwe=None, a_title_norm="cross site scripting",
        b_cwe=None, b_title_norm="cross site scripting",
    )
    assert s == 0.4


def test_cwe_huruf_besar_kecil_dan_spasi_diabaikan():
    s = score_match(
        a_cwe=" cwe-79 ", a_title_norm="xss",
        b_cwe="CWE-79", b_title_norm="xss",
    )
    assert s == 1.0


def test_judul_tanpa_irisan_hanya_menyisakan_bobot_cwe():
    s = score_match(
        a_cwe="CWE-79", a_title_norm="alpha beta",
        b_cwe="CWE-79", b_title_norm="gamma delta",
    )
    assert s == 0.6


def test_rank_mengurutkan_dan_menyaring_ambang():
    target = SimpleNamespace(cwe="CWE-79", title_norm="cross site scripting")
    kandidat = [
        SimpleNamespace(id=1, cwe="CWE-79", title_norm="cross site scripting"),
        SimpleNamespace(id=2, cwe="CWE-79", title_norm="cross site scripting stored"),
        SimpleNamespace(id=3, cwe="CWE-311", title_norm="mixed content"),
    ]
    hasil = rank_matches(target, kandidat, limit=5, min_score=0.3)
    assert [c.id for c, _ in hasil] == [1, 2]
    assert hasil[0][1] > hasil[1][1]


def test_rank_menghormati_limit_dan_daftar_kosong():
    target = SimpleNamespace(cwe="CWE-79", title_norm="xss")
    kandidat = [SimpleNamespace(id=i, cwe="CWE-79", title_norm="xss") for i in range(5)]
    assert len(rank_matches(target, kandidat, limit=2)) == 2
    assert rank_matches(target, [], limit=2) == []
```

- [ ] **Step 3: Jalankan tes, pastikan gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_knowledge_matching.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.knowledge.matching'`

- [ ] **Step 4: Tulis implementasinya**

Buat `backend/app/knowledge/matching.py`:

```python
"""Pencocokan temuan lintas penugasan (Modul 3) — deterministik, tanpa DB.

`Finding.fingerprint` **tidak dapat dipakai** di sini: ia sengaja memuat host,
port, dan path agar dedup tidak pernah menggabungkan dua target berbeda. Justru
karena itu ia tak akan pernah cocok antar klien. Basis Pengetahuan membutuhkan
kebalikannya — membuang segala yang khas satu target, lalu membandingkan sisa
maknanya.

Tanpa LLM dan tanpa embedding: bobot besar pada kesamaan CWE, sisanya irisan
token judul. Auditor harus dapat menjelaskan kenapa dua temuan dianggap mirip.
"""
from __future__ import annotations

import re

# Bobot: CWE yang sama jauh lebih berarti daripada judul yang mirip, karena
# judul ditulis oleh perkakas yang berbeda-beda.
CWE_WEIGHT = 0.6
TITLE_WEIGHT = 0.4

STOPWORDS: frozenset[str] = frozenset(
    {
        # Inggris — bahasa keluaran perkakas.
        "a", "an", "and", "at", "detected", "detection", "for", "found", "in",
        "is", "of", "on", "or", "possible", "potential", "the", "to", "was",
        "with",
        # Indonesia — judul hasil suntingan auditor.
        "dan", "di", "atau", "pada", "yang", "terdeteksi", "ditemukan",
    }
)

_URL_RE = re.compile(r"https?://\S+")
_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
# Nama host dan nomor versi sama-sama berpola "kata.kata"; keduanya memang
# harus hilang karena keduanya khas satu target.
_HOST_RE = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
_PORT_RE = re.compile(r":\d+\b")
_NUM_RE = re.compile(r"\b\d+\b")
_NONWORD_RE = re.compile(r"[^a-z0-9\s]+")


def normalize_title(title: str) -> str:
    """Buang segala yang khas satu target, sisakan makna judulnya.

    Urutannya penting: URL lebih dulu (memuat host sekaligus port), lalu IP,
    host, port, angka berdiri sendiri, terakhir tanda baca.
    """
    text = (title or "").lower()
    text = _URL_RE.sub(" ", text)
    text = _IP_RE.sub(" ", text)
    text = _HOST_RE.sub(" ", text)
    text = _PORT_RE.sub(" ", text)
    text = _NUM_RE.sub(" ", text)
    text = _NONWORD_RE.sub(" ", text)
    kata = [w for w in text.split() if w and w not in STOPWORDS]
    return " ".join(kata)


def title_tokens(title_norm: str) -> set[str]:
    return set((title_norm or "").split())


def _clean_cwe(value: str | None) -> str:
    return (value or "").strip().upper()


def score_match(
    *,
    a_cwe: str | None,
    a_title_norm: str,
    b_cwe: str | None,
    b_title_norm: str,
) -> float:
    """Skor kemiripan 0..1 antara dua temuan.

    CWE kosong **tidak** dianggap cocok dengan CWE kosong lain: ketiadaan data
    bukan bukti kesamaan.
    """
    cwe_a, cwe_b = _clean_cwe(a_cwe), _clean_cwe(b_cwe)
    cwe_part = CWE_WEIGHT if (cwe_a and cwe_b and cwe_a == cwe_b) else 0.0

    ta, tb = title_tokens(a_title_norm), title_tokens(b_title_norm)
    overlap = len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0

    return round(cwe_part + TITLE_WEIGHT * overlap, 4)


def rank_matches(
    target: object,
    candidates: list,
    *,
    limit: int = 5,
    min_score: float = 0.3,
) -> list[tuple[object, float]]:
    """Kandidat termirip lebih dahulu; yang di bawah `min_score` dibuang.

    `target` dan tiap kandidat cukup memiliki atribut `cwe` dan `title_norm`,
    sehingga fungsi ini dapat diuji dengan `SimpleNamespace`.
    """
    scored: list[tuple[object, float]] = []
    for c in candidates:
        s = score_match(
            a_cwe=getattr(target, "cwe", None),
            a_title_norm=getattr(target, "title_norm", "") or "",
            b_cwe=getattr(c, "cwe", None),
            b_title_norm=getattr(c, "title_norm", "") or "",
        )
        if s >= min_score:
            scored.append((c, s))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
```

- [ ] **Step 5: Jalankan tes, pastikan lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_knowledge_matching.py -q`
Expected: PASS — 13 tes lulus

- [ ] **Step 6: Commit**

```bash
git add backend/app/knowledge/ backend/tests/test_knowledge_matching.py
git commit -m "feat(knowledge): pencocokan judul temuan lintas penugasan"
```

---

## Task 2: Modul naratif efektif dan syarat entri

**Files:**
- Create: `backend/app/knowledge/entries.py`
- Test: `backend/tests/test_knowledge_entries.py`

**Interfaces:**
- Consumes: tidak ada
- Produces:
  - `SECTIONS: tuple[str, ...]` = `("description", "impact", "recommendation")`
  - `effective_narrative(finding: object) -> dict[str, str]`
  - `is_auditor_edited(finding: object) -> bool`
  - `should_create_entry(*, status: str, kb_shareable: bool, narrative: dict[str, str], already_exists: bool) -> tuple[bool, str]`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `backend/tests/test_knowledge_entries.py`:

```python
"""Uji unit Modul 3 — naratif efektif & syarat entri Basis Pengetahuan (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.knowledge.entries import (
    effective_narrative,
    is_auditor_edited,
    should_create_entry,
)

DRAF = {
    "description": "Draf AI menjelaskan kerentanan",
    "impact": "Draf AI menjelaskan dampak",
    "recommendation": "Draf AI menyarankan perbaikan",
}
FINAL = {
    "description": "Auditor menulis ulang uraiannya",
    "impact": "Auditor menulis ulang dampaknya",
    "recommendation": "Auditor menulis ulang sarannya",
}


def test_final_menang_atas_draf():
    f = SimpleNamespace(final_narrative=dict(FINAL), ai_draft=dict(DRAF))
    assert effective_narrative(f) == FINAL
    assert is_auditor_edited(f) is True


def test_final_kosong_jatuh_ke_draf_ai():
    """Auditor menerima draf apa adanya — naratifnya tetap ada, bukan hilang."""
    for kosong in (None, {}, {"description": "", "impact": "  ", "recommendation": ""}):
        f = SimpleNamespace(final_narrative=kosong, ai_draft=dict(DRAF))
        assert effective_narrative(f) == DRAF
        assert is_auditor_edited(f) is False


def test_keduanya_kosong_menghasilkan_bagian_kosong():
    f = SimpleNamespace(final_narrative=None, ai_draft=None)
    assert effective_narrative(f) == {
        "description": "", "impact": "", "recommendation": ""
    }
    assert is_auditor_edited(f) is False


def test_spasi_dipangkas_dan_kunci_asing_dibuang():
    f = SimpleNamespace(
        final_narrative={"description": "  ada  ", "catatan": "abaikan"},
        ai_draft=None,
    )
    n = effective_narrative(f)
    assert n["description"] == "ada"
    assert set(n.keys()) == {"description", "impact", "recommendation"}


def test_masukan_bukan_dict_tidak_meledak():
    f = SimpleNamespace(final_narrative="bukan dict", ai_draft=42)
    assert effective_narrative(f) == {
        "description": "", "impact": "", "recommendation": ""
    }


def test_entri_dibuat_saat_disetujui_dan_boleh_dibagi():
    ok, alasan = should_create_entry(
        status="approved", kb_shareable=True, narrative=DRAF, already_exists=False
    )
    assert ok is True
    assert alasan == ""


def test_status_selain_approved_ditolak():
    for st in ("draft", "in_review", "rejected", "false_positive"):
        ok, alasan = should_create_entry(
            status=st, kb_shareable=True, narrative=DRAF, already_exists=False
        )
        assert ok is False
        assert "disetujui" in alasan


def test_kb_shareable_mati_menghormati_kontrak_klien():
    ok, alasan = should_create_entry(
        status="approved", kb_shareable=False, narrative=DRAF, already_exists=False
    )
    assert ok is False
    assert "berbagi" in alasan


def test_naratif_kosong_tidak_menjadi_entri():
    ok, alasan = should_create_entry(
        status="approved",
        kb_shareable=True,
        narrative={"description": "", "impact": "", "recommendation": ""},
        already_exists=False,
    )
    assert ok is False
    assert "kosong" in alasan


def test_entri_ganda_dicegah():
    """Buka-kembali lalu setujui lagi tidak boleh menggandakan entri."""
    ok, alasan = should_create_entry(
        status="approved", kb_shareable=True, narrative=DRAF, already_exists=True
    )
    assert ok is False
    assert "sudah" in alasan
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_knowledge_entries.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.knowledge.entries'`

- [ ] **Step 3: Tulis implementasinya**

Buat `backend/app/knowledge/entries.py`:

```python
"""Syarat dan isi entri Basis Pengetahuan (Modul 3) — deterministik, tanpa DB.

Naratif yang disalin adalah **naratif efektif**, mengikuti aturan yang sama
dengan `reporting/report_data.py` dan `review_diff.py`: `final or draft`.
`final_narrative` yang kosong berarti auditor **menerima draf AI apa adanya**,
bukan tidak punya naratif — membacanya mentah-mentah akan membuang naskah yang
justru sudah disetujui manusia.

`auditor_edited` merekam bedanya agar auditor tahu bobot tiap rujukan; ia
**tidak** dipakai untuk menyaring entri.
"""
from __future__ import annotations

SECTIONS: tuple[str, ...] = ("description", "impact", "recommendation")


def _section(source: object, key: str) -> str:
    """Ambil satu bagian naratif dengan aman; apa pun selain dict dianggap kosong."""
    if not isinstance(source, dict):
        return ""
    return str(source.get(key, "") or "").strip()


def _has_text(source: object) -> bool:
    return any(_section(source, name) for name in SECTIONS)


def effective_narrative(finding: object) -> dict[str, str]:
    """Naratif yang benar-benar berlaku: suntingan auditor menang atas draf AI."""
    final = getattr(finding, "final_narrative", None)
    draft = getattr(finding, "ai_draft", None)
    source = final if _has_text(final) else draft
    return {name: _section(source, name) for name in SECTIONS}


def is_auditor_edited(finding: object) -> bool:
    """True bila naskahnya diketik auditor, bukan draf AI yang diterima apa adanya."""
    return _has_text(getattr(finding, "final_narrative", None))


def should_create_entry(
    *,
    status: str,
    kb_shareable: bool,
    narrative: dict[str, str],
    already_exists: bool,
) -> tuple[bool, str]:
    """Boleh membuat entri KB? Kembalikan (boleh, alasan bila tidak).

    Alasannya dikembalikan sebagai data agar pemanggil dapat mencatat mengapa
    sebuah persetujuan tidak menghasilkan entri, alih-alih diam saja.
    """
    if status != "approved":
        return False, f"Hanya temuan yang disetujui masuk Basis Pengetahuan (status: {status})."
    if not kb_shareable:
        return False, "Penugasan ini menolak berbagi ke Basis Pengetahuan."
    if not _has_text(narrative):
        return False, "Naratif kosong; tidak ada yang dapat dijadikan rujukan."
    if already_exists:
        return False, "Entri untuk temuan ini sudah ada."
    return True, ""
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `docker exec auditforge-api-1 python -m pytest tests/test_knowledge_entries.py -q`
Expected: PASS — 10 tes lulus

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/entries.py backend/tests/test_knowledge_entries.py
git commit -m "feat(knowledge): naratif efektif dan syarat entri basis pengetahuan"
```

---

## Task 3: Model dan migrasi `knowledge_entries`

**Files:**
- Create: `backend/app/models/knowledge_entry.py`
- Create: `backend/alembic/versions/d4b7e2c81f95_knowledge_entries.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: tidak ada
- Produces: `KnowledgeEntry` dengan kolom `id`, `source_finding_id`, `source_engagement_id`, `title`, `title_norm`, `cwe`, `owasp`, `severity`, `narrative`, `auditor_edited`, `created_by`, `created_at`, `usage_count`

- [ ] **Step 1: Tulis model**

Buat `backend/app/models/knowledge_entry.py`:

```python
"""Entri Basis Pengetahuan Temuan (Modul 3).

Salinan **beku** naratif sebuah temuan pada saat ia disetujui. Perubahan
belakangan pada temuan asal sengaja tidak mengubah entri ini: rujukan yang
berubah diam-diam tidak dapat dipercaya.

Naratif disimpan **utuh**, tidak disamarkan — keputusan sadar demi kegunaan,
dengan tiga pengaman: hanya auditor/admin yang boleh membuka, `kb_shareable`
per penugasan menghormati NDA, dan akses baca dicatat ke `audit_logs`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id"), index=True
    )
    source_engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    # Judul ternormalisasi (host/port/angka dibuang) untuk pencocokan lintas klien.
    title_norm: Mapped[str] = mapped_column(String(300), index=True)
    cwe: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    owasp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(10))
    # {description, impact, recommendation} — naratif efektif saat disetujui.
    narrative: Mapped[dict] = mapped_column(JSON)
    # Benar bila naskahnya diketik auditor; salah bila draf AI disetujui apa adanya.
    auditor_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

- [ ] **Step 2: Daftarkan model**

Ubah `backend/app/models/__init__.py` — tambahkan impor dan entri `__all__` mengikuti urutan abjad yang sudah ada:

```python
from app.models.finding import Finding, FindingAttachment, FindingRevision
from app.models.knowledge_entry import KnowledgeEntry
from app.models.scan_upload import ScanUpload
```

dan di `__all__`, setelah `"FindingRevision",`:

```python
    "KnowledgeEntry",
```

- [ ] **Step 3: Tulis migrasi**

Buat `backend/alembic/versions/d4b7e2c81f95_knowledge_entries.py`:

```python
"""tabel basis pengetahuan temuan (Modul 3)

Revision ID: d4b7e2c81f95
Revises: c5e1a90f4b26
Create Date: 2026-08-10 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4b7e2c81f95'
down_revision: str | None = 'c5e1a90f4b26'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'knowledge_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_finding_id', sa.Integer(), nullable=False),
        sa.Column('source_engagement_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('title_norm', sa.String(length=300), nullable=False),
        sa.Column('cwe', sa.String(length=32), nullable=True),
        sa.Column('owasp', sa.String(length=64), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('narrative', sa.JSON(), nullable=False),
        sa.Column('auditor_edited', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['source_finding_id'], ['findings.id']),
        sa.ForeignKeyConstraint(['source_engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        # Satu temuan menghasilkan paling banyak satu entri: buka-kembali lalu
        # setujui ulang tidak boleh menggandakan rujukan.
        sa.UniqueConstraint('source_finding_id', name='uq_knowledge_source_finding'),
    )
    op.create_index(
        'ix_knowledge_entries_source_finding_id',
        'knowledge_entries', ['source_finding_id'],
    )
    op.create_index(
        'ix_knowledge_entries_source_engagement_id',
        'knowledge_entries', ['source_engagement_id'],
    )
    op.create_index('ix_knowledge_entries_title_norm', 'knowledge_entries', ['title_norm'])
    op.create_index('ix_knowledge_entries_cwe', 'knowledge_entries', ['cwe'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_entries_cwe', table_name='knowledge_entries')
    op.drop_index('ix_knowledge_entries_title_norm', table_name='knowledge_entries')
    op.drop_index(
        'ix_knowledge_entries_source_engagement_id', table_name='knowledge_entries'
    )
    op.drop_index(
        'ix_knowledge_entries_source_finding_id', table_name='knowledge_entries'
    )
    op.drop_table('knowledge_entries')
```

- [ ] **Step 4: Jalankan migrasi dan verifikasi siklusnya**

```bash
docker exec auditforge-api-1 alembic upgrade head
docker exec auditforge-api-1 alembic current          # harus d4b7e2c81f95 (head)
docker exec auditforge-api-1 alembic downgrade -1     # buktikan downgrade bersih
docker exec auditforge-api-1 alembic upgrade head
```

Expected: `d4b7e2c81f95 (head)`, siklus turun-naik tanpa galat.

- [ ] **Step 5: Pastikan suite lama tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS — seluruh tes (189 setelah Task 1–2)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/knowledge_entry.py backend/app/models/__init__.py backend/alembic/versions/d4b7e2c81f95_knowledge_entries.py
git commit -m "feat(db): tabel entri basis pengetahuan temuan"
```

---

## Task 4: Entri KB lahir otomatis saat temuan disetujui

**Files:**
- Modify: `backend/app/api/routes/engagements.py` (impor di kepala berkas; fungsi `change_status`)

**Interfaces:**
- Consumes: `app.knowledge.entries.effective_narrative`, `is_auditor_edited`, `should_create_entry`; `app.knowledge.matching.normalize_title`; `KnowledgeEntry`
- Produces: helper modul `_sync_knowledge_entry(db: Session, f: Finding, eng: Engagement, user: User) -> None`

- [ ] **Step 1: Tambahkan impor**

Di `backend/app/api/routes/engagements.py`, sisipkan pada blok impor `app.*` sesuai urutan abjad:

```python
from app.knowledge.entries import effective_narrative, is_auditor_edited, should_create_entry
from app.knowledge.matching import normalize_title
from app.models.knowledge_entry import KnowledgeEntry
```

- [ ] **Step 2: Tambahkan helper tepat di atas `change_status`**

```python
def _sync_knowledge_entry(
    db: Session, f: Finding, eng: Engagement, user: User
) -> None:
    """Buat entri Basis Pengetahuan bila temuan baru saja disetujui (Modul 3).

    Seluruh keputusannya ada di `app.knowledge.entries`; di sini hanya I/O.
    Kegagalan syarat bukan galat — persetujuan tetap sah meski entri tak dibuat
    (mis. penugasan menolak berbagi).
    """
    narrative = effective_narrative(f)
    exists = db.scalar(
        select(KnowledgeEntry.id).where(KnowledgeEntry.source_finding_id == f.id)
    )
    ok, _alasan = should_create_entry(
        status=f.status,
        kb_shareable=bool(eng.kb_shareable),
        narrative=narrative,
        already_exists=exists is not None,
    )
    if not ok:
        return
    db.add(
        KnowledgeEntry(
            source_finding_id=f.id,
            source_engagement_id=eng.id,
            title=f.title,
            title_norm=normalize_title(f.title),
            cwe=f.cwe,
            owasp=f.owasp,
            severity=f.severity,
            narrative=narrative,
            auditor_edited=is_auditor_edited(f),
            created_by=user.id,
        )
    )
```

- [ ] **Step 3: Panggil helper dari `change_status`**

Di `change_status`, ubah baris pertama agar menyimpan penugasannya, lalu panggil helper sebelum `db.commit()`:

```python
    eng = _get_engagement(db, engagement_id, user)
```

(ganti `_get_engagement(db, engagement_id, user)` yang berdiri sendiri)

dan tepat sebelum `db.commit()` di akhir fungsi:

```python
    _sync_knowledge_entry(db, f, eng, user)
    db.commit()
```

- [ ] **Step 4: Verifikasi manual — persetujuan menciptakan entri**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=admin@auditforge.local&password=admin12345' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Buka kembali lalu setujui ulang satu temuan penugasan 18.
curl -s -X POST http://localhost:8000/engagements/18/findings/167/status \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"in_review"}' -o /dev/null -w "reopen %{http_code}\n"
curl -s -X POST http://localhost:8000/engagements/18/findings/167/status \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"approved"}' -o /dev/null -w "approve %{http_code}\n"

docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c \
  "SELECT id, source_finding_id, title_norm, cwe, auditor_edited FROM knowledge_entries;"
```

Expected: `reopen 200`, `approve 200`, dan **satu** baris untuk `source_finding_id = 167` dengan `auditor_edited = f` (temuan itu memakai draf AI apa adanya).

- [ ] **Step 5: Verifikasi manual — persetujuan ulang tidak menggandakan**

Ulangi perintah reopen + approve pada temuan yang sama, lalu hitung barisnya:

```bash
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -t -c \
  "SELECT COUNT(*) FROM knowledge_entries WHERE source_finding_id = 167;"
```

Expected: `1` — bukan 2.

- [ ] **Step 6: Pastikan suite tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/engagements.py
git commit -m "feat(knowledge): entri basis pengetahuan lahir saat temuan disetujui"
```

---

## Task 5: Skrip pengisian mundur

**Files:**
- Create: `backend/app/scripts/backfill_knowledge.py`

**Interfaces:**
- Consumes: `app.knowledge.entries`, `app.knowledge.matching.normalize_title`, `KnowledgeEntry`
- Produces: `python -m app.scripts.backfill_knowledge` (idempoten)

- [ ] **Step 1: Tulis skrip**

Buat `backend/app/scripts/backfill_knowledge.py`:

```python
"""Isi Basis Pengetahuan dari temuan yang sudah disetujui (Modul 3).

Idempoten: dijalankan berulang kali tidak menggandakan entri, karena syaratnya
sama dengan jalur runtime — keduanya memakai `app.knowledge.entries`.

Sengaja **tidak** ditaruh di dalam migrasi: aturan naratif efektif
(`final or draft`) hanya boleh punya satu sumber kebenaran. Menuliskannya ulang
dalam SQL menciptakan salinan kedua yang dapat menyimpang diam-diam.

    docker exec auditforge-api-1 python -m app.scripts.backfill_knowledge
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.knowledge.entries import (
    effective_narrative,
    is_auditor_edited,
    should_create_entry,
)
from app.knowledge.matching import normalize_title
from app.models.engagement import Engagement
from app.models.finding import Finding, FindingRevision
from app.models.knowledge_entry import KnowledgeEntry


def _approver_id(db: Session, finding_id: int) -> int | None:
    """Siapa yang menyetujui temuan ini, menurut riwayat revisinya.

    Bila tak ditemukan, kembalikan None. Mengarang penulis akan merusak
    keterlacakan yang justru menjadi inti modul ini.
    """
    return db.scalar(
        select(FindingRevision.author_id)
        .where(
            FindingRevision.finding_id == finding_id,
            FindingRevision.action == "approve",
        )
        .order_by(FindingRevision.id.desc())
        .limit(1)
    )


def run() -> dict[str, int]:
    db = SessionLocal()
    try:
        sudah_ada = set(db.scalars(select(KnowledgeEntry.source_finding_id)).all())
        engagements = {e.id: e for e in db.scalars(select(Engagement)).all()}
        rows = db.scalars(
            select(Finding).where(Finding.status == "approved").order_by(Finding.id)
        ).all()

        dibuat = dilewati = 0
        for f in rows:
            eng = engagements.get(f.engagement_id)
            if eng is None:
                dilewati += 1
                continue
            narrative = effective_narrative(f)
            ok, _alasan = should_create_entry(
                status=f.status,
                kb_shareable=bool(eng.kb_shareable),
                narrative=narrative,
                already_exists=f.id in sudah_ada,
            )
            if not ok:
                dilewati += 1
                continue
            db.add(
                KnowledgeEntry(
                    source_finding_id=f.id,
                    source_engagement_id=eng.id,
                    title=f.title,
                    title_norm=normalize_title(f.title),
                    cwe=f.cwe,
                    owasp=f.owasp,
                    severity=f.severity,
                    narrative=narrative,
                    auditor_edited=is_auditor_edited(f),
                    created_by=_approver_id(db, f.id),
                )
            )
            sudah_ada.add(f.id)
            dibuat += 1

        db.commit()
        return {"diperiksa": len(rows), "dibuat": dibuat, "dilewati": dilewati}
    finally:
        db.close()


if __name__ == "__main__":
    hasil = run()
    print(
        f"Basis Pengetahuan: {hasil['dibuat']} entri baru, "
        f"{hasil['dilewati']} dilewati, dari {hasil['diperiksa']} temuan disetujui."
    )
```

- [ ] **Step 2: Jalankan skrip**

Run: `docker exec auditforge-api-1 python -m app.scripts.backfill_knowledge`
Expected: laporan berisi jumlah entri baru (sekitar 9, karena temuan 167 sudah punya entri dari Task 4).

- [ ] **Step 3: Buktikan idempoten**

Run: `docker exec auditforge-api-1 python -m app.scripts.backfill_knowledge`
Expected: `0 entri baru` — seluruhnya dilewati.

- [ ] **Step 4: Periksa isinya, termasuk yang naratifnya draf AI**

```bash
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c \
  "SELECT COUNT(*) AS total,
          COUNT(*) FILTER (WHERE auditor_edited) AS disunting_auditor,
          COUNT(*) FILTER (WHERE NOT auditor_edited) AS draf_ai_disetujui
   FROM knowledge_entries;"
```

Expected: total 10, dengan **kedua** kolom terisi bukan nol — bukti bahwa naratif draf AI yang disetujui apa adanya ikut masuk, bukan terbuang.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/backfill_knowledge.py
git commit -m "feat(knowledge): skrip pengisian mundur basis pengetahuan"
```

---

## Task 6: Endpoint Basis Pengetahuan dan pencarian temuan

**Files:**
- Create: `backend/app/schemas/knowledge.py`
- Create: `backend/app/api/routes/knowledge.py`
- Create: `backend/app/api/routes/findings.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `app.knowledge.matching.rank_matches`, `app.access.needs_engagement_filter`, `KnowledgeEntry`
- Produces:
  - `GET /knowledge?cwe=&q=&limit=` → `{"items": [KnowledgeEntryOut]}` — auditor/admin
  - `GET /knowledge/suggest?finding_id=&limit=` → `{"items": [{"entry": …, "score": float}]}` — auditor/admin
  - `GET /findings?q=&severity=&cwe=&owasp=&status=&engagement_id=&limit=` → `{"items": [FindingSearchOut]}` — semua peran, disaring keanggotaan

- [ ] **Step 1: Tulis skema**

Buat `backend/app/schemas/knowledge.py`:

```python
"""Skema Basis Pengetahuan dan pencarian temuan lintas penugasan (Modul 3)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KnowledgeEntryOut(BaseModel):
    id: int
    source_finding_id: int
    source_engagement_id: int
    # Nama penugasan & klien asal ditampilkan mencolok di UI agar auditor selalu
    # sadar sedang melihat data klien lain.
    source_engagement_name: str
    source_client_name: str
    title: str
    cwe: str | None
    owasp: str | None
    severity: str
    narrative: dict
    auditor_edited: bool
    usage_count: int
    created_at: datetime


class KnowledgeSuggestion(BaseModel):
    entry: KnowledgeEntryOut
    score: float


class FindingSearchOut(BaseModel):
    id: int
    engagement_id: int
    engagement_name: str
    client_name: str
    title: str
    severity: str
    status: str
    priority: int | None
    cwe: str | None
    owasp: str | None
    cvss_score: float | None
```

- [ ] **Step 2: Tulis router Basis Pengetahuan**

Buat `backend/app/api/routes/knowledge.py`:

```python
"""Basis Pengetahuan Temuan (Modul 3) — rujukan naratif lintas penugasan.

Tiga pengaman menyertai keputusan menyimpan naratif secara utuh:

1. Hanya **auditor/admin** yang boleh membuka (router ini).
2. `engagements.kb_shareable` menentukan apakah sebuah penugasan boleh menjadi
   rujukan (dijaga saat entri dibuat, lihat `engagements._sync_knowledge_entry`).
3. **Akses baca dicatat.** `AuditMiddleware` hanya mencatat mutasi, jadi route di
   sini menulis `AuditLog` sendiri. Bila klien bertanya siapa saja yang pernah
   melihat temuan mereka, jawabannya tersedia.
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.knowledge.matching import normalize_title, rank_matches
from app.models.audit_log import AuditLog
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.knowledge_entry import KnowledgeEntry
from app.models.user import User
from app.schemas.knowledge import KnowledgeEntryOut, KnowledgeSuggestion

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_KB_ROLES = ("auditor", "admin")


def _log_read(
    db: Session, request: Request, user: User, *, detail: str, entity_id: str | None
) -> None:
    """Catat akses baca ke jejak audit; middleware hanya mencatat mutasi."""
    db.add(
        AuditLog(
            user_id=user.id,
            action="read",
            method="GET",
            path=request.url.path,
            entity="knowledge",
            entity_id=entity_id,
            status_code=200,
            ip=request.client.host if request.client else None,
            detail=detail,
        )
    )
    db.commit()


def _to_out(entry: KnowledgeEntry, eng: Engagement | None) -> KnowledgeEntryOut:
    return KnowledgeEntryOut(
        id=entry.id,
        source_finding_id=entry.source_finding_id,
        source_engagement_id=entry.source_engagement_id,
        source_engagement_name=eng.name if eng else "—",
        source_client_name=eng.client_name if eng else "—",
        title=entry.title,
        cwe=entry.cwe,
        owasp=entry.owasp,
        severity=entry.severity,
        narrative=entry.narrative or {},
        auditor_edited=bool(entry.auditor_edited),
        usage_count=entry.usage_count or 0,
        created_at=entry.created_at,
    )


def _engagement_map(db: Session, entries: list[KnowledgeEntry]) -> dict[int, Engagement]:
    """Ambil seluruh penugasan asal dalam satu kueri, bukan satu per entri."""
    ids = {e.source_engagement_id for e in entries}
    if not ids:
        return {}
    return {
        e.id: e
        for e in db.scalars(select(Engagement).where(Engagement.id.in_(ids))).all()
    }


@router.get("")
def list_knowledge(
    request: Request,
    q: str | None = None,
    cwe: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_KB_ROLES)),
) -> dict:
    """Telusuri Basis Pengetahuan. Akses baca dicatat pada jejak audit."""
    stmt = select(KnowledgeEntry).order_by(KnowledgeEntry.usage_count.desc(), KnowledgeEntry.id.desc())
    if cwe:
        stmt = stmt.where(KnowledgeEntry.cwe == cwe.strip().upper())
    if q:
        # Cocokkan pada judul ternormalisasi agar "example.com:443" pada kueri
        # tidak menghalangi kecocokan.
        needle = normalize_title(q)
        if needle:
            stmt = stmt.where(KnowledgeEntry.title_norm.ilike(f"%{needle}%"))
        else:
            stmt = stmt.where(KnowledgeEntry.title.ilike(f"%{q.strip()}%"))
    entries = list(db.scalars(stmt.limit(max(1, min(limit, 200)))).all())
    engs = _engagement_map(db, entries)

    _log_read(
        db, request, user,
        detail=f"telusur basis pengetahuan q={q or ''} cwe={cwe or ''} hasil={len(entries)}",
        entity_id=None,
    )
    return {"items": [_to_out(e, engs.get(e.source_engagement_id)) for e in entries]}


@router.get("/suggest")
def suggest_knowledge(
    request: Request,
    finding_id: int,
    limit: int = 5,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_KB_ROLES)),
) -> dict:
    """Entri paling mirip untuk satu temuan, memakai pencocokan deterministik."""
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Temuan tak ditemukan")

    target = SimpleNamespace(cwe=f.cwe, title_norm=normalize_title(f.title))
    # Entri dari temuan itu sendiri bukan saran yang berguna.
    candidates = list(
        db.scalars(
            select(KnowledgeEntry).where(KnowledgeEntry.source_finding_id != finding_id)
        ).all()
    )
    ranked = rank_matches(target, candidates, limit=max(1, min(limit, 20)))
    engs = _engagement_map(db, [c for c, _ in ranked])

    _log_read(
        db, request, user,
        detail=f"saran basis pengetahuan untuk temuan {finding_id}, {len(ranked)} hasil",
        entity_id=str(finding_id),
    )
    return {
        "items": [
            KnowledgeSuggestion(
                entry=_to_out(c, engs.get(c.source_engagement_id)), score=score
            )
            for c, score in ranked
        ]
    }
```

- [ ] **Step 3: Tulis router pencarian temuan**

Buat `backend/app/api/routes/findings.py`:

```python
"""Pencarian temuan lintas penugasan (Modul 3).

Berbeda dengan Basis Pengetahuan yang sengaja lintas klien, pencarian ini
**disaring keanggotaan**: seorang analis hanya menemukan temuan pada penugasan
yang memang menjadi tanggung jawabnya. Daftar id kosong berarti nol hasil,
bukan seluruh data — itu bedanya fail-closed dengan fail-open.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import needs_engagement_filter
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.finding import Finding
from app.models.user import User
from app.schemas.knowledge import FindingSearchOut

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("")
def search_findings(
    q: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    cwe: str | None = None,
    owasp: str | None = None,
    engagement_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Cari temuan pada seluruh penugasan yang boleh diakses pengguna."""
    stmt = (
        select(Finding, Engagement)
        .join(Engagement, Finding.engagement_id == Engagement.id)
        .order_by(Finding.priority.asc().nulls_last(), Finding.id.desc())
    )

    if needs_engagement_filter(user.role.name):
        eng_ids = list(
            db.scalars(
                select(EngagementMember.engagement_id).where(
                    EngagementMember.user_id == user.id
                )
            ).all()
        )
        stmt = stmt.where(Finding.engagement_id.in_(eng_ids))

    if engagement_id is not None:
        stmt = stmt.where(Finding.engagement_id == engagement_id)
    if severity:
        stmt = stmt.where(Finding.severity == severity.strip().lower())
    if status:
        stmt = stmt.where(Finding.status == status.strip().lower())
    if cwe:
        stmt = stmt.where(Finding.cwe == cwe.strip().upper())
    if owasp:
        stmt = stmt.where(Finding.owasp == owasp.strip())
    if q:
        stmt = stmt.where(Finding.title.ilike(f"%{q.strip()}%"))

    rows = db.execute(stmt.limit(max(1, min(limit, 500)))).all()
    return {
        "items": [
            FindingSearchOut(
                id=f.id,
                engagement_id=f.engagement_id,
                engagement_name=e.name,
                client_name=e.client_name,
                title=f.title,
                severity=f.severity,
                status=f.status,
                priority=f.priority,
                cwe=f.cwe,
                owasp=f.owasp,
                cvss_score=f.cvss_score,
            )
            for f, e in rows
        ]
    }
```

- [ ] **Step 4: Daftarkan kedua router**

Di `backend/app/main.py`, tambahkan pada blok impor route (urutan abjad):

```python
from app.api.routes import findings as findings_routes
from app.api.routes import knowledge as knowledge_routes
```

dan pada blok `include_router`, setelah `engagement_routes`:

```python
app.include_router(findings_routes.router)
app.include_router(knowledge_routes.router)
```

- [ ] **Step 5: Verifikasi manual — peran dan penyaringan**

```bash
AT=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=analis@auditforge.local&password=analis12345' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=admin@auditforge.local&password=admin12345' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "-- analis (bukan anggota mana pun) --"
curl -s -o /dev/null -w "  /knowledge  %{http_code} (harus 403)\n" \
  http://localhost:8000/knowledge -H "Authorization: Bearer $AT"
curl -s http://localhost:8000/findings -H "Authorization: Bearer $AT" \
  | python -c "import sys,json;print('  /findings items =', len(json.load(sys.stdin)['items']), '(harus 0)')"

echo "-- admin --"
curl -s http://localhost:8000/knowledge -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print('  /knowledge items =', len(json.load(sys.stdin)['items']))"
curl -s http://localhost:8000/findings -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print('  /findings items =', len(json.load(sys.stdin)['items']))"
curl -s "http://localhost:8000/knowledge/suggest?finding_id=165" -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('  saran:', [(i['entry']['title'][:40], i['score']) for i in d['items']])"
```

Expected: analis `403` di `/knowledge` dan **0** item di `/findings`; admin melihat 10 entri KB dan **100** temuan (basis data memuat 116, `limit` bawaan 100 — angka yang lebih kecil berarti penyaringan bocor ke jalur admin); saran mengembalikan entri ber-CWE sama lebih dahulu.

- [ ] **Step 6: Verifikasi manual — akses baca tercatat**

```bash
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c \
  "SELECT user_id, action, entity, entity_id, detail FROM audit_logs
   WHERE entity = 'knowledge' ORDER BY id DESC LIMIT 5;"
```

Expected: baris `action = read`, `entity = knowledge`, dengan `detail` memuat kueri dan jumlah hasil.

- [ ] **Step 7: Pastikan suite tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/knowledge.py backend/app/api/routes/knowledge.py backend/app/api/routes/findings.py backend/app/main.py
git commit -m "feat(api): endpoint basis pengetahuan dan pencarian temuan lintas penugasan"
```

---

## Task 7: Terapkan naratif Basis Pengetahuan ke sebuah temuan

**Files:**
- Modify: `backend/app/api/routes/engagements.py`

**Interfaces:**
- Consumes: `KnowledgeEntry`, `_get_engagement`, `_get_finding`, `_add_revision`, `_finding_detail`
- Produces: `POST /engagements/{engagement_id}/findings/{finding_id}/apply-knowledge/{entry_id}` → `FindingDetailOut`

- [ ] **Step 1: Tambahkan endpoint tepat setelah `edit_narrative`**

```python
@router.post(
    "/{engagement_id}/findings/{finding_id}/apply-knowledge/{entry_id}",
    response_model=FindingDetailOut,
)
def apply_knowledge(
    engagement_id: int,
    finding_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("auditor", "admin")),
) -> FindingDetailOut:
    """Pakai naratif entri Basis Pengetahuan sebagai naratif final temuan ini.

    Tercatat sebagai **suntingan auditor** (`action="edit"`, `author_id` terisi),
    bukan `ai_draft`. Naskah itu berasal dari manusia yang telah menyetujuinya di
    penugasan lain, bukan dari model; menandainya sebagai draf AI akan merusak
    keterlacakan yang menjadi inti prinsip proposal.
    """
    _get_engagement(db, engagement_id, user)
    f = _get_finding(db, engagement_id, finding_id)
    entry = db.get(KnowledgeEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entri Basis Pengetahuan tak ditemukan")

    source = entry.narrative if isinstance(entry.narrative, dict) else {}
    narrative = {
        "description": str(source.get("description", "") or "").strip(),
        "impact": str(source.get("impact", "") or "").strip(),
        "recommendation": str(source.get("recommendation", "") or "").strip(),
    }
    f.final_narrative = narrative
    f.narrative_edited = True
    _add_revision(
        db,
        f,
        action="edit",
        note=f"Naratif diambil dari Basis Pengetahuan (entri #{entry.id}).",
        author_id=user.id,
        narrative=narrative,
    )
    entry.usage_count = (entry.usage_count or 0) + 1
    db.commit()
    db.refresh(f)
    return _finding_detail(f)
```

- [ ] **Step 2: Verifikasi manual — penerapan tercatat sebagai suntingan auditor**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=admin@auditforge.local&password=admin12345' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Ambil satu entri KB yang BUKAN berasal dari temuan 164.
ENTRY=$(curl -s http://localhost:8000/knowledge -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;d=json.load(sys.stdin)['items'];print([e['id'] for e in d if e['source_finding_id']!=164][0])")
echo "entri uji: $ENTRY"

curl -s -X POST "http://localhost:8000/engagements/18/findings/164/apply-knowledge/$ENTRY" \
  -H "Authorization: Bearer $TOKEN" -o /dev/null -w "apply %{http_code}\n"

curl -s http://localhost:8000/engagements/18/findings/164/revisions \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;r=json.load(sys.stdin)[0];print('  aksi =',r['action'],'| author_id =',r['author_id'],'| catatan =',r['note'])"

curl -s http://localhost:8000/knowledge -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;d=json.load(sys.stdin)['items'];print('  usage_count entri:',[(e['id'],e['usage_count']) for e in d if e['usage_count']>0])"
```

Expected: `apply 200`; revisi teratas ber-`action = edit` dengan `author_id = 1` (**bukan** `ai_draft`, **bukan** `author_id = None`); `usage_count` entri itu naik menjadi 1.

- [ ] **Step 3: Verifikasi manual — analis ditolak**

```bash
AT=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=analis@auditforge.local&password=analis12345' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "analis apply -> %{http_code} (harus 403)\n" \
  -X POST "http://localhost:8000/engagements/18/findings/164/apply-knowledge/1" \
  -H "Authorization: Bearer $AT"
```

Expected: `403`.

- [ ] **Step 4: Pastikan suite tetap lulus**

Run: `docker exec auditforge-api-1 python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/engagements.py
git commit -m "feat(api): terapkan naratif basis pengetahuan sebagai suntingan auditor"
```

---

## Task 8: Halaman `/findings` dua tab

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/i18n/messages.ts`
- Modify (ganti seluruh isi): `frontend/src/app/findings/page.tsx`

**Interfaces:**
- Consumes: `GET /findings`, `GET /knowledge` (via proxy `/api/*`)
- Produces: tipe `FindingSearchItem`, `KnowledgeEntry`; fungsi `searchFindings`, `listKnowledge`

- [ ] **Step 1: Tambahkan tipe dan fungsi klien**

Di `frontend/src/lib/api.ts`, tepat sebelum bagian `// ---------- Pusat Ingest ----------`:

```typescript
// ---------- Modul 3: pencarian temuan & Basis Pengetahuan ----------
export interface FindingSearchItem {
  id: number;
  engagement_id: number;
  engagement_name: string;
  client_name: string;
  title: string;
  severity: string;
  status: string;
  priority: number | null;
  cwe: string | null;
  owasp: string | null;
  cvss_score: number | null;
}
export interface FindingSearchFilters {
  q?: string;
  severity?: string;
  status?: string;
  cwe?: string;
}
export const searchFindings = (f: FindingSearchFilters = {}) => {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.severity) p.set("severity", f.severity);
  if (f.status) p.set("status", f.status);
  if (f.cwe) p.set("cwe", f.cwe);
  const qs = p.toString();
  return req<{ items: FindingSearchItem[] }>(`/findings${qs ? `?${qs}` : ""}`);
};

export interface KnowledgeEntry {
  id: number;
  source_finding_id: number;
  source_engagement_id: number;
  source_engagement_name: string;
  source_client_name: string;
  title: string;
  cwe: string | null;
  owasp: string | null;
  severity: string;
  narrative: { description?: string; impact?: string; recommendation?: string };
  /** Naskah diketik auditor; false berarti draf AI yang disetujui apa adanya. */
  auditor_edited: boolean;
  usage_count: number;
  created_at: string;
}
export const listKnowledge = (q?: string, cwe?: string) => {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (cwe) p.set("cwe", cwe);
  const qs = p.toString();
  return req<{ items: KnowledgeEntry[] }>(`/knowledge${qs ? `?${qs}` : ""}`);
};
```

- [ ] **Step 2: Tambahkan teks ID**

Di `frontend/src/i18n/messages.ts`, di dalam blok `id:`, setelah baris `"nav.ingest": "Ingest",`:

```typescript
    "find.subtitle": "Cari temuan pada seluruh penugasan yang menjadi tanggung jawabmu.",
    "find.tabFindings": "Temuan",
    "find.tabKnowledge": "Basis Pengetahuan",
    "find.search": "Kata kunci judul",
    "find.severity": "Keparahan",
    "find.status": "Status",
    "find.cwe": "CWE",
    "find.all": "Semua",
    "find.apply": "Terapkan",
    "find.reset": "Bersihkan",
    "find.colEngagement": "Penugasan",
    "find.colTitle": "Judul",
    "find.colSeverity": "Keparahan",
    "find.colPriority": "Prioritas",
    "find.colCwe": "CWE",
    "find.colStatus": "Status",
    "find.empty": "Tak ada temuan yang cocok.",
    "find.loadError": "Gagal memuat temuan.",
    "kb.subtitle":
      "Naratif dari temuan yang telah disetujui, dapat dipakai ulang di penugasan lain.",
    "kb.warning":
      "Isi di bawah ini berasal dari penugasan klien lain. Penugasan yang menolak berbagi tidak muncul di sini, dan setiap pembukaan halaman ini tercatat pada jejak audit.",
    "kb.from": "Asal",
    "kb.used": "Dipakai",
    "kb.times": "kali",
    "kb.byAuditor": "Ditulis auditor",
    "kb.byAi": "Draf AI disetujui",
    "kb.empty": "Basis Pengetahuan masih kosong.",
    "kb.loadError": "Gagal memuat Basis Pengetahuan.",
    "kb.forbidden": "Basis Pengetahuan hanya untuk auditor dan administrator.",
```

- [ ] **Step 3: Tambahkan teks EN**

Di blok `en:`, pada posisi yang sama:

```typescript
    "find.subtitle": "Search findings across every engagement you are assigned to.",
    "find.tabFindings": "Findings",
    "find.tabKnowledge": "Knowledge Base",
    "find.search": "Title keyword",
    "find.severity": "Severity",
    "find.status": "Status",
    "find.cwe": "CWE",
    "find.all": "All",
    "find.apply": "Apply",
    "find.reset": "Clear",
    "find.colEngagement": "Engagement",
    "find.colTitle": "Title",
    "find.colSeverity": "Severity",
    "find.colPriority": "Priority",
    "find.colCwe": "CWE",
    "find.colStatus": "Status",
    "find.empty": "No matching findings.",
    "find.loadError": "Failed to load findings.",
    "kb.subtitle":
      "Narratives from approved findings, reusable on other engagements.",
    "kb.warning":
      "The content below comes from other clients' engagements. Engagements that opted out do not appear here, and every visit to this page is recorded in the audit trail.",
    "kb.from": "From",
    "kb.used": "Used",
    "kb.times": "times",
    "kb.byAuditor": "Written by auditor",
    "kb.byAi": "Approved AI draft",
    "kb.empty": "The Knowledge Base is still empty.",
    "kb.loadError": "Failed to load the Knowledge Base.",
    "kb.forbidden": "The Knowledge Base is for auditors and administrators only.",
```

- [ ] **Step 4: Ganti seluruh isi halaman**

Ganti isi `frontend/src/app/findings/page.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import { useAuth } from "@/lib/auth";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const STATUSES = ["draft", "in_review", "approved", "rejected", "false_positive"];

function sevClass(sev: string): string {
  if (sev === "critical" || sev === "high") return "badge err";
  if (sev === "medium" || sev === "low") return "badge wait";
  return "badge ok";
}

export default function FindingsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  // Basis Pengetahuan memuat data klien lain; hanya auditor/admin yang boleh.
  const canKb = user?.role === "auditor" || user?.role === "admin";

  const [tab, setTab] = useState<"findings" | "knowledge">("findings");
  const [error, setError] = useState<string | null>(null);

  // --- tab Temuan ---
  const [items, setItems] = useState<api.FindingSearchItem[]>([]);
  const [q, setQ] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  // --- tab Basis Pengetahuan ---
  const [entries, setEntries] = useState<api.KnowledgeEntry[]>([]);
  const [kbQ, setKbQ] = useState("");
  const [kbLoading, setKbLoading] = useState(false);
  const [kbFailed, setKbFailed] = useState(false);

  const loadFindings = useCallback(() => {
    setLoading(true);
    setError(null);
    return api
      .searchFindings({ q, severity, status })
      .then((d) => {
        setItems(d.items);
        setLoadFailed(false);
      })
      .catch((err) => {
        setLoadFailed(true);
        setError(err instanceof ApiError ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [q, severity, status]);

  const loadKnowledge = useCallback(() => {
    setKbLoading(true);
    setError(null);
    return api
      .listKnowledge(kbQ)
      .then((d) => {
        setEntries(d.items);
        setKbFailed(false);
      })
      .catch((err) => {
        setKbFailed(true);
        setError(err instanceof ApiError ? err.message : String(err));
      })
      .finally(() => setKbLoading(false));
  }, [kbQ]);

  useEffect(() => {
    void loadFindings();
  }, [loadFindings]);

  useEffect(() => {
    if (tab === "knowledge" && canKb) void loadKnowledge();
  }, [tab, canKb, loadKnowledge]);

  return (
    <AppShell title={t("nav.findings")}>
      <section className="card">
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button
            className={tab === "findings" ? "btn" : "btn secondary"}
            onClick={() => setTab("findings")}
          >
            {t("find.tabFindings")}
          </button>
          {canKb && (
            <button
              className={tab === "knowledge" ? "btn" : "btn secondary"}
              onClick={() => setTab("knowledge")}
            >
              {t("find.tabKnowledge")}
            </button>
          )}
        </div>

        {tab === "findings" ? (
          <>
            <p className="muted" style={{ marginTop: 0 }}>{t("find.subtitle")}</p>
            <div className="form-row">
              <label className="field">
                <span>{t("find.search")}</span>
                <input value={q} onChange={(e) => setQ(e.target.value)} />
              </label>
              <label className="field">
                <span>{t("find.severity")}</span>
                <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  <option value="">{t("find.all")}</option>
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>{t("find.status")}</span>
                <select value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">{t("find.all")}</option>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>
            </div>
            <button
              className="btn secondary"
              onClick={() => {
                setQ("");
                setSeverity("");
                setStatus("");
              }}
            >
              {t("find.reset")}
            </button>
          </>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>{t("kb.subtitle")}</p>
            <div className="alert ok">{t("kb.warning")}</div>
            <label className="field">
              <span>{t("find.search")}</span>
              <input value={kbQ} onChange={(e) => setKbQ(e.target.value)} />
            </label>
          </>
        )}

        {error && <div className="alert err">{error}</div>}
      </section>

      {tab === "findings" ? (
        <section className="card">
          {loading ? (
            <p className="muted">…</p>
          ) : loadFailed ? (
            <p className="muted">{t("find.loadError")}</p>
          ) : items.length === 0 ? (
            <p className="muted">{t("find.empty")}</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("find.colSeverity")}</th>
                    <th>{t("find.colTitle")}</th>
                    <th>{t("find.colEngagement")}</th>
                    <th>{t("find.colPriority")}</th>
                    <th>{t("find.colCwe")}</th>
                    <th>{t("find.colStatus")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((f) => (
                    <tr key={f.id}>
                      <td><span className={sevClass(f.severity)}>{f.severity}</span></td>
                      <td>{f.title}</td>
                      <td>
                        <Link className="link" href={`/engagements/${f.engagement_id}`}>
                          #{f.engagement_id} {f.engagement_name}
                        </Link>
                        <div className="muted mono">{f.client_name}</div>
                      </td>
                      <td className="mono">{f.priority ? `P${f.priority}` : "—"}</td>
                      <td className="mono">{f.cwe ?? "—"}</td>
                      <td className="mono">{f.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : !canKb ? (
        <section className="card">
          <p className="muted">{t("kb.forbidden")}</p>
        </section>
      ) : (
        <section className="card">
          {kbLoading ? (
            <p className="muted">…</p>
          ) : kbFailed ? (
            <p className="muted">{t("kb.loadError")}</p>
          ) : entries.length === 0 ? (
            <p className="muted">{t("kb.empty")}</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {entries.map((e) => (
                <div
                  key={e.id}
                  className="card"
                  style={{ background: "var(--surface-2)", marginBottom: 0 }}
                >
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span className={sevClass(e.severity)}>{e.severity}</span>
                    <strong>{e.title}</strong>
                    <span className="mono">{e.cwe ?? "—"}</span>
                    <span className="badge ok">
                      {e.auditor_edited ? t("kb.byAuditor") : t("kb.byAi")}
                    </span>
                  </div>
                  <p className="muted mono" style={{ marginBottom: 4 }}>
                    {t("kb.from")}: #{e.source_engagement_id} {e.source_engagement_name}
                    {" · "}{e.source_client_name}
                    {" · "}{t("kb.used")} {e.usage_count} {t("kb.times")}
                  </p>
                  {e.narrative.description && <p>{e.narrative.description}</p>}
                  {e.narrative.recommendation && (
                    <p className="muted">{e.narrative.recommendation}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 5: Typecheck**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: keluaran kosong. Bila ada galat `MessageKey`, satu locale tertinggal — periksa Step 2 dan 3.

- [ ] **Step 6: Verifikasi di peramban**

Buka `http://localhost:3000/findings` sebagai admin.

Expected:
- Tab **Temuan** aktif, tabel memuat temuan dari berbagai penugasan, kolom Penugasan berisi tautan yang berfungsi
- Menyaring keparahan `critical` memangkas daftar; **Bersihkan** memulihkannya
- Tab **Basis Pengetahuan** muncul, memuat kartu-kartu dengan badge asal penugasan/klien dan penanda `Ditulis auditor` / `Draf AI disetujui`
- Seluruh tombol terbaca (bukan putih-di-atas-putih)

Lalu keluar, masuk sebagai `analis@auditforge.local`:
- Tab **Basis Pengetahuan tidak muncul sama sekali**
- Tab Temuan menampilkan "Tak ada temuan yang cocok" (analis bukan anggota penugasan mana pun)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/findings/page.tsx frontend/src/lib/api.ts frontend/src/i18n/messages.ts
git commit -m "feat(web): halaman /findings berisi pencarian temuan dan Basis Pengetahuan"
```

---

## Task 9: Sembunyikan menu Administrasi dari peran non-admin

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `useAuth()` (sudah dipakai di `AppShell`)
- Produces: tidak ada

- [ ] **Step 1: Beri penanda peran pada daftar navigasi**

Di `frontend/src/components/AppShell.tsx`, ubah deklarasi `NAV` menjadi:

```tsx
const NAV: {
  href: string;
  icon: React.ReactNode;
  key: MessageKey;
  /** Bila diisi, item hanya tampil untuk peran-peran ini. */
  roles?: string[];
}[] = [
  { href: "/", icon: <Gauge size={18} weight="bold" />, key: "nav.dashboard" },
  { href: "/engagements", icon: <FolderOpen size={18} />, key: "nav.engagements" },
  { href: "/findings", icon: <Bug size={18} />, key: "nav.findings" },
  { href: "/reports", icon: <FileText size={18} />, key: "nav.reports" },
  { href: "/ingest", icon: <Path size={18} />, key: "nav.ingest" },
  // Route-nya sudah admin-only; menunya ikut disembunyikan agar tak menuntun
  // pengguna ke penolakan.
  { href: "/admin", icon: <ShieldCheck size={18} />, key: "nav.admin", roles: ["admin"] },
];
```

- [ ] **Step 2: Saring saat merender**

Di dalam `AppShell`, tepat sebelum `return`, tambahkan:

```tsx
  const navItems = NAV.filter((it) => !it.roles || (user && it.roles.includes(user.role)));
```

lalu ganti `NAV.map(` pada JSX menjadi `navItems.map(`.

- [ ] **Step 3: Typecheck**

Run: `docker exec auditforge-web-1 npx tsc --noEmit`
Expected: keluaran kosong.

- [ ] **Step 4: Verifikasi di peramban**

Sebagai admin: menu **Administrasi** tetap ada. Keluar, masuk sebagai `analis@auditforge.local`: menu Administrasi **hilang**, lima menu lain tetap.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppShell.tsx
git commit -m "fix(web): sembunyikan menu Administrasi dari peran non-admin"
```

---

## Task 10: Perbarui FLOW.md dan verifikasi menyeluruh

**Files:**
- Modify: `FLOW.md`

- [ ] **Step 1: Sisipkan bagian baru sebelum `## E. Batas AI ↔ Manusia ↔ Deterministik`**

Bagian ini masuk di antara akhir `### Pusat Ingest — memantau ingest lintas penugasan` dan pemisah `---` yang mendahului `## E`. Salin apa adanya:

```markdown
## D2. Basis Pengetahuan Temuan dan pencarian lintas penugasan

Naratif yang sudah **disetujui** tidak berhenti di satu laporan — ia menjadi rujukan untuk
penugasan berikutnya, sehingga kerentanan yang sama tak perlu ditulis ulang dari nol.

→ **Buka:** sidebar **Temuan**. Halaman ini punya dua tab.

**Tab Temuan** — pencarian temuan pada **seluruh penugasan yang menjadi tanggung jawabmu**,
dengan penyaring **kata kunci judul**, **keparahan**, dan **status**. Kolom penugasan tertaut
langsung ke halaman penugasannya. Analis hanya melihat penugasan tempat ia terdaftar sebagai
anggota tim; administrator melihat semua.

**Tab Basis Pengetahuan** — hanya muncul untuk **auditor dan administrator**. Berisi kartu
naratif dari temuan yang telah disetujui, lengkap dengan **penugasan dan klien asalnya**,
berapa kali entri itu **dipakai**, serta penanda apakah naskahnya **ditulis auditor** atau
**draf AI yang disetujui apa adanya**.

Tiga hal yang perlu diketahui tentang tab ini:

1. Entri lahir **otomatis** saat sebuah temuan berpindah ke status **Disetujui**.
2. Penugasan dapat **menolak berbagi**: buka tab **Tim** penugasan itu, hapus centang
   **Boleh jadi rujukan Basis Pengetahuan**, lalu **Simpan Kelengkapan**. Temuan yang
   disetujui di sana tidak akan pernah masuk. Saklar ini menghormati NDA yang melarang data
   klien dipakai untuk keperluan lain sekalipun internal.
3. **Setiap pembukaan tab ini tercatat** pada jejak audit (**Administrasi → Jejak Audit**).
   Bila klien bertanya siapa saja yang pernah melihat temuan mereka, jawabannya tersedia.

Naratif dari sebuah entri dapat dipakai sebagai titik awal temuan lain. Penerapannya dicatat
sebagai **suntingan auditor**, **bukan** draf AI — naskah itu memang berasal dari manusia
yang telah menyetujuinya di penugasan lain.
```

- [ ] **Step 2: Jalankan gerbang penuh**

```bash
docker exec auditforge-api-1 python -m pytest -q
docker exec auditforge-web-1 npx tsc --noEmit
git status --short
```

Expected: seluruh tes lulus (≈189), tsc bersih, working tree bersih setelah commit.

- [ ] **Step 3: Verifikasi menyeluruh sesuai spec §6**

| # | Uji | Hasil yang diharapkan |
|---|---|---|
| 1 | `alembic current` | `d4b7e2c81f95 (head)` |
| 2 | Setujui temuan pada penugasan ber-`kb_shareable` | Entri KB muncul |
| 3 | Matikan **Boleh jadi rujukan Basis Pengetahuan** di tab Tim penugasan lain, setujui temuan di sana | Entri KB **tidak** dibuat |
| 4 | Buka Basis Pengetahuan | Baris `entity='knowledge'`, `action='read'` di `audit_logs` |
| 5 | Terapkan entri KB ke sebuah temuan | Revisi ber-`action='edit'`, `author_id` terisi, `usage_count` naik |
| 6 | Masuk sebagai analis | Tab Basis Pengetahuan tak muncul; `/knowledge` membalas 403; menu Administrasi hilang |
| 7 | KB memuat entri ber-`auditor_edited` benar **dan** salah | Naratif draf AI yang disetujui apa adanya ikut masuk |

Untuk uji #3, matikan saklarnya lewat UI: buka penugasan lain → tab **Tim** → hapus centang **Boleh jadi rujukan Basis Pengetahuan** → **Simpan Kelengkapan**, lalu setujui satu temuan di penugasan itu dan periksa:

```bash
docker exec auditforge-postgres-1 psql -U auditforge -d auditforge -c \
  "SELECT source_engagement_id, COUNT(*) FROM knowledge_entries GROUP BY 1 ORDER BY 1;"
```

- [ ] **Step 4: Commit**

```bash
git add FLOW.md
git commit -m "docs: perbarui FLOW.md untuk Basis Pengetahuan dan halaman Temuan"
```

---

## Kriteria Selesai

- [ ] `/findings` bukan lagi *stub*; dua tab berfungsi
- [ ] Naratif disetujui masuk Basis Pengetahuan otomatis dan dapat dipakai ulang
- [ ] Penerapan naratif KB tercatat sebagai suntingan auditor (`edit` + `author_id`), bukan `ai_draft`
- [ ] `kb_shareable` dihormati; akses baca KB tercatat pada `audit_logs`
- [ ] Naratif draf AI yang disetujui apa adanya **ikut** menjadi rujukan, ditandai `auditor_edited = false`
- [ ] Pencarian temuan disaring keanggotaan (fail-closed); Basis Pengetahuan dibatasi peran auditor/admin
- [ ] Menu Administrasi tidak lagi tampil bagi peran non-admin
- [ ] Seluruh tes lama lulus; tes baru murni tanpa infrastruktur
- [ ] `FLOW.md` diperbarui

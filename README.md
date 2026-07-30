# AuditForge

**Sistem Triase Temuan Keamanan dan Penyusunan Laporan Audit Berbasis Kecerdasan Buatan**
— proyek Kerja Praktik di PT Suryasoft Konsultama (Divisi IT Audit & Security).

AuditForge bekerja pada data **pasca-pengujian**: keluaran perkakas (Nuclei, ZAP, Nmap, Burp,
SARIF) di-*ingest* → dinormalisasi & dedup → diperkaya (CWE/OWASP/CVSS/CVE) → ditriase →
AI menyusun **draf** naratif & ringkasan eksekutif → auditor meninjau/menyunting/menyetujui →
laporan **DOCX/PDF** terbit dari temuan yang disetujui.

> **Prinsip inti:** AI hanya membuat **draf**; **auditor adalah pengambil keputusan akhir.**
> Semua langkah non-AI (parsing, dedup, enrichment, triase, masking, perakitan laporan,
> metrik evaluasi) bersifat **deterministik** dan teruji tanpa memanggil LLM.

## Arsitektur ringkas

| Layanan | Peran | Port host |
|---|---|---|
| `api` | Backend FastAPI (REST) | 8000 |
| `worker` | Proses latar Celery (parsing, enrichment, naratif AI) | — |
| `web` | Frontend Next.js 14 (App Router) | 3000 |
| `postgres` | Basis data (PostgreSQL 16) | 5432 |
| `redis` | Broker Celery | 6379 |
| `minio` | Penyimpanan objek (berkas mentah & bukti) | 9000 (API) · **9101** (konsol) |

> Konsol MinIO dipetakan ke **9101** di host (port 9001 sering dipakai app lain, mis. Herd).

Frontend mematuhi **Blueprint UI/UX Suryasoft** (chrome navy, dark mode *no-flash*, status =
warna + ikon + teks). Font: **Space Grotesk + JetBrains Mono**; ikon: **Phosphor**. Antarmuka
dwibahasa **ID/EN**.

### Tech stack
Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · Celery + Redis ·
PostgreSQL 16 · MinIO · python-docx · WeasyPrint · Jinja2 · Next.js 14 · TypeScript.

## Menjalankan (Docker)

```bash
cp .env.example .env      # sesuaikan bila perlu (LLM diatur dari panel Admin — lihat di bawah)
docker compose up --build
```

| Untuk | URL |
|---|---|
| Web (UI) | http://localhost:3000 |
| Kesehatan API | http://localhost:8000/health |
| Kesehatan LLM | http://localhost:8000/health/ai |
| Dokumentasi API (Swagger) | http://localhost:8000/docs |
| Konsol MinIO | http://localhost:9101 |

### Akun bawaan (seed — ganti sebelum produksi)

Login memakai **alamat surel** (bukan nama pengguna).

| Peran | Surel | Kata sandi |
|---|---|---|
| Admin | `admin@auditforge.local` | `admin12345` |
| Analis | `analis@auditforge.local` | *(seed dev)* |
| Auditor | `auditor@auditforge.local` | *(seed dev)* |

RBAC: **analis** boleh menyunting/mengajukan temuan; hanya **auditor/admin** yang boleh
menyetujui/menolak/menandai positif-palsu; konfigurasi LLM & jejak audit hanya untuk **admin**.

## Konfigurasi LLM (provider-agnostik)

Lapisan AI menerima **LLM apa pun** lewat dua adapter format:

- **OpenAI-compatible** — default **OpenRouter** (juga menampung Ollama lokal, OpenAI, dll).
- **Anthropic** — Claude native.

Cukup isi **Base URL + API key + nama model + format** dari halaman **Administrasi** di UI
(tersimpan di tabel `app_settings`, fallback ke `.env`). Ganti model **tanpa rebuild/restart**.
Model default dev: `google/gemma-4-26b-a4b-it:free` (JSON bersih, ikut bahasa UI).

> **Masking otomatis:** sebelum teks keluar ke LLM, data sensitif (IP/host internal,
> kredensial, kunci, email) disamarkan (`[IP-INTERNAL-1]`, `[HOST-1]`, `[SECRET-1]`, …) lalu
> hasil AI di-*unmask* di server. Peta placeholder tidak pernah dikirim keluar. Uji jaminan
> ini ada di `tests/test_security.py`; pratinjaunya di panel Admin.

## Laporan

Dirakit dari temuan **disetujui** (naratif final auditor menang atas draf AI):

- `GET /engagements/{id}/report.docx?include=approved|all&lang=id|en` — DOCX (python-docx)
- `GET /engagements/{id}/report.pdf?...` — PDF (WeasyPrint; HTML Jinja2 → PDF)
- `GET /engagements/{id}/report.html?...` — pratinjau HTML

Kop surat (organisasi/judul/aksen) dari brand runtime (panel Admin). Grafik *house-style*
(distribusi severity + matriks risiko) di-*render* sebagai SVG inline; bukti lampiran disisipkan
sebagai data-URI.

## Pengembangan & pengujian

```bash
# di dalam kontainer api / worker
docker exec auditforge-api-1 python -m pytest -q      # unit + integrasi
docker exec auditforge-api-1 ruff check .
docker exec auditforge-api-1 mypy app
docker exec auditforge-web-1 npx tsc --noEmit         # typecheck frontend
```

Migrasi DB: `docker exec auditforge-api-1 alembic upgrade head`.

> **Catatan:** `docker compose build` + recreate menghapus perkakas dev transien (pytest/ruff/mypy)
> — instal ulang di kontainer setelah rebuild bila perlu. Perubahan kode **task Celery**
> membutuhkan restart `worker`.

## Struktur

```
auditforge/
├── backend/
│   ├── app/
│   │   ├── api/            # router FastAPI (engagements, admin, auth, …)
│   │   ├── models/         # SQLAlchemy (engagement, finding, revision, attachment, …)
│   │   ├── parsers/        # BaseParser + 5 turunan (nuclei/zap/nmap/burp/sarif)
│   │   ├── ai/             # providers (OpenAI-compat/Anthropic), llm.draft, masking, prompts
│   │   ├── reporting/      # report_data, docx/html/pdf writer, charts, branding
│   │   ├── eval/           # metrik dedup/enrichment + evaluasi per-penugasan
│   │   ├── normalize.py · enrichment.py · triage.py · review.py
│   │   └── workers/        # task Celery
│   ├── tests/
│   └── alembic/
├── frontend/               # Next.js (App Router) + design system Suryasoft
├── datasets/               # lab & data uji (tidak di-commit)
├── docker-compose.yml
└── .env.example
```

## Catatan keamanan (sebelum produksi/GitHub)

- Kredensial hanya dari `.env`/DB — **tidak** di-*hardcode*; `.env` **wajib** di `.gitignore`.
- Data sensitif **selalu** disamarkan sebelum ke LLM (lihat di atas).
- **Ganti kredensial bawaan**: postgres/minio (`auditforge`), `secret_key` JWT, akun seed
  (`admin12345`, akun dev `uji_*`).
- Artefak ter-*generate* (mis. `eval_data/report.json`) di-*gitignore* sebelum push.

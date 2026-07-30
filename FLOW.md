# Alur Aplikasi — AuditForge

Dokumen ini menjelaskan **alur kerja end-to-end** AuditForge: dari keluaran perkakas
pemindaian sampai laporan audit final. Prinsip yang mendasari seluruh alur:

> **AI hanya membuat draf. Auditor adalah pengambil keputusan akhir.**
> Semua tahap non-AI (parse, dedup, enrichment, triase, masking, perakitan laporan,
> metrik) bersifat **deterministik** dan teruji tanpa memanggil LLM.

AuditForge bekerja pada tahap **pascapengujian** — ia **tidak** memindai/mengeksploitasi
sistem apa pun.

---

## 1. Alur nilai utama (end-to-end)

```mermaid
flowchart TD
    A["Keluaran perkakas<br/>(Nuclei/ZAP/Nmap/Burp/SARIF)"] -->|unggah manual UI<br/>atau folder terpantau R3| B[Simpan mentah ke MinIO<br/>+ ScanUpload]
    B --> C[Parse → temuan terpadu<br/>deteksi perkakas via sniff]
    C --> D[Normalisasi keparahan]
    D --> E[Enrichment<br/>CWE · OWASP · CVSS · CVE]
    E --> F[Deduplikasi<br/>gabung lintas perkakas/berkas]
    F --> G[Triase deterministik<br/>prioritas P1–P4]
    G --> H{Naratif AI?}
    H -->|ya| I[Masking data sensitif] --> J[LLM susun draf<br/>deskripsi/dampak/remediasi] --> K[Unmask + tandai 'buatan AI']
    H -->|manual| L[Auditor tulis naratif]
    K --> M[Tinjau auditor]
    L --> M
    M -->|setujui| N[Temuan disetujui]
    M -->|tolak / positif palsu| X[Dikecualikan dari laporan]
    N --> O[Rakit laporan<br/>hanya temuan disetujui]
    O --> P["Laporan DOCX / PDF<br/>+ kop, grafik, bukti"]
```

**Ringkas per tahap:**

| # | Tahap | Sifat | Modul |
|---|---|---|---|
| 1 | Ingest berkas (unggah UI / folder terpantau) | Deterministik | `api/routes/engagements`, `ingest/watcher` |
| 2 | Parse → skema temuan terpadu | Deterministik | `parsers/` (5 perkakas + `sniff`) |
| 3 | Normalisasi keparahan | Deterministik | `normalize` |
| 4 | Enrichment (CWE/OWASP/CVSS/CVE) | Deterministik | `enrichment` |
| 5 | Deduplikasi (fingerprint, gabung) | Deterministik | `normalize` |
| 6 | Triase prioritas P1–P4 | Deterministik | `triage` |
| 7 | Draf naratif + ringkasan eksekutif | **AI** (+ masking) | `ai/narrative`, `ai/summary`, `ai/masking`, `ai/llm` |
| 8 | Tinjau · sunting · setujui | **Manusia** (auditor) | `review`, `models/finding` |
| 9 | Rakit & terbitkan laporan | Deterministik | `reporting/` (DOCX/PDF/HTML/charts) |
| 10 | Evaluasi terukur | Deterministik | `eval/engagement_eval` |

---

## 2. Peran & tanggung jawab

```mermaid
flowchart LR
    An[Analis] -->|buat penugasan, unggah,<br/>jalankan proses, susun draf| Sys[(AuditForge)]
    Au[Auditor] -->|tinjau, sunting, SETUJUI,<br/>terbitkan laporan| Sys
    Ad[Administrator] -->|kelola pengguna/peran,<br/>konfig LLM, jejak audit| Sys
    Sys -.->|metadata tersamar| LLM[Layanan AI / LLM<br/>agnostik-penyedia]
    LLM -.->|draf naratif| Sys
```

- **Analis** — menyiapkan penugasan, mengunggah keluaran perkakas, menjalankan pemrosesan,
  menyusun draf. **Tidak** boleh menyetujui.
- **Auditor** — meninjau, menyunting, **menyetujui/menolak/menandai positif palsu**,
  menerbitkan laporan. **Pemegang keputusan akhir.**
- **Administrator** — mengelola pengguna & peran, konfigurasi LLM (panel Admin), dan
  memantau jejak audit.

RBAC (fail-closed): status persetujuan (approved/rejected/false_positive) **hanya**
untuk auditor/admin; analis boleh menyunting & mengajukan.

---

## 3. Siklus status satu temuan

```mermaid
stateDiagram-v2
    [*] --> draft: hasil parse (+ draf AI)
    draft --> in_review: analis ajukan
    in_review --> approved: auditor setujui
    in_review --> rejected: auditor tolak
    in_review --> false_positive: auditor tandai FP
    approved --> in_review: buka kembali
    rejected --> in_review: buka kembali
    false_positive --> in_review: buka kembali
    approved --> [*]: masuk laporan
```

Setiap transisi & suntingan naratif tercatat di **riwayat versi** (`finding_revisions`) —
termasuk asal draf AI (model + versi prompt) vs suntingan auditor. Hanya temuan
**approved** yang masuk laporan.

---

## 4. Batas AI ↔ Manusia ↔ Deterministik

```mermaid
flowchart TD
    subgraph DET[Deterministik - dapat diuji tanpa LLM]
        P[Parse] --> N[Normalisasi] --> EN[Enrichment] --> DD[Dedup] --> TR[Triase]
    end
    subgraph AI[Lapisan AI - hanya draf]
        MK[Masking data sensitif] --> DR[Draf naratif/ringkasan] --> UM[Unmask + tandai AI]
    end
    subgraph HUM[Keputusan manusia]
        RV[Tinjau/sunting] --> AP[Setujui / tolak / FP]
    end
    TR --> MK
    UM --> RV
    AP --> RPT[Laporan - hanya yang disetujui]
```

**Masking** menjamin data sensitif (IP internal, hostname, kredensial, email) **tak pernah
sampai ke LLM** — disamarkan jadi `[IP-INTERNAL-1]`, `[HOST-1]`, `[SECRET-1]`, … lalu hasil
AI dipulihkan (unmask) di server. Untuk data sangat rahasia, Base URL LLM dapat diarahkan
ke model lokal/on-premise sehingga tidak ada data yang keluar.

---

## 5. Auto-ingest folder terpantau (R3)

Alternatif tanpa unggah manual — auditor cukup menaruh berkas di folder terpantau:

```mermaid
flowchart LR
    U["Taruh berkas di<br/>inbox/&lt;engagement_id&gt;/"] --> B[Celery beat<br/>scan tiap 30 dtk]
    B --> S["scan_inbox:<br/>berkas stabil?"]
    S -->|ya| I[Ingest: MinIO + ScanUpload<br/>auto-sniff perkakas]
    I --> PL[Pipeline sama:<br/>parse→dedup→enrich→triase]
    PL --> M{berhasil?}
    M -->|ya| PR["pindah ke processed/"]
    M -->|tidak| FA["pindah ke failed/"]
```

Berkas yang baru ditulis (< 5 dtk) dilewati agar tak mengurai berkas separuh. Temuan masuk
ke pipeline dedup/enrichment/triase yang **sama** dengan unggah manual.

---

## 6. Arsitektur runtime (layanan)

```mermaid
flowchart TB
    Web[web · Next.js :3000] -->|/api proxy| Api[api · FastAPI :8000]
    Api --> PG[(PostgreSQL)]
    Api --> MinIO[(MinIO<br/>berkas & bukti)]
    Api -->|antre tugas| Redis[(Redis)]
    Worker[worker · Celery] --> PG
    Worker --> MinIO
    Worker -.->|masking→| LLM[LLM eksternal<br/>OpenRouter/Anthropic/lokal]
    Beat[beat · Celery] -->|jadwal scan_inbox| Redis
    Redis --> Worker
```

Semua dikemas dalam satu `docker-compose.yml` dan berjalan **on-premise**. Frontend
mem-proxy `/api/*` ke backend (same-origin) sehingga hanya port 3000 yang perlu diekspos.

---

## 7. Ringkasan

AuditForge mengubah keluaran perkakas mentah menjadi laporan audit yang **deterministik,
tertelusuri, dan diputuskan manusia** — dengan AI mempercepat penyusunan naratif tanpa
pernah menggantikan penilaian auditor. Lihat `README.md` untuk cara menjalankan dan
`DPPL_AuditForge.tex` / `DUPL_AuditForge.tex` untuk perancangan & kebutuhan rinci.

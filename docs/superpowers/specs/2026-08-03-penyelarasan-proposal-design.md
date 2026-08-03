# Desain — Penyelarasan dengan Proposal: Metrik Waktu, Anggota Tim, dan Basis Pengetahuan

**Tanggal:** 3 Agustus 2026
**Status:** Disetujui untuk perencanaan
**Ruang lingkup:** AuditForge — tiga modul yang tercantum di proposal namun belum dibangun,
sekaligus mengisi dua halaman kosong (`/reports`, `/findings`)

---

## 1. Latar Belakang

Pemeriksaan langsung terhadap kode (3 Agustus 2026) menemukan enam butir yang dijanjikan
proposal namun belum ada implementasinya. Tiga di antaranya dipilih untuk dikerjakan:

| Janji proposal | Status kode | Dikerjakan |
|---|---|---|
| Indikator Keberhasilan: *"penurunan waktu penyusunan laporan minimal 50%"* | Tidak ada pengukuran waktu sama sekali | **Ya — Modul 1** |
| Modul Pengelolaan Penugasan: *"cakupan pengujian, periode pelaksanaan, dan anggota tim"* | Hanya nama, klien, deskripsi, status | **Ya — Modul 2** |
| Antarmuka Peninjauan: *"perbandingan versi penyuntingan"* | Riwayat revisi ada; perbandingannya belum | **Ya — Modul 2** |
| Modul Basis Pengetahuan Temuan | Tidak ada | **Ya — Modul 3** |
| Triase Berbantuan AI: *"menandai kandidat positif palsu disertai alasannya"* | Hanya triase deterministik | Ditunda |
| Keamanan Data: *"menonaktifkan fitur AI untuk penugasan tertentu"* | Tidak ada | Ditunda |

Halaman `/findings` dan `/reports` pada frontend saat ini adalah *stub* 15 baris berisi
`placeholder.soon`. Keduanya merupakan rumah alami bagi Modul 3 dan Modul 1.

### Mengapa Modul 1 mendesak

Indikator keberhasilan utama proposal adalah penurunan waktu penyusunan laporan sebesar
50%, dengan metode pengukuran "penugasan dengan jumlah temuan setara". Selama sistem tidak
pernah mencatat waktu, klaim itu tidak dapat dibuktikan pada saat penyerahan hasil Kerja
Praktik. Kebetulan, sebagian besar datanya **sudah terkumpul** sejak awal.

---

## 2. Urutan Pengerjaan

Urutan terkunci oleh ketergantungan, bukan preferensi:

```
Modul 1 (metrik + /reports)   ── mandiri, kerjakan lebih dulu
        │
Modul 2 (anggota tim + RBAC)  ── mengubah hak akses
        │
        ▼
Modul 3 (basis pengetahuan)   ── bergantung pada "siapa boleh lihat apa"
```

Modul 3 tidak boleh dibangun sebelum Modul 2 selesai: Basis Pengetahuan memuat naratif dari
penugasan klien lain, sehingga aturan aksesnya harus sudah tegak lebih dulu.

### Non-tujuan

- Tidak menyentuh masking LLM, pipeline deterministik (parse → dedup → enrichment → triase),
  maupun perakitan laporan yang sudah berjalan.
- Tidak menambah pemanggilan LLM baru. Ketiga modul ini seluruhnya deterministik.
- Tidak mengubah alur status temuan.

---

## 3. Modul 1 — Pengukuran Waktu dan Halaman `/reports`

### 3.1 Data yang sudah tersedia

Tidak diperlukan instrumentasi baru. Jejak waktu sudah terekam:

| Sumber | Isi |
|---|---|
| `FindingRevision.created_at` + `.action` | Stempel waktu tiap transisi: `ai_draft`, `edit`, `submit`, `approve`, `reject`, `false_positive`, `reopen` |
| `Finding.created_at` | Kapan temuan lahir dari proses parse |
| `Finding.reviewed_at` | Kapan temuan selesai ditinjau |
| `ScanUpload` | Kapan berkas masuk |

Konsekuensi menyenangkan: metrik dapat dihitung **mundur** untuk penugasan yang sudah
berjalan, sehingga angka pembanding tersedia tanpa menunggu penugasan baru.

### 3.2 Waktu kerja aktif, bukan waktu kalender

Selisih polos antara berkas pertama masuk dan temuan terakhir disetujui akan mencakup malam
hari, akhir pekan, dan penugasan yang terbengkalai — angka itu tidak jujur dan mudah
dipatahkan penguji.

Yang dihitung adalah **waktu kerja aktif**: urutkan seluruh stempel waktu revisi pada satu
penugasan, lalu jumlahkan selisih antar-peristiwa yang **lebih pendek dari ambang jeda**
(default 30 menit). Selisih yang lebih panjang dianggap istirahat dan tidak dihitung.

Teknik ini deterministik, dapat diuji tanpa basis data, dan dapat dipertahankan saat
ditanya bagaimana angkanya diperoleh.

### 3.3 Baseline pembanding

Sistem tidak memiliki cara mengetahui berapa lama laporan disusun secara manual. Karena itu
angka pembanding **dimasukkan manusia**, bukan ditebak:

Kolom baru pada `engagements`:

- `baseline_hours` — Float, nullable. Estimasi jam penyusunan manual untuk penugasan dengan
  bobot setara.
- `baseline_note` — Text, nullable. Dasar estimasinya (mis. "rata-rata 3 penugasan serupa
  2025").

Penghematan = `(baseline_hours − actual_hours) / baseline_hours`.

Bila `baseline_hours` kosong, sistem tetap menampilkan waktu aktual tetapi tidak mengklaim
penghematan apa pun. Lebih baik kosong daripada mengarang.

### 3.4 Modul murni `app/eval/timing.py`

Mengikuti pola `eval/engagement_eval.py` yang sudah ada (duck-typed, tanpa DB):

```python
def active_work_seconds(events: list[tuple[str, datetime]], *, gap_seconds: float = 1800) -> float
def timing_summary(events, *, baseline_hours: float | None = None) -> dict
```

Keluaran `timing_summary`: waktu aktif, waktu kalender, jumlah peristiwa, waktu per tahap
(ingest / draf AI / review), dan penghematan bila baseline tersedia.

### 3.5 Endpoint

| Endpoint | Peran | Fungsi |
|---|---|---|
| `GET /engagements/{id}/timing` | pengguna terautentikasi | Rincian waktu satu penugasan |
| `PUT /engagements/{id}/baseline` | auditor, admin | Isi `baseline_hours` + `baseline_note` |
| `GET /stats/timing` | pengguna terautentikasi | Agregat lintas penugasan untuk `/reports` |

**Catatan urutan:** Modul 1 dikerjakan sebelum keanggotaan tim ada, sehingga pada tahap ini
hak aksesnya masih seluas sekarang. Endpoint `timing` memanggil `_get_engagement()`, sehingga
pembatasan keanggotaan pada Modul 2 langsung berlaku padanya tanpa perubahan kode. `GET
/stats/timing` perlu disaring secara eksplisit ketika Modul 2 dikerjakan.

### 3.6 Halaman `/reports`

Menggantikan *stub* yang ada:

- **Daftar laporan lintas penugasan** — nama, klien, jumlah temuan disetujui, status, tombol
  unduh DOCX / PDF / pratinjau HTML (endpoint laporannya sudah ada, tinggal dikumpulkan)
- **Kartu metrik** — rata-rata penghematan waktu, jumlah laporan terbit, rata-rata waktu
  penyusunan
- **Grafik batang** — waktu aktual vs baseline per penugasan

Pada tahap Modul 1 halaman ini menampilkan seluruh penugasan; penyaringan berdasarkan
keanggotaan menyusul bersama Modul 2.

---

## 4. Modul 2 — Kelengkapan Penugasan, Anggota Tim, dan Diff

### 4.1 Kolom baru pada `engagements`

| Kolom | Tipe | Keterangan |
|---|---|---|
| `scope` | Text, nullable | Cakupan pengujian (aset, domain, batasan) |
| `period_start` | Date, nullable | Awal periode pelaksanaan |
| `period_end` | Date, nullable | Akhir periode pelaksanaan |
| `kb_shareable` | Boolean, default `True` | Boleh menjadi rujukan Basis Pengetahuan (Modul 3) |

`baseline_hours` dan `baseline_note` **sudah ditambahkan oleh migrasi Modul 1**; keduanya
tidak diulang di sini.

Ketiga kolom pertama juga dicetak pada kop laporan (`reporting/report_data.py`), sehingga
laporan akhir memuat periode dan cakupan sebagaimana dijanjikan proposal.

### 4.2 Tabel baru `engagement_members`

| Kolom | Tipe |
|---|---|
| `id` | int, PK |
| `engagement_id` | FK → `engagements.id` |
| `user_id` | FK → `users.id` |
| `role_in_team` | String(20) — `lead` \| `member` |
| `added_by` | FK → `users.id`, nullable |
| `created_at` | DateTime |

Batasan unik pada `(engagement_id, user_id)`.

### 4.3 Pembatasan akses

Aturannya sederhana dan *fail-closed*:

- **admin** — seluruh penugasan
- **selain admin** — hanya penugasan tempat ia terdaftar sebagai anggota

Titik penerapannya sudah tersedia: `_get_engagement()` pada `api/routes/engagements.py:48`
dipanggil oleh **18 dari 21 route**. Menambahkan pengecekan di sana menutup hampir seluruh
permukaan sekaligus, tanpa menyebar logika ke mana-mana.

Yang perlu ditangani terpisah:

- `GET /engagements` (daftar) — saring berdasarkan keanggotaan
- `POST /engagements` (buat) — pembuat otomatis menjadi anggota `lead`
- `GET /stats` — agregat hanya dari penugasan yang boleh diakses

Helper murni pada `app/access.py` agar dapat diuji tanpa basis data:

```python
def can_access_engagement(*, role: str, is_member: bool) -> bool
```

### 4.4 Migrasi — bahaya mengunci diri sendiri

**Ini bagian paling berisiko dari seluruh spec.**

Basis data saat ini memuat 17 penugasan dan **tak satu pun memiliki anggota tim**. Bila
pembatasan akses diaktifkan tanpa pengisian data, setiap pengguna non-admin akan kehilangan
akses ke seluruh penugasan seketika.

Karena itu migrasi Alembic yang sama **wajib** melakukan pengisian, bukan diserahkan ke
skrip terpisah yang bisa lupa dijalankan:

1. Untuk setiap penugasan dengan `created_by` non-null → sisipkan anggota `lead` dari
   `created_by`.
2. Untuk penugasan dengan `created_by` null → sisipkan seluruh pengguna ber-peran `admin`
   sebagai `lead`.
3. Verifikasi: tidak boleh ada penugasan tanpa anggota setelah migrasi selesai.

Langkah `downgrade` menghapus tabel beserta kolomnya; tidak ada data yang tak dapat
dipulihkan karena keanggotaan diturunkan dari `created_by` yang tetap ada.

### 4.5 Perbandingan versi (diff)

Modul murni `app/review_diff.py`:

```python
def diff_narrative(before: dict | None, after: dict | None) -> dict
```

Membandingkan **per bagian** naratif (`description`, `impact`, `recommendation`) — bukan
diff baris mentah. Yang ingin diketahui auditor adalah "bagian mana yang saya ubah dari draf
AI", bukan pergeseran karakter.

Keluaran per bagian: teks sebelum, teks sesudah, daftar kata yang ditambah/dihapus, dan
**rasio kata berubah**. Rasio ini sekaligus menjadi bahan bukti indikator proposal
*"maksimal 30% kalimat memerlukan penyuntingan berat"*.

| Endpoint | Fungsi |
|---|---|
| `GET /engagements/{id}/findings/{fid}/diff` | Bandingkan `ai_draft` dengan `final_narrative` |
| `GET /engagements/{id}/findings/{fid}/diff?from={rev}&to={rev}` | Bandingkan dua revisi mana pun |

Di UI: tab **Perbandingan** pada panel review, di samping Riwayat yang sudah ada.

---

## 5. Modul 3 — Basis Pengetahuan Temuan dan Halaman `/findings`

### 5.1 Keputusan kerahasiaan

Naratif disimpan **utuh** — tidak disamarkan — dengan tiga pengaman:

1. **Hanya auditor/admin** yang boleh membuka Basis Pengetahuan.
2. **Opt-out per penugasan** melalui `engagements.kb_shareable`. Sebagian NDA melarang data
   klien dipakai untuk keperluan lain sekalipun internal; saklar ini menghormati kontrak
   semacam itu. Pola ini mengikuti apa yang sudah ditetapkan proposal untuk fitur AI
   (*"dapat menonaktifkan untuk penugasan tertentu apabila kontrak klien mensyaratkan"*).
3. **Akses baca tercatat.** `AuditMiddleware` hanya mencatat mutasi, sehingga route Basis
   Pengetahuan menulis `AuditLog` secara eksplisit pada operasi baca. Bila klien bertanya
   siapa saja yang pernah melihat temuan mereka, jawabannya tersedia.

Setiap entri menampilkan penugasan dan klien asalnya secara mencolok di UI, agar auditor
selalu sadar sedang melihat data klien lain.

*Catatan: opsi menyamarkan naratif sebelum masuk KB sempat diajukan dan ditolak secara sadar
demi kegunaan. Ketiga pengaman di atas adalah kompensasinya.*

### 5.2 Tabel `knowledge_entries`

| Kolom | Tipe |
|---|---|
| `id` | int, PK |
| `source_finding_id` | FK → `findings.id` |
| `source_engagement_id` | FK → `engagements.id` |
| `title` | String(300) |
| `title_norm` | String(300), indexed — judul ternormalisasi untuk pencocokan |
| `cwe` | String(32), indexed, nullable |
| `owasp` | String(64), nullable |
| `severity` | String(10) |
| `narrative` | JSON — salinan `final_narrative` saat disetujui |
| `created_by` | FK → `users.id` |
| `created_at` | DateTime |
| `usage_count` | Integer, default 0 |

**Kapan entri dibuat:** saat temuan berpindah ke `approved`, bila
`engagement.kb_shareable` bernilai benar. Salinan diambil pada saat itu — perubahan
belakangan pada temuan asal tidak mengubah entri KB, sehingga rujukan bersifat stabil.

### 5.3 Pencocokan lintas penugasan

`fingerprint` yang ada **tidak dapat dipakai**: ia memuat host, port, dan path, sehingga
tidak akan pernah cocok antar klien — memang begitu rancangannya untuk dedup, tetapi salah
alat untuk Basis Pengetahuan.

Modul murni `app/knowledge/matching.py`:

```python
def normalize_title(title: str) -> str
def score_match(a_cwe, a_title_norm, b_cwe, b_title_norm) -> float
```

`normalize_title` membuang angka, alamat IP, nama host, dan nomor port; menurunkan huruf;
serta membuang kata umum. Pencocokan memberi bobot besar pada kesamaan CWE, lalu tumpang
tindih token judul. Sepenuhnya deterministik — tanpa LLM, tanpa *embedding*.

### 5.4 Endpoint

| Endpoint | Peran | Fungsi |
|---|---|---|
| `GET /knowledge?cwe=&q=` | auditor, admin | Telusuri Basis Pengetahuan (akses dicatat) |
| `GET /knowledge/suggest?finding_id=` | auditor, admin | Entri paling mirip untuk satu temuan |
| `POST /engagements/{id}/findings/{fid}/apply-knowledge/{entry_id}` | auditor, admin | Pakai naratif entri sebagai titik awal |

**Penerapan naratif KB tercatat sebagai suntingan auditor** (`FindingRevision.action =
"edit"`, `author_id` = pengguna), **bukan** `ai_draft`. Naskah itu berasal dari manusia yang
telah menyetujuinya di penugasan lain, bukan dari model. Menandainya sebagai draf AI akan
merusak keterlacakan yang menjadi inti prinsip proposal. `usage_count` dinaikkan.

### 5.5 Halaman `/findings`

Menggantikan *stub* yang ada, dua tab:

- **Temuan** — pencarian lintas penugasan yang boleh diakses; saring berdasarkan severity,
  CWE, OWASP, status, penugasan
- **Basis Pengetahuan** — telusuri naratif rujukan; tiap kartu menampilkan judul, CWE, badge
  penugasan/klien asal, dan `usage_count`

---

## 6. Pengujian

Mengikuti konvensi repo: 109 tes yang ada seluruhnya murni — tanpa DB, Redis, MinIO, LLM,
dan tanpa `conftest.py`. Seluruh keputusan ditempatkan pada modul murni, lapisan route
dibiarkan tipis.

| Berkas | Cakupan |
|---|---|
| `tests/test_timing.py` | Waktu kerja aktif, ambang jeda, daftar kosong, peristiwa tunggal, hitung penghematan, baseline kosong tidak mengklaim apa pun |
| `tests/test_access.py` | admin melihat semua, anggota boleh, non-anggota ditolak (*fail-closed*) |
| `tests/test_review_diff.py` | Diff per bagian, rasio kata, bagian kosong, naratif tak berubah |
| `tests/test_knowledge_matching.py` | Normalisasi judul (IP/host/port/angka hilang), bobot CWE, peringkat hasil |

**Verifikasi manual sebelum dinyatakan selesai:**

1. Jalankan migrasi pada salinan basis data yang ada → seluruh 17 penugasan memiliki anggota,
   tidak ada pengguna yang kehilangan akses.
2. Masuk sebagai non-admin bukan anggota → penugasan tersebut tidak tampak dan tidak dapat
   diakses langsung lewat URL.
3. Setujui satu temuan pada penugasan ber-`kb_shareable` → entri KB muncul.
4. Matikan `kb_shareable`, setujui temuan lain → entri KB **tidak** dibuat.
5. Buka Basis Pengetahuan → tercatat pada jejak audit.
6. `docker exec auditforge-api-1 python -m pytest -q` → seluruh tes lama tetap lulus.

---

## 7. Kriteria Selesai

- [ ] `/reports` dan `/findings` bukan lagi *stub*
- [ ] Waktu penyusunan terukur, dan penghematan terhadap baseline dapat ditunjukkan
- [ ] Penugasan memuat periode, cakupan, dan anggota tim; ketiganya tercetak di laporan
- [ ] Akses penugasan dibatasi keanggotaan; migrasi tidak mengunci siapa pun
- [ ] Naratif disetujui masuk Basis Pengetahuan dan dapat dipakai ulang, tercatat sebagai
      suntingan auditor
- [ ] `kb_shareable` dihormati; akses baca KB tercatat
- [ ] Diff AI-vs-auditor tersedia beserta rasio suntingannya
- [ ] Seluruh tes lama lulus; tes baru murni tanpa infrastruktur
- [ ] `FLOW.md` diperbarui: langkah anggota tim, KB, dan halaman baru

---

## 8. Ditunda ke Spec Terpisah

| Topik | Alasan |
|---|---|
| **Triase Berbantuan AI** — penanda kandidat positif palsu beserta alasannya | Modul proposal yang belum dibangun; tidak dipilih pada putaran ini |
| **Mematikan AI per-penugasan** | Disebut pada bagian Keamanan Data proposal; tidak dipilih pada putaran ini |
| **Claude Skills** | Tujuannya belum jelas — tooling pengembangan atau fitur produk. Perlu brainstorm sendiri |
| **Agent pengiriman jarak jauh** | Sudah memiliki spec sendiri: `2026-08-03-remote-scan-ingest-design.md` |

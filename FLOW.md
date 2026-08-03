# Alur Aplikasi — AuditForge

Dokumen ini menjelaskan **urutan alur kerja** AuditForge dari awal sampai laporan jadi,
dijelaskan langkah demi langkah.

Prinsip yang mendasari seluruh alur:

> **AI hanya membuat draf. Auditor adalah pengambil keputusan akhir.**

Semua tahap non-AI (parse, dedup, enrichment, triase, masking, perakitan laporan) bersifat
**deterministik** — hasilnya pasti dan bisa diuji tanpa memanggil AI. AuditForge bekerja pada
tahap **pascapengujian**; ia tidak memindai atau mengeksploitasi sistem apa pun.

---

## A. Alur utama: dari keluaran perkakas sampai laporan

Tiap langkah disertai **Buka:** — menu/tab yang perlu dibuka di aplikasi (mulai dari
`http://localhost:3000`, setelah login).

**0. Masuk.**
→ **Buka:** halaman **Login** → isi email + kata sandi → **Masuk**.
Untuk mencoba semua fitur, pakai akun **admin**.

**1. Buat penugasan.**
Analis membuat sebuah penugasan (proyek audit) sebagai wadah untuk satu klien.
→ **Buka:** sidebar **Penugasan** → isi form **"Buat Penugasan Baru"** (nama + klien) → **Buat**.
Penugasan baru muncul di **Daftar Penugasan**.

**2. Masukkan berkas keluaran perkakas.**
Analis mengunggah berkas hasil pemindaian (Nuclei, ZAP, Nmap, Burp, atau SARIF). Berkas mentah
disimpan ke MinIO dan dicatat sebagai `ScanUpload`.
→ **Buka:** di Daftar Penugasan klik **Buka** pada penugasan → tab **Berkas** → **"Unggah
Berkas Scan"** (pilih berkas, perkakas boleh dibiarkan auto) → **Unggah**.
*(Alternatif tanpa unggah manual: taruh berkas di folder terpantau — lihat bagian D.)*

**3. Uraikan berkas menjadi temuan.**
Sistem mengenali jenis perkakas otomatis (`sniff`), lalu parser mengubah isi berkas menjadi
**temuan** terpadu. Berjalan di latar (Celery). Berkas gagal ditandai `failed` tanpa
mengganggu yang lain.
→ **Buka:** tab **Berkas** — pantau kolom **Status** tiap berkas (`parsed` / `failed`).

**4. Normalisasi keparahan.**
Keparahan dari berbagai perkakas disatukan ke satu skala: critical / high / medium / low / info.
*(Otomatis di latar.)*
→ **Buka:** tab **Temuan** — lihat kolom **Keparahan** (warna + ikon + teks).

**5. Pengayaan (enrichment).**
Tiap temuan dipetakan ke **CWE** & **OWASP Top 10**, dihitung **skor CVSS v3.1**, dan ditautkan
ke **CVE** bila ada. *(Otomatis.)*
→ **Buka:** tab **Temuan** — lihat kolom **CWE / OWASP / CVSS / CVE**.

**6. Deduplikasi.**
Sistem membuat sidik jari tiap temuan, lalu **menggabungkan temuan yang sama** (lintas berkas
& perkakas); yang digabung mencatat asalnya dan menaikkan hitungan. *(Otomatis.)*
→ **Buka:** tab **Temuan** — lihat kolom **Sumber** (perkakas asal) & **Jumlah** (×N).

**7. Triase prioritas.**
Sistem menghitung prioritas **P1–P4** dari keparahan + CVSS + kemunculan + CVE.
→ **Buka:** tab **Temuan** — kolom **Prioritas** (P1–P4). Tombol **"Hitung Ulang Triase"** untuk
menghitung ulang.

**8. Susun draf naratif dengan AI (opsional, tapi umum).**
Sistem menyamarkan data sensitif → LLM menyusun **draf** (deskripsi/dampak/reproduksi/remediasi)
→ data dipulihkan & ditandai **"buatan AI"** + model/versi prompt.
→ **Buka:** tab **Temuan** → tombol **"Buat Naratif AI"** (batch), lalu klik **✨ Lihat** pada
kolom Naratif tiap temuan. Untuk **ringkasan eksekutif**: tab **Ringkasan** → **"Buat Ringkasan
Eksekutif"**.

**9. Tinjau & setujui (auditor).**
Auditor membaca naratif (bagian AI ditandai), **menyunting bila perlu**, mengonfirmasi/menolak
positif palsu, lalu menetapkan status. Bukti bisa dilampirkan.
→ **Buka:** tab **Temuan** → klik **badge status** (atau kartu di mode Kanban) sebuah temuan →
panel review: **Sunting** naratif, **Setujui / Tolak / Tandai False Positive**, **Lampiran
Bukti**, **Riwayat**.

**10. Terbitkan laporan.**
Sistem merakit laporan **hanya dari temuan disetujui** (naratif final auditor menang atas draf
AI) + kop surat, grafik, dan bukti.
→ **Buka:** tab **Ringkasan** → **Pratinjau** (HTML), **Unduh DOCX**, atau **Unduh PDF**.
Branding kop diatur di **Administrasi** → **Branding Laporan**.

**11. Evaluasi.**
Metrik terukur nilai sistem: efisiensi dedup, cakupan draf AI, kemajuan review, rasio suntingan.
→ **Buka:** tab **Ringkasan** — **kartu metrik** di bagian atas.

> **Fitur admin** (di luar alur utama) → **Buka:** sidebar **Administrasi** → **Konfigurasi LLM**
> (Base URL/key/model), **Branding Laporan**, **Pratinjau Masking**, **Jejak Audit**.

---

## B. Siapa melakukan apa (peran)

- **Analis** — membuat penugasan, mengunggah berkas, menjalankan pemrosesan, menyusun draf.
  **Tidak** boleh menyetujui temuan.
- **Auditor** — meninjau, menyunting, dan **menyetujui/menolak/menandai positif palsu**;
  menerbitkan laporan. **Pemegang keputusan akhir.**
- **Administrator** — mengelola pengguna & peran, mengatur konfigurasi LLM (panel Admin), dan
  memantau jejak audit.

Pembatasan akses bersifat *fail-closed*: status persetujuan hanya bisa diubah auditor/admin;
analis hanya boleh menyunting dan mengajukan.

---

## C. Urutan status sebuah temuan

Sebuah temuan bergerak melalui status berikut:

1. **draft** — baru hasil parse (mungkin sudah punya draf AI).
2. **in_review** — analis mengajukannya untuk ditinjau.
3. Dari in_review, auditor memilih salah satu:
   - **approved** — disetujui → **masuk laporan**;
   - **rejected** — ditolak → dikecualikan dari laporan;
   - **false_positive** — positif palsu → dikecualikan dari laporan.
4. Status apa pun bisa **dibuka kembali** (reopen) → kembali ke in_review bila perlu revisi.

Hanya temuan **approved** yang muncul di laporan akhir. Semua transisi tercatat di riwayat
versi (`finding_revisions`), termasuk membedakan asal draf AI vs suntingan auditor.

---

## D. Alur auto-ingest folder terpantau (R3)

Alternatif tanpa unggah manual lewat UI:

1. Auditor/skrip menaruh berkas di `datasets/watch/inbox/<engagement_id>/`.
2. Penjadwal (Celery **beat**) memindai folder itu **tiap ~30 detik**.
3. Berkas yang sudah stabil (bukan yang baru saja ditulis) **diserap otomatis**: disimpan ke
   MinIO, dibuat `ScanUpload`, perkakas dideteksi otomatis.
4. Masuk **pipeline yang sama** dengan unggah manual (langkah A3–A7).
5. Berkas lalu dipindah ke `processed/<id>/` (berhasil) atau `failed/<id>/` (gagal).

---

## E. Batas AI ↔ Manusia ↔ Deterministik

- **Deterministik** (parse → normalisasi → enrichment → dedup → triase) — logika pasti,
  teruji, tanpa AI.
- **AI** (draf naratif & ringkasan) — hanya membuat **usulan**; selalu didahului **masking**
  sehingga data sensitif **tak pernah sampai ke LLM**. Untuk data sangat rahasia, Base URL
  LLM bisa diarahkan ke model lokal/on-premise agar tidak ada data yang keluar.
- **Manusia** (auditor) — meninjau, menyunting, dan **memutuskan**. Laporan hanya berisi yang
  disetujui manusia.

---

## F. Layanan yang berjalan (runtime)

Semua dikemas dalam satu `docker-compose.yml` dan berjalan **on-premise**:

- **web** (Next.js, :3000) — antarmuka; mem-proxy `/api/*` ke backend (same-origin).
- **api** (FastAPI, :8000) — REST API.
- **worker** (Celery) — proses latar: parsing, enrichment, naratif AI, auto-ingest.
- **beat** (Celery) — penjadwal auto-ingest (R3).
- **postgres** — basis data.
- **redis** — antrean tugas untuk worker.
- **minio** — penyimpanan berkas mentah & bukti.
- **LLM eksternal** (OpenRouter/Anthropic/lokal) — dipanggil worker, hanya menerima data yang
  sudah tersamar.

---

Untuk cara menjalankan aplikasi lihat `README.md`; untuk perancangan & kebutuhan rinci lihat
`DPPL_AuditForge.tex` dan `DUPL_AuditForge.tex`.

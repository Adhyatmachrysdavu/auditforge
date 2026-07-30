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

Urutannya seperti ini:

**1. Buat penugasan.**
Analis membuat sebuah penugasan (proyek audit) sebagai wadah untuk satu klien — berisi
seluruh berkas, temuan, dan laporan.

**2. Masukkan berkas keluaran perkakas.**
Analis mengunggah berkas hasil pemindaian (Nuclei, ZAP, Nmap, Burp, atau SARIF) lewat UI.
Berkas mentah disimpan ke MinIO, dan dibuat catatan `ScanUpload`. *(Alternatif tanpa unggah
manual: taruh berkas di folder terpantau — lihat bagian D.)*

**3. Uraikan berkas menjadi temuan.**
Sistem mengenali jenis perkakas secara otomatis (`sniff`), lalu parser mengubah isi berkas
menjadi **temuan** dalam satu skema terpadu. Proses ini berjalan di latar (Celery) sehingga
UI tetap responsif. Berkas yang gagal diurai ditandai `failed` tanpa mengganggu berkas lain.

**4. Normalisasi keparahan.**
Tingkat keparahan dari berbagai perkakas (yang formatnya beda-beda) disatukan ke satu skala
baku: critical / high / medium / low / info.

**5. Pengayaan (enrichment).**
Tiap temuan dipetakan ke **CWE** dan **OWASP Top 10**, dihitung **skor CVSS v3.1**, dan
ditautkan ke **CVE** bila ada. Bila CVE dikenal, CWE/skor yang kurang bisa di-backfill.

**6. Deduplikasi.**
Sistem membuat sidik jari (fingerprint) tiap temuan, lalu **menggabungkan temuan yang sama**
— baik dari berkas berbeda maupun perkakas berbeda. Yang digabung mencatat semua asalnya dan
menaikkan hitungan kemunculan; keparahan/CVSS tertinggi yang menang.

**7. Triase prioritas.**
Sistem menghitung prioritas **P1–P4** secara deterministik dari keparahan + skor CVSS +
jumlah kemunculan + ada/tidaknya CVE. Ini membantu auditor tahu mana yang harus ditangani
duluan.

**8. Susun draf naratif dengan AI (opsional, tapi umum).**
Untuk temuan terpilih, sistem:
   - **menyamarkan data sensitif** dulu (IP internal, hostname, kredensial, email) →
     jadi `[IP-INTERNAL-1]`, `[SECRET-1]`, dst;
   - mengirim permintaan terstruktur ke LLM → LLM mengembalikan **draf**
     deskripsi, dampak, langkah reproduksi, dan remediasi;
   - **memulihkan** data yang disamarkan pada hasilnya, menyimpannya sebagai draf, dan
     **menandainya "buatan AI"** beserta model + versi prompt.

   Sistem juga bisa membuat **ringkasan eksekutif** per penugasan dengan cara serupa. Bila AI
   tidak dipakai, auditor menulis naratif manual.

**9. Tinjau & setujui (auditor).**
Auditor membuka tiap temuan, membaca naratif (bagian buatan AI ditandai jelas), **menyunting
bila perlu**, mengonfirmasi/menolak kandidat positif palsu, lalu menetapkan status:
**disetujui**, **ditolak**, atau **positif palsu**. Setiap suntingan & perubahan status
tercatat di riwayat versi. Bukti (tangkapan layar) bisa dilampirkan di sini.

**10. Terbitkan laporan.**
Sistem merakit laporan **hanya dari temuan yang disetujui** (naratif final auditor menang
atas draf AI), lengkap dengan kop surat, ringkasan eksekutif, grafik (distribusi keparahan +
matriks risiko), dan bukti. Laporan diunduh sebagai **DOCX** atau **PDF**, atau dipratinjau
sebagai HTML.

**11. Evaluasi.**
Tab Ringkasan menampilkan metrik terukur: efisiensi dedup, cakupan draf AI, kemajuan review,
dan rasio suntingan auditor — untuk mengukur nilai yang diberikan sistem.

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

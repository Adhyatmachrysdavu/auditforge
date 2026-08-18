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
Penugasan baru muncul di **Daftar Penugasan**. Pembuatnya otomatis menjadi anggota tim
penugasan itu.

**1b. Lengkapi tim, periode, dan cakupan.**
Tentukan siapa saja yang boleh membuka penugasan ini, kapan pengujian dilaksanakan, dan apa
saja yang diuji. **Hanya anggota tim yang dapat membuka sebuah penugasan** — administrator
selalu bisa. Periode dan cakupan ikut tercetak di kop laporan akhir.
→ **Buka:** tab **Tim** → pilih pengguna pada **"Pilih pengguna"** → **Tambah Anggota**;
lalu isi **Mulai**, **Selesai**, dan **Cakupan pengujian** → **Simpan Kelengkapan**.
Menambah/mengeluarkan anggota hanya boleh oleh **auditor/admin**; anggota terakhir tidak
dapat dikeluarkan. Saklar **"Boleh jadi rujukan Basis Pengetahuan"** dimatikan bila kontrak
klien melarang datanya dipakai untuk penugasan lain.

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
Berkas `failed` tidak perlu diunggah ulang: tombol **Urai Ulang** pada barisnya memakai berkas
mentah yang masih tersimpan di MinIO. Berguna setelah penyebab kegagalan diperbaiki (misalnya
parser baru ditambahkan). Tombol hanya muncul bila berkas mentahnya masih ada, dan ditolak bila
isi berkas itu ternyata sudah berhasil diserap lewat unggahan lain — mengurainya dua kali akan
menggelembungkan hitungan kemunculan yang ikut menentukan prioritas triase.
Berkas yang isinya **sama persis** dengan berkas yang sudah berhasil diurai di penugasan ini
ditolak saat diunggah (sidik jari SHA-256 isi berkas). Yang dulu **gagal** tetap boleh dikirim
ulang.
*(Melihat berkas gagal dari seluruh penugasan sekaligus: lihat bagian D.)*

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
Bukti**, **Riwayat**, **Perbandingan**.

Tombol **Perbandingan** menampilkan seberapa banyak naratif diubah auditor dari draf AI:
porsi kata yang berubah per bagian (deskripsi/dampak/rekomendasi) beserta kata yang
ditambahkan dan dihapus. Angka inilah bukti terukur untuk indikator *"maksimal 30% kalimat
memerlukan penyuntingan berat"*.

**10. Terbitkan laporan.**
Sistem merakit laporan **hanya dari temuan disetujui** (naratif final auditor menang atas draf
AI) + kop surat, grafik, dan bukti.
→ **Buka:** tab **Ringkasan** → **Pratinjau** (HTML), **Unduh DOCX**, atau **Unduh PDF**.
Alternatif lintas penugasan → **Buka:** sidebar **Laporan** — satu baris per penugasan dengan
tombol **Pratinjau / DOCX / PDF** yang sama. Bahasa laporan mengikuti pilihan **ID/EN** di
antarmuka. Branding kop diatur di **Administrasi** → **Branding Laporan**.

**11. Isi baseline waktu penyusunan manual (auditor/admin).**
Perkiraan jam yang dibutuhkan bila laporan ini disusun manual — menjadi pembanding klaim
penghematan waktu. Isi juga catatan sumber angkanya agar dapat dipertahankan saat ditanya.
→ **Buka:** tab **Ringkasan** → kartu **"Baseline Waktu Penyusunan Manual"** → isi **Baseline
(jam)** + **Catatan sumber angka** → **Simpan Baseline**. Di bawahnya langsung tampil **waktu
aktif tercatat**, jumlah **jejak revisi**, serta **hemat** dan **penghematan (%)**.
Analis tidak boleh mengisi baseline (ditolak 403).

**12. Evaluasi.**
Metrik terukur nilai sistem: efisiensi dedup, cakupan draf AI, kemajuan review, rasio suntingan.
→ **Buka:** tab **Ringkasan** — **kartu metrik** di bagian atas.

**13. Baca agregat waktu penyusunan.**
Rata-rata penghematan waktu lintas penugasan — bukti untuk indikator "penurunan waktu penyusunan
laporan minimal 50%". Waktu dihitung dari jejak revisi temuan; jeda antar-peristiwa dibatasi 30
menit agar malam dan akhir pekan tidak ikut terhitung.
→ **Buka:** sidebar **Laporan** — kartu **Rata-rata penghematan waktu**, **Penugasan terukur**,
dan tabel per penugasan (**Waktu aktif**, **Baseline**, **Hemat**).
Penugasan berlabel **"belum terukur"** memiliki kurang dari dua jejak revisi: sistem sengaja
menahan angka penghematannya, bukan mengklaim 100%.

> **Fitur admin** (di luar alur utama) → **Buka:** sidebar **Administrasi** → **Konfigurasi LLM**
> (Base URL/key/model), **Branding Laporan**, **Pratinjau Masking**, **Jejak Audit**.

---

## B. Siapa melakukan apa (peran)

- **Analis** — membuat penugasan, mengunggah berkas, menjalankan pemrosesan, menyusun draf.
  **Tidak** boleh menyetujui temuan.
- **Auditor** — meninjau, menyunting, dan **menyetujui/menolak/menandai positif palsu**;
  menerbitkan laporan. **Pemegang keputusan akhir.**
- **Administrator** — mengelola pengguna & peran, mengatur konfigurasi LLM (panel Admin), dan
  memantau jejak audit. **Melihat seluruh penugasan** tanpa perlu terdaftar sebagai anggota.

**Keanggotaan tim menentukan siapa melihat apa.** Selain administrator, seorang pengguna
hanya melihat penugasan tempat ia terdaftar — termasuk di daftar penugasan, dasbor, halaman
**Laporan**, dan **Ingest**. Membuka penugasan orang lain lewat URL langsung dibalas
*"tak ditemukan"*, bukan *"akses ditolak"*: memberi tahu bahwa penugasan bernomor itu ada
sudah membocorkan informasi, karena nama klien kerap dapat ditebak dari nomor berurutan.

Menambah atau mengeluarkan anggota hanya boleh **auditor/admin** — memberi seseorang akses
ke data kerentanan klien adalah keputusan kepercayaan, bukan pekerjaan analisis harian.

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

## C2. Memverifikasi perbaikan klien (retest)

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

---

## D. Alur auto-ingest folder terpantau (R3)

Alternatif tanpa unggah manual lewat UI:

1. Auditor/skrip menaruh berkas di `datasets/watch/inbox/<engagement_id>/`.
2. Penjadwal (Celery **beat**) memindai folder itu **tiap ~30 detik**.
3. Berkas yang sudah stabil (bukan yang baru saja ditulis) **diserap otomatis**: disimpan ke
   MinIO, dibuat `ScanUpload`, perkakas dideteksi otomatis.
4. Masuk **pipeline yang sama** dengan unggah manual (langkah A3–A7).
5. Berkas lalu dipindah ke `processed/<id>/` (berhasil) atau `failed/<id>/` (gagal).
6. Berkas yang isinya sama persis dengan berkas yang **sudah berhasil** diurai di penugasan itu
   **dilewati tanpa diproses**: tidak ada `ScanUpload` baru, berkasnya tetap dipindah ke
   `processed/<id>/` (ini bukan kegagalan), dan alasannya dicatat di log worker. Penghitung task
   memisahkannya sebagai `duplicates`, terpisah dari `processed`.

### Pusat Ingest — memantau ingest lintas penugasan

Semua aktivitas di atas — unggah manual maupun serapan otomatis — terkumpul di satu halaman,
sehingga berkas gagal tak perlu dicari dengan membuka tab **Berkas** penugasan satu per satu.
→ **Buka:** sidebar **Ingest**. Berisi ringkasan (**masuk 24 jam terakhir**, **gagal belum
ditangani**, **total berkas**), penyaring **Semua / Gagal saja**, dan satu baris per berkas
dengan **waktu**, **penugasan** (tertaut), **berkas**, **perkakas**, **asal** (*manual* /
*otomatis*), serta **status** — arahkan kursor ke badge status untuk membaca pesan galatnya.
Baris yang memenuhi syarat punya tombol **Urai Ulang** yang sama dengan di tab Berkas.

---

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

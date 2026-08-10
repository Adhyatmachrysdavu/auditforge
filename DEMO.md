# Mencoba AuditForge

Panduan untuk yang baru pertama membuka repositori ini dan ingin melihat
sistemnya bekerja. Sekitar 20 menit, sebagian besar menunggu build pertama.

---

## Apa ini

AuditForge membantu auditor keamanan menyusun **laporan audit** dari keluaran
perkakas pemindai (Nuclei, ZAP, Nmap, Burp, SARIF). Berkas hasil pemindaian
masuk, lalu sistem menormalkan, menggabungkan duplikat, memperkaya dengan
CWE/OWASP/CVSS, dan memberi prioritas P1–P4 — semuanya **deterministik**.
Setelah itu AI menuliskan **draf** narasi tiap temuan dan ringkasan eksekutif;
auditor meninjau, menyunting, dan menyetujui; barulah laporan DOCX/PDF terbit.

Ia bekerja pada data **pasca-pengujian**. AuditForge tidak pernah memindai
maupun mengeksploitasi apa pun.

Dua prinsip yang membentuk hampir seluruh keputusan rancangannya:

1. **AI hanya membuat draf; auditor pengambil keputusan akhir.** Laporan hanya
   memuat temuan yang disetujui manusia, dan naskah auditor selalu menang atas
   draf AI. Seluruh langkah non-AI teruji tanpa memanggil LLM sama sekali.
2. **Data sensitif disamarkan sebelum meninggalkan mesin.** Setiap panggilan
   LLM melewati satu pintu yang menyamarkan IP internal, nama host, kredensial,
   dan surel menjadi `[IP-INTERNAL-1]`, `[HOST-1]`, `[SECRET-1]`, lalu memulihkan
   jawabannya di sisi server. Peta penyamarannya tidak pernah keluar.

---

## Menjalankan

**Yang dibutuhkan:** Docker Desktop (atau Docker Engine + Compose v2), RAM luang
sekitar 4 GB, dan ruang disk ~5 GB. Build pertama memakan **10–15 menit** karena
seluruh image dibangun dari nol; setelahnya penyalaan hanya beberapa detik.

```bash
git clone https://github.com/davuchrys/auditforge.git
cd auditforge

cp .env.example .env
docker compose up -d --build

./scripts/demo.sh          # muat data contoh
```

Lalu buka **<http://localhost:3000>**. Tersedia tiga akun, satu untuk tiap peran:

| Surel | Kata sandi | Peran | Boleh apa |
|---|---|---|---|
| `admin@auditforge.local` | `admin12345` | admin | Segalanya, termasuk panel Administrasi, jejak audit, dan menghapus penugasan |
| `auditor@auditforge.local` | `auditor12345` | auditor | Menyetujui, menolak, menandai positif-palsu, membuka Basis Pengetahuan, mengelola anggota tim |
| `analis@auditforge.local` | `analis12345` | analis | Menyunting naratif dan mengajukan tinjauan, tetapi **tidak** boleh menyetujui |

Mulailah sebagai **admin**. Dua akun lain berguna untuk melihat pembatasan
peran bekerja, seperti pada langkah 4 di bawah.

> Login memakai **alamat surel**, bukan nama pengguna.

**Tanpa `./scripts/demo.sh`, aplikasinya kosong** — nol penugasan, nol temuan.
Skrip itu memuat tiga penugasan contoh lengkap dengan narasi AI yang sudah jadi,
sehingga seluruh sistem dapat ditelusuri **tanpa kunci LLM sama sekali**. Datanya
sepenuhnya sintetis (`example.com`, "PT Contoh"); tidak ada apa pun milik klien
sungguhan.

Kalau ada yang tak beres, jalankan `./scripts/smoke.sh` — ia memeriksa 31
endpoint dan menunjukkan persis bagian mana yang gagal.

---

## Tur berpandu

Data demo memuat tiga penugasan:

| # | Penugasan | Klien | Status | Temuan |
|---|---|---|---|---|
| 17 | Audit Infrastruktur Internal — Fase 1 | PT Suryasoft Konsultama | berjalan | 11 (4 disetujui) |
| 18 | Audit Aplikasi Web Internal 2026 | PT Contoh | selesai | 5 (semua disetujui) |
| 19 | Audit Portal Pelanggan 2026 | PT Contoh | selesai | 5 (semua disetujui) |

### 1. Hasil olahan yang deterministik

Buka **Penugasan**, pilih **Audit Aplikasi Web Internal 2026**, lalu tab **Temuan**.

Lima temuan, terurut prioritas. Perhatikan bahwa setiap baris sudah membawa
**CWE**, **kategori OWASP**, dan **prioritas** — tidak satu pun diisi manusia,
dan tidak satu pun berasal dari AI:

```
critical  P1  CWE-502  A08:2021   Apache Log4j2 Remote Code Execution (Log4Shell)
high      P2  CWE-79   A03:2021   Cross Site Scripting (Reflected)
low       P4  CWE-352  A01:2021   Absence of Anti-CSRF Tokens
low       P4  CWE-311  A02:2021   Mixed Content
info      P4  CWE-200  A01:2021   TLS Version Detection
```

Prioritas dihitung dari keparahan, skor CVSS, jumlah kemunculan, dan ada-tidaknya
CVE. Karena rumusnya pasti, hasilnya dapat dijelaskan kepada klien — dan diuji
tanpa memanggil AI.

### 2. Batas antara AI dan manusia

Masih di tab Temuan, klik **Lihat** pada baris Log4Shell.

Panel yang terbuka menampilkan naratifnya beserta label asalnya: **"Naratif final
(auditor)"** bila auditor menyuntingnya, atau **"Draf AI"** beserta nama model
bila diterima apa adanya.

Tekan **Perbandingan**. Sistem menghitung berapa persen kata yang benar-benar
diubah auditor terhadap draf AI, per bagian, lengkap dengan kata yang ditambah
dan dihapus. Pada temuan ini hasilnya **3%** — auditor menerima hampir seluruh
draf dan hanya memperhalus beberapa kata.

Angka itu bukan hiasan: proposal Kerja Praktik ini menjanjikan *"maksimal 30%
kalimat memerlukan penyuntingan berat"*, dan inilah pengukurannya.

Tekan **Riwayat** untuk melihat jejak lengkapnya. Revisi buatan AI tercatat tanpa
penulis; revisi manusia membawa nama penyuntingnya. Pemisahan itu yang membuat
klaim "AI hanya membantu" dapat diperiksa, bukan sekadar dinyatakan.

### 3. Laporan

Buka **tab Ringkasan**.

Di sana ada ringkasan eksekutif hasil draf AI (gambaran umum, risiko utama,
rekomendasi) beserta **postur keamanan**, lalu metrik evaluasi, dan tombol unduh
laporan.

Tekan **Pratinjau HTML**. Laporan memuat kop dengan nama klien, periode, dan
cakupan pengujian; distribusi keparahan; matriks risiko; ringkasan eksekutif;
lalu tiap temuan terurut prioritas. Temuan yang disunting auditor ditandai
`(disunting auditor)`.

Unduhan **DOCX** dan **PDF** menghasilkan isi yang sama.

Yang penting: laporan **hanya memuat temuan berstatus Disetujui**. Buka
penugasan #17 yang baru 4 dari 11 temuannya disetujui — laporannya hanya berisi
empat itu.

### 4. Pembatasan akses

Keluar, lalu masuk sebagai `analis@auditforge.local` / `analis12345`.

Analis ini bukan anggota tim penugasan mana pun, jadi dasbornya menunjukkan nol
di semua angka dan daftar penugasannya kosong. Mencoba membuka
`/engagements/18` langsung lewat URL dibalas **"tidak ditemukan"** — bukan
"tidak berhak". Itu disengaja: nomor penugasan berurutan, dan "tidak berhak"
akan membocorkan bahwa klien ke-18 memang ada.

Menu **Administrasi** juga tidak muncul untuknya.

Kembali masuk sebagai admin untuk melanjutkan.

### 5. Basis Pengetahuan

Buka **Temuan** di bilah sisi (bukan tab di dalam penugasan).

Halaman ini punya dua tab. **Temuan** mencari di seluruh penugasan yang menjadi
tanggung jawab pengguna. **Basis Pengetahuan** memuat 13 naratif dari temuan yang
telah disetujui, agar kerentanan yang sama tidak perlu ditulis ulang dari nol di
penugasan berikutnya.

Tiap kartu menampilkan penugasan dan klien asalnya secara mencolok — supaya
auditor selalu sadar sedang melihat data klien lain — serta penanda apakah
naskahnya **ditulis auditor** atau **draf AI yang disetujui**.

Tiga pengaman menyertainya:

- hanya **auditor dan admin** yang dapat membukanya;
- setiap penugasan dapat **menolak berbagi** lewat tab **Tim**, dengan menghapus
  centang *Boleh jadi rujukan Basis Pengetahuan*. Penolakan itu **berlaku surut**:
  naratif yang sudah terlanjur masuk pun langsung berhenti tampil;
- **setiap pembukaan halaman ini tercatat** pada jejak audit
  (menu **Administrasi**, bagian **Jejak Audit**).

Untuk melihat kegunaannya, buka penugasan #19, pilih temuan Log4Shell, tekan
**Lihat**, lalu **Saran Rujukan**. Sistem menemukan naratif Log4Shell dari penugasan #17 dan #18
dengan skor kemiripan 100%, dan menawarkan **Pakai Naratif Ini**. Penerapannya
dicatat sebagai **suntingan auditor**, bukan draf AI — karena naskahnya memang
berasal dari manusia yang telah menyetujuinya di penugasan lain.

### 6. Metrik waktu

Buka **Laporan** di bilah sisi.

Halaman ini mengukur waktu kerja **manusia** pada tiap penugasan dan
membandingkannya dengan estimasi penyusunan manual yang dimasukkan auditor:

```
#17  1.51 jam  vs baseline 6 jam   hemat 74.9%
#18  0.86 jam  vs baseline 6 jam   hemat 85.7%
```

Yang dihitung adalah waktu kerja aktif, bukan waktu kalender: selisih antar
peristiwa dijumlahkan dengan setiap jeda dibatasi 30 menit, sehingga malam hari
dan akhir pekan tidak ikut terhitung. Draf yang dikerjakan worker AI **tidak**
dimasukkan — hanya jejak yang berpenulis manusia. Penugasan tanpa estimasi
pembanding tidak mengklaim penghematan apa pun.

---

## Auto-ingest: berkas masuk tanpa diunggah

Ini bagian yang paling mudah dilewatkan, padahal ia menghilangkan langkah paling
membosankan dalam alur kerja audit.

Selain mengunggah lewat antarmuka, AuditForge **memantau sebuah folder**. Berkas
hasil pemindaian yang dijatuhkan ke sana akan terserap sendiri: perkakasnya
dikenali otomatis, diurai, diperkaya, dan ditriase — lewat jalur yang **persis
sama** dengan unggahan manual.

### Mencobanya

Dari direktori repositori, jatuhkan satu berkas contoh ke folder terpantau
milik penugasan #19:

```bash
mkdir -p datasets/watch/inbox/19
cp datasets/fixtures/nmap-sample.xml datasets/watch/inbox/19/
```

Tunggu sekitar **30–40 detik** (penjadwal memindai tiap 30 detik), lalu:

- buka **Ingest** di bilah sisi. Berkasnya muncul dengan asal **otomatis**,
  perkakas terdeteksi `nmap`, status `parsed`;
- buka penugasan #19, tab **Temuan**. Empat temuan baru muncul, masing-masing
  sudah bertriase. Perhatikan bahwa hanya `Nmap script: ssl-heartbleed` yang
  memperoleh CWE (CWE-125, prioritas P1); tiga sisanya berupa daftar port
  terbuka dan **dibiarkan tanpa CWE**, karena memang tak ada padanannya. Sistem
  mengosongkan yang tak dapat dipetakan alih-alih mengarang;
- periksa foldernya. Berkas tadi sudah **pindah sendiri** dari `inbox/` ke
  `processed/19/`.

```bash
ls datasets/watch/inbox/19/      # kosong
ls datasets/watch/processed/19/  # nmap-sample.xml
```

### Yang perlu diketahui tentangnya

- **Perkakas tidak perlu disebutkan.** Sistem mengendus isi berkas untuk
  mengenali Nuclei, ZAP, Nmap, Burp, atau SARIF.
- **Berkas yang masih ditulis diabaikan.** Berkas baru diproses setelah ukuran
  dan waktu ubahnya diam selama 5 detik, sehingga pemindaian yang belum selesai
  tidak terbaca separuh.
- **Isi yang sama persis tidak diproses dua kali.** Berkas identik dengan yang
  sudah pernah berhasil diurai di penugasan itu dilewati, dan dihitung terpisah
  sebagai duplikat — bukan sebagai kegagalan.
- **Berkas rusak tidak hilang diam-diam.** Ia pindah ke `failed/<id>/` dan
  muncul di halaman **Ingest** dengan pesan galatnya; setelah diperbaiki, ada
  tombol **Urai Ulang**.
- Foldernya diatur lewat `WATCH_HOST_DIR`; bawaannya `./datasets/watch`.

Halaman **Ingest** mengumpulkan seluruh aktivitas ini lintas penugasan — unggahan
manual maupun serapan otomatis — sehingga berkas gagal tak perlu dicari dengan
membuka tab Berkas tiap penugasan satu per satu.

---

## Yang sudah ada

| Bagian | Isi |
|---|---|
| **Ingest** | Parser Nuclei, ZAP, Nmap, Burp, SARIF; deteksi perkakas otomatis; unggah manual + folder terpantau; tolak duplikat; urai ulang berkas gagal |
| **Pengolahan deterministik** | Normalisasi keparahan, dedup lintas berkas & lintas perkakas dalam satu penugasan, pemetaan CWE/OWASP, hitung CVSS v3.1, tautan CVE, triase P1–P4 |
| **AI (draf saja)** | Naratif per temuan + ringkasan eksekutif; provider bebas (OpenRouter, OpenAI, Ollama lokal, Claude); model dapat diganti dari panel Admin tanpa build ulang; seluruh prompt melewati penyamaran |
| **Review** | Alur status draf, ditinjau, lalu disetujui/ditolak/positif-palsu; penyunting naratif; riwayat revisi; perbandingan AI vs auditor; lampiran bukti; papan Kanban |
| **Pengelolaan penugasan** | Periode, cakupan, anggota tim; akses dibatasi keanggotaan; hapus penugasan (admin, dengan konfirmasi nama) |
| **Basis Pengetahuan** | Rujukan naratif lintas penugasan, saran otomatis per temuan, terapkan sebagai suntingan auditor, opt-out per penugasan, akses baca tercatat |
| **Laporan** | DOCX, PDF, pratinjau HTML; kop berkop klien/periode/cakupan; distribusi keparahan; matriks risiko; hanya temuan disetujui |
| **Metrik** | Efisiensi dedup, cakupan draf AI, kemajuan tinjauan, rasio suntingan, waktu kerja manusia vs baseline |
| **Keamanan** | Peran analis/auditor/admin (fail-closed), jejak audit seluruh mutasi + akses baca Basis Pengetahuan, penyamaran sebelum LLM, penolakan menyala di produksi bila rahasia bawaan belum diganti |
| **Antarmuka** | Dwibahasa ID/EN, mode gelap tanpa kedip |

**Pengujian:** 222 tes unit yang seluruhnya murni — tanpa basis data, Redis,
MinIO, maupun LLM — dijalankan dengan
`docker exec auditforge-api-1 python -m pytest -q` (pasang dulu
`pip install -e ".[dev]"` di dalam kontainer). Ditambah `./scripts/smoke.sh`
yang memeriksa 31 endpoint pada sistem yang benar-benar berjalan.

## Yang belum ada

Disebutkan terang-terangan agar tidak ada yang mengira sudah berfungsi:

- **Agent pengirim dari laptop pentester.** Rancangannya sudah ditulis
  (`docs/superpowers/specs/2026-08-03-remote-scan-ingest-design.md`) tetapi belum
  dibangun. Untuk sekarang berkas disalin sendiri ke folder terpantau, atau
  diunggah lewat antarmuka.
- **Verifikasi remediasi (retest) dan skor kepercayaan lintas-perkakas.**
  Rancangannya ada, implementasinya belum.
- **Notifikasi** dalam aplikasi maupun surel.
- **Triase berbantuan AI** — penandaan kandidat positif-palsu beserta alasannya.
  Triase yang ada sepenuhnya deterministik.

---

## Bacaan lanjutan

| Berkas | Isi |
|---|---|
| [`FLOW.md`](FLOW.md) | Alur kerja langkah demi langkah untuk pengguna akhir, keyed ke tab antarmuka |
| [`README.md`](README.md) | Arsitektur, tumpukan teknologi, konfigurasi LLM |
| [`DEPLOY.md`](DEPLOY.md) | Memasang di server sungguhan: mode produksi, Tailscale, pencadangan |
| `docs/superpowers/specs/` | Rancangan tiap modul, termasuk yang belum dibangun |

## Menghentikan

```bash
docker compose down          # berhenti, data tetap tersimpan
docker compose down -v       # berhenti dan HAPUS seluruh data
```

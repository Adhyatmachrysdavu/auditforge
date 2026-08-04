# Desain — Pusat Ingest: Visibilitas, Urai Ulang, dan Dedup Berkas

**Tanggal:** 4 Agustus 2026
**Status:** Disetujui untuk perencanaan
**Ruang lingkup:** AuditForge — melengkapi auto-ingest (R3) agar benar-benar mengurangi pekerjaan, bukan memindahkannya

---

## 1. Latar Belakang

Auto-ingest folder terpantau (R3) sudah terbukti bekerja: berkas yang ditaruh di
`<watch_dir>/inbox/<engagement_id>/` diserap otomatis tiap ~30 detik melalui pipeline yang
sama dengan unggah manual. Yang belum ada adalah segala sesuatu **di sekitarnya**.

Pemeriksaan basis data pada 4 Agustus 2026 menemukan tiga celah, seluruhnya terbukti dari
data nyata:

| Celah | Bukti |
|---|---|
| Berkas gagal mati permanen | **7 upload berstatus `failed`**, tersebar di 4 penugasan. `parse_upload` hanya dipanggil sekali, saat berkas pertama masuk (`engagements.py:149`). Tidak ada jalan mengulang. |
| Kegagalan tak terlihat lintas penugasan | Ketujuhnya hanya dapat ditemukan dengan membuka tab Berkas pada tiap penugasan satu per satu |
| Berkas yang sama bisa diserap berulang | `ScanUpload` tidak menyimpan hash isi berkas |

Yang membuat celah pertama layak diperbaiki sekarang: **ketujuh berkas gagal itu masih
menyimpan `storage_key`-nya** — berkas mentahnya utuh di MinIO. Mengurai ulang tinggal
memanggil task yang sudah ada. Tanpa itu, ketika parser baru ditambahkan kelak (Nessus dan
Semgrep sudah disebut proposal), berkas lama tetap tidak akan pernah bisa masuk.

### Mengapa ini bukan sekadar kenyamanan

Auto-ingest tanpa ketiga hal ini **memindahkan** pekerjaan, bukan menghapusnya. Berkas masuk
sendiri, tetapi auditor tetap harus membuka tiap penugasan untuk memastikan tidak ada yang
gagal — dan bila gagal, satu-satunya jalan adalah masuk ke server dan memindahkan berkas
kembali ke `inbox/`.

---

## 2. Lingkup

### Termasuk

1. **Halaman `/ingest`** — aktivitas ingest seluruh penugasan dalam satu tabel
2. **Urai ulang** berkas yang gagal, dari UI
3. **Dedup berkas** berdasarkan hash isi

### Tidak termasuk (spec terpisah)

**Notifikasi (in-app + email).** Disetujui untuk dibangun, tetapi **setelah** bagian ini
selesai — bukan karena ketergantungan teknis, melainkan karena bagian ini yang menghasilkan
peristiwa yang akan dikirimkan. Membangun pengirim sebelum jelas apa yang layak dikirim
menghasilkan notifikasi yang tidak dibaca siapa pun. Kanal yang sudah diputuskan: dalam
aplikasi **dan** email; **tidak ada webhook pihak ketiga**, dan isi pesan dibatasi pada
nomor penugasan, jenis peristiwa, serta jumlah — tanpa nama klien maupun judul kerentanan.

### Non-tujuan

- Tidak menyentuh pipeline deterministik (parse → enrichment → dedup → triase), masking,
  maupun alur persetujuan.
- Tidak menambah model baru. Seluruh data yang dibutuhkan halaman `/ingest` sudah tersimpan
  di `ScanUpload`; yang kurang hanyalah satu kolom hash.
- Tidak menghitung mundur hash berkas lama. Mengunduh puluhan berkas dari MinIO demi
  manfaat nol tidak sepadan; dedup berlaku untuk berkas yang masuk sejak fitur ini aktif.

---

## 3. Perubahan Model

Satu kolom pada `scan_uploads`:

| Kolom | Tipe | Keterangan |
|---|---|---|
| `content_hash` | String(64), nullable, indexed | SHA-256 isi berkas. Kosong untuk berkas yang masuk sebelum fitur ini ada. |

Nullable dan terindeks. Nullable karena berkas lama tidak punya nilai ini dan tidak boleh
dianggap duplikat karenanya; terindeks karena setiap ingest melakukan satu pencarian
terhadapnya.

---

## 4. Modul Murni `app/ingest/rules.py`

Seluruh keputusan ditempatkan di sini agar dapat diuji tanpa basis data, mengikuti pola
`review.py` dan `ingest/watcher.py`.

```python
def can_reparse(*, status: str, has_storage_key: bool) -> tuple[bool, str]:
    """(boleh, alasan). Hanya berkas gagal yang berkasnya masih ada."""

def is_duplicate(*, content_hash: str | None, parsed_hashes: set[str]) -> bool:
    """True bila hash ini sudah pernah BERHASIL diurai di penugasan yang sama."""
```

### Dua aturan yang mengikat

**Urai ulang hanya untuk berkas `failed`.** Mengurai ulang berkas yang sudah `parsed` akan
menaikkan `occurrences` setiap temuan di dalamnya. Deduplikasi memang menanganinya tanpa
menciptakan baris ganda, tetapi angka `occurrences` menjadi bohong — dan angka itu ikut
menentukan prioritas triase.

**Dedup hanya menolak yang sudah pernah *berhasil*.** Kata "berhasil" adalah inti aturannya.
Berkas yang dulu gagal harus tetap boleh dikirim ulang; tanpa pengecualian ini, begitu
parser baru ditambahkan, tidak satu pun berkas lama dapat masuk lagi karena hash-nya sudah
tercatat. `content_hash` kosong tidak pernah dianggap duplikat.

---

## 5. Endpoint

| Endpoint | Berkas | Peran | Fungsi |
|---|---|---|---|
| `GET /ingest` | `api/routes/ingest.py` (**baru**) | pengguna terautentikasi | Daftar aktivitas ingest lintas penugasan; saring `status`, `engagement_id`, batas jumlah |
| `POST /engagements/{eid}/uploads/{uid}/reparse` | `api/routes/engagements.py` | analyst, auditor, admin | Urai ulang berkas gagal |

Router baru `api/routes/ingest.py` didaftarkan di `main.py` bersama router lain.
`engagements.py` sudah ~710 baris; menambahkan endpoint lintas-penugasan ke sana akan
mencampur dua cakupan yang berbeda dalam satu berkas yang sudah besar.

**Mengapa endpoint urai ulang diletakkan di bawah penugasan, bukan `/ingest/…`:** ketika
Modul 2 memasang pembatasan akses berbasis keanggotaan tim, seluruh route di bawah
`/engagements/{id}` ikut terlindungi lewat `_get_engagement()` tanpa perubahan apa pun.
Menempatkannya di `/ingest/…` berarti aturan akses harus ditulis dua kali.

`GET /ingest` perlu penyaringan keanggotaan tersendiri saat Modul 2 dikerjakan — ditandai
dengan komentar `TODO(Modul 2)` di kode, sebagaimana sudah dilakukan pada `/stats/timing`.

**Peran untuk urai ulang mencakup analis:** ini bukan keputusan persetujuan, melainkan
pekerjaan pemrosesan berkas — setara dengan hak mengunggah yang sudah dimiliki analis.

---

## 6. Alur

### Berkas masuk (manual maupun watcher)

```
berkas → SHA-256 → cari ScanUpload (penugasan sama, hash sama, status 'parsed')
   ├── ketemu  → JALUR MANUAL : 409 + nomor upload aslinya
   │             JALUR WATCHER: pindah ke processed/ tanpa diproses, dicatat
   └── kosong  → simpan hash → pipeline seperti biasa
```

### Urai ulang

```
validasi (failed + storage_key ada) → status='uploaded', error=NULL
   → parse_upload.delay(upload_id) → hasilnya 'parsed' atau kembali 'failed' + pesan baru
```

Tidak diperlukan kode penanganan hasil: `parse_upload` yang sudah ada sudah menulis status
akhir beserta pesan galatnya.

---

## 7. Penanganan Kegagalan

| Kejadian | Perlakuan |
|---|---|
| Berkas hilang dari MinIO | `409` dengan pesan jelas — bukan `500` dari `get_bytes` |
| Hash gagal dihitung | Ingest tetap berjalan, `content_hash` dibiarkan kosong. Dedup tidak boleh memblokir pekerjaan |
| Urai ulang pada berkas `parsed` | `409` beserta alasannya |
| Urai ulang gagal lagi | Kembali `failed` dengan pesan baru; berkas tetap tersimpan dan boleh dicoba lagi |
| Duplikat lewat watcher | Dipindah ke `processed/`, bukan `failed/` — ini bukan kegagalan |

---

## 8. Antarmuka

### Halaman `/ingest` (item baru di sidebar)

Kartu ringkas di atas: **masuk hari ini**, **gagal belum ditangani**, **total berkas**.

Tabel:

| Kolom | Isi |
|---|---|
| Waktu | `created_at` |
| Penugasan | nomor + nama, tertaut ke halaman penugasan |
| Berkas | `filename` |
| Perkakas | `tool` hasil deteksi |
| Asal | `manual` / `watcher` — diturunkan dari `uploaded_by` (null = watcher) |
| Status | `parsed` / `failed` / `parsing`, warna + ikon + teks sesuai blueprint |
| Aksi | tombol **Urai Ulang** hanya pada baris `failed` yang berkasnya masih ada |

Penyaring status, dan penyorotan baris gagal agar langsung terlihat.

Kolom **Asal** sengaja diturunkan dari `uploaded_by` alih-alih menambah kolom `source` —
konvensi `uploaded_by=None` untuk ingest otomatis sudah dipakai `_ingest_watched_file`.
Ketika agent pengiriman jarak jauh dibangun (spec `remote-scan-ingest`), spec tersebut sudah
merencanakan kolom `source` dan `agent_token_id` tersendiri; kolom Asal di sini tinggal
membacanya.

### Tab Berkas pada halaman penugasan

Tombol **Urai Ulang** yang sama ditambahkan pada baris berstatus `failed`, agar auditor yang
sudah berada di dalam sebuah penugasan tidak perlu berpindah halaman.

Seluruh teks baru wajib ditambahkan ke **kedua** locale di `i18n/messages.ts`.

---

## 9. Pengujian

`tests/test_ingest_rules.py`, murni tanpa DB/jaringan sesuai konvensi repo:

| Kasus | Harapan |
|---|---|
| `can_reparse` — gagal + berkas ada | boleh |
| `can_reparse` — gagal + berkas hilang | tidak, dengan alasan |
| `can_reparse` — sudah `parsed` | tidak, dengan alasan |
| `can_reparse` — sedang `parsing` | tidak (menghindari dua task berjalan bersamaan) |
| `is_duplicate` — hash sama, sudah `parsed` | duplikat |
| `is_duplicate` — hash sama, sebelumnya gagal | **bukan** duplikat |
| `is_duplicate` — hash kosong | bukan duplikat |
| `is_duplicate` — himpunan kosong | bukan duplikat |

### Verifikasi manual

1. Buka `/ingest` → tujuh berkas gagal tampil, tersebar di empat penugasan, tanpa perlu
   membuka penugasan satu per satu.
2. **Bukti urai ulang:** jangan memakai `broken-sample.xml` — berkas itu memang rusak,
   sehingga gagal lagi tidak membuktikan apa pun. Ambil satu upload berstatus `parsed`,
   ubah statusnya menjadi `failed` langsung di basis data, lalu tekan Urai Ulang di UI. Ia
   harus kembali menjadi `parsed`.
3. Unggah berkas yang isinya identik dengan yang sudah berhasil diserap → ditolak `409`
   beserta nomor upload aslinya.
4. Taruh berkas identik itu di folder terpantau → berpindah ke `processed/`, tidak ada
   `ScanUpload` baru, tidak ada temuan baru.
5. `docker exec auditforge-api-1 python -m pytest -q` → seluruh tes lama lulus.

---

## 10. Kriteria Selesai

- [ ] `/ingest` menampilkan aktivitas seluruh penugasan dalam satu tabel
- [ ] Berkas gagal dapat diurai ulang dari UI, dan berhasil bila penyebabnya sudah teratasi
- [ ] Urai ulang ditolak untuk berkas `parsed`, `parsing`, atau yang berkasnya hilang
- [ ] Berkas identik yang sudah berhasil diserap ditolak; yang sebelumnya gagal tetap boleh
- [ ] Tidak ada model baru; hanya satu kolom tambahan
- [ ] Seluruh tes lama lulus; tes baru murni tanpa infrastruktur
- [ ] `FLOW.md` diperbarui dengan langkah menangani berkas gagal

---

## 11. Hubungan dengan Spec Lain

| Spec | Hubungan |
|---|---|
| `2026-08-03-remote-scan-ingest-design.md` (agent) | Saling melengkapi. Agent menambah jalur ingest ketiga; halaman `/ingest` menampilkannya lewat kolom `source` yang sudah direncanakan spec tersebut. Tidak ada ketergantungan urutan. |
| `2026-08-03-penyelarasan-proposal-design.md` Modul 2 | `GET /ingest` perlu penyaringan keanggotaan saat Modul 2 dikerjakan. Ditandai `TODO(Modul 2)` di kode. |
| Notifikasi (belum ada spec) | Dibangun setelah ini; peristiwa yang dikirimkannya berasal dari sini. |

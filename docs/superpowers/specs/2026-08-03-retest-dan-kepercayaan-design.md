# Desain — Verifikasi Remediasi (Retest) dan Skor Kepercayaan Lintas-Perkakas

**Tanggal:** 3 Agustus 2026
**Status:** Disetujui untuk perencanaan
**Ruang lingkup:** AuditForge — dua kemampuan **di luar proposal**, disetujui secara sadar
dengan syarat "tidak terlalu jauh dan lebih baik dari proposal"

---

## 1. Latar Belakang

Proposal tidak menyebut retest sama sekali, padahal setiap penugasan uji penetrasi yang
serius memiliki babak kedua: klien memperbaiki, sistem diuji ulang, lalu terbit laporan yang
menyatakan mana yang sudah beres, mana yang masih terbuka, dan mana yang baru muncul.
Laporan itu pekerjaan yang klien bayar lagi.

Kemampuan ini nyaris gratis karena mesinnya sudah ada. `fingerprint` yang dibangun untuk
deduplikasi justru **alat yang tepat** untuk membandingkan dua penugasan pada klien yang
sama — tidak ada logika pencocokan baru yang perlu ditulis.

Efek sampingnya, kalimat *"basis pengetahuan temuan yang dapat digunakan kembali dan menjadi
bahan analisis tren keamanan lintas klien"* pada bagian Nilai Bisnis proposal akhirnya punya
data pendukung, bukan sekadar klaim.

### Batas yang tetap dijaga

Kelonggaran "boleh melenceng dari proposal" **tidak** berlaku untuk tiga hal, karena
alasannya berdiri sendiri di luar dokumen:

1. AuditForge tetap tidak memindai maupun mengeksploitasi apa pun.
2. AI tetap hanya membuat draf; auditor tetap pengambil keputusan akhir.
3. Penyamaran data sensitif tetap dilakukan sebelum teks keluar ke LLM.

Kedua modul dalam spec ini seluruhnya deterministik dan tidak memanggil LLM sama sekali.

---

## 2. Modul A — Verifikasi Remediasi (Retest)

### 2.1 Keputusan: retest adalah Engagement terpisah

Penugasan retest **wajib** menjadi `Engagement` baru yang menunjuk ke penugasan asal, bukan
putaran kedua di dalam penugasan yang sama.

Alasannya dipaksakan oleh arsitektur yang sudah ada, bukan selera: deduplikasi bekerja
**lintas-berkas di dalam satu engagement** (`_ingest_findings`). Bila hasil pemindaian
retest diunggah ke penugasan yang sama, fingerprint-nya akan cocok dengan temuan lama lalu
**tergabung** — `occurrences` naik menjadi 2 dan kedua putaran melebur menjadi satu baris.
Kemampuan membandingkan hancur seketika, dan tidak ada cara memulihkannya.

Kebetulan keputusan ini juga sesuai praktik nyata: retest umumnya kontrak dan laporan
terpisah.

Kolom baru pada `engagements`:

| Kolom | Tipe | Keterangan |
|---|---|---|
| `parent_engagement_id` | FK → `engagements.id`, nullable, indexed | Non-null berarti penugasan ini adalah retest dari penugasan tersebut |

### 2.2 Keputusan: hasil perbandingan disimpan di tabel sendiri

Persoalan yang muncul saat menyusun desain ini: temuan berstatus **terperbaiki** ada di
penugasan *baseline* tetapi **tidak memiliki baris apa pun** di penugasan retest — karena
memang sudah tidak terdeteksi lagi. Statusnya hendak disimpan di mana?

Menuliskannya ke temuan baseline adalah pilihan yang buruk: penugasan lama bisa jadi sudah
ditutup dan laporannya sudah diserahkan ke klien. Memodifikasi temuan yang laporannya sudah
terbit merusak keterlacakan.

Karena itu hasil perbandingan disimpan pada tabel relasi tersendiri, dan **tidak ada satu
pun temuan lama yang disentuh**:

**Tabel `retest_results`**

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | int, PK | |
| `retest_engagement_id` | FK → `engagements.id`, indexed | Penugasan retest |
| `baseline_finding_id` | FK → `findings.id`, nullable | `null` = temuan baru |
| `retest_finding_id` | FK → `findings.id`, nullable | `null` = terperbaiki (tidak muncul lagi) |
| `computed_status` | String(20) | Kesimpulan sistem: `fixed` \| `still_open` \| `new` |
| `status` | String(20) | Kesimpulan berlaku — sama dengan `computed_status` kecuali auditor menimpanya |
| `verified_by` | FK → `users.id`, nullable | Auditor yang menimpa |
| `note` | Text, nullable | Alasan koreksi |
| `created_at` / `updated_at` | DateTime | |

Menyimpan `computed_status` terpisah dari `status` memungkinkan laporan menyatakan "sistem
menyimpulkan X, auditor mengubahnya menjadi Y beserta alasannya" — jejak yang selaras dengan
prinsip keterlacakan yang sudah berlaku di seluruh aplikasi.

### 2.3 Mengapa auditor harus bisa menimpa

Pemindaian bisa menipu. Layanan yang kebetulan sedang mati saat retest akan terbaca
"terperbaiki" padahal belum disentuh sama sekali; jaringan yang memblokir pemindai
menghasilkan kesimpulan yang sama. Laporan retest yang menyatakan sesuatu sudah beres
padahal belum adalah jenis kesalahan yang paling merusak kepercayaan klien — dan bisa
berujung insiden nyata.

Karena itu pola yang sudah berlaku di seluruh AuditForge diterapkan lagi di sini: **sistem
mengusulkan, auditor memutuskan.**

### 2.4 Modul murni `app/retest.py`

Tanpa DB, mengikuti pola `review.py` dan `triage.py`:

```python
def compare_fingerprints(
    baseline: dict[str, int],   # fingerprint → finding_id (penugasan asal)
    retest: dict[str, int],     # fingerprint → finding_id (penugasan retest)
) -> list[tuple[str, int | None, int | None]]
```

Mengembalikan daftar `(status, baseline_finding_id, retest_finding_id)`:

| Kondisi | Status |
|---|---|
| Ada di baseline, tidak ada di retest | `fixed` |
| Ada di keduanya | `still_open` |
| Hanya ada di retest | `new` |

Temuan tanpa `fingerprint` (nilainya nullable) dilewati dan dihitung terpisah sebagai "tak
dapat dibandingkan", agar tidak diam-diam dilaporkan sebagai temuan baru.

### 2.5 Kapan dihitung, dan aturan yang tidak boleh dilanggar

Perhitungan dijalankan lewat endpoint eksplisit — mengikuti pola tombol "Hitung Ulang
Triase" yang sudah ada — bukan diam-diam di latar.

**Aturan mutlak saat menghitung ulang: baris yang sudah ditimpa auditor
(`verified_by` non-null) tidak boleh ditimpa balik oleh sistem.** `computed_status`
diperbarui, `status` dipertahankan. Tanpa aturan ini, satu klik "hitung ulang" akan
menghapus seluruh verifikasi manual auditor tanpa jejak — kegagalan yang persis merusak
kepercayaan yang hendak dibangun modul ini.

### 2.6 Endpoint

| Endpoint | Peran | Fungsi |
|---|---|---|
| `POST /engagements/{id}/retest/compute` | auditor, admin | Hitung/perbarui perbandingan terhadap `parent_engagement_id` |
| `GET /engagements/{id}/retest` | anggota penugasan | Hasil perbandingan beserta ringkasannya |
| `PUT /engagements/{id}/retest/{result_id}` | auditor, admin | Timpa `status` + isi `note`; mengisi `verified_by` |

Menolak dengan pesan jelas bila penugasan tidak memiliki `parent_engagement_id`.

### 2.7 Laporan retest

Bila `parent_engagement_id` non-null, laporan yang dihasilkan (`reporting/report_data.py`)
menyertakan bagian tambahan **Status Remediasi**:

- Ringkasan angka: jumlah terperbaiki / masih terbuka / temuan baru
- Tabel temuan yang masih terbuka, disertai **berapa lama dibiarkan** — angka yang sangat
  berbicara bagi manajemen klien. Dihitung dari `period_end` penugasan baseline ke
  `period_start` penugasan retest bila kolom periode tersedia (ditambahkan oleh
  `2026-08-03-penyelarasan-proposal-design.md`); bila kosong, jatuh ke selisih
  `engagements.created_at` keduanya. Bila kedua penugasan tidak memiliki tanggal yang masuk
  akal, kolom ini dikosongkan alih-alih menampilkan angka yang menyesatkan.
- Catatan koreksi auditor bila ada, lengkap dengan alasannya

Struktur laporan yang ada tidak berubah untuk penugasan biasa; bagian ini hanya muncul pada
penugasan retest.

### 2.8 Antarmuka

Tab **Retest** pada halaman penugasan, muncul hanya bila penugasan memiliki induk. Tiga
kelompok (terperbaiki / masih terbuka / baru), masing-masing dengan tombol koreksi yang
meminta alasan. Baris yang telah dikoreksi auditor ditandai jelas beserta kesimpulan asli
sistem.

Pada pembuatan penugasan, tambahkan pilihan opsional "penugasan ini adalah retest dari …".

---

## 3. Modul B — Skor Kepercayaan Lintas-Perkakas

### 3.1 Alasan

Temuan yang dilaporkan Nuclei **dan** ZAP jauh lebih meyakinkan daripada yang hanya muncul
sekali di satu perkakas. Datanya sudah tersimpan sejak lama di `Finding.sources` (daftar
`{tool, upload_id}`) dan `Finding.occurrences`, tetapi belum pernah dipakai sebagai sinyal
apa pun. Auditor saat ini harus menilainya sendiri satu per satu.

### 3.2 Keputusan: tidak menyentuh rumus triase

Skor kepercayaan disimpan pada kolom tersendiri dan **tidak mengubah `priority` maupun
`priority_score`**.

`triage.py` sudah dikunci oleh `tests/test_triage.py`. Mengubah rumusnya berarti menulis
ulang tes-tes itu sekaligus kehilangan basis pembanding untuk evaluasi — padahal
ketelusuran triase deterministik adalah salah satu klaim utama proposal. Kepercayaan adalah
dimensi yang berbeda dari prioritas: sebuah temuan bisa berprioritas P1 namun berkepercayaan
rendah, dan justru kombinasi itulah yang perlu dilihat auditor.

Kolom baru pada `findings`:

| Kolom | Tipe | Keterangan |
|---|---|---|
| `confidence` | String(10), nullable | `low` \| `medium` \| `high` |
| `confidence_score` | Float, nullable | 0.0–1.0, untuk pengurutan |

### 3.3 Modul murni `app/confidence.py`

```python
def compute_confidence(
    *, tools: list[str], occurrences: int, has_cve: bool, cvss_score: float | None
) -> tuple[str, float]
```

Aturan deterministik dan dapat dijelaskan:

| Kondisi | Hasil |
|---|---|
| ≥ 2 perkakas berbeda melaporkan temuan yang sama | `high` |
| 1 perkakas, tetapi memiliki CVE atau CVSS | `medium` |
| 1 perkakas, tanpa CVE/CVSS | `low` |

Jumlah perkakas dihitung dari **nilai unik** `tool` di dalam `sources` — bukan panjang
daftarnya, karena satu perkakas yang mengunggah dua berkas tidak menambah kepercayaan apa
pun. Ini titik yang mudah salah dan sudah dikunci di tes.

### 3.4 Kapan dihitung

Dipanggil di tempat yang sama dengan `_apply_triage()` pada `workers/tasks.py`, yaitu
setelah setiap proses ingest, untuk seluruh temuan dalam penugasan. Fungsi `triage()` sendiri
tidak disentuh; keduanya berdampingan.

Endpoint "Hitung Ulang Triase" yang sudah ada sekaligus memperbarui kepercayaan.

### 3.5 Antarmuka

Kolom **Kepercayaan** pada tabel temuan (warna + ikon + teks, sesuai blueprint) beserta
penyaringnya. Kegunaan utamanya: auditor dapat mendahulukan temuan berprioritas tinggi
**dan** berkepercayaan tinggi, lalu memeriksa temuan berkepercayaan rendah sebagai kandidat
positif palsu — tanpa melibatkan AI sama sekali.

---

## 4. Migrasi

Satu migrasi Alembic:

1. `engagements.parent_engagement_id` (FK, nullable, indexed)
2. `findings.confidence`, `findings.confidence_score` (keduanya nullable)
3. Tabel `retest_results`

Seluruhnya bersifat menambah dan nullable, sehingga data yang ada tidak terpengaruh dan
tidak ada risiko mengunci siapa pun. Nilai `confidence` untuk temuan lama terisi saat
"Hitung Ulang Triase" dijalankan; sampai saat itu bernilai kosong dan tidak ditampilkan.

`downgrade` menghapus tabel dan kolom tersebut.

---

## 5. Pengujian

Mengikuti konvensi repo — seluruhnya murni, tanpa DB, jaringan, maupun LLM:

| Berkas | Cakupan |
|---|---|
| `tests/test_retest.py` | Ketiga kategori perbandingan; baseline kosong; retest kosong; fingerprint `None` dilewati dan dihitung terpisah; tidak ada temuan yang hilang dari salah satu kategori |
| `tests/test_confidence.py` | Dua perkakas berbeda → `high`; satu perkakas dua unggahan tetap **bukan** `high`; CVE menaikkan ke `medium`; daftar `sources` kosong tidak meledak |

**Verifikasi manual sebelum dinyatakan selesai:**

1. Buat penugasan retest dengan induk, unggah hasil pemindaian baru → ketiga kategori muncul
   dengan angka yang benar.
2. Timpa satu baris sebagai auditor, lalu tekan "hitung ulang" → **koreksi tetap bertahan**,
   dan `computed_status` diperbarui di baliknya.
3. Terbitkan laporan retest → bagian Status Remediasi muncul beserta lama temuan dibiarkan.
4. Temuan yang dilaporkan dua perkakas → `confidence` bernilai `high`; prioritas P1–P4
   **tidak berubah** dibanding sebelum modul ini ada.
5. `docker exec auditforge-api-1 python -m pytest -q` → seluruh tes lama lulus, termasuk
   `test_triage.py` tanpa perubahan.

---

## 6. Kriteria Selesai

- [ ] Penugasan dapat ditandai sebagai retest dari penugasan lain
- [ ] Perbandingan menghasilkan terperbaiki / masih terbuka / temuan baru dengan benar
- [ ] Auditor dapat mengoreksi kesimpulan sistem beserta alasannya
- [ ] Menghitung ulang **tidak pernah** menghapus koreksi auditor
- [ ] Laporan retest memuat bagian Status Remediasi beserta lama temuan dibiarkan
- [ ] Tidak satu pun temuan pada penugasan baseline dimodifikasi
- [ ] Skor kepercayaan tampil dan dapat disaring; `triage.py` dan tesnya tidak berubah
- [ ] Seluruh tes lama lulus; tes baru murni tanpa infrastruktur
- [ ] `FLOW.md` diperbarui dengan alur retest

---

## 7. Hubungan dengan Spec Lain

| Spec | Hubungan |
|---|---|
| `2026-08-03-remote-scan-ingest-design.md` | Tidak bergantung. Agent mengirim berkas ke penugasan retest sama seperti penugasan biasa — token retest cukup dibuat terpisah |
| `2026-08-03-penyelarasan-proposal-design.md` | Sebaiknya **setelah** Modul 2 spec tersebut, agar pembatasan akses berbasis anggota tim sudah berlaku pada endpoint retest. Bukan penghalang mutlak, tetapi menghindari pengerjaan ulang aturan akses |

---

## 8. Yang Tidak Dipilih pada Putaran Ini

| Usulan | Alasan |
|---|---|
| **Parser Nessus & Semgrep** | Ditawarkan dan tidak dipilih. Tetap murah bila kelak diinginkan: `BaseParser` sudah ada, satu perkakas ≈ satu berkas parser + satu berkas tes |
| **Ekspor Excel pelacakan remediasi** | Ditawarkan dan tidak dipilih. Berpasangan wajar dengan modul retest bila kelak dibutuhkan |

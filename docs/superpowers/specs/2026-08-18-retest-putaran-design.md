# Desain — Verifikasi Remediasi (Retest) Berbasis Putaran

**Tanggal:** 18 Agustus 2026
**Status:** disetujui, menunggu rencana implementasi
**Menggantikan:** Modul A pada `2026-08-03-retest-dan-kepercayaan-design.md`

---

## 1. Latar Belakang

Setelah klien memperbaiki temuan, auditor memindai ulang dan harus menjawab satu
pertanyaan: mana yang benar-benar tertutup, mana yang masih terbuka, dan mana yang
kambuh. Saat ini AuditForge tidak punya cara menjawabnya. Berkas pemindaian ulang akan
tergabung ke temuan lama dan yang berubah hanya angka `occurrences`.

### Batas yang tetap dijaga

Tiga garis identitas produk tidak boleh dilewati oleh fitur ini:

1. **AuditForge tidak memindai dan tidak mengeksploitasi.** Pemindaian ulang tetap
   dijalankan pentester dengan perkakasnya sendiri; yang masuk ke sini hanya
   keluarannya.
2. **Sistem mengusulkan, auditor memutuskan.** Berlaku penuh di sini, dengan alasan
   yang lebih tajam daripada di tempat lain (lihat 2.2).
3. **Seluruh logika keputusan deterministik dan teruji tanpa LLM.** Tidak ada AI yang
   menyentuh penentuan status remediasi.

---

## 2. Keputusan

### 2.1 Retest adalah putaran di dalam penugasan yang sama

Penugasan memiliki `current_round` yang dimulai dari 1. Audit awal adalah Putaran 1;
retest pertama adalah Putaran 2, dan seterusnya. Riwayat satu klien tetap menyatu di
satu tempat, dan pembatasan akses per anggota tim tidak perlu diatur ulang tiap
putaran.

**Mengapa berbeda dari spec 3 Agustus.** Spec itu menolak model putaran karena dedup
`_ingest_findings` akan melumerkan kedua putaran menjadi satu baris sehingga
"kemampuan membandingkan hancur seketika". Keberatan itu benar untuk skema saat itu,
tetapi tidak lagi berlaku begitu **tiap penampakan dicap nomor putaran**. Dengan
`rounds_seen`, penggabungan justru yang diinginkan: satu kerentanan tetap satu baris,
dan ketidakhadirannya di putaran terbaru tetap terbaca.

Keberatan kedua spec itu tetap sah, yaitu bahwa penugasan yang laporannya sudah
diserahkan tak boleh berubah isinya. Itu ditutup dengan dua pembatasan: kolom remediasi
hanya muncul pada laporan bila `current_round > 1`, dan pipeline hanya menulis data
putaran — narasi, persetujuan, dan lampiran bukti tidak pernah disentuh.

### 2.2 Sistem mengusulkan, auditor menetapkan

Ketidakhadiran sebuah temuan di putaran terbaru **bukan bukti** ia sudah diperbaiki.
Cakupan pemindaian ulang bisa berbeda, target bisa sedang mati, jaringan bisa memblokir
pemindai, atau perkakas kebetulan tak mendeteksi. Laporan audit yang menyatakan sebuah
kerentanan tertutup padahal masih ada adalah kesalahan yang paling merusak kepercayaan
klien, dan bisa berujung insiden nyata.

Karena itu usulan sistem tampil sebagai lencana yang menunggu ditegaskan, dan **hanya
status yang sudah ditegaskan auditor yang masuk laporan** — dengan satu penyempurnaan
pada 2.5 untuk penegasan yang sudah dibantah putaran berikutnya.

Auditor juga boleh menegaskan sebuah temuan tertutup **tanpa** pemindaian ulang,
misalnya karena melihat sendiri buktinya.

### 2.3 Satu temuan, riwayat per putaran

Kerentanan yang sama tetap satu baris `findings`. Yang bertambah hanya catatan putaran
mana saja ia terlihat. Narasi, lampiran bukti, dan persetujuan tidak pernah diulang.

### 2.4 Putaran dibuka secara eksplisit

Ada tombol **Mulai Putaran Baru**. Sejak ditekan, setiap berkas yang masuk menjadi milik
putaran terbaru, termasuk yang datang lewat auto-ingest (R3) yang tak punya manusia di
baliknya. Membuka putaran baru adalah keputusan, bukan kebetulan, jadi menuntut satu
tindakan sadar justru benar.

### 2.5 Penegasan bisa kedaluwarsa, dan tidak pernah dihapus diam-diam

Auditor menegaskan sebuah temuan **tertutup** di Putaran 2. Di Putaran 3 temuan itu
terdeteksi lagi. Status tersimpan kini bertentangan dengan kenyataan.

Penegasan lama **tidak dihapus** — menghapus keputusan manusia diam-diam merusak
keterlacakan, dan penegasan itu memang benar pada saat diberikan. Sebagai gantinya
disimpan `remediation_confirmed_round`, dan berlaku aturan:

> Penegasan dianggap **kedaluwarsa** bila `remediation_confirmed_round < current_round`
> **dan** usulan sistem berbeda dari status tersimpan.

Penegasan yang kedaluwarsa diperlakukan seperti belum ditegaskan: ia **tidak masuk
laporan**, dan antarmuka menampilkannya sebagai peringatan yang meminta penegasan
ulang, misalnya *ditegaskan tertutup pada Putaran 2, tetapi terlihat lagi di Putaran 3*.

Penegasan yang **sejalan** dengan usulan tidak menjadi kedaluwarsa meski putarannya
bertambah, sehingga auditor tak perlu menegaskan ulang hal yang tidak berubah.

### 2.6 Hasil retest muncul sebagai kolom di laporan yang sudah ada

Bukan format laporan kedua. Satu jalur perakitan laporan lebih mudah dijaga, dan
penugasan yang belum pernah diretest tetap terbaca wajar.

---

## 3. Skema

Tanpa tabel baru.

**`engagements`**

| Kolom | Tipe | Keterangan |
|---|---|---|
| `current_round` | Integer, default 1, server_default `"1"` | Putaran yang sedang berjalan |

**`scan_uploads`**

| Kolom | Tipe | Keterangan |
|---|---|---|
| `round` | Integer, default 1, server_default `"1"` | Dicap saat berkas masuk, dari `current_round` |

**`findings`**

| Kolom | Tipe | Keterangan |
|---|---|---|
| `rounds_seen` | JSON, default list | Putaran tempat temuan ini terlihat, mis. `[1, 3]` |
| `remediation_status` | String(20), nullable | Keputusan auditor; `null` = belum ditegaskan |
| `remediation_note` | Text, nullable | Alasan, terutama bila menimpa usulan |
| `remediation_confirmed_round` | Integer, nullable | Putaran saat penegasan diberikan |
| `remediation_confirmed_by` | FK → `users.id`, nullable | |
| `remediation_confirmed_at` | DateTime, nullable | |

Entri pada `findings.sources` bertambah kunci `round`, sehingga tiap penampakan dapat
ditelusuri sampai ke berkas asalnya.

**Usulan sistem tidak disimpan.** Ia dihitung ulang tiap kali dibaca, sehingga tak
mungkin basi. Yang tersimpan hanya keputusan manusia. Ini sekaligus alasan tak ada kolom
`computed_status` seperti pada spec lama.

---

## 4. Modul murni `app/retest.py`

Tanpa DB, tanpa LLM, mengikuti pola `triage.py` dan `review.py`.

```python
STATUS_NOT_TESTED = "not_tested"
STATUS_OPEN = "open"
STATUS_FIXED = "fixed"
STATUS_RECURRING = "recurring"

def propose(rounds_seen: list[int], current_round: int) -> str:
    """Usulan status remediasi dari riwayat penampakan."""

def is_new_in_round(rounds_seen: list[int], current_round: int) -> bool:
    """True bila temuan ini pertama kali terlihat pada putaran berjalan."""

def is_stale(
    confirmed_status: str | None, confirmed_round: int | None,
    rounds_seen: list[int], current_round: int,
) -> bool:
    """True bila penegasan lama sudah dibantah putaran yang lebih baru."""

def effective_status(
    confirmed_status: str | None, confirmed_round: int | None,
    rounds_seen: list[int], current_round: int,
) -> str | None:
    """Status yang berlaku untuk laporan; None bila belum/kedaluwarsa."""

def summarize(rows: Iterable[object]) -> dict[str, int]:
    """Hitung temuan per status yang BERLAKU, untuk laporan."""
```

Aturan `propose`:

| Keadaan | Hasil |
|---|---|
| `current_round <= 1` | `not_tested` — belum ada putaran pembanding |
| `rounds_seen` kosong | `not_tested` — bertahan terhadap data lama |
| Terlihat di putaran berjalan, tanpa putaran terlewat di tengah | `open` |
| Terlihat di putaran berjalan, ada putaran terlewat di tengah | `recurring` |
| Tak terlihat di putaran berjalan | `fixed` |

"Baru di putaran ini" **bukan** status tersendiri; ia turunan dari
`min(rounds_seen) == current_round` dan hanya dipakai sebagai penanda tampilan.
Menjadikannya status akan bertabrakan dengan `open`, sebab temuan baru memang terbuka.

---

## 5. Perubahan pipeline

Di `_ingest_findings` (`workers/tasks.py`), dua tambahan dan tidak lebih:

1. Sisipkan putaran berjalan ke `rounds_seen` bila belum ada.
2. Cantumkan `round` pada entri `sources` yang baru.

Ikuti pola yang sudah berlaku: **tugaskan ulang kolom daftar** (`row.rounds_seen = [...]`)
alih-alih memutasinya, agar SQLAlchemy mendeteksi perubahannya.

Urutan pipeline tidak berubah, dan dedup tetap lintas-berkas serta lintas-perkakas dalam
satu penugasan.

---

## 6. Endpoint

| Endpoint | Wewenang | Keterangan |
|---|---|---|
| `POST /engagements/{id}/rounds` | auditor, admin | Naikkan `current_round`, kembalikan nomor barunya |
| `PATCH /engagements/{id}/findings/{fid}/remediation` | auditor, admin | Tetapkan `remediation_status` dan `remediation_note` |

Payload temuan bertambah `rounds_seen`, `remediation_status`, dan
`remediation_proposal` (dihitung, hanya-baca).

RBAC mengikuti aturan yang sudah ada: **analis boleh melihat, tidak boleh menegaskan**,
sama seperti ia tak boleh menyetujui temuan. Penegasan dicatat `AuditMiddleware` seperti
mutasi lainnya, dan ditambah satu baris `FindingRevision` beraksi `remediation` agar
terbaca di riwayat temuan.

---

## 7. Antarmuka

- **Kepala penugasan** menampilkan `Putaran N` beserta tombol **Mulai Putaran Baru**
  (hanya auditor/admin).
- **Tabel temuan** mendapat kolom **Remediasi**. Status yang sudah ditegaskan tampil
  sebagai lencana biasa; usulan yang belum ditegaskan tampil redup dengan kata
  "usulan". Ditambah penapis berdasarkan status remediasi.
- **Panel detail temuan** mendapat garis waktu ringkas, misalnya *terlihat di Putaran 1,
  tidak di Putaran 2*, beserta tombol penegasan dan kolom alasan.

Pilihan kata yang mengikat: lencana usulan berbunyi **"tak terlihat di Putaran N"**,
bukan "sudah diperbaiki". Sampai auditor menegaskannya, hanya itu yang sistem ketahui.

Seluruh teks baru wajib ada di kedua lokal `id` dan `en` (`i18n/messages.ts`).

---

## 8. Laporan

- Kolom status remediasi pada tabel temuan, **hanya dirender bila `current_round > 1`**.
- Satu kalimat di ringkasan eksekutif: berapa temuan yang tertutup dan terverifikasi
  dari total yang disetujui.
- **Hanya status yang berlaku yang tercetak**, yaitu hasil `effective_status`. Usulan
  tidak pernah masuk laporan, dan penegasan yang kedaluwarsa juga tidak.

---

## 9. Migrasi

Satu revisi Alembic menyusul `d4b7e2c81f95`. Seluruh kolom bernilai bawaan yang aman
untuk data lama: `current_round` dan `round` menjadi 1, `rounds_seen` menjadi `[1]` untuk
temuan yang sudah ada, dan kolom remediasi menjadi `null`.

Mengisi `rounds_seen` dengan `[1]`, bukan daftar kosong, penting agar penugasan lama
langsung terbaca benar begitu putaran kedua dibuka.

---

## 10. Pengujian

Seluruh tes tetap murni: tanpa DB, Redis, MinIO, maupun LLM.

**`tests/test_retest.py`** menutup `propose` untuk lima keadaan: belum ada retest, masih
terbuka, tertutup, kambuh, dan baru di putaran belakangan. Ditambah `is_new_in_round`,
`summarize`, serta `is_stale`/`effective_status` untuk penegasan yang dibantah putaran
berikutnya dan penegasan yang tetap sejalan.

**Tes ingest** memastikan `rounds_seen` bertambah saat temuan yang sama muncul di putaran
berikutnya, dan tidak berubah bila muncul dua kali dalam putaran yang sama. Fake ORM
memakai `SimpleNamespace` seperti `tests/test_reporting.py`.

**`scripts/smoke.sh`** bertambah dua endpoint baru dan satu penolakan yang harus tetap
berlaku, yaitu analis dilarang menegaskan remediasi.

---

## 11. Kriteria Selesai

1. Membuka Putaran 2 lalu memasukkan berkas pemindaian ulang menghasilkan usulan yang
   benar untuk keempat status.
2. Penegasan yang dibantah putaran berikutnya ditandai kedaluwarsa, tidak masuk laporan,
   dan tidak terhapus dari riwayat.
3. Usulan tidak pernah muncul di laporan; status yang ditegaskan muncul.
4. Penugasan yang masih di Putaran 1 menghasilkan laporan yang identik dengan sebelum
   fitur ini ada.
5. Analis tak dapat menegaskan status remediasi, baik lewat antarmuka maupun lewat API
   langsung.
6. Auto-ingest menempatkan berkas pada putaran yang sedang berjalan.
7. Seluruh gerbang hijau: pytest, `tsc --noEmit`, dan `scripts/smoke.sh`.

---

## 12. Yang Tidak Dikerjakan pada Putaran Ini

- **Laporan retest tersendiri.** Kolom pada laporan yang ada sudah menjawab kebutuhan.
- **Potret laporan per putaran.** Laporan tetap dirakit dari keadaan terkini.
- **Penanganan cakupan pemindaian yang berbeda antar putaran.** Justru inilah alasan
  usulan tetap berupa usulan, bukan penetapan.
- **Skor kepercayaan lintas-perkakas.** Tetap tersimpan sebagai Modul B pada spec
  3 Agustus, belum diambil.
- **Notifikasi** saat putaran baru dibuka atau status berubah.

---

## 13. Hubungan dengan Spec Lain

- **Menggantikan Modul A** pada `2026-08-03-retest-dan-kepercayaan-design.md`. Modul B
  spec tersebut tetap berlaku sebagai pekerjaan yang belum diambil.
- **Menyentuh R3 auto-ingest** (`2026-08-04-pusat-ingest-design.md`) hanya pada satu
  titik: berkas yang masuk dicap putaran berjalan.

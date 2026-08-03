# Desain — Pengiriman Hasil Scan Jarak Jauh (Agent) + Penerapan Server

**Tanggal:** 3 Agustus 2026
**Status:** Disetujui untuk perencanaan
**Ruang lingkup:** AuditForge — R4 (agent ingest) dan R5 (penerapan)

---

## 1. Latar Belakang

Saat ini berkas keluaran perkakas masuk ke AuditForge lewat dua jalur, dan keduanya
mengharuskan berkas sudah berada di mesin yang sama dengan server:

1. **Unggah manual** lewat UI (`POST /engagements/{id}/uploads`).
2. **Folder terpantau (R3)** — berkas ditaruh di `<watch_dir>/inbox/<engagement_id>/`,
   Celery beat menyerapnya tiap ~30 detik.

Jalur R3 sudah **terbukti bekerja end-to-end** (diverifikasi 3 Agustus 2026, lihat
Lampiran A). Ketiga jalur — berkas valid, berkas rusak, dan penugasan tak dikenal —
berperilaku benar, dan dedup lintas-unggahan berfungsi.

Yang belum ada: pentester yang menjalankan Nmap/Nuclei **di laptopnya sendiri, dari luar
kantor**, tetap harus mengunggah hasilnya secara manual. Ini titik gesek terbesar yang
tersisa pada alur pascapengujian.

### Celah yang ditemukan saat verifikasi

Kegagalan bersifat **senyap**. Ketika `broken-sample.xml` gagal diurai, sistem mencatat
`ScanUpload.status = failed` beserta alasannya (`ParseError: unclosed token: line 5,
column 6`) dan memindahkan berkas ke `failed/17/` — semuanya benar, tetapi **tidak ada
seorang pun yang diberi tahu**. Informasi itu hanya duduk di satu kolom basis data dan
satu folder di server. Untuk jalur agent, kelemahan ini fatal: pentester akan mengira
kirimannya berhasil padahal menguap.

---

## 2. Tujuan dan Non-Tujuan

### Tujuan

1. Hasil scan dari laptop mana pun masuk otomatis ke penugasan yang benar, tanpa unggah
   manual dan tanpa VPN kantor.
2. Kegagalan diketahui **oleh orang yang bisa bertindak atasnya**, saat ia masih bisa
   bertindak.
3. Berkas tidak pernah hilang, walaupun laptop sedang tanpa koneksi.
4. AuditForge dapat dijangkau dari luar kantor tanpa mengekspos data temuan ke internet
   publik.

### Non-Tujuan (tidak dibangun)

- **AuditForge tidak akan bisa memicu pemindaian.** Manusia tetap menjalankan Nmap/Nuclei
  sendiri; agent hanya mengirimkan hasilnya. Ini mempertahankan lingkup proposal
  ("Tidak Termasuk dalam Lingkup: Pelaksanaan pemindaian, eksploitasi, maupun aktivitas
  ofensif dalam bentuk apa pun") dan sifat pascapengujian sistem.
- Agent tidak mengurai apa pun di laptop. Ia mengirim berkas mentah; seluruh parsing,
  pengayaan, dedup, dan triase tetap terjadi di server melalui satu pipeline yang sama.
- Tidak menyentuh masking, RBAC persetujuan, maupun perakitan laporan yang sudah berjalan.
- Folder terpantau (R3) **tidak dihapus**. Ia tetap jalur sah untuk berkas lokal dan batch.

---

## 3. Arsitektur

Dua pintu masuk, satu pipeline:

```
[Laptop pentester]                          [Server kantor]
 nmap -oX ~/scans/t.xml
        │
        ▼
 auditforge-agent  ─── via Tailscale (WireGuard) ──►  POST /agent/uploads
 (pantau folder,                                        │
  antrean offline)                                      ▼
                                                 token → engagement_id
                                                        │
 [Berkas lokal] ──► inbox/<eid>/ ──► scan_inbox ──►  MinIO + ScanUpload
                        (R3)                            │
                                                        ▼
                                                 parse_upload (Celery)
                                                        │
                                 parse → enrichment → dedup → triase
```

### Keputusan arsitektural utama

**Endpoint agent tidak menerima `engagement_id`.** Penugasan tujuan diturunkan dari token,
bukan dari URL:

```
POST /agent/uploads
Authorization: Bearer af_xxxxxxxx
X-Filename: target.xml
<isi berkas mentah sebagai body>
```

Konsekuensinya: agent yang dipegang pentester **secara struktural tidak bisa** mengirim ke
penugasan klien lain, bahkan bila salah konfigurasi atau tokennya bocor. Seluruh kelas
kesalahan "temuan klien A nyasar ke laporan klien B" dihapus di tingkat desain, bukan
diserahkan ke validasi. Untuk data sekelas peta kerentanan klien, ini sepadan.

**Body mentah, bukan multipart.** Agent cukup memakai `urllib` dari pustaka standar Python
tanpa menyusun multipart secara manual dan tanpa `pip install` apa pun di mesin pentester
(Kali Linux sudah membawa Python 3). Endpoint unggah manual di UI tetap memakai multipart —
keduanya endpoint berbeda, tidak saling mengganggu.

---

## 4. Komponen

### 4.1 Model `AgentToken` (`models/agent_token.py`)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | int, PK | |
| `engagement_id` | FK → `engagements.id` | penugasan tujuan, **tidak dapat diubah** |
| `label` | String(100) | mis. "Laptop Kali — Davu" |
| `token_prefix` | String(16), indexed | 11 karakter pertama, untuk pencarian & tampilan UI |
| `token_hash` | String(255) | hash bcrypt dari token penuh |
| `created_by` | FK → `users.id` | |
| `created_at` | DateTime | |
| `last_used_at` | DateTime, nullable | diperbarui tiap pemakaian sukses |
| `revoked_at` | DateTime, nullable | non-null = dicabut, ditolak selamanya |

**Format token:** `af_` + `secrets.token_urlsafe(32)`.
Prefiks `af_` memudahkan pemindai rahasia mengenalinya bila tak sengaja ter-*commit*.

**Penyimpanan:** hanya hash yang disimpan, seperti kata sandi. Teks asli ditampilkan
**satu kali** saat pembuatan; setelah itu tidak dapat dilihat lagi, hanya dapat dicabut.

**Verifikasi dua tahap** (penting untuk kinerja): cari baris berdasarkan `token_prefix`
yang terindeks → verifikasi bcrypt sekali terhadap baris itu saja. Tanpa prefiks,
verifikasi harus mencoba bcrypt ke seluruh token (O(n) × ~100 ms) dan endpoint akan
melambat seiring bertambahnya token.

### 4.2 Logika token murni (`app/agent/tokens.py`)

Dipisah dari lapisan route agar dapat diuji tanpa basis data, mengikuti pola yang sudah
dipakai `review.py` dan `ingest/watcher.py`:

- `generate_token() -> tuple[str, str, str]` → `(token_penuh, prefix, hash)`
- `verify_token(token, hash) -> bool`
- `is_usable(revoked_at) -> bool`

### 4.3 Route agent (`api/routes/agent.py`)

| Endpoint | Auth | Fungsi |
|---|---|---|
| `POST /agent/uploads` | token agent | Terima berkas → MinIO → `ScanUpload` → `parse_upload.delay()` → balas `{upload_id}` |
| `GET /agent/uploads/{id}` | token agent | Status parse, untuk *polling* agent. Ditolak bila upload bukan milik penugasan token tersebut. |
| `GET /agent/whoami` | token agent | Verifikasi token + nama penugasan, untuk `auditforge-agent --check` |

Dependency baru `get_agent_token()` membaca header `Authorization: Bearer af_…`,
mengembalikan `401` bila token tidak ada, tidak cocok, atau sudah dicabut (*fail-closed*).

**Batas ukuran berkas: 100 MB**, dibaca secara *streaming*. Keluaran Nmap XML pada
pemindaian besar dapat mencapai puluhan megabita; tanpa batas eksplisit, satu berkas
raksasa dapat menghabiskan memori worker.

### 4.4 Kelola token (`api/routes/engagements.py` + UI)

| Endpoint | Peran | Fungsi |
|---|---|---|
| `POST /engagements/{id}/agent-tokens` | auditor, admin | Buat token; balas teks asli **sekali saja** |
| `GET /engagements/{id}/agent-tokens` | auditor, admin, analyst | Daftar token (prefiks + label + status, tanpa teks asli) |
| `DELETE /engagements/{id}/agent-tokens/{tid}` | auditor, admin | Cabut (isi `revoked_at`) |

**Keputusan RBAC:** pembuatan dan pencabutan token dibatasi pada **auditor/admin**. Token
adalah kredensial berumur panjang yang memberi akses tulis ke sebuah penugasan, sehingga
setara dengan keputusan kepercayaan, bukan pekerjaan analisis harian. Ini konsisten dengan
pola *fail-closed* yang sudah berlaku di repo. Analis tetap dapat melihat daftar token agar
tahu perangkat apa saja yang aktif mengirim.

Seluruh operasi ini otomatis tercatat di `audit_logs` melalui `AuditMiddleware` yang sudah
ada.

### 4.5 Perubahan `ScanUpload`

Dua kolom baru (satu migrasi Alembic):

- `source` — String(16), default `"manual"`; nilai: `manual` | `watcher` | `agent`
- `agent_token_id` — FK → `agent_tokens.id`, nullable

Asal berkas sebenarnya dapat disimpulkan (`uploaded_by` non-null = manual; keduanya null =
watcher), tetapi kolom eksplisit membuat kueri UI sederhana dan maksudnya tidak ambigu bagi
pembaca kode berikutnya.

### 4.6 Agent CLI (`agent/auditforge_agent.py`)

Satu berkas Python, **pustaka standar saja**, tanpa `pip install` di mesin pentester.

```bash
auditforge-agent --token af_xxx --server http://auditforge-srv:8000 --watch ~/scans
```

Konfigurasi tersimpan di `~/.auditforge-agent/`:

```
config.json     # server, token   (chmod 600 — berisi kredensial)
queue/          # berkas menunggu kirim
sent.json       # hash berkas terkirim + upload_id (cegah kirim ganda)
```

Siklus kerjanya:

1. Pantau folder; abaikan berkas yang mtime **atau** ukurannya masih berubah (default 5
   detik, sama dengan `watch_settle_seconds` pada R3).
2. Saring berdasarkan ekstensi (`.xml .json .jsonl .sarif .nessus .txt`, dapat diubah) agar
   berkas sampah di folder tidak ikut terkirim.
3. Hitung hash; lewati bila sudah pernah terkirim.
4. Kirim. Bila gagal → masuk `queue/`, coba lagi dengan jeda menaik.
5. Setelah `201`, *polling* status parse lalu cetak hasilnya ke terminal.

---

## 5. Penanganan Kegagalan

Setiap jenis kegagalan diperlakukan berbeda. Ini yang membedakan agent yang membantu dari
agent yang menjadi hama:

| Kejadian | Perlakuan |
|---|---|
| Tanpa koneksi / server mati | Masuk antrean lokal; coba lagi dengan jeda 5 dtk → 15 dtk → 60 dtk → 5 mnt → 15 mnt (maksimum). **Berkas tidak pernah dibuang.** |
| Token dicabut/salah (`401`) | **Berhenti total** dengan pesan jelas. Mencoba ulang hanya akan membanjiri log server tanpa kemungkinan berhasil. |
| Berkas > 100 MB (`413`) | Tidak diantrekan ulang; laporkan ke pengguna. |
| Format tak dikenali | Server mencatat `failed` + alasannya; agent mencetak alasan itu apa adanya. |
| Berkas sama dikirim ulang | Dicegah oleh hash di `sent.json`. |
| Kegagalan di server (`5xx`) | Diantrekan ulang seperti kegagalan koneksi. |

### Menutup celah "gagal senyap"

Agent **tidak berhenti setelah "terkirim"**. Ia menunggu hasil parse lalu mencetaknya:

```
✓ target.xml       → nmap, 12 temuan (3 baru, 9 digabung)
✗ hasil-burp.xml   → gagal: ParseError: unclosed token: line 5, column 6
```

Ini keputusan desain yang disengaja. Orang yang paling perlu tahu suatu berkas gagal adalah
**pentester yang baru saja mengirimnya** — ia masih di depan laptop, masih ingat
konteksnya, dan masih dapat mengulang pemindaian. Bukan auditor tiga hari kemudian.

Untuk sisi auditor, dua tambahan kecil di web:

- Kolom **asal** pada tab Berkas: `manual` / `watcher` / `agent · <label token>`
- **Badge jumlah berkas gagal** pada daftar penugasan, agar tak perlu membuka satu per satu

---

## 6. Keamanan

- Token disimpan sebagai hash bcrypt; teks asli hanya ada di layar sekali dan di
  `config.json` milik pentester (`chmod 600`).
- Token terikat pada **satu** penugasan dan tidak dapat dipindahkan.
- Pencabutan berlaku seketika: `revoked_at` diperiksa pada setiap permintaan.
- `last_used_at` memungkinkan auditor mengenali token yang sudah lama menganggur dan
  mencabutnya.
- Seluruh pembuatan/pencabutan token tercatat di `audit_logs`.
- Endpoint agent **tidak** dapat membaca temuan, menyetujui apa pun, atau menyentuh
  laporan. Kemampuannya hanya menambah berkas dan membaca status berkasnya sendiri.
- Berkas mentah tetap disimpan di MinIO, tidak pernah di basis data.
- Masking LLM tidak terpengaruh: agent berhenti di tahap unggah, jauh sebelum lapisan AI.

---

## 7. Penerapan (Deploy) — Tailscale

**Keputusan: Tailscale**, bukan Cloudflare Tunnel. Alasan utamanya bukan biaya (keduanya
gratis untuk skala ini) melainkan keselarasan dengan janji proposal:

> *"Seluruh komponen dijalankan di lingkungan internal perusahaan mengingat sifat data
> temuan yang sangat rahasia."*

Tailscale menepati kalimat itu secara harfiah: AuditForge tidak pernah memiliki alamat di
internet publik. Tidak ada pintu untuk digedor dan tidak ada yang dapat dipindai orang
asing. Cloudflare Tunnel menempatkan aplikasi di internet publik (dapat dikunci dengan
Access, tetapi tetap berada di sana) — selisih yang sulit dipertahankan untuk aplikasi
yang isinya peta kerentanan klien.

**Paket gratis Tailscale:** 6 pengguna, perangkat milik pengguna tanpa batas.

### Langkah penerapan

1. Server kantor: pasang Docker + Docker Compose.
2. Server kantor: pasang Tailscale, `tailscale up`, catat nama mesinnya (mis.
   `auditforge-srv`).
3. `git clone`, `cp .env.example .env`, **ganti seluruh kredensial bawaan** (postgres,
   MinIO, `secret_key` JWT, kata sandi akun seed).
4. `docker compose up -d --build`, lalu `alembic upgrade head` dan seed admin.
5. Laptop auditor & pentester: pasang Tailscale, bergabung ke tailnet yang sama.
6. Akses web: `http://auditforge-srv:3000` dari dalam tailnet.
7. Agent: `auditforge-agent --server http://auditforge-srv:8000 --token af_…`

**Mengapa `http://` dan bukan `https://`:** seluruh lalu lintas di dalam tailnet sudah
terenkripsi ujung-ke-ujung oleh WireGuard. Menambahkan TLS di atasnya berarti mengurus
sertifikat tanpa memperoleh kerahasiaan tambahan. Bila kelak jalur ini dipindah ke internet
publik (mis. Cloudflare Tunnel), TLS menjadi wajib — dan karena alamat server adalah
konfigurasi, bukan kode, perpindahan itu tidak menuntut perubahan pada agent.

**Mengapa agent menuju `:8000` (api) langsung, bukan `:3000`:** proxy same-origin pada
`frontend/next.config.mjs` ada untuk kebutuhan browser (menghindari CORS). Agent bukan
browser, sehingga hop tambahan itu tidak berguna baginya.

### Konsekuensi yang diterima

- Server **dan** setiap laptop wajib memasang Tailscale serta login sekali.
- Auditor hanya dapat membuka web dari dalam tailnet — tidak bisa dari perangkat sembarang.
- Batas 6 pengguna gratis; bila tim audit Suryasoft lebih besar, keputusan ini perlu
  ditinjau ulang.

### Catatan pra-produksi

`docker-compose.yml` saat ini memetakan Postgres (5432), Redis (6379), dan MinIO (9000)
ke host. Untuk penerapan sebenarnya, pemetaan tersebut sebaiknya dihapus agar hanya `web`
dan `api` yang terjangkau; layanan lain cukup diakses antar-kontainer.

---

## 8. Pengujian

Mengikuti konvensi repo — 109 tes yang ada seluruhnya murni, tanpa DB, Redis, MinIO,
maupun LLM, dan tanpa `conftest.py`. Tes baru mengikuti pola yang sama:

| Berkas | Cakupan |
|---|---|
| `tests/test_agent_token.py` | Pembuatan token, bentuk prefiks, verifikasi hash, penolakan token dicabut (*fail-closed*), token penugasan lain ditolak |
| `tests/test_agent_queue.py` | Antrean offline, jeda menaik, berhenti pada `401`, antre ulang pada `5xx` |
| `tests/test_agent_watch.py` | Deteksi berkas stabil (mtime + ukuran), saringan ekstensi, pencegahan kirim ganda lewat hash |

Logika yang butuh basis data dibiarkan tipis di lapisan route; seluruh keputusan
ditempatkan pada modul murni yang dapat diuji terisolasi.

**Verifikasi manual sebelum dinyatakan selesai:**

1. Jalankan `nmap -oX ~/scans/t.xml` di laptop lewat Tailscale → temuan muncul pada
   penugasan yang benar tanpa unggah manual.
2. Cabut token → agent berhenti dengan pesan jelas, bukan mencoba ulang selamanya.
3. Matikan koneksi saat mengirim → berkas terkirim otomatis setelah koneksi kembali.
4. Kirim berkas rusak → alasan kegagalan tercetak di terminal pentester.
5. `docker exec auditforge-api-1 python -m pytest -q` → seluruh tes lama tetap lulus.

---

## 9. Kriteria Selesai

- [ ] Pentester dari luar kantor menjalankan pemindaian; temuan muncul di penugasan yang
      benar tanpa menyentuh UI.
- [ ] Setiap kegagalan sampai ke pentester dalam hitungan detik, bukan tersimpan diam-diam.
- [ ] Berkas tidak pernah hilang saat koneksi terputus.
- [ ] Token dapat dicabut dari web dan berlaku seketika.
- [ ] AuditForge tidak memiliki alamat di internet publik.
- [ ] Folder terpantau (R3) tetap berfungsi seperti sebelumnya.
- [ ] Seluruh tes lama lulus; tes baru murni tanpa infrastruktur.
- [ ] `FLOW.md` diperbarui: bagian D bertambah jalur agent.

---

## 10. Ditunda ke Spec Terpisah

| Topik | Alasan penundaan |
|---|---|
| **Claude Skills** | Belum jelas apakah untuk membantu pengembangan (tooling) atau menjadi fitur di dalam produk. Perlu brainstorm sendiri. |
| **Fitur tambahan** | Terdapat celah nyata antara proposal dan kode: **Basis Pengetahuan Temuan** (naratif disetujui dipakai ulang lintas penugasan), **triase AI penanda kandidat positif-palsu**, **opsi mematikan AI per-penugasan** (disebut pada bagian Keamanan Data proposal), dan **pengukuran waktu penyusunan laporan** (indikator keberhasilan "turun 50%"). Semuanya tercantum di proposal namun belum dibangun, dan layak dibahas serius. |

---

## Lampiran A — Hasil Verifikasi Auto-Ingest (3 Agustus 2026)

Dijalankan terhadap penugasan #17 pada tumpukan yang sedang berjalan:

| Masukan | Hasil | Bukti |
|---|---|---|
| `nuclei-sample.jsonl` (valid) | Berhasil | → `processed/17/`; upload #110 `parsed`; perkakas terdeteksi otomatis sebagai `nuclei` |
| `broken-sample.xml` (rusak) | Gagal dengan benar | → `failed/17/`; upload #109 `failed`; `ParseError: unclosed token: line 5, column 6` |
| `inbox/999/` (penugasan tak ada) | Gagal dengan benar | → `failed/999/`; tidak ada baris upload dibuat |

Dedup terkonfirmasi: berkas nuclei tersebut sudah pernah diserap sebelumnya, dan
penyerapan ulang menghasilkan **0 temuan baru** — ketiga temuan yang cocok digabungkan
(`occurrences` 1 → 2, `sources` bertambah menjadi 2 perkakas).

Kesimpulan: mekanisme R3 sehat. Yang kurang hanyalah visibilitas, dan itu ditangani oleh
desain ini.

*(Catatan: verifikasi ini menambahkan 2 baris `scan_uploads` pada penugasan #17 dan
menaikkan `occurrences` tiga temuan. Data uji, aman dihapus.)*

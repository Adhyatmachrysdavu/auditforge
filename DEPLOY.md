# Memasang AuditForge di server

Panduan ini menjelaskan cara menjalankan AuditForge di server kantor dan
membukanya lewat **Tailscale**, tanpa domain, tanpa sertifikat, dan tanpa
membuka port apa pun ke internet.

Seluruh langkah di bawah sudah dijalankan dan diverifikasi pada 10 Agustus 2026,
kecuali bagian Tailscale yang bergantung pada server kantor.

---

## 0. Ringkasan

| | Pengembangan | Server |
|---|---|---|
| Perintah | `docker compose up -d` | `docker compose -f docker-compose.yml -f docker-compose.prod.yml …` |
| Kode | bind-mount dari direktori host | di dalam image (**wajib `--build`**) |
| Frontend | `next dev`, hot-reload | `next build` + `next start` |
| Backend | `uvicorn --reload` | `uvicorn --workers 4`, dengan healthcheck |
| Port terbuka | 3000, 8000, 5432, 6379, 9000, 9101 | **hanya 3000** |
| Rahasia bawaan | boleh | aplikasi **menolak menyala** |

---

## 1. Siapkan berkas rahasia

Jangan pakai `.env` pengembangan di server. Cara termudah:

```bash
./scripts/buat-env-prod.sh
```

Skrip itu membuat `.env.prod` berisi nilai acak, menyamakan sandi Postgres di
kedua tempat yang membutuhkannya, menyetel izin berkas ke `600`, lalu mencetak
kata sandi admin pertama **satu kali** — catat saat itu juga. Ia menolak
menimpa berkas yang sudah ada, karena mengganti sandi basis data yang sedang
dipakai akan memutus koneksi ke data yang sudah tersimpan.

Setelahnya tinggal isi `AI_API_KEY` bila ingin memakai LLM daring; LLM juga
dapat diatur belakangan lewat panel Admin tanpa build ulang.

<details>
<summary>Atau isi sendiri dari berkas contoh</summary>

```bash
cp .env.example .env.prod
chmod 600 .env.prod
```

Isi setiap baris bertanda `[WAJIB DIGANTI]`. Nilai acak dibuat dengan:

```bash
openssl rand -hex 32     # SECRET_KEY
openssl rand -hex 16     # POSTGRES_PASSWORD, MINIO_SECRET_KEY, SEED_ADMIN_PASSWORD
```

**Sandi Postgres harus sama persis** di `POSTGRES_PASSWORD` dan di dalam
`DATABASE_URL`. Ketidakcocokan di sini membuat API gagal terhubung tanpa
penjelasan yang jelas.

</details>

Yang wajib diganti:

| Variabel | Kenapa |
|---|---|
| `SECRET_KEY` | Kunci penanda-tangan JWT. Nilai bawaannya terbit di repositori publik — siapa pun yang membacanya dapat membuat token admin sendiri. |
| `POSTGRES_PASSWORD` | Sandi basis data. **Samakan** dengan sandi di dalam `DATABASE_URL`. |
| `DATABASE_URL` | Ganti `auditforge:auditforge` menjadi `auditforge:<sandi baru>`. |
| `MINIO_SECRET_KEY` | Berkas scan mentah dan lampiran bukti tersimpan di MinIO. |
| `SEED_ADMIN_PASSWORD` | Kata sandi admin pertama. |

Terakhir setel:

```
ENVIRONMENT=production
```

> **Pengaman.** Bila salah satu variabel di atas masih bernilai bawaan,
> AuditForge **menolak menyala** dan mencetak daftar variabel yang salah.
> Ini disengaja: peringatan pada log gampang terlewat, kegagalan boot tidak.
> Lihat `backend/app/core/hardening.py`.

Amankan berkasnya:

```bash
chmod 600 .env.prod
```

---

## 2. Nyalakan

```bash
export ENV_FILE=.env.prod

docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build
```

Tiga hal yang mudah keliru:

1. **`--build` wajib.** Di mode produksi kode dibaca dari dalam image, bukan
   dari direktori host. Tanpa `--build`, server menjalankan kode lama tanpa
   tanda apa pun.
2. **`ENV_FILE` dan `--env-file` keduanya perlu.** `--env-file` hanya
   memengaruhi interpolasi `${...}` di berkas compose; `ENV_FILE` yang
   menentukan berkas mana yang dimuat **ke dalam** kontainer. Tanpa `ENV_FILE`,
   kontainer tetap memuat `.env` pengembangan diam-diam.
3. Jalankan dari direktori repo, karena kedua berkas compose dirujuk relatif.

### Migrasi dan admin pertama

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    alembic upgrade head

docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    python -m app.scripts.seed
```

`seed` mencetak email dan kata sandi admin yang dibuat. Ia idempoten — aman
dijalankan ulang.

### Pastikan benar-benar sehat

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Kolom status `api` harus berbunyi **`(healthy)`**, bukan sekadar `Up`.
Bedanya penting: dengan `--workers`, proses induk uvicorn tetap hidup meski
seluruh worker-nya mati berulang, sehingga kontainer yang tak melayani apa pun
tetap tampak `Up`. Healthcheck yang membedakannya.

Bila `api` tidak kunjung `healthy`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api | tail -30
```

---

## 3. Buka lewat Tailscale

Tailscale membuat jaringan privat antar-perangkat. Server tidak perlu IP
publik, tidak perlu domain, dan tidak ada port yang terbuka ke internet.

**Di server:**

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Ikuti tautan yang muncul untuk masuk. Lalu terbitkan aplikasinya:

```bash
sudo tailscale serve --bg 3000
```

Perintah itu memberi HTTPS otomatis pada alamat seperti
`https://nama-server.namatailnet.ts.net` — sertifikatnya diurus Tailscale.

**Di laptop tiap auditor:** pasang Tailscale, masuk dengan akun yang sama,
lalu buka alamat tadi di peramban. Selesai.

> Jangan pakai `tailscale funnel` kecuali memang ingin aplikasinya terjangkau
> dari internet luas. `serve` membatasi akses ke anggota tailnet saja, dan
> itulah yang diinginkan untuk data audit klien.

Siapa yang boleh masuk diatur di admin Tailscale (Users → Invite). Mengeluarkan
seseorang dari tailnet langsung memutus aksesnya, terpisah dari peran di dalam
aplikasi.

---

## 4. Pencadangan

Tanpa cadangan, satu `docker compose down -v` yang keliru menghapus seluruh
penugasan, temuan, dan lampiran bukti.

```bash
./scripts/backup.sh /path/ke/cadangan
```

Menghasilkan dua berkas bertanggal; **keduanya** diperlukan:

- `auditforge-db-*.sql.gz` — temuan, naratif, keanggotaan tim, jejak audit
- `auditforge-objek-*.tar.gz` — berkas scan mentah dan lampiran bukti

Laporan yang temuannya ada tetapi buktinya hilang tidak dapat
dipertanggungjawabkan, jadi jangan mencadangkan salah satu saja. Skripnya
memeriksa hasilnya sendiri dan keluar dengan kode galat bila salah satu
cadangan kosong.

Jadwalkan harian lewat cron:

```cron
0 2 * * * cd /srv/auditforge && ./scripts/backup.sh /srv/cadangan >> /var/log/auditforge-backup.log 2>&1
```

**Salin hasilnya ke luar server.** Cadangan yang hanya tersimpan di mesin yang
sama tidak menolong saat mesin itu yang bermasalah.

### Memulihkan

```bash
# 1. Basis data
gzip -dc auditforge-db-20260810-020000.sql.gz | \
  docker exec -i auditforge-postgres-1 psql -U auditforge -d auditforge

# 2. Penyimpanan objek
docker run --rm -i -v auditforge_miniodata:/data alpine:3 \
  sh -c 'tar xzf - -C /data' < auditforge-objek-20260810-020000.tar.gz

# 3. Nyalakan ulang
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

---

## 5. Memperbarui versi

```bash
git pull
export ENV_FILE=.env.prod
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    alembic upgrade head
```

Cadangkan lebih dulu bila pembaruan memuat migrasi basis data.

---

## 6. Auto-ingest di server

Folder terpantau (R3) berada di `./datasets/watch` relatif terhadap repo.
Untuk menaruhnya di tempat lain, setel di `.env.prod`:

```
WATCH_HOST_DIR=/srv/auditforge-watch
```

Berkas hasil scan diletakkan di `<WATCH_HOST_DIR>/inbox/<id-penugasan>/`, lalu
worker memindahkannya ke `processed/` atau `failed/`. Alurnya sama persis
dengan unggah manual.

---

## 7. Yang belum ada

- **Agent pengirim dari laptop pentester** — spec tersedia di
  `docs/superpowers/specs/2026-08-03-remote-scan-ingest-design.md`, belum
  dibangun. Untuk sekarang berkas disalin sendiri ke folder terpantau, atau
  diunggah lewat antarmuka.
- **Notifikasi** — belum ada.
- **Rotasi log** — `docker compose logs` tumbuh tanpa batas. Setel
  `log-driver`/`max-size` bila server dipakai lama.

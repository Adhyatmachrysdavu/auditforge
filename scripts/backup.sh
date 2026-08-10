#!/usr/bin/env bash
# Cadangkan basis data dan penyimpanan objek AuditForge.
#
#   ./scripts/backup.sh [direktori-tujuan]
#
# Menghasilkan dua berkas bertanggal di direktori tujuan (bawaan: ./backups):
#   auditforge-db-YYYYmmdd-HHMMSS.sql.gz     — seluruh basis data
#   auditforge-objek-YYYYmmdd-HHMMSS.tar.gz  — berkas scan mentah & lampiran bukti
#
# Keduanya diperlukan. Basis data memuat temuan, naratif, dan jejak audit;
# MinIO memuat berkas unggahan asli dan lampiran bukti — laporan yang temuannya
# ada tetapi buktinya hilang tidak dapat dipertanggungjawabkan.
#
# Pemulihan dijelaskan di DEPLOY.md.

set -euo pipefail

# Git Bash (MSYS) mengubah argumen yang mirip jalur Unix menjadi jalur Windows,
# sehingga `-C /data` di dalam kontainer menjadi `C:/Program Files/Git/data`.
# Variabel ini mematikannya; pada Linux ia tak berpengaruh apa-apa.
export MSYS_NO_PATHCONV=1

TUJUAN="${1:-./backups}"
CAP="$(date +%Y%m%d-%H%M%S)"
PREFIX="auditforge"

PG_USER="${POSTGRES_USER:-auditforge}"
PG_DB="${POSTGRES_DB:-auditforge}"

# Nama kontainer & volume mengikuti `name: auditforge` di docker-compose.yml.
KON_DB="${BACKUP_DB_CONTAINER:-auditforge-postgres-1}"
VOL_OBJ="${BACKUP_MINIO_VOLUME:-auditforge_miniodata}"

if ! docker ps --format '{{.Names}}' | grep -qx "$KON_DB"; then
    echo "Kontainer '$KON_DB' tidak berjalan. Nyalakan stack lebih dulu." >&2
    exit 1
fi
if ! docker volume ls --format '{{.Name}}' | grep -qx "$VOL_OBJ"; then
    echo "Volume '$VOL_OBJ' tidak ditemukan." >&2
    exit 1
fi

mkdir -p "$TUJUAN"

BERKAS_DB="$TUJUAN/$PREFIX-db-$CAP.sql.gz"
BERKAS_OBJ="$TUJUAN/$PREFIX-objek-$CAP.tar.gz"

# Tulis ke berkas `.parsial` dulu lalu ganti nama: bila prosesnya gagal di
# tengah jalan, yang tertinggal jelas-jelas bukan cadangan yang sah.
echo "[1/2] Basis data ($KON_DB)…"
docker exec "$KON_DB" pg_dump -U "$PG_USER" -d "$PG_DB" | gzip > "$BERKAS_DB.parsial"
mv "$BERKAS_DB.parsial" "$BERKAS_DB"

# Image MinIO tidak memuat `tar`, jadi volume-nya di-mount ke kontainer bantu.
# Hasilnya dialirkan ke stdout agar tak perlu memetakan direktori host —
# pemetaan itulah yang menyulitkan di Windows.
echo "[2/2] Penyimpanan objek (volume $VOL_OBJ)…"
docker run --rm -v "$VOL_OBJ:/data:ro" alpine:3 \
    sh -c 'tar czf - -C /data .' > "$BERKAS_OBJ.parsial"
mv "$BERKAS_OBJ.parsial" "$BERKAS_OBJ"

# Cadangan kosong adalah kegagalan yang paling mahal: ia baru ketahuan saat
# dibutuhkan. Periksa sekarang, bukan nanti.
# Arsip dibaca lewat stdin, bukan dengan memberi jalurnya ke tar. GNU tar
# menyangka awalan "C:" pada jalur Windows absolut sebagai nama host jarak jauh
# dan gagal dengan "Cannot connect to C: resolve failed".
JML_OBJ="$(gzip -dc "$BERKAS_OBJ" | tar tf - | wc -l | tr -d ' ')"
JML_TABEL="$(gzip -dc "$BERKAS_DB" | grep -c 'CREATE TABLE' || true)"

echo
echo "Selesai:"
ls -lh "$BERKAS_DB" "$BERKAS_OBJ" | sed 's/^/  /'
echo "  basis data     : $JML_TABEL tabel"
echo "  objek          : $JML_OBJ entri"

if [ "$JML_TABEL" -lt 1 ] || [ "$JML_OBJ" -lt 1 ]; then
    echo
    echo "PERINGATAN: salah satu cadangan kosong. Jangan anggap ini berhasil." >&2
    exit 1
fi

echo
echo "Salin kedua berkas ke luar server ini. Cadangan yang tersimpan hanya di"
echo "mesin yang sama tidak menolong saat mesin itu yang bermasalah."

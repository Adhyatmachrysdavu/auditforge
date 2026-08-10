#!/usr/bin/env bash
# Muat data demo AuditForge ke stack yang sedang berjalan.
#
#   ./scripts/demo.sh            # muat, tolak bila sudah ada data
#   ./scripts/demo.sh --force    # timpa data yang ada (MENGHAPUS isi basis data)
#
# Tanpa ini, `docker compose up` menghasilkan aplikasi kosong: nol penugasan,
# nol temuan, nol laporan. Seluruh bagian yang menarik — triase, naratif AI,
# Basis Pengetahuan, laporan PDF — baru terlihat setelah ada isinya.
#
# Data demonya sepenuhnya sintetis (example.com, "PT Contoh"); tak ada apa pun
# milik klien sungguhan. Naratif AI di dalamnya sudah jadi, sehingga aplikasi
# dapat ditelusuri penuh **tanpa kunci LLM sama sekali**.

set -euo pipefail

# Git Bash (MSYS) mengubah argumen mirip jalur Unix menjadi jalur Windows;
# pada Linux variabel ini tak berpengaruh apa-apa.
export MSYS_NO_PATHCONV=1

PAKSA=0
[ "${1:-}" = "--force" ] && PAKSA=1

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_DUMP="$AKAR/datasets/demo/auditforge-demo-db.sql.gz"
OBJ_DUMP="$AKAR/datasets/demo/auditforge-demo-objek.tar.gz"

KON_DB="${DEMO_DB_CONTAINER:-auditforge-postgres-1}"
KON_MINIO="${DEMO_MINIO_CONTAINER:-auditforge-minio-1}"
VOL_OBJ="${DEMO_MINIO_VOLUME:-auditforge_miniodata}"
PG_USER="${POSTGRES_USER:-auditforge}"
PG_DB="${POSTGRES_DB:-auditforge}"

for f in "$DB_DUMP" "$OBJ_DUMP"; do
    [ -f "$f" ] || { echo "Berkas demo tak ditemukan: $f" >&2; exit 1; }
done
docker ps --format '{{.Names}}' | grep -qx "$KON_DB" \
    || { echo "Kontainer '$KON_DB' tak berjalan. Jalankan 'docker compose up -d' dulu." >&2; exit 1; }

# Jangan pernah menimpa data diam-diam: seseorang bisa saja sudah memakai
# instance ini untuk pekerjaan sungguhan.
ADA=$(docker exec "$KON_DB" psql -U "$PG_USER" -d "$PG_DB" -tAc \
    "SELECT COUNT(*) FROM engagements" 2>/dev/null || echo 0)
if [ "${ADA:-0}" -gt 0 ] && [ "$PAKSA" -eq 0 ]; then
    echo "Basis data sudah memuat $ADA penugasan."
    echo "Memuat data demo akan MENGHAPUS seluruh isinya."
    echo "Jalankan ulang dengan --force bila memang itu yang diinginkan."
    exit 1
fi

echo "→ Memuat basis data demo…"
# client_min_messages=WARNING menahan banjir NOTICE dari DROP CASCADE. Keluaran
# yang berisik membuat kegagalan sungguhan sulit terlihat di antaranya.
PGOPT="-c client_min_messages=WARNING"
docker exec -i -e PGOPTIONS="$PGOPT" "$KON_DB" psql -U "$PG_USER" -d "$PG_DB" -q \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
gzip -dc "$DB_DUMP" \
    | docker exec -i -e PGOPTIONS="$PGOPT" "$KON_DB" psql -U "$PG_USER" -d "$PG_DB" -q >/dev/null

echo "→ Memuat berkas scan & lampiran bukti…"
docker run --rm -i -v "$VOL_OBJ:/data" alpine:3 sh -c 'tar xzf - -C /data' < "$OBJ_DUMP"
# MinIO membaca ulang isi direktori datanya saat mulai; tanpa restart, berkas
# yang baru disalin belum terlihat olehnya.
docker restart "$KON_MINIO" >/dev/null 2>&1 || true

JML=$(docker exec "$KON_DB" psql -U "$PG_USER" -d "$PG_DB" -tAc \
    "SELECT (SELECT COUNT(*) FROM engagements) || ' penugasan, ' ||
            (SELECT COUNT(*) FROM findings) || ' temuan, ' ||
            (SELECT COUNT(*) FROM knowledge_entries) || ' entri Basis Pengetahuan'")

cat <<EOF

Selesai — $JML.

Buka  http://localhost:3000
Masuk admin@auditforge.local / admin12345   (login memakai EMAIL)

Mulai dari DEMO.md untuk tur berpandu.
EOF

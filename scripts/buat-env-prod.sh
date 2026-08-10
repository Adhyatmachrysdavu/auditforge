#!/usr/bin/env bash
# Buat berkas rahasia produksi berisi nilai acak.
#
#   ./scripts/buat-env-prod.sh [berkas-tujuan]      # bawaan: .env.prod
#
# Mengisi sendiri semua nilai yang ditandai [WAJIB DIGANTI] di .env.example,
# termasuk menyamakan sandi Postgres di dua tempat — kekeliruan paling mudah
# terjadi saat menyalin berkas contoh dengan tangan, dan akibatnya API gagal
# terhubung ke basis data tanpa penjelasan yang jelas.
#
# Berkas hasilnya TIDAK boleh di-commit; `.env.*` sudah ada di .gitignore.

set -euo pipefail

TUJUAN="${1:-.env.prod}"

if [ -e "$TUJUAN" ]; then
    echo "'$TUJUAN' sudah ada. Hapus atau pilih nama lain dulu — menimpanya" >&2
    echo "akan membuat basis data yang sudah berjalan tak dapat dihubungi lagi." >&2
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl tidak ditemukan. Pasang dulu, atau isi .env.prod secara manual." >&2
    exit 1
fi

acak() { openssl rand -hex "$1"; }

SECRET_KEY="$(acak 32)"
PG_PASS="$(acak 16)"
MINIO_PASS="$(acak 16)"
ADMIN_PASS="$(acak 12)"

cat > "$TUJUAN" <<EOF
# AuditForge — rahasia produksi. Dibuat $(date '+%Y-%m-%d %H:%M:%S').
# JANGAN di-commit dan jangan dikirim lewat kanal yang tak terenkripsi.

ENVIRONMENT=production

# --- Keamanan / autentikasi ---
SECRET_KEY=$SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=480

SEED_ADMIN_EMAIL=admin@auditforge.local
SEED_ADMIN_PASSWORD=$ADMIN_PASS
SEED_ADMIN_NAME=Administrator

# --- Basis data & broker ---
# Sandi di DATABASE_URL dan POSTGRES_PASSWORD sengaja dibuat sama.
DATABASE_URL=postgresql+psycopg://auditforge:$PG_PASS@postgres:5432/auditforge
POSTGRES_USER=auditforge
POSTGRES_PASSWORD=$PG_PASS
POSTGRES_DB=auditforge

REDIS_URL=redis://redis:6379/0

# --- Penyimpanan objek (MinIO) ---
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=auditforge
MINIO_SECRET_KEY=$MINIO_PASS
MINIO_BUCKET=auditforge
MINIO_SECURE=false

# --- Kecerdasan Buatan ---
# Isi AI_API_KEY dengan kunci OpenRouter/OpenAI, atau arahkan AI_BASE_URL ke
# model lokal bila data tak boleh keluar jaringan sendiri. Dapat juga diubah
# runtime lewat panel Admin tanpa build ulang.
AI_FORMAT=openai
AI_BASE_URL=https://openrouter.ai/api/v1
AI_API_KEY=
AI_MODEL=meta-llama/llama-3.3-70b-instruct:free

# --- Auto-ingest folder terpantau (R3) ---
WATCH_ENABLED=true
WATCH_DIR=/watch
WATCH_INTERVAL_SECONDS=30
WATCH_SETTLE_SECONDS=5
# Folder di HOST yang dipantau. Ubah bila tak ingin di dalam direktori repo.
WATCH_HOST_DIR=./datasets/watch

# --- Branding laporan ---
BRAND_ORG_NAME=PT Suryasoft Konsultama
BRAND_REPORT_TITLE=Laporan Audit Keamanan
BRAND_ACCENT=#1E5F9F
EOF

chmod 600 "$TUJUAN" 2>/dev/null || true

echo "Dibuat: $TUJUAN (izin 600)"
echo
echo "Kata sandi admin pertama — CATAT SEKARANG, ia tak ditampilkan lagi:"
echo
echo "    admin@auditforge.local"
echo "    $ADMIN_PASS"
echo
echo "Yang masih perlu kamu isi sendiri:"
echo "  - AI_API_KEY (boleh dikosongkan; LLM juga dapat diatur dari panel Admin)"
echo
echo "Lanjutkan dengan:"
echo "    export ENV_FILE=$TUJUAN"
echo "    docker compose --env-file $TUJUAN \\"
echo "      -f docker-compose.yml -f docker-compose.prod.yml up -d --build"

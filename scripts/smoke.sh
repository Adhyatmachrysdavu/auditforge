#!/usr/bin/env bash
# Pemeriksaan asap lapisan route — jalankan pada stack yang sedang menyala.
#
#   ./scripts/smoke.sh [base-url] [email] [sandi]
#   ./scripts/smoke.sh http://localhost:8000 admin@auditforge.local admin12345
#
# KENAPA INI ADA. Seluruh 222 tes pytest bersifat murni: tanpa DB, Redis, MinIO,
# maupun LLM, dan tak satu pun menyentuh lapisan route. Itu memang disengaja dan
# membuat suite-nya cepat — tetapi berarti cacat yang hidup di route lolos
# sepenuhnya. Dua kejadian nyata:
#
#   * `_assemble_report` kehilangan parameter setelah penggantian mekanis →
#     SELURUH endpoint laporan membalas 500, dan 164 tes tetap hijau.
#   * Nama penugasan ber-em-dash meruntuhkan header Content-Disposition →
#     report.pdf membalas 500, report.html tetap normal.
#
# Keduanya akan tertangkap skrip ini dalam hitungan detik. Ini bukan pengganti
# pytest, melainkan gerbang terakhir sebelum merge dan setelah deploy.
#
# Keluar dengan kode 1 bila ada satu saja pemeriksaan gagal.

set -uo pipefail

BASE="${1:-http://localhost:8000}"
EMAIL="${2:-admin@auditforge.local}"
SANDI="${3:-admin12345}"

LULUS=0
GAGAL=0

cek() {
    # cek <harapan> <metode> <jalur> [data]
    local harap="$1" metode="$2" jalur="$3" data="${4:-}"
    local kode
    if [ -n "$data" ]; then
        kode=$(curl -s -o /dev/null -w '%{http_code}' -X "$metode" "$BASE$jalur" \
            -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$data")
    else
        kode=$(curl -s -o /dev/null -w '%{http_code}' -X "$metode" "$BASE$jalur" \
            -H "Authorization: Bearer $TOKEN")
    fi
    if [ "$kode" = "$harap" ]; then
        LULUS=$((LULUS + 1))
        printf '  \033[32mok\033[0m   %-3s %s %s\n' "$kode" "$metode" "$jalur"
    else
        GAGAL=$((GAGAL + 1))
        printf '  \033[31mGAGAL\033[0m %s %s -> %s (harap %s)\n' "$metode" "$jalur" "$kode" "$harap"
    fi
}

echo "AuditForge — pemeriksaan asap terhadap $BASE"
echo

TOKEN=$(curl -s -X POST "$BASE/auth/login" -d "username=$EMAIL&password=$SANDI" \
    | python -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "  GAGAL: tak dapat masuk sebagai $EMAIL" >&2
    exit 1
fi
echo "  masuk sebagai $EMAIL"
echo

echo "Umum"
cek 200 GET /health
cek 200 GET /auth/me
cek 200 GET /users
cek 200 GET /stats
cek 200 GET /stats/timing
cek 200 GET /ingest
cek 200 GET /findings
cek 200 GET /knowledge
cek 200 GET /engagements
echo

EID=$(curl -s "$BASE/engagements" -H "Authorization: Bearer $TOKEN" \
    | python -c "import sys,json;d=json.load(sys.stdin);print(d[0]['id'] if d else '')" 2>/dev/null)
if [ -z "$EID" ]; then
    echo "  (tak ada penugasan — pemeriksaan per-penugasan dilewati)"
else
    echo "Penugasan #$EID"
    cek 200 GET "/engagements/$EID"
    cek 200 GET "/engagements/$EID/uploads"
    cek 200 GET "/engagements/$EID/findings"
    cek 200 GET "/engagements/$EID/members"
    cek 200 GET "/engagements/$EID/timing"
    cek 200 GET "/engagements/$EID/evaluation"

    FID=$(curl -s "$BASE/engagements/$EID/findings" -H "Authorization: Bearer $TOKEN" \
        | python -c "import sys,json;d=json.load(sys.stdin);print(d[0]['id'] if d else '')" 2>/dev/null)
    if [ -n "$FID" ]; then
        echo
        echo "Temuan #$FID"
        cek 200 GET "/engagements/$EID/findings/$FID"
        cek 200 GET "/engagements/$EID/findings/$FID/revisions"
        cek 200 GET "/engagements/$EID/findings/$FID/diff"
        cek 200 GET "/engagements/$EID/findings/$FID/attachments"
        cek 200 GET "/knowledge/suggest?finding_id=$FID"
    fi
fi

echo
# Laporan diuji untuk SETIAP penugasan, bukan hanya yang pertama. Cacat header
# Content-Disposition hanya muncul pada penugasan yang namanya memuat karakter
# di luar latin-1 — menguji satu penugasan saja akan melewatkannya.
echo "Laporan seluruh penugasan (tiga format)"
for e in $(curl -s "$BASE/engagements" -H "Authorization: Bearer $TOKEN" \
    | python -c "import sys,json;print(' '.join(str(x['id']) for x in json.load(sys.stdin)))" 2>/dev/null); do
    cek 200 GET "/engagements/$e/report.html"
    cek 200 GET "/engagements/$e/report.docx"
    cek 200 GET "/engagements/$e/report.pdf"
done

echo
echo "Penolakan yang harus tetap berlaku"
cek 404 GET "/engagements/99999"
cek 400 DELETE "/engagements/$EID" '{"confirm_name":"salah"}'

echo
echo "  $LULUS lulus, $GAGAL gagal"
[ "$GAGAL" -eq 0 ] || exit 1

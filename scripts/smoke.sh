#!/usr/bin/env bash
# Pemeriksaan asap lapisan route — jalankan pada stack yang sedang menyala.
#
#   ./scripts/smoke.sh [base-url] [email] [sandi] [email-analis] [sandi-analis]
#   ./scripts/smoke.sh http://localhost:8000 admin@auditforge.local admin12345
#
# Dua argumen terakhir opsional. Bila diisi, penolakan RBAC retest ikut diuji
# sebagai analis sungguhan; bila tidak, bagian itu menandai dirinya "lewat".
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
# Bagian terakhir keluar dari lapisan route: ia membandingkan aturan pengenalan
# perkakas di frontend dengan yang di backend. Bagian itu butuh kontainer lokal,
# dan akan menandai dirinya "lewat" bila tak ada — bukan diam-diam lulus.
#
# Keluar dengan kode 1 bila ada satu saja pemeriksaan gagal.

set -uo pipefail

BASE="${1:-http://localhost:8000}"
EMAIL="${2:-admin@auditforge.local}"
SANDI="${3:-admin12345}"
# Opsional. Bila diisi, penolakan RBAC retest diuji ujung ke ujung sebagai
# analis sungguhan. Tanpa ini bagian itu menandai dirinya "lewat" secara
# terlihat — server sungguhan tak punya akun analis bawaan, dan skrip ini
# tidak boleh membuat akun demi sebuah pemeriksaan.
ANALIS_EMAIL="${4:-}"
ANALIS_SANDI="${5:-}"

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

cek_sniff() {
    local fx="$AKAR/datasets/fixtures"
    # Dilewati harus TERLIHAT, bukan dianggap lulus: skrip ini juga dipakai
    # menembak server jarak jauh, dan di sana kontainernya memang tak ada.
    if [ ! -d "$fx" ]; then
        printf '  \033[33mlewat\033[0m  %s tak ada\n' "$fx"
        return
    fi
    for k in auditforge-api-1 auditforge-web-1; do
        if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$k"; then
            printf '  \033[33mlewat\033[0m  kontainer %s tak berjalan\n' "$k"
            return
        fi
    done

    # Git Bash mengubah jalur mirip Unix pada argumen docker; di Linux tak berefek.
    # Ia mematikan konversi untuk KEDUA sisi, dan itu yang menjebak: tujuan di
    # dalam kontainer memang harus dibiarkan apa adanya, tetapi jalur sumber di
    # host justru butuh dikonversi. Karena itu sumbernya ditulis relatif dari
    # akar repo — jalur relatif tak pernah disentuh MSYS.
    export MSYS_NO_PATHCONV=1
    local tmp=/tmp/af-sniff-fx
    for k in auditforge-api-1 auditforge-web-1; do
        # Hapus dulu: `docker cp` ke direktori yang sudah ada akan menyarangkan
        # salinannya (…/af-sniff-fx/fixtures) alih-alih menimpanya.
        docker exec "$k" rm -rf "$tmp" >/dev/null 2>&1
        ( cd "$AKAR" && docker cp datasets/fixtures "$k:$tmp" ) >/dev/null 2>&1 || {
            printf '  \033[31mGAGAL\033[0m tak dapat menyalin berkas contoh ke %s\n' "$k"
            GAGAL=$((GAGAL + 1))
            return
        }
    done

    local be fe
    be=$(docker exec -i auditforge-api-1 python - <<'PY' 2>/dev/null
import pathlib
from app.parsers import select_parser
for f in sorted(pathlib.Path("/tmp/af-sniff-fx").iterdir()):
    if f.is_file():
        t = getattr(select_parser(None, f.name, f.read_bytes()), "tool", None)
        print(f"{f.name}\t{getattr(t, 'value', None) or '-'}")
PY
    )
    # Node 22 memuat TypeScript langsung dengan --experimental-strip-types,
    # jadi yang diuji berkas sumber yang sesungguhnya, bukan salinan terkompilasi
    # yang bisa saja tertinggal versi.
    fe=$(docker exec -i auditforge-web-1 node --experimental-strip-types - <<'JS' 2>/dev/null
const fs = require("fs");
const { sniffTool } = require("/app/src/lib/sniff.ts");
for (const n of fs.readdirSync("/tmp/af-sniff-fx").sort()) {
  const p = "/tmp/af-sniff-fx/" + n;
  if (!fs.statSync(p).isFile()) continue;
  console.log(n + "\t" + (sniffTool(n, fs.readFileSync(p, "utf8")) || "-"));
}
JS
    )

    if [ -z "$be" ] || [ -z "$fe" ]; then
        printf '  \033[31mGAGAL\033[0m salah satu sisi tak menghasilkan keluaran\n'
        GAGAL=$((GAGAL + 1))
        return
    fi

    local nama sisi_be sisi_fe
    while IFS=$'\t' read -r nama sisi_be; do
        [ -n "$nama" ] || continue
        sisi_fe=$(printf '%s\n' "$fe" | awk -F'\t' -v n="$nama" '$1==n {print $2}')
        if [ "$sisi_be" = "$sisi_fe" ]; then
            LULUS=$((LULUS + 1))
            printf '  \033[32mok\033[0m   %-28s %s\n' "$nama" "$sisi_be"
        else
            GAGAL=$((GAGAL + 1))
            printf '  \033[31mGAGAL\033[0m %-28s backend=%s frontend=%s\n' \
                "$nama" "$sisi_be" "${sisi_fe:-(tak ada)}"
        fi
    done <<< "$be"
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
        # R4: payload temuan wajib memuat usulan remediasi yang SAH. Field ini
        # dihitung, jadi serialisasi yang putus tak akan membuat satu pun
        # endpoint membalas selain 200. Nilainya ikut diperiksa, bukan hanya
        # keberadaan kuncinya: `remediation_proposal` punya nilai bawaan
        # "not_tested", sehingga memeriksa kuncinya saja nyaris tak menambah
        # daya deteksi di atas cek 200 tepat di atas ini.
        if curl -s "$BASE/engagements/$EID/findings" -H "Authorization: Bearer $TOKEN" \
            | python -c '
import sys, json
sah = {"not_tested", "open", "fixed", "recurring"}
d = json.load(sys.stdin)
assert d, "daftar temuan kosong"
buruk = [f["id"] for f in d if f.get("remediation_proposal") not in sah]
assert not buruk, buruk
' 2>/dev/null; then
            LULUS=$((LULUS + 1))
            printf '  \033[32mok\033[0m   remediation_proposal sah di seluruh temuan\n'
        else
            GAGAL=$((GAGAL + 1))
            printf '  \033[31mGAGAL\033[0m remediation_proposal hilang atau tak sah\n'
        fi
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
# Hanya bila ada penugasan. Pada basis data yang masih kosong, $EID kosong dan
# jalurnya menjadi "/engagements/", yang dibalas 308 oleh pengalihan slash —
# kegagalan palsu yang menyamarkan hasil sesungguhnya.
if [ -n "$EID" ]; then
    cek 400 DELETE "/engagements/$EID" '{"confirm_name":"salah"}'
    if [ -n "$FID" ]; then
        cek 400 PATCH "/engagements/$EID/findings/$FID/remediation" '{"status":"ngawur"}'
    else
        printf '  [33mlewat[0m  validasi status remediasi (belum ada temuan)
'
    fi
else
    printf '  [33mlewat[0m  penolakan hapus (belum ada penugasan)
'
fi


# Spec R4 bagian 10: analis dilarang menegaskan remediasi. Penolakan itu dijaga
# permanen oleh `tests/test_retest_rbac.py`, yang memanggil dependency perannya
# langsung dari pohon route sehingga selalu ikut berjalan di pytest. Di sini ia
# diuji sekali lagi menembus HTTP sungguhan, sebab tes murni tak dapat
# membuktikan bahwa token analis benar-benar dibalas 403 oleh server yang hidup.
if [ -n "$EID" ] && [ -n "$FID" ] && [ -n "$ANALIS_EMAIL" ]; then
    TOKEN_ADMIN="$TOKEN"
    TOKEN=$(curl -s -X POST "$BASE/auth/login"         -d "username=$ANALIS_EMAIL&password=$ANALIS_SANDI"         | python -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
    if [ -z "$TOKEN" ]; then
        GAGAL=$((GAGAL + 1))
        printf '  [31mGAGAL[0m tak dapat masuk sebagai analis %s
' "$ANALIS_EMAIL"
    else
        # Pastikan akunnya BENAR-BENAR analis sebelum menembak. Kedua permintaan
        # di bawah adalah mutasi sungguhan: bila akun yang diberikan ternyata
        # berhak, ia tidak dibalas 403 melainkan BERHASIL, menaikkan putaran
        # penugasan dan menimpa status remediasi sebuah temuan. Skrip ini juga
        # ditembakkan ke server produksi, jadi salah kredensial harus berhenti
        # di sini, bukan berakhir sebagai kerusakan data.
        PERAN=$(curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN"             | python -c "import sys,json;print(json.load(sys.stdin).get('role',''))" 2>/dev/null)
        if [ "$PERAN" != "analyst" ]; then
            GAGAL=$((GAGAL + 1))
            printf '  [31mGAGAL[0m %s berperan "%s", bukan analis — cek dibatalkan agar tak memutasi data
'                 "$ANALIS_EMAIL" "$PERAN"
        else
            cek 403 PATCH "/engagements/$EID/findings/$FID/remediation" '{"status":"fixed"}'
            cek 403 POST "/engagements/$EID/rounds"
        fi
    fi
    TOKEN="$TOKEN_ADMIN"
else
    printf '  [33mlewat[0m  penolakan analis (kredensial analis tak diberikan)
'
fi

echo
# Aturan pengenalan perkakas hidup di DUA tempat: `backend/app/parsers/*.sniff`
# dan `frontend/src/lib/sniff.ts`. Yang kedua meniru yang pertama agar dropdown
# unggah terisi sendiri sebelum berkas dikirim. Penyimpangan di antara keduanya
# tidak akan meruntuhkan apa pun — dropdown hanya menampilkan tebakan keliru
# sementara backend mengurai dengan benar — dan justru itu yang membuatnya
# berbahaya: tak ada galat, tak ada tes yang jatuh, tak ada yang menyadarinya.
# Di sini keduanya dijalankan atas berkas contoh yang sama lalu dibandingkan.
echo "Kesepadanan pengenalan perkakas (frontend vs backend)"
cek_sniff

echo
echo "  $LULUS lulus, $GAGAL gagal"
[ "$GAGAL" -eq 0 ] || exit 1

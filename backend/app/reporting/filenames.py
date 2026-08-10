"""Nama berkas pada header unduhan — deterministik, tanpa I/O.

Header HTTP hanya boleh memuat **latin-1**; Starlette meng-encode-nya begitu.
Sementara itu nama penugasan dan nama berkas bukti datang dari manusia, jadi ia
wajar memuat tanda pisah panjang, kutip melengkung, atau huruf beraksen. Satu
karakter semacam itu cukup membuat seluruh unduhan membalas 500 — teramati
sungguhan pada penugasan bernama "Audit Infrastruktur Internal — Fase 1".

Solusinya bentuk ganda sesuai RFC 6266/5987: `filename=` berisi versi ASCII
untuk peramban lama, `filename*=UTF-8''…` berisi nama aslinya untuk yang
modern. Dengan begitu tak ada yang gagal, dan tak ada nama yang hilang.
"""
from __future__ import annotations

import unicodedata
from urllib.parse import quote

_PENGGANTI = "laporan"

# Karakter yang tak boleh masuk nama berkas maupun header, apa pun kodenya:
# pemisah jalur bisa menulis ke luar direktori, kutip ganda memecah header.
_BERBAHAYA = {"/": "_", "\\": "_", '"': "", "\r": "", "\n": ""}


def ascii_fallback(name: str | None) -> str:
    """Versi ASCII yang aman dipakai di header latin-1.

    Huruf beraksen **diturunkan** ke padanan ASCII-nya (é → e) alih-alih
    dibuang, agar nama tetap terbaca. Yang benar-benar tak punya padanan
    diganti garis bawah.
    """
    teks = (name or "").strip()
    if not teks:
        return _PENGGANTI

    for jelek, ganti in _BERBAHAYA.items():
        teks = teks.replace(jelek, ganti)

    # NFKD memisahkan huruf dari tanda diakritiknya sehingga tanda itu dapat
    # dibuang tanpa menghilangkan hurufnya.
    terurai = unicodedata.normalize("NFKD", teks)
    hasil = []
    for ch in terurai:
        if unicodedata.combining(ch):
            continue
        hasil.append(ch if ch.isascii() else "_")

    bersih = "".join(hasil).strip(" ._")
    # Rapikan garis bawah beruntun agar nama tak berubah jadi deretan "_".
    while "__" in bersih:
        bersih = bersih.replace("__", "_")
    return bersih or _PENGGANTI


def content_disposition(filename: str | None, *, disposition: str = "attachment") -> str:
    """Nilai header `Content-Disposition` yang aman sekaligus lengkap.

    Selalu dapat di-encode sebagai latin-1, dan tetap membawa nama asli dalam
    bentuk `filename*` ber-persen-kode UTF-8.
    """
    asli = (filename or "").strip() or _PENGGANTI
    aman = ascii_fallback(asli)
    terkode = quote(asli, safe="")
    return f"{disposition}; filename=\"{aman}\"; filename*=UTF-8''{terkode}"

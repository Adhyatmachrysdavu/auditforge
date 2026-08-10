"""Pencocokan temuan lintas penugasan (Modul 3) — deterministik, tanpa DB.

`Finding.fingerprint` **tidak dapat dipakai** di sini: ia sengaja memuat host,
port, dan path agar dedup tidak pernah menggabungkan dua target berbeda. Justru
karena itu ia tak akan pernah cocok antar klien. Basis Pengetahuan membutuhkan
kebalikannya — membuang segala yang khas satu target, lalu membandingkan sisa
maknanya.

Tanpa LLM dan tanpa embedding: bobot besar pada kesamaan CWE, sisanya irisan
token judul. Auditor harus dapat menjelaskan kenapa dua temuan dianggap mirip.
"""
from __future__ import annotations

import re

# Bobot: CWE yang sama jauh lebih berarti daripada judul yang mirip, karena
# judul ditulis oleh perkakas yang berbeda-beda.
CWE_WEIGHT = 0.6
TITLE_WEIGHT = 0.4

STOPWORDS: frozenset[str] = frozenset(
    {
        # Inggris — bahasa keluaran perkakas.
        "a", "an", "and", "at", "detected", "detection", "for", "found", "in",
        "is", "of", "on", "or", "possible", "potential", "the", "to", "was",
        "with",
        # Indonesia — judul hasil suntingan auditor.
        "dan", "di", "atau", "pada", "yang", "terdeteksi", "ditemukan",
    }
)

_URL_RE = re.compile(r"https?://\S+")
_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
# Nama host dan nomor versi sama-sama berpola "kata.kata"; keduanya memang
# harus hilang karena keduanya khas satu target.
_HOST_RE = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
_PORT_RE = re.compile(r":\d+\b")
_NUM_RE = re.compile(r"\b\d+\b")
_NONWORD_RE = re.compile(r"[^a-z0-9\s]+")


def normalize_title(title: str) -> str:
    """Buang segala yang khas satu target, sisakan makna judulnya.

    Urutannya penting: URL lebih dulu (memuat host sekaligus port), lalu IP,
    host, port, angka berdiri sendiri, terakhir tanda baca.
    """
    text = (title or "").lower()
    text = _URL_RE.sub(" ", text)
    text = _IP_RE.sub(" ", text)
    text = _HOST_RE.sub(" ", text)
    text = _PORT_RE.sub(" ", text)
    text = _NUM_RE.sub(" ", text)
    text = _NONWORD_RE.sub(" ", text)
    kata = [w for w in text.split() if w and w not in STOPWORDS]
    return " ".join(kata)


def title_tokens(title_norm: str) -> set[str]:
    return set((title_norm or "").split())


def _clean_cwe(value: str | None) -> str:
    return (value or "").strip().upper()


def score_match(
    *,
    a_cwe: str | None,
    a_title_norm: str,
    b_cwe: str | None,
    b_title_norm: str,
) -> float:
    """Skor kemiripan 0..1 antara dua temuan.

    CWE kosong **tidak** dianggap cocok dengan CWE kosong lain: ketiadaan data
    bukan bukti kesamaan.
    """
    cwe_a, cwe_b = _clean_cwe(a_cwe), _clean_cwe(b_cwe)
    cwe_part = CWE_WEIGHT if (cwe_a and cwe_b and cwe_a == cwe_b) else 0.0

    ta, tb = title_tokens(a_title_norm), title_tokens(b_title_norm)
    overlap = len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0

    return round(cwe_part + TITLE_WEIGHT * overlap, 4)


def rank_matches(
    target: object,
    candidates: list,
    *,
    limit: int = 5,
    min_score: float = 0.3,
) -> list[tuple[object, float]]:
    """Kandidat termirip lebih dahulu; yang di bawah `min_score` dibuang.

    `target` dan tiap kandidat cukup memiliki atribut `cwe` dan `title_norm`,
    sehingga fungsi ini dapat diuji dengan `SimpleNamespace`.
    """
    scored: list[tuple[object, float]] = []
    for c in candidates:
        s = score_match(
            a_cwe=getattr(target, "cwe", None),
            a_title_norm=getattr(target, "title_norm", "") or "",
            b_cwe=getattr(c, "cwe", None),
            b_title_norm=getattr(c, "title_norm", "") or "",
        )
        if s >= min_score:
            scored.append((c, s))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]

"""Metrik evaluasi murni (D12) — tanpa I/O, dapat diuji penuh.

- `cluster_prf`: presisi/recall/F1 deduplikasi berbasis pasangan (pairwise). Dua
  temuan dianggap "pasangan positif" bila berada di kelompok yang sama. Metrik
  ini menghukum baik over-merge (FP) maupun under-merge (FN).
- `narrative_score`: skor heuristik offline draf naratif vs naratif rujukan
  (overlap token Jaccard per-field + kelengkapan struktur). Bukan penilai
  semantik; sebagai baseline keterlacakan mutu sampai golden auditor lengkap.
"""
from __future__ import annotations

import re
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from itertools import combinations


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


def _same_pairs(labels: Sequence[Hashable]) -> set[tuple[int, int]]:
    """Kumpulan pasangan indeks (i<j) yang berada di label/kelompok yang sama."""
    groups: dict[Hashable, list[int]] = {}
    for i, lab in enumerate(labels):
        groups.setdefault(lab, []).append(i)
    pairs: set[tuple[int, int]] = set()
    for members in groups.values():
        for a, b in combinations(sorted(members), 2):
            pairs.add((a, b))
    return pairs


def cluster_prf(gold: Sequence[Hashable], pred: Sequence[Hashable]) -> PRF:
    """Presisi/recall/F1 pengelompokan berbasis pasangan.

    `gold` & `pred` adalah label kelompok per-item pada urutan yang sama. Item
    dengan label sama dianggap satu kelompok. Tanpa pasangan positif sama sekali
    (semua unik dan benar) → presisi & recall = 1.0 (konvensi).
    """
    if len(gold) != len(pred):
        raise ValueError("panjang gold dan pred harus sama")
    gp = _same_pairs(gold)
    pp = _same_pairs(pred)
    tp = len(gp & pp)
    fp = len(pp - gp)
    fn = len(gp - pp)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return PRF(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        tp=tp,
        fp=fp,
        fn=fn,
    )


_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str | None) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def jaccard(a: str | None, b: str | None) -> float:
    """Kemiripan token Jaccard dua teks (0..1)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


_NARR_FIELDS = ("description", "impact", "recommendation")


def narrative_score(candidate: dict[str, str], reference: dict[str, str]) -> dict[str, object]:
    """Skor heuristik draf naratif vs rujukan.

    Kembalikan overlap per-field, `structure` (fraksi field terisi pada draf),
    dan `overlap` (rata-rata Jaccard antar field).
    """
    per_field = {
        f: round(jaccard(candidate.get(f), reference.get(f)), 4) for f in _NARR_FIELDS
    }
    filled = sum(1 for f in _NARR_FIELDS if (candidate.get(f) or "").strip())
    structure = round(filled / len(_NARR_FIELDS), 4)
    overlap = round(sum(per_field.values()) / len(_NARR_FIELDS), 4)
    return {"per_field": per_field, "structure": structure, "overlap": overlap}

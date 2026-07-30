"""Eval harness AuditForge (D12) — metrik mutu deterministik.

Mengukur pipeline inti (dedup, enrichment) terhadap *golden set* berlabel tanpa
LLM/data rahasia, plus scaffold penilaian naratif AI vs naratif auditor (§6.4).
Dijalankan via ``python -m app.eval.run``.
"""

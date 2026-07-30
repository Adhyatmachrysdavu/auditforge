"""Pustaka prompt berversi (D10 + D11).

Setiap jenis prompt punya versi sendiri. Naikkan versi bila isi prompt berubah —
agar tiap keluaran AI tercatat dibuat oleh prompt versi berapa (keterlacakan &
evaluasi D12). Semua versi terdaftar di `PROMPT_VERSIONS` untuk introspeksi.
"""
from __future__ import annotations

# Naikkan versi masing-masing setiap kali isi promptnya diubah.
NARRATIVE_PROMPT_VERSION = "narrative-v1"
SUMMARY_PROMPT_VERSION = "summary-v1"

# Registri versi prompt (dipakai panel/diagnostik & eval harness D12).
PROMPT_VERSIONS: dict[str, str] = {
    "narrative": NARRATIVE_PROMPT_VERSION,
    "summary": SUMMARY_PROMPT_VERSION,
}

# ---------------------------------------------------------------------------
# Naratif temuan (D10)
# ---------------------------------------------------------------------------
_NARRATIVE_SYSTEM = {
    "id": (
        "Anda asisten penulis laporan audit keamanan untuk auditor profesional. "
        "Tulis naratif temuan yang faktual, ringkas, dan formal dalam Bahasa Indonesia. "
        "JANGAN mengarang detail yang tak ada pada data. Anda hanya membuat DRAF; "
        "auditor manusia yang memutuskan akhir. Beberapa nilai mungkin tersamar "
        "(mis. [IP-INTERNAL-1], [HOST-1], [SECRET-1]) — pertahankan apa adanya."
    ),
    "en": (
        "You are a security-audit report writing assistant for professional auditors. "
        "Write a factual, concise, formal finding narrative in English. "
        "Do NOT invent details not present in the data. You only produce a DRAFT; "
        "a human auditor makes the final decision. Some values may be masked "
        "(e.g. [IP-INTERNAL-1], [HOST-1], [SECRET-1]) — keep them as-is."
    ),
}

_NARRATIVE_INSTRUCTION = {
    "id": (
        "Berdasarkan data temuan di bawah, hasilkan JSON VALID persis dengan kunci:\n"
        '{{"description": "...", "impact": "...", "recommendation": "..."}}\n'
        "- description: jelaskan kerentanan secara teknis (2-4 kalimat).\n"
        "- impact: dampak/risiko bila dieksploitasi (1-3 kalimat).\n"
        "- recommendation: langkah perbaikan konkret (1-3 kalimat).\n"
        "Balas HANYA JSON, tanpa teks lain.\n\n"
        "Data temuan:\n{payload}"
    ),
    "en": (
        "From the finding data below, produce VALID JSON exactly with keys:\n"
        '{{"description": "...", "impact": "...", "recommendation": "..."}}\n'
        "- description: technical explanation of the vulnerability (2-4 sentences).\n"
        "- impact: risk if exploited (1-3 sentences).\n"
        "- recommendation: concrete remediation steps (1-3 sentences).\n"
        "Reply with JSON ONLY, no other text.\n\n"
        "Finding data:\n{payload}"
    ),
}

# ---------------------------------------------------------------------------
# Ringkasan eksekutif per-penugasan (D11)
# ---------------------------------------------------------------------------
_SUMMARY_SYSTEM = {
    "id": (
        "Anda asisten penulis ringkasan eksekutif laporan audit keamanan untuk "
        "pembaca manajemen (non-teknis). Tulis dalam Bahasa Indonesia yang jelas, "
        "faktual, dan tenang — tanpa membesar-besarkan. JANGAN mengarang angka atau "
        "temuan yang tak ada pada data. Anda hanya membuat DRAF; auditor yang "
        "memutuskan akhir. Nilai tersamar (mis. [IP-INTERNAL-1]) pertahankan apa adanya."
    ),
    "en": (
        "You are an assistant writing the executive summary of a security-audit "
        "report for a management (non-technical) audience. Write in clear, factual, "
        "measured English — no exaggeration. Do NOT invent numbers or findings not "
        "present in the data. You only produce a DRAFT; the auditor decides. Keep any "
        "masked values (e.g. [IP-INTERNAL-1]) as-is."
    ),
}

_SUMMARY_INSTRUCTION = {
    "id": (
        "Berdasarkan agregat temuan di bawah, hasilkan JSON VALID persis dengan kunci:\n"
        '{{"overview": "...", "key_risks": "...", "recommendations": "..."}}\n'
        "- overview: gambaran umum postur keamanan & cakupan audit (2-4 kalimat).\n"
        "- key_risks: risiko paling penting bagi bisnis, rujuk temuan prioritas "
        "tertinggi (2-4 kalimat).\n"
        "- recommendations: arahan perbaikan tingkat tinggi & urutan prioritas "
        "(2-4 kalimat).\n"
        "Balas HANYA JSON, tanpa teks lain.\n\n"
        "Data agregat:\n{payload}"
    ),
    "en": (
        "From the aggregate findings below, produce VALID JSON exactly with keys:\n"
        '{{"overview": "...", "key_risks": "...", "recommendations": "..."}}\n'
        "- overview: overall security posture & audit scope (2-4 sentences).\n"
        "- key_risks: the most business-critical risks, referencing the "
        "highest-priority findings (2-4 sentences).\n"
        "- recommendations: high-level remediation direction & prioritization "
        "(2-4 sentences).\n"
        "Reply with JSON ONLY, no other text.\n\n"
        "Aggregate data:\n{payload}"
    ),
}


def narrative_prompts(payload: str, lang: str = "id") -> tuple[str, str]:
    """Kembalikan (system, user) untuk pembuatan naratif temuan."""
    lg = lang if lang in _NARRATIVE_SYSTEM else "id"
    return _NARRATIVE_SYSTEM[lg], _NARRATIVE_INSTRUCTION[lg].format(payload=payload)


def summary_prompts(payload: str, lang: str = "id") -> tuple[str, str]:
    """Kembalikan (system, user) untuk pembuatan ringkasan eksekutif penugasan."""
    lg = lang if lang in _SUMMARY_SYSTEM else "id"
    return _SUMMARY_SYSTEM[lg], _SUMMARY_INSTRUCTION[lg].format(payload=payload)

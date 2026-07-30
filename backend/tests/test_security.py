"""Uji keamanan D17 — jaminan masking (data sensitif tak keluar ke LLM) + RBAC.

Properti kritis AuditForge: SEMUA konten temuan melewati `llm.draft`, yang
menyamarkan data sensitif SEBELUM provider (mis. OpenRouter) melihatnya, lalu
mengembalikan nilai asli pada hasil. Uji ini mengunci properti itu tanpa DB/HTTP.
"""
from __future__ import annotations

from app.ai import llm
from app.review import APPROVAL_STATES, role_allows_transition


def test_draft_masks_sensitive_before_provider(monkeypatch):
    captured: dict[str, str] = {}

    class Stub:
        name = "stub"
        model = "stub"

        def generate(self, prompt: str, *, system=None, max_tokens=1024) -> str:
            captured["prompt"] = prompt
            return "Analisis: " + prompt  # echo agar bisa uji unmask

    monkeypatch.setattr(llm, "get_provider", lambda: Stub())

    raw = "Server 10.1.2.3 (db.internal.local) bocor password=SuperSecret123, kontak admin@corp.local"
    out = llm.draft(raw)

    seen = captured["prompt"]
    # Provider TIDAK boleh melihat nilai sensitif mentah.
    assert "10.1.2.3" not in seen
    assert "SuperSecret123" not in seen
    assert "db.internal.local" not in seen
    assert "admin@corp.local" not in seen
    # Placeholder harus ada sebagai gantinya.
    assert "[" in seen and "]" in seen


def test_draft_unmasks_reply(monkeypatch):
    class Stub:
        name = "stub"
        model = "stub"

        def generate(self, prompt: str, *, system=None, max_tokens=1024) -> str:
            return prompt  # kembalikan teks tersamar apa adanya

    monkeypatch.setattr(llm, "get_provider", lambda: Stub())
    out = llm.draft("Host 192.168.1.10 dengan token=abc123XYZsecret")
    # Nilai asli dipulihkan pada hasil (placeholder → nilai semula).
    assert "192.168.1.10" in out


def test_preview_masked_hides_internal_and_secrets():
    masked = llm.preview_masked(
        "IP 192.168.1.5 host app.internal user admin@corp.local secret_key=TopSecretValue1"
    )
    assert "192.168.1.5" not in masked
    assert "admin@corp.local" not in masked
    assert "TopSecretValue1" not in masked


def test_masking_covers_compound_secret_labels():
    # Hardening D17: label majemuk (underscore) kini ikut tersamar.
    for kv in ("access_token=abcXYZ123", "secret_key=shh999", "auth_token=zzz111"):
        masked = llm.preview_masked(f"config {kv} end")
        secret_val = kv.split("=", 1)[1]
        assert secret_val not in masked, f"{kv} tak tersamar"


def test_public_ip_and_domain_preserved():
    # Konteks publik dipertahankan (bukan data rahasia klien) agar naratif berguna.
    masked = llm.preview_masked("Rujukan publik 8.8.8.8 dan example.com untuk CVE")
    assert "8.8.8.8" in masked
    assert "example.com" in masked


def test_rbac_analyst_cannot_reach_approval_states():
    for target in APPROVAL_STATES:
        assert not role_allows_transition("analyst", target)
        assert role_allows_transition("auditor", target)
        assert role_allows_transition("admin", target)


def test_rbac_unknown_role_denied_everywhere():
    for target in ("in_review", "approved", "rejected", "false_positive", "draft"):
        assert not role_allows_transition("intruder", target)

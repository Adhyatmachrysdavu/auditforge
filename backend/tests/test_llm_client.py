"""Uji unit D9 — klien LLM terpusat memasang masking (stub provider, tanpa jaringan)."""
from __future__ import annotations

import app.ai.llm as llm
from app.ai.providers import AINotConfigured


class _StubProvider:
    """Provider palsu: merekam prompt yang diterima, balas teks tetap."""

    name = "stub"
    model = "stub-model"

    def __init__(self, reply: str = "Analisis untuk [IP-INTERNAL-1] selesai."):
        self.reply = reply
        self.seen_prompt: str | None = None

    def generate(self, prompt, *, system=None, max_tokens=1024):
        self.seen_prompt = prompt
        return self.reply


def test_prompt_is_masked_before_reaching_provider(monkeypatch):
    stub = _StubProvider()
    monkeypatch.setattr(llm, "get_provider", lambda: stub)

    out = llm.draft("Host 192.168.1.10 rentan; password=hunter2")

    # Provider TIDAK boleh menerima data sensitif asli.
    assert "192.168.1.10" not in stub.seen_prompt
    assert "hunter2" not in stub.seen_prompt
    assert "[IP-INTERNAL-1]" in stub.seen_prompt
    # Placeholder pada balasan dikembalikan ke nilai asli.
    assert "192.168.1.10" in out


def test_retry_then_success(monkeypatch):
    calls = {"n": 0}

    class Flaky(_StubProvider):
        def generate(self, prompt, *, system=None, max_tokens=1024):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("galat sesaat")
            return "ok"

    monkeypatch.setattr(llm, "get_provider", lambda: Flaky())
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)  # jangan menunggu di uji
    assert llm.draft("halo", retries=2) == "ok"
    assert calls["n"] == 2


def test_not_configured_is_not_retried(monkeypatch):
    calls = {"n": 0}

    class Unconfigured(_StubProvider):
        def generate(self, prompt, *, system=None, max_tokens=1024):
            calls["n"] += 1
            raise AINotConfigured("AI_API_KEY belum diisi")

    monkeypatch.setattr(llm, "get_provider", lambda: Unconfigured())
    try:
        llm.draft("halo", retries=3)
        raised = False
    except AINotConfigured:
        raised = True
    assert raised
    assert calls["n"] == 1  # tak ada retry untuk kesalahan konfigurasi


def test_preview_masked_does_not_call_llm(monkeypatch):
    def boom():
        raise AssertionError("provider tak boleh dipanggil")

    monkeypatch.setattr(llm, "get_provider", boom)
    masked = llm.preview_masked("IP 10.0.0.1 dan admin@corp.local")
    assert "10.0.0.1" not in masked
    assert "admin@corp.local" not in masked

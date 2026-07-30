"""Lapisan AI swappable untuk AuditForge.

Seluruh pemanggilan AI melewati `get_provider()`, sehingga pilihan model,
penyamaran data, dan pencatatan biaya terkelola di satu tempat. Provider
ditentukan oleh `AI_PROVIDER`:

- ``anthropic`` — Claude API (target produksi, model ``claude-opus-4-8``).
- ``ollama``    — LLM lokal (dev/demo gratis; data audit tak keluar dari mesin,
  selaras dengan prinsip on-premise AuditForge).

Antarmuka kedua provider identik (`ping`, `generate`), sehingga sisa aplikasi
tidak perlu tahu provider mana yang aktif.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.ai.config_store import LLMConfig, load_llm_config
from app.core.config import get_settings

# Sanity-check singkat untuk memverifikasi akses provider.
_PING_PROMPT = "Balas persis dengan: AuditForge OK"


class AINotConfigured(RuntimeError):
    """Provider AI belum siap dipakai (mis. kredensial belum diisi)."""


class AIProvider:
    """Antarmuka bersama semua provider AI."""

    name: str = "base"

    @property
    def model(self) -> str:  # pragma: no cover - antarmuka
        raise NotImplementedError

    def ping(self) -> str:
        """Minta balasan singkat untuk memverifikasi akses provider."""
        raise NotImplementedError

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> str:
        """Hasilkan teks dari prompt (dipakai mulai Sprint 2: naratif, ringkasan)."""
        raise NotImplementedError


class AnthropicProvider(AIProvider):
    """Provider Claude via Anthropic SDK (jalur produksi)."""

    name = "anthropic"

    def __init__(self, cfg: LLMConfig) -> None:
        self._cfg = cfg

    @property
    def model(self) -> str:
        return self._cfg.model

    def ping(self) -> str:
        return self.generate(_PING_PROMPT, max_tokens=64)

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> str:
        if not self._cfg.api_key:
            raise AINotConfigured("API key Anthropic belum diisi (.env / panel Admin)")
        import anthropic

        client = anthropic.Anthropic(api_key=self._cfg.api_key)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if b.type == "text").strip()


class OpenAICompatibleProvider(AIProvider):
    """Adapter format OpenAI-compatible (OpenRouter default; juga Ollama/OpenAI/dll).

    Cukup Base URL + API key + model. Endpoint: ``{base_url}/chat/completions``.
    Untuk OpenRouter, base_url = ``https://openrouter.ai/api/v1``.
    Untuk Ollama lokal, base_url = ``http://host.docker.internal:11434/v1`` (key apa saja).
    """

    name = "openai"

    def __init__(self, cfg: LLMConfig) -> None:
        self._base_url = cfg.base_url.rstrip("/")
        self._api_key = cfg.api_key
        self._model = cfg.model

    @property
    def model(self) -> str:
        return self._model

    def ping(self) -> str:
        return self.generate(_PING_PROMPT, max_tokens=32)

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> str:
        if not self._api_key:
            raise AINotConfigured("AI_API_KEY belum diisi (lihat .env / panel Admin)")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    # Header opsional OpenRouter (atribusi); tak wajib.
                    "HTTP-Referer": "https://auditforge.local",
                    "X-Title": "AuditForge",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            raise RuntimeError(
                f"LLM {self._base_url} menolak permintaan (HTTP {exc.response.status_code}): "
                f"{body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"LLM tak terjangkau di {self._base_url}: {exc}."
            ) from exc
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Respons LLM tak terduga: {str(data)[:300]}") from exc
        return (str(content) if content else "").strip()


class OllamaProvider(AIProvider):
    """Provider LLM lokal via Ollama (dev/demo gratis, on-premise)."""

    name = "ollama"

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    @property
    def model(self) -> str:
        return self._model

    def ping(self) -> str:
        return self.generate(_PING_PROMPT, max_tokens=32)

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=120,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama tak terjangkau di {self._base_url}: {exc}. "
                "Pastikan layanan Ollama berjalan dan modelnya tersedia."
            ) from exc
        data = resp.json()
        content = (data.get("message") or {}).get("content", "")
        return str(content).strip()


def get_provider() -> AIProvider:
    """Provider aktif dari konfigurasi efektif (DB `app_settings` → fallback `.env`).

    `ai_format`: ``openai`` → OpenAI-compatible (OpenRouter/Ollama/OpenAI),
    ``anthropic`` → Claude. Bila kosong, jatuh ke `ai_provider` (Ollama) lama.
    Tidak di-cache agar perubahan dari panel Admin langsung berlaku.
    """
    cfg = load_llm_config()
    fmt = (cfg.format or "").lower()
    if fmt == "openai":
        return OpenAICompatibleProvider(cfg)
    if fmt == "anthropic":
        return AnthropicProvider(cfg)
    # Fallback kompatibilitas: konfigurasi lama via AI_PROVIDER (Ollama lokal).
    if get_settings().ai_provider.lower() == "ollama":
        return OllamaProvider()
    raise ValueError(f"AI_FORMAT tak dikenal: {fmt!r} (pilih 'openai' atau 'anthropic')")

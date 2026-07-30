"""Lapisan masking (D9) — menyamarkan data sensitif sebelum teks dikirim ke LLM.

Deterministik, tanpa AI. Menyamarkan (dengan placeholder konsisten per nilai unik):
- **Kunci privat** (blok PEM `-----BEGIN … PRIVATE KEY-----`).
- **Kredensial** di URL (`scheme://user:pass@host`).
- **Header Authorization** (`Bearer`/`Basic <token>`).
- **Rahasia berlabel** (`password=…`, `api_key=…`, `token=…`, dll.).
- **Kunci akses AWS** (`AKIA…`).
- **Email**.
- **IP internal** (RFC1918, loopback, link-local).
- **Hostname internal** (sufiks `.local`/`.internal`/`.corp`/`.lan`/`.intranet`
  + domain klien tambahan).

Prinsip on-premise AuditForge: bila LLM berada di cloud (mis. OpenRouter), data
rahasia klien tak boleh keluar apa adanya. `mask_text()` mengembalikan teks
tersamar **beserta peta** placeholder→asli yang HANYA disimpan di sisi server
(untuk audit / potensi unmask hasil AI), tak pernah ikut terkirim ke LLM.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# Sufiks domain yang dianggap internal (disamarkan). Domain publik (mis.
# example.com) dibiarkan agar konteks temuan tetap berguna bagi LLM.
DEFAULT_INTERNAL_SUFFIXES: tuple[str, ...] = (
    ".local",
    ".internal",
    ".corp",
    ".lan",
    ".intranet",
)

_PRIVKEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_BASIC_AUTH_RE = re.compile(r"://([^/\s:@]+:[^/\s:@]+)@")
_AUTH_HEADER_RE = re.compile(
    r"(?i)(\bAuthorization\s*:\s*(?:Bearer|Basic)\s+)([A-Za-z0-9._\-+/=]+)"
)
# Label rahasia berlabel. Prefix `[\w-]*` menangkap bentuk majemuk (mis.
# `secret_key`, `access_token`, `auth_token`) yang lolos bila hanya mengandalkan
# `\b` sebelum kata inti (underscore = word-char → tak ada boundary). Kata inti
# tetap spesifik agar `key=`/`id=` biasa tak ikut tersamar (hindari false positive).
_SECRET_KV_RE = re.compile(
    r"(?i)\b([\w-]*(?:password|passwd|pwd|pass|secret|token|apikey|api[_-]?key|"
    r"access[_-]?key|secret[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?token))"
    r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOST_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}\b", re.IGNORECASE)


@dataclass
class MaskResult:
    """Teks tersamar + peta placeholder→nilai asli (rahasia, sisi server saja)."""

    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.mapping)


def _is_internal_ip(token: str) -> bool:
    try:
        ip = ipaddress.ip_address(token)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def _is_internal_host(host: str, suffixes: Sequence[str], extra: Sequence[str]) -> bool:
    h = host.lower().rstrip(".")
    if any(h == d.lower() or h.endswith("." + d.lower().lstrip(".")) for d in extra):
        return True
    return any(h.endswith(s) for s in suffixes)


def mask_text(
    text: str | None,
    *,
    internal_suffixes: Sequence[str] = DEFAULT_INTERNAL_SUFFIXES,
    extra_domains: Iterable[str] = (),
) -> MaskResult:
    """Samarkan data sensitif pada `text`. Placeholder konsisten per nilai unik."""
    if not text:
        return MaskResult(text=text or "", mapping={})

    extra = tuple(extra_domains)
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}
    seen: dict[tuple[str, str], str] = {}

    def placeholder(category: str, original: str) -> str:
        key = (category, original)
        if key in seen:
            return seen[key]
        counters[category] = counters.get(category, 0) + 1
        token = f"[{category}-{counters[category]}]"
        seen[key] = token
        mapping[token] = original
        return token

    out = text
    # Urutan penting: item paling spesifik dulu.
    out = _PRIVKEY_RE.sub(lambda m: placeholder("PRIVKEY", m.group(0)), out)
    out = _BASIC_AUTH_RE.sub(lambda m: "://" + placeholder("CRED", m.group(1)) + "@", out)
    out = _AUTH_HEADER_RE.sub(
        lambda m: m.group(1) + placeholder("SECRET", m.group(2)), out
    )
    out = _SECRET_KV_RE.sub(
        lambda m: m.group(1) + m.group(2) + placeholder("SECRET", m.group(3)), out
    )
    out = _AWS_KEY_RE.sub(lambda m: placeholder("SECRET", m.group(0)), out)
    out = _EMAIL_RE.sub(lambda m: placeholder("EMAIL", m.group(0)), out)
    out = _IPV4_RE.sub(
        lambda m: placeholder("IP-INTERNAL", m.group(0))
        if _is_internal_ip(m.group(0))
        else m.group(0),
        out,
    )
    out = _HOST_RE.sub(
        lambda m: placeholder("HOST", m.group(0))
        if _is_internal_host(m.group(0), internal_suffixes, extra)
        else m.group(0),
        out,
    )
    return MaskResult(text=out, mapping=mapping)


def unmask_text(text: str, mapping: dict[str, str]) -> str:
    """Kembalikan placeholder ke nilai asli (untuk hasil AI, sisi server)."""
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text

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

Lapisan yang sama juga menangkal **prompt injection** (OWASP LLM01): konten
temuan berasal dari berkas hasil scan yang diunggah pengguna, jadi bukan hanya
sistem yang diaudit yang bisa berisi muatan berbahaya — teks yang dikirim ke
LLM pun jadi permukaan serangan. Frasa yang menyerupai upaya membajak instruksi
(mis. "ignore previous instructions", token kendali gaya `<|im_start|>`/`[INST]`)
diganti token tetap `[SUSPECTED-INJECTION]` **sebelum** masking rahasia
lainnya, dan token itu sengaja TIDAK dimasukkan ke peta unmask — jika balasan
LLM mengulanginya, token itu tak pernah dikembalikan ke frasa aslinya.
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

# Pola upaya prompt injection / jailbreak pada konten temuan (berasal dari
# berkas scan pihak luar, jadi tak tepercaya). Tiap pola diberi label kategori
# agar pemanggil bisa menampilkan peringatan tanpa perlu tahu regex-nya.
# Sengaja permisif (boleh false-positive) — konsekuensi salah tangkap hanya
# frasa netral diganti token, bukan kebocoran/pembajakan instruksi ke LLM.
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "IGNORE-INSTRUCTIONS",
        re.compile(
            r"(?i)\b(?:ignore|disregard|forget)\b[^.\n]{0,40}\b(?:previous|above|prior|"
            r"earlier|all)\b[^.\n]{0,20}\b(?:instructions?|prompt|rules|guidelines)\b"
        ),
    ),
    (
        "OVERRIDE-SYSTEM",
        re.compile(
            r"(?i)\b(?:override|bypass)\b[^.\n]{0,30}\b(?:your|the|system)\b[^.\n]{0,20}"
            r"\b(?:instructions?|guidelines|rules|prompt)\b"
        ),
    ),
    (
        "ROLE-HIJACK",
        re.compile(
            r"(?i)\byou are now\b|\bpretend (?:you are|to be)\b|\bact as (?:if you (?:are|were)|a\s*[:\-])"
        ),
    ),
    (
        "REVEAL-SYSTEM-PROMPT",
        re.compile(
            r"(?i)\b(?:reveal|print|show|repeat)\b[^.\n]{0,20}\b(?:your|the)\b[^.\n]{0,15}"
            r"\b(?:system prompt|initial instructions|hidden instructions)\b"
        ),
    ),
    (
        "CONTROL-TOKEN",
        re.compile(
            r"<\|im_start\|>|<\|im_end\|>|\[/?INST\]|<<SYS>>|<</SYS>>|</?system>",
            re.IGNORECASE,
        ),
    ),
)


@dataclass
class MaskResult:
    """Teks tersamar + peta placeholder→nilai asli (rahasia, sisi server saja)."""

    text: str
    mapping: dict[str, str] = field(default_factory=dict)
    injection_flags: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.mapping)

    @property
    def injection_detected(self) -> bool:
        return bool(self.injection_flags)


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
    injection_flags: list[str] = []

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
    # Deteksi & netralkan upaya prompt injection dulu, sebelum masking rahasia.
    # Token pengganti TETAP (bukan lewat placeholder()) → tak masuk peta unmask.
    for label, pattern in _INJECTION_PATTERNS:
        if pattern.search(out):
            if label not in injection_flags:
                injection_flags.append(label)
            out = pattern.sub("[SUSPECTED-INJECTION]", out)
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
    return MaskResult(text=out, mapping=mapping, injection_flags=injection_flags)


def unmask_text(text: str, mapping: dict[str, str]) -> str:
    """Kembalikan placeholder ke nilai asli (untuk hasil AI, sisi server)."""
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text

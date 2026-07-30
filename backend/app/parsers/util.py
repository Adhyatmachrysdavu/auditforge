"""Utilitas kecil bersama antar-parser."""
from __future__ import annotations

import re
from typing import Any

_TAG = re.compile(r"<[^>]+>")


def strip_html(value: str | None) -> str | None:
    if not value:
        return value
    return _TAG.sub("", value).strip()


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]


def first(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def first_json_line(content: bytes) -> str | None:
    for raw in content.splitlines():
        s = raw.strip()
        if s:
            return s.decode("utf-8", "replace")
    return None

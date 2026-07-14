from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|bearer|password|secret|token|resume[_-]?url)", re.IGNORECASE)
SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]+"),
    re.compile(r"(?i)\bsk-[a-z0-9._\-]+"),
    re.compile(r"(?i)resume[_-]?url\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)https?://[^\s,;]*/resume/[^\s,;]+"),
]


def sanitize_text(value: str, max_length: int = 4000) -> str:
    cleaned = value[:max_length]
    for pattern in SENSITIVE_TEXT_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def sanitize_payload(value: Any, max_text_length: int = 4000) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, max_text_length)
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = sanitize_payload(item, max_text_length)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item, max_text_length) for item in value]
    return value

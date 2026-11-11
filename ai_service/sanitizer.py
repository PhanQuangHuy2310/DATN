"""PII and secret sanitization utilities (ISO/IEC 27001 & SOC 2 Privacy Criteria).

Scrubs sensitive user credentials, payment card numbers (PAN), and national identity
numbers (CCCD) from text before sending payloads to external cloud LLMs or third-party APIs.
"""

from __future__ import annotations

import re

# 13 to 16-digit credit card PANs (with optional spaces or dashes)
_PAN_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

# 12-digit Vietnamese CCCD/CMND numbers starting with 0
_CCCD_REGEX = re.compile(r"\b0\d{11}\b")

# Bearer tokens and key=value secrets
_SECRET_KEY_REGEX = re.compile(
    r"(?i)(bearer\s+[a-z0-9_\-\.]{20,}|(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?)"
)


def sanitize_prompt_text(text: str) -> str:
    """Mask PII and secrets before dispatching to external LLM (ISO 27001 / SOC 2 Privacy)."""
    if not text:
        return text
    text = _SECRET_KEY_REGEX.sub("[REDACTED_SECRET]", text)
    text = _PAN_REGEX.sub("[REDACTED_PAN]", text)
    text = _CCCD_REGEX.sub("[REDACTED_ID]", text)
    return text

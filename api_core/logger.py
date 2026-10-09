from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)((?:password|secret|token|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]+"),
    re.compile(r"postgres(?:ql)?://[^\s]+"),
)


def redact(value: object) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        if (
            pattern.pattern.startswith("(?i)(authorization")
            or "password|secret" in pattern.pattern
        ):
            text = pattern.sub(r"\1[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text.replace("\r", "\\r").replace("\n", "\\n")


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = redact(correlation_id)
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


logger = logging.getLogger("eas")

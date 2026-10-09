from __future__ import annotations

import hashlib
import unicodedata
from typing import Any

import rfc8785


class AuditCanonicalizationError(ValueError):
    pass


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise AuditCanonicalizationError("Audit object keys must be strings")
        return {_nfc(key): _nfc(item) for key, item in value.items()}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise AuditCanonicalizationError("Unsupported audit value")


def canonical_bytes(value: Any) -> bytes:
    try:
        return rfc8785.dumps(_nfc(value))
    except (rfc8785.CanonicalizationError, UnicodeError, ValueError) as exc:
        raise AuditCanonicalizationError("Audit event cannot be canonicalized") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

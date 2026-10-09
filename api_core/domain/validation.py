from __future__ import annotations

import html
import re
import unicodedata
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

HTML_TAG = re.compile(r"<[^>]+>")
SUPPORTED_TYPES = {"integer", "string"}
SUPPORTED_P0_TYPES = {"ACCESS", "EQUIPMENT", "LEAVE"}
COMMON_PROPERTY_KEYS = {"type"}
STRING_PROPERTY_KEYS = COMMON_PROPERTY_KEYS | {
    "enum",
    "format",
    "maxLength",
    "minLength",
}
INTEGER_PROPERTY_KEYS = COMMON_PROPERTY_KEYS | {"maximum", "minimum"}


class PayloadValidationError(ValueError):
    def __init__(self, errors: dict[str, list[str]]):
        super().__init__("Payload validation failed")
        self.errors = errors


def _add(errors: dict[str, list[str]], field: str, code: str) -> None:
    errors.setdefault(field, []).append(code)


def _normalized_string(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def validate_payload(
    *,
    type_code: str,
    payload: dict[str, Any],
    form_schema: dict[str, Any],
    requester_id: str,
    today: date | None = None,
) -> dict[str, Any]:
    """Validate and normalize one submitted P0 payload.

    This is a deliberately small JSON-schema profile. Unknown keywords and
    unsupported field types fail closed during config publication; this
    command validates only already-published schemas from that profile.
    """

    errors: dict[str, list[str]] = {}
    if not isinstance(payload, dict):
        raise PayloadValidationError({"$": ["OBJECT_REQUIRED"]})
    if type_code not in SUPPORTED_P0_TYPES:
        raise PayloadValidationError({"type_code": ["UNSUPPORTED_REQUEST_TYPE"]})

    properties = form_schema.get("properties")
    required = form_schema.get("required")
    if (
        form_schema.get("schema_version") != 1
        or form_schema.get("type") != "object"
        or form_schema.get("additionalProperties") is not False
    ):
        raise PayloadValidationError({"$schema": ["UNSUPPORTED_SCHEMA"]})
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise PayloadValidationError({"$schema": ["INVALID_SCHEMA"]})
    if (
        any(not isinstance(field, str) for field in required)
        or len(set(required)) != len(required)
        or not set(required).issubset(properties)
    ):
        raise PayloadValidationError({"$schema": ["INVALID_REQUIRED_FIELDS"]})

    schema_errors: list[str] = []
    for field, spec in properties.items():
        if not isinstance(field, str) or not isinstance(spec, dict):
            schema_errors.append("INVALID_PROPERTY_SCHEMA")
            continue
        expected = spec.get("type")
        if expected not in SUPPORTED_TYPES:
            schema_errors.append(f"{field}:UNSUPPORTED_FIELD_TYPE")
            continue
        allowed_keys = (
            STRING_PROPERTY_KEYS if expected == "string" else INTEGER_PROPERTY_KEYS
        )
        if set(spec) - allowed_keys:
            schema_errors.append(f"{field}:UNSUPPORTED_KEYWORD")
        if expected == "string":
            minimum = spec.get("minLength", 0)
            maximum = spec.get("maxLength", 2**31)
            if (
                isinstance(minimum, bool)
                or not isinstance(minimum, int)
                or isinstance(maximum, bool)
                or not isinstance(maximum, int)
                or minimum < 0
                or maximum < minimum
            ):
                schema_errors.append(f"{field}:INVALID_LENGTH_BOUNDS")
            if spec.get("format") not in {None, "date", "uuid"}:
                schema_errors.append(f"{field}:UNSUPPORTED_FORMAT")
            if "enum" in spec:
                enum = spec["enum"]
                if (
                    not isinstance(enum, list)
                    or not enum
                    or any(not isinstance(item, str) for item in enum)
                    or len(set(enum)) != len(enum)
                ):
                    schema_errors.append(f"{field}:INVALID_ENUM")
        else:
            minimum = spec.get("minimum", -(2**63))
            maximum = spec.get("maximum", 2**63 - 1)
            if (
                isinstance(minimum, bool)
                or not isinstance(minimum, int)
                or isinstance(maximum, bool)
                or not isinstance(maximum, int)
                or maximum < minimum
            ):
                schema_errors.append(f"{field}:INVALID_NUMERIC_BOUNDS")
    if schema_errors:
        raise PayloadValidationError({"$schema": sorted(set(schema_errors))})

    unknown = sorted(set(payload) - set(properties))
    for field in unknown:
        _add(errors, field, "UNKNOWN_FIELD")
    for field in required:
        if field not in payload:
            _add(errors, str(field), "REQUIRED")

    normalized: dict[str, Any] = {}
    for field, value in payload.items():
        spec = properties.get(field)
        if not isinstance(spec, dict):
            continue
        expected = spec.get("type")

        if expected == "string":
            if not isinstance(value, str):
                _add(errors, field, "STRING_REQUIRED")
                continue
            clean = _normalized_string(value)
            if HTML_TAG.search(html.unescape(clean)):
                _add(errors, field, "HTML_NOT_ALLOWED")
            if len(clean) < spec.get("minLength", 0):
                _add(errors, field, "TOO_SHORT")
            if len(clean) > spec.get("maxLength", 2**31):
                _add(errors, field, "TOO_LONG")
            if "enum" in spec and clean not in spec["enum"]:
                _add(errors, field, "NOT_ALLOWED")
            if spec.get("format") == "uuid":
                try:
                    clean = str(UUID(clean))
                except (ValueError, TypeError, AttributeError):
                    _add(errors, field, "INVALID_UUID")
            elif spec.get("format") == "date":
                try:
                    date.fromisoformat(clean)
                except ValueError:
                    _add(errors, field, "INVALID_DATE")
            normalized[field] = clean
        elif expected == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                _add(errors, field, "INTEGER_REQUIRED")
                continue
            if value < spec.get("minimum", -(2**63)):
                _add(errors, field, "BELOW_MINIMUM")
            if value > spec.get("maximum", 2**63 - 1):
                _add(errors, field, "ABOVE_MAXIMUM")
            normalized[field] = value
    if type_code == "LEAVE" and all(
        k in normalized for k in ("start_date", "end_date")
    ):
        try:
            start = date.fromisoformat(normalized["start_date"])
            end = date.fromisoformat(normalized["end_date"])
            business_today = today or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            if start < business_today:
                _add(errors, "start_date", "DATE_IN_PAST")
            if end < start:
                _add(errors, "end_date", "END_BEFORE_START")
            if (end - start).days + 1 > 30:
                _add(errors, "end_date", "RANGE_EXCEEDS_30_DAYS")
        except ValueError:
            pass
        try:
            normalized_requester_id = str(UUID(requester_id))
        except (ValueError, TypeError, AttributeError):
            raise PayloadValidationError(
                {"requester_id": ["INVALID_INTERNAL_ACTOR_ID"]}
            ) from None
        if normalized.get("handover_user_id") == normalized_requester_id:
            _add(errors, "handover_user_id", "REQUESTER_CANNOT_BE_HANDOVER")

    if type_code in {"LEAVE", "ACCESS"} and "amount_vnd" in normalized:
        _add(errors, "amount_vnd", "AMOUNT_NOT_ALLOWED")
    if type_code == "EQUIPMENT" and "amount_vnd" not in normalized:
        _add(errors, "amount_vnd", "REQUIRED")

    if errors:
        raise PayloadValidationError(errors)
    return normalized

from __future__ import annotations

import html
import re
import unicodedata
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from .plan_constraints import plan_business_errors
from .routing import ACCEPTOR_SLOTS, APPROVER_SLOTS, EXECUTOR_SLOTS

SCHEMA_ERROR_KEY = "$schema"
HTML_TAG = re.compile(r"<[^>]+>")
SUPPORTED_TYPES = {"integer", "string"}
SUPPORTED_P0_TYPES = {"ACCESS", "EQUIPMENT", "LEAVE"}
TYPE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,29}$")
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


def _validate_schema_structure(
    form_schema: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    properties = form_schema.get("properties")
    required = form_schema.get("required")
    if (
        form_schema.get("schema_version") != 1
        or form_schema.get("type") != "object"
        or form_schema.get("additionalProperties") is not False
    ):
        raise PayloadValidationError({SCHEMA_ERROR_KEY: ["UNSUPPORTED_SCHEMA"]})
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise PayloadValidationError({SCHEMA_ERROR_KEY: ["INVALID_SCHEMA"]})
    if (
        any(not isinstance(field, str) for field in required)
        or len(set(required)) != len(required)
        or not set(required).issubset(properties)
    ):
        raise PayloadValidationError({SCHEMA_ERROR_KEY: ["INVALID_REQUIRED_FIELDS"]})

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
        raise PayloadValidationError({SCHEMA_ERROR_KEY: sorted(set(schema_errors))})
    return properties, required


def _validate_field_value(
    field: str,
    value: Any,
    spec: dict[str, Any],
    errors: dict[str, list[str]],
) -> tuple[Any, bool]:
    expected = spec.get("type")
    if expected == "string":
        if not isinstance(value, str):
            _add(errors, field, "STRING_REQUIRED")
            return None, False
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
        return clean, True
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            _add(errors, field, "INTEGER_REQUIRED")
            return None, False
        if value < spec.get("minimum", -(2**63)):
            _add(errors, field, "BELOW_MINIMUM")
        if value > spec.get("maximum", 2**63 - 1):
            _add(errors, field, "ABOVE_MAXIMUM")
        return value, True
    return None, False


def _validate_leave_rules(
    normalized: dict[str, Any],
    requester_id: str,
    today: date | None,
    errors: dict[str, list[str]],
) -> None:
    if "start_date" in normalized and "end_date" in normalized:
        try:
            start = date.fromisoformat(normalized["start_date"])
            end = date.fromisoformat(normalized["end_date"])
            business_today = (
                today or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
            )
            if start < business_today:
                _add(errors, "start_date", "DATE_IN_PAST")
            if end < start:
                _add(errors, "end_date", "END_BEFORE_START")
            if (end - start).days + 1 > 30:
                _add(errors, "end_date", "RANGE_EXCEEDS_30_DAYS")
        except ValueError:
            pass
    if "handover_user_id" in normalized:
        try:
            normalized_requester_id = str(UUID(requester_id))
            if normalized.get("handover_user_id") == normalized_requester_id:
                _add(errors, "handover_user_id", "REQUESTER_CANNOT_BE_HANDOVER")
        except (ValueError, TypeError, AttributeError):
            raise PayloadValidationError(
                {"requester_id": ["INVALID_INTERNAL_ACTOR_ID"]}
            ) from None


def _normalize_payload(
    payload: dict[str, Any],
    properties: dict[str, Any],
    errors: dict[str, list[str]],
) -> dict[str, Any]:
    unknown = sorted(set(payload) - set(properties))
    for field in unknown:
        _add(errors, field, "UNKNOWN_FIELD")

    normalized: dict[str, Any] = {}
    for field, value in payload.items():
        spec = properties.get(field)
        if not isinstance(spec, dict):
            continue
        clean_val, is_valid = _validate_field_value(field, value, spec, errors)
        if is_valid and clean_val is not None:
            normalized[field] = clean_val
    return normalized


def validate_payload(
    *,
    type_code: str,
    payload: dict[str, Any],
    form_schema: dict[str, Any],
    requester_id: str,
    today: date | None = None,
) -> dict[str, Any]:
    """Validate and normalize a submitted payload from a published configuration.

    This is a deliberately small JSON-schema profile. Unknown keywords and
    unsupported field types fail closed during config publication; this
    command validates only already-published schemas from that profile.
    """
    errors: dict[str, list[str]] = {}
    if not isinstance(payload, dict):
        raise PayloadValidationError({"$": ["OBJECT_REQUIRED"]})
    if not isinstance(type_code, str) or not TYPE_CODE_RE.fullmatch(type_code):
        raise PayloadValidationError({"type_code": ["INVALID_REQUEST_TYPE"]})

    properties, required = _validate_schema_structure(form_schema)

    for field in required:
        if field not in payload:
            _add(errors, str(field), "REQUIRED")

    normalized = _normalize_payload(payload, properties, errors)

    if type_code in {"LEAVE", "LEAVE_SPECIAL"}:
        _validate_leave_rules(normalized, requester_id, today, errors)

    if type_code in {"LEAVE", "ACCESS"} and "amount_vnd" in normalized:
        _add(errors, "amount_vnd", "AMOUNT_NOT_ALLOWED")
    if type_code == "EQUIPMENT" and "amount_vnd" not in normalized:
        _add(errors, "amount_vnd", "REQUIRED")

    for field, messages in plan_business_errors(type_code, normalized).items():
        errors.setdefault(field, []).extend(messages)
    if errors:
        raise PayloadValidationError(errors)
    return normalized


def validate_draft_payload(
    *,
    type_code: str,
    payload: dict[str, Any],
    form_schema: dict[str, Any],
    requester_id: str,
    today: date | None = None,
) -> dict[str, Any]:
    """Validate partial draft payload without enforcing 'required' fields."""

    errors: dict[str, list[str]] = {}
    if not isinstance(payload, dict):
        raise PayloadValidationError({"$": ["OBJECT_REQUIRED"]})
    if not isinstance(type_code, str) or not TYPE_CODE_RE.fullmatch(type_code):
        raise PayloadValidationError({"type_code": ["INVALID_REQUEST_TYPE"]})

    properties = form_schema.get("properties")
    if (
        form_schema.get("schema_version") != 1
        or form_schema.get("type") != "object"
        or form_schema.get("additionalProperties") is not False
        or not isinstance(properties, dict)
    ):
        raise PayloadValidationError({SCHEMA_ERROR_KEY: ["UNSUPPORTED_SCHEMA"]})

    normalized = _normalize_payload(payload, properties, errors)

    if type_code in {"LEAVE", "LEAVE_SPECIAL"}:
        _validate_leave_rules(normalized, requester_id, today, errors)

    if type_code in {"LEAVE", "ACCESS"} and "amount_vnd" in normalized:
        _add(errors, "amount_vnd", "AMOUNT_NOT_ALLOWED")

    if errors:
        raise PayloadValidationError(errors)
    return normalized


def _validate_route_rules_config(
    route_rules: dict[str, Any], lifecycle: str, errs: list[str]
) -> None:
    rules = route_rules.get("rules")
    if not isinstance(rules, list) or len(rules) == 0:
        errs.append("route_rules:rules must be non-empty array")
        return

    default_count = 0
    rule_ids = set()
    priorities = set()
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errs.append(f"route_rules:rules[{idx}] must be object")
            continue
        r_id = rule.get("id")
        if not isinstance(r_id, str) or not r_id.strip():
            errs.append(f"route_rules:rules[{idx}]:missing id")
        elif r_id in rule_ids:
            errs.append(f"route_rules:duplicate rule id {r_id}")
        else:
            rule_ids.add(r_id)

        approvers = rule.get("approvers")
        if not isinstance(approvers, list) or not (1 <= len(approvers) <= 5):
            errs.append(f"route_rules:rules[{idx}]:approvers must be 1..5 items")
        else:
            for app in approvers:
                if app not in APPROVER_SLOTS:
                    errs.append(f"route_rules:unknown approver {app}")

        is_default = rule.get("default") is True
        if is_default:
            default_count += 1
            if "when" in rule or "priority" in rule:
                errs.append(
                    f"route_rules:rules[{idx}]:default rule cannot have when/priority"
                )
        else:
            prio = rule.get("priority")
            if isinstance(prio, bool) or not isinstance(prio, int) or prio <= 0:
                errs.append(
                    f"route_rules:rules[{idx}]:priority must be positive integer"
                )
            elif prio in priorities:
                errs.append(f"route_rules:duplicate priority {prio}")
            else:
                priorities.add(prio)

            when = rule.get("when")
            if not isinstance(when, dict) or len(when) == 0:
                errs.append(f"route_rules:rules[{idx}]:when must be non-empty object")
            else:
                for k, v in when.items():
                    if k not in {
                        "amount_gt",
                        "amount_gte",
                        "days_gt",
                        "app_code_in",
                    }:
                        errs.append(f"route_rules:unknown condition operator {k}")
                    elif k in {"amount_gt", "amount_gte"}:
                        if (
                            isinstance(v, bool)
                            or not isinstance(v, int)
                            or not (0 <= v <= 1_000_000_000_000)
                        ):
                            errs.append(
                                f"route_rules:invalid amount condition value {v}"
                            )
                    elif k == "days_gt":
                        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                            errs.append(
                                f"route_rules:invalid days_gt condition value {v}"
                            )
                    elif k == "app_code_in" and (
                        not isinstance(v, list)
                        or len(v) == 0
                        or not all(isinstance(x, str) and x.strip() for x in v)
                    ):
                        errs.append(
                            f"route_rules:invalid app_code_in condition value {v}"
                        )

    if default_count != 1 or rules[-1].get("default") is not True:
        errs.append("route_rules:exactly one final default rule required")

    executor = route_rules.get("executor")
    acceptor = route_rules.get("acceptor")
    if lifecycle == "A" and (executor is not None or acceptor is not None):
        errs.append("route_rules:lifecycle A requires null executor and acceptor")
    elif lifecycle == "B" and (
        executor not in EXECUTOR_SLOTS or executor is None or acceptor is not None
    ):
        errs.append(
            "route_rules:lifecycle B requires a valid executor and null acceptor"
        )
    elif lifecycle == "C" and (
        executor not in EXECUTOR_SLOTS
        or executor is None
        or acceptor not in ACCEPTOR_SLOTS
        or acceptor is None
    ):
        errs.append(
            "route_rules:lifecycle C requires valid executor and acceptor"
        )


def _validate_sla_profile_config(
    sla_profile: dict[str, Any], lifecycle: str, errs: list[str]
) -> None:
    clock = sla_profile.get("clock")
    reminder_fraction = sla_profile.get("reminder_fraction")
    if clock != "CALENDAR_UTC":
        errs.append("sla_profile:clock must be CALENDAR_UTC")
    if reminder_fraction != 0.5:
        errs.append("sla_profile:reminder_fraction must be 0.5")

    app_h = sla_profile.get("approval_hours")
    exec_h = sla_profile.get("execution_hours")
    acc_h = sla_profile.get("acceptance_hours")

    if isinstance(app_h, bool) or not isinstance(app_h, int) or not (1 <= app_h <= 720):
        errs.append("sla_profile:approval_hours must be integer 1..720")

    if lifecycle == "A":
        if exec_h is not None or acc_h is not None:
            errs.append(
                "sla_profile:lifecycle A requires null execution_hours and acceptance_hours"
            )
    elif lifecycle == "B":
        if (
            isinstance(exec_h, bool)
            or not isinstance(exec_h, int)
            or not (1 <= exec_h <= 720)
            or acc_h is not None
        ):
            errs.append(
                "sla_profile:lifecycle B requires execution_hours 1..720 and null acceptance_hours"
            )
    elif lifecycle == "C":
        if (
            isinstance(exec_h, bool)
            or not isinstance(exec_h, int)
            or not (1 <= exec_h <= 720)
        ):
            errs.append(
                "sla_profile:lifecycle C requires execution_hours integer 1..720"
            )
        if (
            isinstance(acc_h, bool)
            or not isinstance(acc_h, int)
            or not (1 <= acc_h <= 720)
        ):
            errs.append(
                "sla_profile:lifecycle C requires acceptance_hours integer 1..720"
            )


def _check_release_docs_version(jsons: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for name, doc in jsons.items():
        if not isinstance(doc, dict):
            errs.append(f"{name}:MUST_BE_OBJECT")
            continue
        if doc.get("schema_version") != 1:
            errs.append(f"{name}:SCHEMA_VERSION_MUST_BE_1")
    return errs


def _check_form_schema_doc(form_schema: dict[str, Any], errs: list[str]) -> None:
    if form_schema.get("type") != "object":
        errs.append("form_schema:type must be object")
    if form_schema.get("additionalProperties") is not False:
        errs.append("form_schema:additionalProperties must be false")
    properties = form_schema.get("properties")
    required = form_schema.get("required")
    if not isinstance(properties, dict):
        errs.append("form_schema:properties must be object")
    if not isinstance(required, list):
        errs.append("form_schema:required must be array")
    elif isinstance(properties, dict):
        for req_field in required:
            if not isinstance(req_field, str) or req_field not in properties:
                errs.append(f"form_schema:required field {req_field} not in properties")


def validate_config_release_payload(
    *,
    lifecycle: str,
    form_schema: dict[str, Any],
    route_rules: dict[str, Any],
    actor_bindings: dict[str, Any],
    sla_profile: dict[str, Any],
) -> list[str]:
    """Validate 4 configuration release JSON documents against guard_release rules."""
    jsons = {
        "form_schema": form_schema,
        "route_rules": route_rules,
        "actor_bindings": actor_bindings,
        "sla_profile": sla_profile,
    }
    errs = _check_release_docs_version(jsons)
    if errs:
        return errs

    _check_form_schema_doc(form_schema, errs)

    departments = actor_bindings.get("departments")
    if not isinstance(departments, dict):
        errs.append("actor_bindings:departments must be object")

    _validate_route_rules_config(route_rules, lifecycle, errs)
    _validate_sla_profile_config(sla_profile, lifecycle, errs)

    return errs

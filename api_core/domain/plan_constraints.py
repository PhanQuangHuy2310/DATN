"""Additional plan.docx and enterprise 5-level submission rules for canonical request types.

Rules operate on already-normalized, server-validated payloads and never grant
any approval or bypass published policy/actor scope. No external data is assumed.
"""

import re
from datetime import date, datetime


def plan_business_errors(type_code: str, values: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    def reject(name, message):
        errors.setdefault(name, []).append(message)

    # The plan defines three exclusive monetary advance bands.
    value = values.get("amount")
    if isinstance(value, int) and not isinstance(value, bool):
        if type_code == "ADVANCE_SMALL" and value >= 10_000_000:
            reject("amount", "ADVANCE_AMOUNT_MUST_BE_BELOW_10M")
        if type_code == "ADVANCE_MEDIUM" and not (10_000_000 <= value <= 50_000_000):
            reject("amount", "ADVANCE_AMOUNT_MUST_BE_BETWEEN_10M_AND_50M")
        if type_code == "ADVANCE_LARGE" and value <= 50_000_000:
            reject("amount", "ADVANCE_AMOUNT_MUST_BE_OVER_50M")

    # Leave start/end, resubmission retains the backend's state and authorization checks.
    if type_code in ("LEAVE_ANNUAL", "LEAVE_LONG"):
        try:
            begin = date.fromisoformat(values["start_date"])
            end = date.fromisoformat(values["end_date"])
            if end < begin:
                reject("end_date", "END_BEFORE_START")
            elif type_code == "LEAVE_LONG" and (end - begin).days + 1 <= 2:
                reject("end_date", "LEAVE_LONG_REQUIRES_MORE_THAN_TWO_DAYS")
            elif type_code == "LEAVE_ANNUAL" and (end - begin).days + 1 >= 3:
                reject("end_date", "USE_LONG_LEAVE_FOR_THREE_OR_MORE_DAYS")
        except (KeyError, ValueError, TypeError):
            pass  # base schema already rejects date parsing errors

    if type_code == "ROOM_VEHICLE":
        try:
            start = datetime.fromisoformat(values["start_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(values["end_time"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None:
                reject("start_time", "TIMEZONE_REQUIRED")
            elif end <= start:
                reject("end_time", "END_MUST_BE_AFTER_START")
        except (KeyError, ValueError, TypeError, AttributeError):
            reject("start_time", "INVALID_ISO_DATETIME")
    # The new business-menu examples specify a few cross-field invariants.
    if (
        type_code == "WAREHOUSE_TRANSFER"
        and values.get("source_warehouse")
        and values.get("destination_warehouse")
        and values["source_warehouse"].casefold()
        == values["destination_warehouse"].casefold()
    ):
        reject("destination_warehouse", "SOURCE_AND_DESTINATION_MUST_DIFFER")
    if (
        type_code == "BUDGET_REALLOCATION"
        and values.get("source_budget_code")
        and values.get("target_budget_code")
        and values["source_budget_code"].casefold()
        == values["target_budget_code"].casefold()
    ):
        reject("target_budget_code", "SOURCE_AND_TARGET_BUDGET_MUST_DIFFER")
    if type_code == "SPECIAL_DISCOUNT":
        deal_val = values.get("deal_value_vnd")
        disc_val = values.get("amount_vnd")
        if (
            isinstance(deal_val, int)
            and isinstance(disc_val, int)
            and disc_val > deal_val
        ):
            reject("amount_vnd", "DISCOUNT_EXCEEDS_DEAL_VALUE")
    if type_code == "FLASH_SALE_VOUCHER":
        try:
            if date.fromisoformat(values["end_date"]) < date.fromisoformat(
                values["start_date"]
            ):
                reject("end_date", "END_BEFORE_START")
        except (KeyError, ValueError, TypeError):
            pass
    if type_code in ("ROOM_STUDIO", "ROOM_BOOKING"):
        start, end = values.get("start_time"), values.get("end_time")
        if start and end:
            if not re.fullmatch(
                r"(?:[01]\d|2[0-3]):[0-5]\d", start
            ) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", end):
                reject("start_time", "INVALID_TIME_FORMAT")
            elif end <= start:
                reject("end_time", "END_MUST_BE_AFTER_START")
    if type_code in (
        "LEAVE_SPECIAL",
        "BUSINESS_TRIP",
        "ACCESS_FACILITY",
        "EQUIPMENT_BORROW",
        "WFH_REQ",
        "SOFTWARE_ACCESS",
        "PROD_DATA_ACCESS",
        "TRAINING_COURSE",
        "MARKETING_CAMPAIGN",
    ):
        try:
            if (
                "start_date" in values
                and "end_date" in values
                and date.fromisoformat(values["end_date"])
                < date.fromisoformat(values["start_date"])
            ):
                reject("end_date", "END_BEFORE_START")
        except (KeyError, ValueError, TypeError):
            pass
    return errors

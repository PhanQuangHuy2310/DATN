"""Additional plan.docx and enterprise 5-level submission rules for canonical request types.

Rules operate on already-normalized, server-validated payloads and never grant
any approval or bypass published policy/actor scope. No external data is assumed.
"""

import re
from datetime import date, datetime


def _check_advance_amounts(type_code: str, values: dict, reject) -> None:
    value = values.get("amount")
    if not isinstance(value, int) or isinstance(value, bool):
        return
    if type_code == "ADVANCE_SMALL" and value >= 10_000_000:
        reject("amount", "ADVANCE_AMOUNT_MUST_BE_BELOW_10M")
    elif type_code == "ADVANCE_MEDIUM" and not (10_000_000 <= value <= 50_000_000):
        reject("amount", "ADVANCE_AMOUNT_MUST_BE_BETWEEN_10M_AND_50M")
    elif type_code == "ADVANCE_LARGE" and value <= 50_000_000:
        reject("amount", "ADVANCE_AMOUNT_MUST_BE_OVER_50M")


def _check_leave_dates(type_code: str, values: dict, reject) -> None:
    if type_code not in ("LEAVE_ANNUAL", "LEAVE_LONG"):
        return
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
        pass


def _check_room_vehicle(type_code: str, values: dict, reject) -> None:
    if type_code != "ROOM_VEHICLE":
        return
    try:
        start = datetime.fromisoformat(values["start_time"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(values["end_time"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            reject("start_time", "TIMEZONE_REQUIRED")
        elif end <= start:
            reject("end_time", "END_MUST_BE_AFTER_START")
    except (KeyError, ValueError, TypeError, AttributeError):
        reject("start_time", "INVALID_ISO_DATETIME")


def _check_transfers_and_discounts(type_code: str, values: dict, reject) -> None:
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


def _check_date_and_time_ranges(type_code: str, values: dict, reject) -> None:
    if type_code in ("ROOM_STUDIO", "ROOM_BOOKING"):
        start, end = values.get("start_time"), values.get("end_time")
        if start and end:
            if not re.fullmatch(
                r"(?:[01]\d|2[0-3]):[0-5]\d", start
            ) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", end):
                reject("start_time", "INVALID_TIME_FORMAT")
            elif end <= start:
                reject("end_time", "END_MUST_BE_AFTER_START")
    range_codes = (
        "FLASH_SALE_VOUCHER",
        "LEAVE_SPECIAL",
        "BUSINESS_TRIP",
        "ACCESS_FACILITY",
        "EQUIPMENT_BORROW",
        "WFH_REQ",
        "SOFTWARE_ACCESS",
        "PROD_DATA_ACCESS",
        "TRAINING_COURSE",
        "MARKETING_CAMPAIGN",
    )
    if type_code in range_codes:
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


def plan_business_errors(type_code: str, values: dict) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}

    def reject(name, message):
        errors.setdefault(name, []).append(message)

    _check_advance_amounts(type_code, values, reject)
    _check_leave_dates(type_code, values, reject)
    _check_room_vehicle(type_code, values, reject)
    _check_transfers_and_discounts(type_code, values, reject)
    _check_date_and_time_ranges(type_code, values, reject)
    return errors

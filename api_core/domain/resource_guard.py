"""Resource availability guard (owner decision C2).

Authority thresholds (route rules) add approval levels; this module answers a
different question: is there enough *confirmed* leave balance or budget?

Only a balance that is (1) from a source designated authoritative, (2) linked
to this requester/department, and (3) fresh may block a submission. Anything
else is reported as UNVERIFIED with the reason, never silently treated as
sufficient or insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

OK = "OK"
INSUFFICIENT = "INSUFFICIENT"
UNVERIFIED = "UNVERIFIED"

MODES = ("off", "advisory", "enforce")


@dataclass(frozen=True)
class Balance:
    source: str
    available: Decimal
    as_of: datetime
    authoritative: bool


@dataclass(frozen=True)
class GuardResult:
    kind: str  # LEAVE | BUDGET
    status: str
    reason: str
    message: str
    requested: Decimal
    available: Decimal | None
    reserved: Decimal
    source: str | None
    blocking: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "status": self.status,
            "reason": self.reason,
            "message": self.message,
            "requested": str(self.requested),
            "available": None if self.available is None else str(self.available),
            "reserved": str(self.reserved),
            "source": self.source,
            "blocking": self.blocking,
        }


def _amount(kind: str, value: Decimal) -> str:
    if kind == "LEAVE":
        text = f"{value.normalize():f}"
        return f"{text} ngày"
    return f"{int(value):,} VNĐ".replace(",", ".")


UNVERIFIED_MESSAGES = {
    "NO_LINKED_RECORD": "Chưa liên kết được hồ sơ {what} của bạn với nguồn dữ liệu nên chưa xác nhận được số dư.",
    "SOURCE_NOT_AUTHORITATIVE": "Nguồn {source} là dữ liệu mô phỏng, chưa được xác nhận là nguồn chính thức; số dư chỉ để tham khảo.",
    "STALE": "Số dư {what} cập nhật lần cuối {as_of}, quá thời hạn tin cậy {hours} giờ; chưa thể xác nhận.",
}


def evaluate(
    *,
    kind: str,
    requested: Decimal,
    balance: Balance | None,
    reserved: Decimal,
    now: datetime,
    max_age: timedelta,
    mode: str,
) -> GuardResult:
    what = "ngày phép" if kind == "LEAVE" else "ngân sách phòng ban"

    def result(status, reason, message, available=None, blocking=False):
        return GuardResult(
            kind=kind,
            status=status,
            reason=reason,
            message=message,
            requested=requested,
            available=available,
            reserved=reserved,
            source=balance.source if balance else None,
            blocking=blocking,
        )

    if balance is None:
        return result(
            UNVERIFIED,
            "NO_LINKED_RECORD",
            UNVERIFIED_MESSAGES["NO_LINKED_RECORD"].format(what=what),
        )
    remaining = balance.available - reserved
    shortfall = requested > remaining
    detail = (
        f"Yêu cầu {_amount(kind, requested)}; còn {_amount(kind, remaining)} "
        f"(số dư {_amount(kind, balance.available)}, đang chờ xử lý "
        f"{_amount(kind, reserved)})."
    )
    if now - balance.as_of > max_age:
        return result(
            UNVERIFIED,
            "STALE",
            UNVERIFIED_MESSAGES["STALE"].format(
                what=what,
                as_of=balance.as_of.strftime("%d/%m/%Y %H:%M UTC"),
                hours=int(max_age.total_seconds() // 3600),
            )
            + " "
            + detail,
            available=remaining,
        )
    if not balance.authoritative:
        return result(
            UNVERIFIED,
            "SOURCE_NOT_AUTHORITATIVE",
            UNVERIFIED_MESSAGES["SOURCE_NOT_AUTHORITATIVE"].format(
                source=balance.source
            )
            + " "
            + detail,
            available=remaining,
        )
    if shortfall:
        return result(
            INSUFFICIENT,
            "INSUFFICIENT_BALANCE",
            f"Không đủ {what}. {detail}",
            available=remaining,
            blocking=mode == "enforce",
        )
    return result(OK, "SUFFICIENT", f"Đủ {what}. {detail}", available=remaining)

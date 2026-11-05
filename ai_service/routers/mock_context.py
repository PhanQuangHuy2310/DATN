"""
Router: ngữ cảnh từ các hệ thống ngoài (ai_service/routers/mock_context.py)

AI tra cứu quỹ phép (HRM), tình trạng phòng họp / xe (toà nhà) và ngân sách
phòng ban (ERP) bằng cách GỌI API của các hệ thống đó (Mock Systems API).
Không đọc bản chụp JSON và không kết nối PostgreSQL
(docs/TICH_HOP_HE_THONG_NGOAI.md §3). Kết quả được cache 60 giây.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

try:
    from fastapi import APIRouter, HTTPException, Query
except ImportError:  # pragma: no cover - lookups stay importable without FastAPI
    APIRouter, HTTPException, Query = object, Exception, lambda *args, **kwargs: None

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging

    logger = logging.getLogger("mock_context")

try:
    from config import get_settings
except (ImportError, AttributeError):
    from ai_service.config import get_settings

router = APIRouter()
CACHE_SECONDS = 60
_cache: dict[tuple, tuple[float, Any]] = {}


def _get(path: str, **params: Any) -> dict[str, Any] | None:
    """GET on the Mock Systems API; None when unreachable (AI then escalates)."""
    key = (path, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    settings = get_settings()
    try:
        response = httpx.get(
            f"{settings.eas_mock_api_url.rstrip('/')}/{path}",
            params=params,
            headers={"X-Integration-Secret": settings.eas_mock_api_secret},
            timeout=3.0,
        )
        if response.status_code >= 400:
            return None
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(f"Mock Systems API không phản hồi ({path}): {exc}")
        return None
    _cache[key] = (time.monotonic() + CACHE_SECONDS, data)
    return data


def _employee_email(email_code_or_name: str) -> str | None:
    target = (email_code_or_name or "").strip().lower()
    if not target:
        return None
    if "@" in target:
        return target
    employees = (_get("hr/employees") or {}).get("items", [])
    for emp in employees:
        if (emp.get("employee_code") or "").lower() == target or (
            emp.get("display_name") or ""
        ).lower() == target:
            return emp.get("work_email")
    return None


def lookup_leave_balance(
    employee_email_code_or_name: str, leave_type: str = "ANNUAL"
) -> float | int | None:
    """Số ngày phép còn lại theo HRM."""
    email = _employee_email(employee_email_code_or_name)
    if not email:
        return None
    balances = (_get("hr/leave-balances", employee_email=email) or {}).get("items", [])
    for b in balances:
        if (b.get("leave_type") or "").upper() == leave_type.upper():
            value = float(b.get("remaining_days") or 0)
            return int(value) if value.is_integer() else value
    return None


def lookup_facility_available(resource_code: str) -> bool | None:
    """Phòng / xe đang hoạt động (không bảo trì) theo hệ thống toà nhà."""
    resources = (_get("facilities/resources") or {}).get("items", [])
    for r in resources:
        if (r.get("code") or "").lower() == (resource_code or "").strip().lower():
            return (r.get("status") or "").upper() in {"AVAILABLE", "RESERVED"}
    return None


def lookup_department_budget(dept_code: str) -> dict[str, Any] | None:
    """Ngân sách còn lại của phòng ban theo ERP tài chính."""
    data = _get("finance/budgets", department_code=(dept_code or "").upper())
    if not data:
        return None
    return {
        "fiscal_year": data.get("fiscal_year"),
        "allocated_amount": data.get("approved_minor"),
        "committed_amount": data.get("committed_minor"),
        "remaining_amount": data.get("available_minor"),
        "currency": data.get("currency", "VND"),
    }


@router.get("/context/leave-balance", summary="Số ngày phép còn lại (HRM)")
async def query_leave_balance(
    employee: str = Query(..., description="Email, mã NV hoặc tên"),
):
    balance = lookup_leave_balance(employee)
    if balance is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy số phép cho: {employee}"
        )
    return {"employee": employee, "remaining_leave_days": balance}


@router.get("/context/facility-status", summary="Tình trạng phòng họp / xe (toà nhà)")
async def query_facility_status(
    resource: str = Query(..., description="Mã phòng / xe"),
):
    is_available = lookup_facility_available(resource)
    if is_available is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy tài nguyên: {resource}"
        )
    return {"resource": resource, "is_available": is_available}


@router.get("/context/department-budget", summary="Ngân sách phòng ban (ERP)")
async def query_department_budget(
    department: str = Query(..., description="Mã phòng ban EAS (TECH, FIN, ...)"),
):
    budget = lookup_department_budget(department)
    if budget is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy ngân sách cho phòng: {department}"
        )
    return {"department": department, "budget": budget}

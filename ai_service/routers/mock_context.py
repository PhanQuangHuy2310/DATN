"""
Router: Mock Context Provider (ai_service/routers/mock_context.py)

MỤC ĐÍCH:
  Cung cấp dữ liệu ngữ cảnh từ 8 schema mock đã chuẩn hóa (data/mock/*.json)
  để hỗ trợ AI Service trong việc:
  - Đánh giá Auto-Approve (kiểm tra quỹ phép, tình trạng phòng họp, thiết bị)
  - Đánh giá Risk Scoring (đối chiếu ngân sách trung tâm chi phí, hạn mức hợp đồng)
  - Tra cứu thông tin nhân sự, phòng ban phục vụ Smart Classifier

TẠI SAO ĐẶT TẠI AI SERVICE:
  - AI Service chạy ở chế độ Least Privilege, không có kết nối trực tiếp đến PostgreSQL
  - Toàn bộ dữ liệu được nạp từ volume snapshot JSON read-only (/app/data/mock)
  - Cho phép AI tra cứu nhanh chóng (<1ms) từ bộ nhớ RAM thay vì truy vấn DB
"""

import json
import os
from typing import Any

try:
    from fastapi import APIRouter, HTTPException, Query
except ImportError:
    APIRouter, HTTPException, Query = object, Exception, lambda *args, **kwargs: None

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("mock_context")

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK_DATA_DIR = os.path.join(BASE_DIR, "data", "mock")

# In-memory cache cho 8 snapshot JSON
_mock_cache: dict[str, Any] = {}
_manifest_cache: dict[str, Any] | None = None


def get_mock_data(schema_name: str) -> dict[str, Any] | None:
    """Tải và cache snapshot JSON của một schema mock."""
    if schema_name in _mock_cache:
        return _mock_cache[schema_name]

    file_path = os.path.join(MOCK_DATA_DIR, f"{schema_name}.json")
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            _mock_cache[schema_name] = data
            return data
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lỗi khi đọc snapshot {file_path}: {e}")
        return None


def get_manifest() -> dict[str, Any] | None:
    """Tải và cache _manifest.json tổng hợp."""
    global _manifest_cache
    if _manifest_cache is not None:
        return _manifest_cache

    manifest_path = os.path.join(MOCK_DATA_DIR, "_manifest.json")
    if not os.path.exists(manifest_path):
        return None

    try:
        with open(manifest_path, encoding="utf-8") as f:
            _manifest_cache = json.load(f)
            return _manifest_cache
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lỗi khi đọc manifest {manifest_path}: {e}")
        return None


# ---------------------------------------------------------------------------
# Helper functions phục vụ logic nghiệp vụ của AI
# ---------------------------------------------------------------------------


def lookup_leave_balance(
    employee_code_or_name: str, leave_type: str = "ANNUAL"
) -> float | int | None:
    """Tra cứu số ngày phép còn lại từ mock_hr snapshot."""
    hr_data = get_mock_data("mock_hr")
    if not hr_data:
        return None

    employees = (
        hr_data.get("entities", {}).get("employee_directory", {}).get("data", [])
    )
    emp_id = None
    target = employee_code_or_name.lower().strip()

    for emp in employees:
        code_val = (emp.get("code") or emp.get("employee_code") or "").lower()
        name_val = (
            emp.get("label") or emp.get("display_name") or emp.get("name") or ""
        ).lower()
        if code_val == target or (target and target in name_val):
            emp_id = emp.get("id")
            break

    if not emp_id:
        return None

    balances = hr_data.get("entities", {}).get("leave_balance", {}).get("data", [])
    target_type = leave_type.upper().strip()
    for b in balances:
        b_type = (b.get("type") or b.get("leave_type") or "").upper().strip()
        if str(b.get("employee_id")) == str(emp_id) and b_type == target_type:
            if "remaining" in b and b["remaining"] is not None:
                val = float(b["remaining"])
                return int(val) if val.is_integer() else val
            entitled = float(b.get("entitled", b.get("entitled_days", 0)) or 0)
            used = float(b.get("used", b.get("used_days", 0)) or 0)
            diff = max(0.0, entitled - used)
            return int(diff) if diff.is_integer() else diff

    return None


def lookup_facility_available(resource_code_or_name: str) -> bool | None:
    """Kiểm tra tình trạng khả dụng của phòng họp / xe từ mock_facilities snapshot."""
    fac_data = get_mock_data("mock_facilities")
    if not fac_data:
        return None

    resources = fac_data.get("entities", {}).get("resource_catalog", {}).get("data", [])
    target = resource_code_or_name.lower().strip()

    for r in resources:
        code_val = (r.get("code") or r.get("resource_code") or "").lower()
        name_val = (r.get("label") or r.get("name") or "").lower()
        if code_val == target or (target and target in name_val):
            if "is_available" in r and r["is_available"] is not None:
                return bool(r["is_available"])
            status = (r.get("status") or r.get("availability_status") or "").upper()
            return status == "AVAILABLE"

    return None


def lookup_department_budget(dept_code: str) -> dict[str, Any] | None:
    """Tra cứu hạn mức ngân sách từ mock_finance snapshot."""
    fin_data = get_mock_data("mock_finance")
    if not fin_data:
        return None

    target = dept_code.upper().strip()
    cost_center_target = target

    # Nếu dept_code là mã phòng ban (ví dụ 'IT', 'FIN', 'OPS', 'HQ'), tìm cost_center tương ứng từ mock_hr
    hr_data = get_mock_data("mock_hr")
    if hr_data:
        depts = hr_data.get("entities", {}).get("department", {}).get("data", [])
        for d in depts:
            if (d.get("code") or "").upper() == target:
                cc = d.get("cost_center")
                if cc:
                    cost_center_target = cc.upper()
                break

    budgets = fin_data.get("entities", {}).get("cost_center_budget", {}).get("data", [])
    for b in budgets:
        b_cc = (b.get("cost_center") or b.get("cost_center_code") or "").upper()
        if b_cc in (target, cost_center_target):
            allocated = b.get("approved_vnd") or b.get("allocated_amount_vnd")
            committed = b.get("committed_vnd") or b.get("committed_amount_vnd")
            remaining = b.get("remaining_vnd")
            if remaining is None and allocated is not None and committed is not None:
                remaining = max(0, float(allocated) - float(committed))
            return {
                "fiscal_year": b.get("year") or b.get("fiscal_year"),
                "allocated_amount": allocated,
                "committed_amount": committed,
                "remaining_amount": remaining,
                "currency": b.get("currency", "VND"),
            }

    return None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.get("/manifest", summary="Lấy metadata tổng hợp của 8 mock schema")
async def get_mock_manifest():
    manifest = get_manifest()
    if not manifest:
        raise HTTPException(status_code=404, detail="Chưa tìm thấy _manifest.json")
    return manifest


@router.get("/schemas", summary="Danh sách 8 schema mock khả dụng trong snapshot")
async def list_mock_schemas():
    manifest = get_manifest()
    if not manifest:
        raise HTTPException(status_code=404, detail="Dữ liệu mock chưa được khởi tạo")
    return {
        "generator": manifest.get("generator"),
        "source": manifest.get("source"),
        "generated_at": manifest.get("generated_at"),
        "schemas": list(manifest.get("schemas", {}).keys()),
        "summary": manifest.get("schemas", {}),
    }


@router.get(
    "/schema/{schema_name}", summary="Lấy toàn bộ snapshot JSON của 1 schema mock"
)
async def get_schema_snapshot(schema_name: str):
    valid_schemas = [
        "mock_hr",
        "mock_assets",
        "mock_facilities",
        "mock_crm",
        "mock_procurement",
        "mock_it",
        "mock_finance",
        "mock_travel",
    ]
    if schema_name not in valid_schemas:
        raise HTTPException(
            status_code=400,
            detail=f"Schema '{schema_name}' không hợp lệ. Cho phép: {', '.join(valid_schemas)}",
        )

    data = get_mock_data(schema_name)
    if not data:
        raise HTTPException(
            status_code=404, detail=f"Chưa có snapshot cho {schema_name}"
        )
    return data


@router.get("/context/leave-balance", summary="Tra cứu số ngày phép còn lại từ mock HR")
async def query_leave_balance(employee: str = Query(..., description="Mã NV hoặc tên")):
    balance = lookup_leave_balance(employee)
    if balance is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy số phép cho: {employee}"
        )
    return {"employee": employee, "remaining_leave_days": balance}


@router.get(
    "/context/facility-status",
    summary="Kiểm tra trạng thái phòng họp/xe từ mock Facilities",
)
async def query_facility_status(
    resource: str = Query(..., description="Mã phòng hoặc tên"),
):
    is_available = lookup_facility_available(resource)
    if is_available is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy tài nguyên: {resource}"
        )
    return {"resource": resource, "is_available": is_available}


@router.get("/context/department-budget", summary="Tra cứu ngân sách từ mock Finance")
async def query_department_budget(
    department: str = Query(..., description="Mã phòng ban (IT, HR, FIN, ...)"),
):
    budget = lookup_department_budget(department)
    if budget is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy ngân sách cho phòng: {department}"
        )
    return {"department": department, "budget": budget}

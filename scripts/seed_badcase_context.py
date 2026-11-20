"""Seed 5-7 varied A/B/C requests per employee account with deliberate Bad Case context.

Usage inside `api` container (or host with local Postgres + API env configured):
  docker compose stop worker
  docker compose exec -T -e EAS_LOCAL_SUPERUSER_DSN=... api \
    python scripts/seed_badcase_context.py > seed_summary.json
  docker compose start worker
  docker compose exec -T redis redis-cli FLUSHALL

Safety:
  * Refuses to apply superuser timestamp adjustments against non-local Postgres hosts.
  * Submits and advances workflows through api_core.workflow.service & attachments so
    schema validation, SoD routing, HRM leave_sync, and SHA-256 audit chains are genuine.
  * Keeps a reserved STAFF cohort clean in the recent 30d finance/attendance window so
    tests/live/test_bad_cases.py and test_ai_feedback_learning.py remain runnable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if Path("/app/manage.py").exists():
    ROOT = Path("/app")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
django.setup()

import psycopg
from django.db import connection

from api_core.authn.models import Actor
from api_core.integrations import requests as ext_requests
from api_core.workflow import attachments, service

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "host.docker.internal"}
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
NAMED_CUSTOMERS = (
    "Công ty TNHH Minh Phát",
    "Tập đoàn Hoàng Gia",
    "Công ty CP Sao Việt",
    "Tập đoàn An Khang",
    "Công ty TNHH Thịnh Vượng",
)
RESERVED_FOR_LIVE_TESTS = {
    "quang.pham@eas.com",
    "dat.ha@eas.com",
    "dung.vo@eas.com",
    "uyen.lam@eas.com",
    "yen.ho@eas.com",
    "nhung.duong@eas.com",
}

TYPE_A_POOL = (
    "WFH_REQ",
    "EXPENSE_CLAIM",
    "LEAVE",
    "ATTENDANCE_ADJUSTMENT",
    "REFUND_COMPENSATION",
    "SPECIAL_DISCOUNT",
    "VISITOR_SECURITY_PASS",
    "ROOM_BOOKING",
    "LEAVE_SPECIAL",
)
TYPE_B_POOL = (
    "IT_SUPPORT",
    "OFFICE_SUPPLIES",
    "OVERTIME_REQ",
    "HR_CERTIFICATE",
    "DOCUMENT_SEAL",
    "TRAINING_COURSE",
    "ADVANCE_SMALL",
    "BUSINESS_TRIP",
    "ACCESS",
    "REIMBURSEMENT",
    "SALARY_ADVANCE",
)
TYPE_C_POOL = (
    "TASK_REQUEST",
    "CROSS_DEPT_SUPPORT",
    "LAPTOP_PROVISION",
    "EQUIPMENT_BORROW",
    "EQUIPMENT",
    "PROJECT_INITIATION",
    "CONTRACT_APPROVAL",
    "FACILITY_REPAIR",
)
FULL_POOLS = {
    "A": TYPE_A_POOL,
    "B": TYPE_B_POOL,
    "C": TYPE_C_POOL,
}
OPEN_STATUSES = (
    "PENDING_APPROVAL",
    "IN_PROGRESS",
    "WAITING_FOR_ACCEPTANCE",
)


def _business_ts(days_ago: int, slot: int, *, off_hours: bool = False) -> datetime:
    base_date = datetime.now(VN_TZ).date() - timedelta(days=days_ago)
    if off_hours:
        hour = 21 + (slot % 2)
        minute = 15 + (slot * 11) % 35
    else:
        while base_date.isoweekday() >= 6:
            base_date -= timedelta(days=1)
        hour = 9 + (slot % 7)
        minute = 5 + (slot * 13) % 50
    return datetime.combine(
        base_date, time(hour=hour, minute=minute), tzinfo=VN_TZ
    ).astimezone(timezone.utc)


def _load_actors() -> tuple[
    dict[str, Actor], list[dict[str, Any]], dict[str, list[dict[str, Any]]]
]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT u.id::text, u.email, u.display_name, u.department_id::text,
                   d.code AS dept_code, u.manager_id::text,
                   COALESCE(array_agg(DISTINCT rm.role) FILTER (WHERE rm.revoked_at IS NULL), '{}') AS roles
            FROM eas.app_user u
            JOIN eas.department d ON d.id = u.department_id
            LEFT JOIN eas.role_membership rm ON rm.user_id = u.id
            WHERE u.is_active AND NOT u.is_system_account
            GROUP BY u.id, u.email, u.display_name, u.department_id, d.code, u.manager_id
            ORDER BY d.code, u.email
            """
        )
        rows = cur.fetchall()

    actors_by_id: dict[str, Actor] = {}
    users: list[dict[str, Any]] = []
    by_dept: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for uid, email, name, dept_id, dept_code, mgr_id, roles_arr in rows:
        roles = frozenset(roles_arr or ())
        actor = Actor(
            id=uid,
            email=email,
            display_name=name,
            department_id=dept_id,
            auth_version=1,
            roles=roles,
            must_change_password=False,
        )
        actors_by_id[uid] = actor
        info = {
            "id": uid,
            "email": email,
            "display_name": name,
            "department_id": dept_id,
            "dept_code": dept_code,
            "manager_id": mgr_id,
            "roles": roles,
            "actor": actor,
        }
        if "REQUESTER" in roles:
            users.append(info)
        by_dept[dept_code].append(info)
    return actors_by_id, users, by_dept


def _load_existing_per_user() -> dict[str, dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT r.requester_id::text, rt.code, COALESCE(wi.lifecycle, rt.lifecycle)
            FROM eas.request r
            JOIN eas.request_type rt ON rt.id = r.type_id
            LEFT JOIN eas.workflow_instance wi ON wi.request_id = r.id AND wi.state = 'ACTIVE'
            WHERE r.status <> 'DRAFT'
            """
        )
        rows = cur.fetchall()
    summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "types": set(), "lifecycles": set()}
    )
    for uid, tcode, lc in rows:
        entry = summary[uid]
        entry["total"] += 1
        entry["types"].add(tcode)
        entry["lifecycles"].add(lc)
    return summary


def _load_pickers() -> dict[str, Any]:
    pickers: dict[str, Any] = {}
    for tcode in (
        "EXPENSE_CLAIM",
        "ROOM_BOOKING",
        "VEHICLE_BOOKING",
        "EQUIPMENT_BORROW",
        "ACCESS",
    ):
        try:
            opts = ext_requests.options(tcode)
            pickers[tcode] = {
                k: [item for item in items if item.get("available", True)]
                for k, items in opts.items()
            }
        except (OSError, ValueError):
            pickers[tcode] = {}
    return pickers


def _pick_option(
    pickers: dict[str, Any],
    type_code: str,
    field: str,
    fallback: str,
    seq: int,
) -> str:
    options = pickers.get(type_code, {}).get(field) or [{"value": fallback}]
    return str(options[seq % len(options)]["value"])


def _p_wfh(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    d = ctx["today"] + timedelta(days=3 + (seq % 12))
    return {
        "title": f"Làm việc từ xa xử lý hồ sơ nghiệp vụ {dept} #{seq}",
        "date": d.isoformat(),
        "task_list": f"Hoàn thiện tài liệu và báo cáo nghiệp vụ {dept}",
        "communication_channel": "Microsoft Teams & Email công ty",
    }


def _p_expense_claim(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    cat = _pick_option(
        ctx["pickers"], "EXPENSE_CLAIM", "expense_category", "OFFICE", seq
    )
    amt = ctx["amount_override"] or (1_200_000 + (seq % 5) * 400_000)
    return {
        "title": f"Thanh toán chi phí nghiệp vụ {dept} đợt {seq}",
        "amount_vnd": amt,
        "expense_category": cat,
        "invoice_number": f"HD-SEED-{dept}-{seq:04d}",
        "beneficiary_account": f"VCB 0123{seq:06d} - {ctx['name']}",
        "reason": f"Thanh toán chứng từ nghiệp vụ phát sinh của bộ phận {dept}.",
    }


def _p_leave(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    start_off, dur = ctx["leave_window"] or (14 + (seq % 20), 1)
    d1 = ctx["today"] + timedelta(days=start_off)
    d2 = d1 + timedelta(days=max(0, dur - 1))
    return {
        "title": f"Đăng ký nghỉ phép kế hoạch {dept} - {ctx['name']}",
        "leave_kind": "CO_LUONG",
        "start_date": d1.isoformat(),
        "end_date": d2.isoformat(),
        "handover_user_id": ctx["handover"],
        "reason": f"Nghỉ phép theo kế hoạch cá nhân và đã sắp xếp bàn giao tại {dept}.",
    }


def _p_leave_special(ctx: dict[str, Any]) -> dict[str, Any]:
    d1 = ctx["today"] + timedelta(days=18 + (ctx["seq"] % 10))
    return {
        "title": f"Nghỉ phép chế độ đặc biệt {ctx['dept']} - {ctx['name']}",
        "special_leave_type": "KHAC",
        "start_date": d1.isoformat(),
        "end_date": d1.isoformat(),
        "handover_user_id": ctx["handover"],
        "reason": "Giải quyết công việc gia đình theo chế độ nội bộ công ty.",
    }


def _p_attendance(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    d1 = ctx["today"] - timedelta(days=2 + (seq % 12))
    kinds = ("Đi muộn", "Về sớm", "Quên chấm công")
    return {
        "title": f"Điều chỉnh dữ liệu chấm công {ctx['dept']} #{seq}",
        "work_date": d1.isoformat(),
        "change_type": kinds[seq % len(kinds)],
        "reason": "Họp với đối tác bên ngoài trước giờ làm việc nên cần xác nhận công.",
    }


def _p_refund(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    amt = ctx["amount_override"] or (1_500_000 + (seq % 4) * 500_000)
    return {
        "title": f"Đề xuất hoàn tiền giao dịch khách hàng #{seq}",
        "order_code": f"ORD-SEED-{dept}-{seq:04d}",
        "amount_vnd": amt,
        "customer_reference": f"KH-{dept}-{seq:04d}",
        "reason": "Hoàn tiền chênh lệch dịch vụ theo biên bản đối soát khách hàng.",
    }


def _p_discount(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    cust = ctx["customer_name"] or NAMED_CUSTOMERS[seq % len(NAMED_CUSTOMERS)]
    return {
        "title": f"Phê duyệt chiết khấu hợp đồng {cust}",
        "customer_name": cust,
        "deal_value_vnd": 80_000_000,
        "discount_percent": 5,
        "amount_vnd": 4_000_000,
        "reason": "Áp dụng mức chiết khấu chiến lược cho gói gia hạn hợp đồng năm.",
    }


def _p_visitor(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    d1 = ctx["today"] + timedelta(days=10 + (seq % 15))
    return {
        "title": f"Đăng ký thẻ an ninh tiếp đón đối tác {ctx['dept']}",
        "visitor_name": f"Nguyễn Văn Khách {seq}",
        "visitor_org": "Công ty Đối tác Chiến lược Việt Nam",
        "visit_date": d1.isoformat(),
        "facility_zone": "Khu vực sảnh tiếp khách tầng 3",
        "reason": "Đón đoàn đối tác sang trao đổi tiến độ triển khai dự án quý IV.",
    }


def _p_room(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    room = _pick_option(ctx["pickers"], "ROOM_BOOKING", "room_code", "MR-HCM-01", seq)
    d1 = ctx["today"] + timedelta(days=12 + (seq % 35))
    hour = 9 + (seq % 7)
    return {
        "title": f"Đặt phòng họp giao ban chuyên môn {ctx['dept']} #{seq}",
        "room_code": room,
        "booking_date": d1.isoformat(),
        "start_time": f"{hour:02d}:00",
        "end_time": f"{hour + 1:02d}:00",
        "attendees_count": 6,
        "purpose": f"Họp rà soát tiến độ công việc định kỳ của phòng {ctx['dept']}.",
    }


def _p_advance_small(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    amt = ctx["amount_override"] or (4_500_000 + (seq % 4) * 500_000)
    return {
        "title": f"Tạm ứng chi phí triển khai {dept} đợt {seq}",
        "amount": amt,
        "currency": "VND",
        "purpose": f"Tạm ứng mua sắm vật tư và chi phí tiếp khách của {dept}.",
        "expected_refund_date": (ctx["today"] + timedelta(days=25)).isoformat(),
    }


def _p_business_trip(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    d1 = ctx["today"] + timedelta(days=20 + (seq % 20))
    return {
        "title": f"Đăng ký công tác làm việc với chi nhánh #{seq}",
        "destination": "Đà Nẵng",
        "transportation": "MAY_BAY",
        "start_date": d1.isoformat(),
        "end_date": (d1 + timedelta(days=1)).isoformat(),
        "amount_vnd": 4_200_000,
        "reason": "Làm việc trực tiếp với khách hàng doanh nghiệp tại khu vực miền Trung.",
    }


def _p_it_support(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    return {
        "title": f"Yêu cầu hỗ trợ cài đặt phần mềm {dept} #{seq}",
        "support_category": "PHAN_MEM_OFFICE",
        "urgency": "BINH_THUONG",
        "device_asset_tag": f"LAP-{dept}-{seq:03d}",
        "reason": "Cấp quyền và cài đặt bộ công cụ văn phòng phục vụ báo cáo quý.",
    }


def _p_office_supplies(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"Đề nghị cấp văn phòng phẩm định kỳ {ctx['dept']}",
        "items_list": "Giấy in A4, bút bi xanh, kẹp hồ sơ và sổ ghi chép",
        "quantity": 10,
        "department_id": ctx["user"]["department_id"],
    }


def _p_overtime(ctx: dict[str, Any]) -> dict[str, Any]:
    dept = ctx["dept"]
    return {
        "title": f"Đăng ký làm thêm giờ hoàn tất bàn giao {dept}",
        "work_date": (ctx["today"] + timedelta(days=1)).isoformat(),
        "hours": 2,
        "project_id": f"PRJ-{dept}-2026",
        "deliverables": "Hoàn tất rà soát số liệu và tổng hợp báo cáo tuần.",
    }


def _p_hr_cert(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"Xin giấy xác nhận công tác tại {ctx['dept']}",
        "certificate_kind": "CONG_TAC",
        "purpose": "Hoàn thiện hồ sơ cá nhân theo yêu cầu thủ tục hành chính.",
    }


def _p_doc_seal(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    return {
        "title": f"Đề nghị đóng dấu văn bản phối hợp {dept}",
        "document_name": f"Biên bản xác nhận khối lượng {dept} số {seq}",
        "copies": 2,
        "reason": "Đóng dấu pháp nhân để gửi đối tác lưu trữ theo hợp đồng đã ký.",
    }


def _p_training(ctx: dict[str, Any]) -> dict[str, Any]:
    d1 = ctx["today"] + timedelta(days=25 + (ctx["seq"] % 15))
    return {
        "title": f"Đăng ký khóa đào tạo chuyên môn {ctx['dept']}",
        "course_name": "Quản trị rủi ro & vận hành hệ thống doanh nghiệp",
        "provider": "Học viện Quản trị Doanh nghiệp Việt Nam",
        "start_date": d1.isoformat(),
        "end_date": (d1 + timedelta(days=1)).isoformat(),
        "amount_vnd": 2_500_000,
        "reason": "Nâng cao kỹ năng kiểm soát quy trình và đánh giá nghiệp vụ.",
    }


def _p_access(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    app_val = _pick_option(ctx["pickers"], "ACCESS", "app_code", "CRM", seq)
    roles_opt = ctx["pickers"].get("ACCESS", {}).get("requested_role") or []
    matching = [r for r in roles_opt if r.get("app_code") == app_val] or roles_opt
    role_val = matching[0]["value"] if matching else "CRM_SALES_REP"
    return {
        "title": f"Cấp quyền truy cập hệ thống {app_val} cho {dept}",
        "app_code": app_val,
        "requested_role": role_val,
        "duration_days": 30,
        "purpose": "Phục vụ tra cứu và đối soát số liệu công việc hằng ngày.",
        "reason": "Cần quyền truy cập đọc báo cáo để phối hợp xử lý hồ sơ liên phòng ban.",
    }


def _p_reimbursement(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    return {
        "title": f"Quyết toán chi phí tiếp khách phòng {ctx['dept']} #{seq}",
        "invoice_images": f"receipt_seed_{seq}.png",
        "total_amount": ctx["amount_override"] or 1_800_000,
        "tax_id": "0102030405",
        "merchant": "Công ty Dịch vụ Văn phòng An Bình",
    }


def _p_salary_advance(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"Đề nghị tạm ứng lương đột xuất tháng 11 #{ctx['seq']}",
        "amount_vnd": ctx["amount_override"] or 3_000_000,
        "reason": "Có kế hoạch chi tiêu gia đình cần xử lý sớm trong tháng.",
    }


def _p_task(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    return {
        "title": f"Giao việc rà soát quy trình nội bộ {dept} #{seq}",
        "description": f"Tổng hợp các điểm tồn đọng và lập bảng theo dõi tiến độ cho {dept}.",
        "due_date": (ctx["today"] + timedelta(days=7 + (seq % 10))).isoformat(),
    }


def _p_cross_dept(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    return {
        "title": f"Đề nghị hỗ trợ đối soát liên phòng ban {ctx['dept']} #{seq}",
        "target_department": "OPS",
        "description": "Phối hợp kiểm tra chứng từ và cập nhật trạng thái hồ sơ giữa hai đơn vị.",
        "due_date": (ctx["today"] + timedelta(days=8 + (seq % 10))).isoformat(),
    }


def _p_laptop(ctx: dict[str, Any]) -> dict[str, Any]:
    dept = ctx["dept"]
    return {
        "title": f"Đề nghị cấp thiết bị làm việc chuyên dụng {dept}",
        "specs_needed": "Laptop Core i5, RAM 16GB, SSD 512GB",
        "position": f"Chuyên viên {dept}",
        "location": "Văn phòng TP. Hồ Chí Minh",
        "reason": "Bổ sung thiết bị làm việc phục vụ xử lý dữ liệu nghiệp vụ.",
    }


def _p_equipment_borrow(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    cat = _pick_option(ctx["pickers"], "EQUIPMENT_BORROW", "asset_category", "AV", seq)
    d1 = ctx["today"] + timedelta(days=15 + (seq % 15))
    return {
        "title": f"Mượn thiết bị trình chiếu phục vụ hội thảo {ctx['dept']}",
        "asset_category": cat,
        "start_date": d1.isoformat(),
        "end_date": (d1 + timedelta(days=1)).isoformat(),
        "quantity": 1,
        "reason": "Sử dụng cho buổi tập huấn quy trình vận hành phòng ban.",
    }


def _p_equipment(ctx: dict[str, Any]) -> dict[str, Any]:
    dept = ctx["dept"]
    return {
        "title": f"Đề nghị trang bị thiết bị văn phòng {dept} #{ctx['seq']}",
        "item_name": "Màn hình làm việc 27 inch chống lóa",
        "quantity": 1,
        "amount_vnd": 5_500_000,
        "specs": "Độ phân giải 2K IPS, hỗ trợ USB-C và chân nâng hạ chuẩn công thái học",
        "location": f"Khu vực làm việc {dept} tầng 5",
        "reason": "Thay thế thiết bị đã hết khấu hao để đảm bảo tiến độ xử lý hồ sơ.",
    }


def _p_project(ctx: dict[str, Any]) -> dict[str, Any]:
    d1 = ctx["today"] + timedelta(days=5)
    return {
        "title": f"Đề xuất khởi tạo sáng kiến cải tiến {ctx['dept']} #{ctx['seq']}",
        "objective": "Tự động hóa đối soát chứng từ định kỳ và giảm thời gian xử lý thủ công.",
        "amount_vnd": 15_000_000,
        "start_date": d1.isoformat(),
        "end_date": (d1 + timedelta(days=45)).isoformat(),
    }


def _p_contract(ctx: dict[str, Any]) -> dict[str, Any]:
    seq = ctx["seq"]
    dept = ctx["dept"]
    return {
        "title": f"Phê duyệt hợp đồng dịch vụ bảo trì {dept} #{seq}",
        "contract_title": f"Hợp đồng cung cấp dịch vụ định kỳ {dept} 2026",
        "partner": "Công ty Cổ phần Giải pháp Công nghệ Việt",
        "amount_vnd": 18_000_000,
        "purpose": "Đảm bảo hạ tầng vận hành ổn định và hỗ trợ kỹ thuật 24/7.",
        "contract_reference": f"HDVT-{dept}-{seq:04d}",
    }


def _p_facility(ctx: dict[str, Any]) -> dict[str, Any]:
    dept = ctx["dept"]
    return {
        "title": f"Đề xuất xử lý bảo trì sự cố văn phòng {dept} #{ctx['seq']}",
        "location": f"Khu vực {dept} tầng 4",
        "issue_type": "Thiết bị điện chiếu sáng và điều hòa văn phòng",
        "photo_evidence": "photo_seed.png",
        "urgency": "BINH_THUONG",
    }


_PAYLOAD_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "WFH_REQ": _p_wfh,
    "EXPENSE_CLAIM": _p_expense_claim,
    "LEAVE": _p_leave,
    "LEAVE_SPECIAL": _p_leave_special,
    "ATTENDANCE_ADJUSTMENT": _p_attendance,
    "REFUND_COMPENSATION": _p_refund,
    "SPECIAL_DISCOUNT": _p_discount,
    "VISITOR_SECURITY_PASS": _p_visitor,
    "ROOM_BOOKING": _p_room,
    "ADVANCE_SMALL": _p_advance_small,
    "BUSINESS_TRIP": _p_business_trip,
    "IT_SUPPORT": _p_it_support,
    "OFFICE_SUPPLIES": _p_office_supplies,
    "OVERTIME_REQ": _p_overtime,
    "HR_CERTIFICATE": _p_hr_cert,
    "DOCUMENT_SEAL": _p_doc_seal,
    "TRAINING_COURSE": _p_training,
    "ACCESS": _p_access,
    "REIMBURSEMENT": _p_reimbursement,
    "SALARY_ADVANCE": _p_salary_advance,
    "TASK_REQUEST": _p_task,
    "CROSS_DEPT_SUPPORT": _p_cross_dept,
    "LAPTOP_PROVISION": _p_laptop,
    "EQUIPMENT_BORROW": _p_equipment_borrow,
    "EQUIPMENT": _p_equipment,
    "PROJECT_INITIATION": _p_project,
    "CONTRACT_APPROVAL": _p_contract,
    "FACILITY_REPAIR": _p_facility,
}


def _build_payload(
    type_code: str,
    user: dict[str, Any],
    peers: list[dict[str, Any]],
    pickers: dict[str, Any],
    *,
    seq: int,
    leave_window: tuple[int, int] | None = None,
    amount_override: int | None = None,
    customer_name: str | None = None,
) -> dict[str, Any]:
    other_peers = [p for p in peers if p["id"] != user["id"]]
    handover = other_peers[seq % len(other_peers)]["id"] if other_peers else user["id"]
    ctx = {
        "today": datetime.now(VN_TZ).date(),
        "dept": user["dept_code"],
        "name": user["display_name"],
        "user": user,
        "handover": handover,
        "pickers": pickers,
        "seq": seq,
        "leave_window": leave_window,
        "amount_override": amount_override,
        "customer_name": customer_name,
    }
    return _PAYLOAD_BUILDERS.get(type_code, _p_facility)(ctx)


def _create_and_submit(
    actor: Actor, type_code: str, payload: dict[str, Any]
) -> tuple[str, int, str]:
    draft = service.create_draft(
        actor=actor,
        body={"type_code": type_code, "title": payload["title"]},
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    req_obj = draft.body["request"]
    req_id = str(req_obj["id"])
    version = int(req_obj["lock_version"])
    submitted = service.submit_request(
        actor=actor,
        body={
            "request_id": req_id,
            "expected_version": version,
            "type_code": type_code,
            "payload": payload,
        },
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    out_req = submitted.body["request"]
    return str(out_req["id"]), int(out_req["lock_version"]), str(out_req["status"])


def _reject_active_step(
    req_id: str,
    status: str,
    version: int,
    actors_by_id: dict[str, Actor],
) -> tuple[str, int]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT s.assignee_id::text
            FROM eas.approval_step s
            JOIN eas.workflow_instance wi ON wi.id = s.instance_id
            WHERE s.request_id = %s AND wi.state = 'ACTIVE' AND s.state = 'ACTIVE'
            ORDER BY s.step_no LIMIT 1
            """,
            [req_id],
        )
        row = cur.fetchone()
    if not row or row[0] not in actors_by_id:
        return status, version
    res = service.decide_approval(
        actor=actors_by_id[row[0]],
        request_id=req_id,
        body={
            "outcome": "REJECT",
            "reason": "Chứng từ bổ sung chưa khớp kế hoạch ngân sách kỳ này.",
            "expected_version": version,
        },
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    out_r = res.body["request"]
    return str(out_r["status"]), int(out_r["lock_version"])


def _approve_all_steps(
    req_id: str,
    status: str,
    version: int,
    actors_by_id: dict[str, Actor],
) -> tuple[str, int]:
    for _ in range(8):
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT r.status, r.lock_version, s.assignee_id::text
                FROM eas.request r
                JOIN eas.workflow_instance wi ON wi.revision_id = r.current_revision_id AND wi.state = 'ACTIVE'
                LEFT JOIN eas.approval_step s ON s.instance_id = wi.id AND s.state = 'ACTIVE'
                WHERE r.id = %s
                """,
                [req_id],
            )
            row = cur.fetchone()
        if not row or row[0] != "PENDING_APPROVAL" or not row[2]:
            break
        approver = actors_by_id.get(row[2])
        if not approver:
            break
        res = service.decide_approval(
            actor=approver,
            request_id=req_id,
            body={
                "outcome": "APPROVE",
                "reason": "Đã kiểm tra đầy đủ thông tin, đồng ý phê duyệt theo quy định.",
                "expected_version": int(row[1]),
            },
            idempotency_key=str(uuid4()),
            correlation_id=str(uuid4()),
        )
        out_r = res.body["request"]
        status = str(out_r["status"])
        version = int(out_r["lock_version"])
        if status != "PENDING_APPROVAL":
            break
    return status, version


def _run_execution_phase(
    req_id: str,
    status: str,
    version: int,
    target_state: str,
    actors_by_id: dict[str, Actor],
) -> tuple[str, int]:
    if status != "READY_FOR_EXECUTION":
        return status, version
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT a.executor_id::text
            FROM eas.execution_attempt a
            JOIN eas.workflow_instance wi ON wi.id = a.instance_id AND wi.state = 'ACTIVE'
            WHERE a.request_id = %s AND a.state = 'READY'
            ORDER BY a.attempt_no DESC LIMIT 1
            """,
            [req_id],
        )
        ex_row = cur.fetchone()
    if not ex_row or ex_row[0] not in actors_by_id:
        return status, version
    executor = actors_by_id[ex_row[0]]
    start_res = service.start_execution(
        actor=executor,
        request_id=req_id,
        body={"expected_version": version},
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    status = str(start_res.body["request"]["status"])
    version = int(start_res.body["request"]["lock_version"])
    if target_state == "IN_PROGRESS":
        return status, version

    attachments.register_execution_evidence(
        actor=executor,
        request_id=req_id,
        original_name="bien_ban_hoan_thanh.pdf",
        data=MINIMAL_PDF,
        correlation_id=str(uuid4()),
    )
    sub_res = service.submit_execution(
        actor=executor,
        request_id=req_id,
        body={
            "expected_version": version,
            "result_note": "Đã hoàn tất xử lý nghiệp vụ và đính kèm biên bản xác nhận đầy đủ.",
            "external_reference": f"REF-{req_id[:8].upper()}",
        },
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    out_r = sub_res.body["request"]
    return str(out_r["status"]), int(out_r["lock_version"])


def _run_acceptance_phase(
    req_id: str,
    status: str,
    version: int,
    actors_by_id: dict[str, Actor],
) -> tuple[str, int]:
    if status != "WAITING_FOR_ACCEPTANCE":
        return status, version
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT wi.acceptor_id::text
            FROM eas.workflow_instance wi
            JOIN eas.request r ON r.current_revision_id = wi.revision_id
            WHERE r.id = %s AND wi.state = 'ACTIVE'
            """,
            [req_id],
        )
        acc_row = cur.fetchone()
    if not acc_row or acc_row[0] not in actors_by_id:
        return status, version
    acc_res = service.decide_acceptance(
        actor=actors_by_id[acc_row[0]],
        request_id=req_id,
        body={
            "outcome": "ACCEPT",
            "reason": "Kết quả bàn giao và chứng từ đối chiếu đạt yêu cầu nghiệm thu.",
            "expected_version": version,
        },
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    out_r = acc_res.body["request"]
    return str(out_r["status"]), int(out_r["lock_version"])


def _advance_workflow(
    req_id: str,
    version: int,
    status: str,
    target_state: str,
    actors_by_id: dict[str, Actor],
) -> tuple[str, int]:
    """Advance a submitted request cleanly through service layer to `target_state`."""
    if target_state == "PENDING_APPROVAL":
        return status, version
    if target_state == "REJECTED":
        return _reject_active_step(req_id, status, version, actors_by_id)

    status, version = _approve_all_steps(req_id, status, version, actors_by_id)
    status, version = _run_execution_phase(
        req_id, status, version, target_state, actors_by_id
    )
    if target_state == "WAITING_FOR_ACCEPTANCE":
        return status, version
    return _run_acceptance_phase(req_id, status, version, actors_by_id)


def _apply_oracle_adjustments(
    dsn: str,
    created_adjustments: list[dict[str, Any]],
) -> None:
    if not created_adjustments:
        return
    host = urlsplit(dsn).hostname
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"Refusing non-local superuser DSN host: {host}")
    with psycopg.connect(dsn) as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL session_replication_role = replica")
        req_ids = [item["request_id"] for item in created_adjustments]
        # Mark outbox SENT so worker never back-processes historical seeded traffic
        cur.execute(
            """
            UPDATE eas.outbox_event
            SET state = 'SENT', sent_at = now()
            WHERE request_id = ANY(%s::uuid[]) AND state <> 'SENT'
            """,
            [req_ids],
        )
        for item in created_adjustments:
            ts = item["ts"]
            rid = item["request_id"]
            cur.execute(
                """
                UPDATE eas.request
                SET created_at = %s,
                    approved_at = CASE
                        WHEN approved_at IS NOT NULL THEN %s + interval '1 hour'
                        ELSE NULL
                    END,
                    completed_at = CASE
                        WHEN status = 'COMPLETED' THEN %s + interval '2 hours'
                        ELSE NULL
                    END,
                    updated_at = CASE
                        WHEN status = 'COMPLETED' THEN %s + interval '2 hours'
                        WHEN approved_at IS NOT NULL THEN %s + interval '1 hour'
                        ELSE %s
                    END
                WHERE id = %s
                """,
                [ts, ts, ts, ts, ts, ts, rid],
            )
            cur.execute(
                "UPDATE eas.request_revision SET submitted_at = %s WHERE request_id = %s",
                [ts, rid],
            )
            if item.get("due_hours") is not None:
                due_at = datetime.now(timezone.utc) + timedelta(hours=item["due_hours"])
                cur.execute(
                    """
                    UPDATE eas.sla_stage
                    SET started_at = LEAST(started_at, %s - interval '1 hour'),
                        due_at = %s
                    WHERE request_id = %s AND closed_at IS NULL
                    """,
                    [ts, due_at, rid],
                )


def _build_cohorts(
    requesters: list[dict[str, Any]],
) -> tuple[set[str], set[str], set[str], set[str]]:
    # Reserve ~24 clean STAFF accounts (plus live-test targets) so test_bad_cases & feedback learning stay clean
    reserved_ids: set[str] = set()
    dept_reserved_counts: dict[str, int] = defaultdict(int)
    for u in requesters:
        if u["email"] in RESERVED_FOR_LIVE_TESTS:
            reserved_ids.add(u["id"])
            dept_reserved_counts[u["dept_code"]] += 1
    for u in requesters:
        if u["id"] in reserved_ids or u["dept_code"] == "BOD":
            continue
        if (
            "STAFF" in u["roles"]
            and u["manager_id"]
            and not (
                {"OPS_ADMIN", "POLICY_ADMIN", "DIRECTOR", "VICE_DIRECTOR", "APPROVER"}
                & u["roles"]
            )
            and dept_reserved_counts[u["dept_code"]] < 2
        ):
            reserved_ids.add(u["id"])
            dept_reserved_counts[u["dept_code"]] += 1

    non_reserved = [u for u in requesters if u["id"] not in reserved_ids]
    ops_absence_ids = {
        u["id"] for u in non_reserved if u["dept_code"] == "OPS" and u["manager_id"]
    }
    ops_absence_ids = set(sorted(ops_absence_ids)[:9])
    mkt_absence_ids = {
        u["id"] for u in non_reserved if u["dept_code"] == "MKT" and u["manager_id"]
    }
    mkt_absence_ids = set(sorted(mkt_absence_ids)[:9])
    team_peak_ids = ops_absence_ids | mkt_absence_ids

    split_cohort_ids = {
        u["id"]
        for u in non_reserved
        if u["dept_code"] != "BOD" and u["manager_id"] and u["id"] not in team_peak_ids
    }
    split_cohort_ids = set(sorted(split_cohort_ids)[:45])

    off_hours_cohort_ids = {
        u["id"] for u in non_reserved if u["id"] not in team_peak_ids
    }
    off_hours_cohort_ids = set(sorted(off_hours_cohort_ids)[:12])
    return reserved_ids, team_peak_ids, split_cohort_ids, off_hours_cohort_ids


def _compute_history_timing(
    *,
    uid: str,
    tcode: str,
    status: str,
    item_i: int,
    slot: int,
    reserved_ids: set[str],
    split_cohort_ids: set[str],
    off_hours_cohort_ids: set[str],
) -> tuple[datetime, int | None]:
    is_reserved = uid in reserved_ids
    is_open = status in OPEN_STATUSES
    due_hours: int | None = None

    if is_reserved and tcode in (
        "EXPENSE_CLAIM",
        "ATTENDANCE_ADJUSTMENT",
        "REFUND_COMPENSATION",
        "ADVANCE_SMALL",
    ):
        days_ago = 42 + (slot % 15)
        off_hours = False
    elif is_open:
        days_ago = 1
        due_hours = 8 + (slot % 12)
        off_hours = False
    elif (
        uid in split_cohort_ids
        and tcode in ("EXPENSE_CLAIM", "ADVANCE_SMALL", "REFUND_COMPENSATION")
    ) or (not is_reserved and tcode == "SPECIAL_DISCOUNT"):
        days_ago = 2 + (item_i % 3)
        off_hours = (uid in off_hours_cohort_ids) and (item_i < 2)
    elif uid in off_hours_cohort_ids and item_i < 2:
        days_ago = 1 + (item_i % 3)
        off_hours = True
    else:
        days_ago = 2 + ((slot * 3 + item_i) % 24)
        off_hours = False

    return _business_ts(days_ago, slot + item_i, off_hours=off_hours), due_hours


def _reconcile_recent_requests(
    dsn: str,
    minutes: int,
    reserved_ids: set[str],
    split_cohort_ids: set[str],
    off_hours_cohort_ids: set[str],
) -> dict[str, Any]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT r.id::text, r.requester_id::text, rt.code, r.status
            FROM eas.request r
            JOIN eas.request_type rt ON rt.id = r.type_id
            WHERE r.status <> 'DRAFT'
              AND r.created_at >= now() - make_interval(mins => %s)
            ORDER BY r.requester_id, r.created_at, r.id
            """,
            [minutes],
        )
        rows = cur.fetchall()

    per_user_idx: dict[str, int] = defaultdict(int)
    per_user_non_open_idx: dict[str, int] = defaultdict(int)
    adjustments: list[dict[str, Any]] = []
    open_count = 0
    off_hours_count = 0
    for idx, (rid, uid, tcode, status) in enumerate(rows):
        u_i = per_user_idx[uid]
        per_user_idx[uid] += 1
        is_open = status in OPEN_STATUSES
        eff_i = u_i if is_open else per_user_non_open_idx[uid]
        if not is_open:
            per_user_non_open_idx[uid] += 1
        ts, due_hours = _compute_history_timing(
            uid=uid,
            tcode=tcode,
            status=status,
            item_i=eff_i,
            slot=idx,
            reserved_ids=reserved_ids,
            split_cohort_ids=split_cohort_ids,
            off_hours_cohort_ids=off_hours_cohort_ids,
        )
        if due_hours is not None:
            open_count += 1
        if ts.astimezone(VN_TZ).hour >= 21:
            off_hours_count += 1
        adjustments.append({"request_id": rid, "ts": ts, "due_hours": due_hours})

    _apply_oracle_adjustments(dsn, adjustments)
    return {
        "reconciled_total": len(adjustments),
        "open_sla_adjusted": open_count,
        "off_hours_adjusted": off_hours_count,
    }


def _plan_user_lifecycles(info: dict[str, Any], idx: int) -> list[str]:
    target_total = 5 + (idx % 3)  # 5, 6, or 7
    need_more = max(0, target_total - info["total"])
    missing_lcs = [lc for lc in ("A", "B", "C") if lc not in info["lifecycles"]]
    if need_more == 0 and not missing_lcs:
        return []

    if info["total"] == 0:
        planned = ["A", "A", "B", "B", "C"]
        even = idx % 2 == 0
        if target_total >= 6:
            planned.append("A" if even else "C")
        if target_total >= 7:
            planned.append("B" if even else "C")
        return planned

    planned = list(missing_lcs)
    goal = max(need_more, len(missing_lcs))
    for lc in ("C", "B", "A"):
        if len(planned) >= goal:
            break
        if lc not in planned:
            planned.append(lc)
    while len(planned) < need_more:
        planned.append(("A", "B", "C")[len(planned) % 3])
    return planned


def _select_type_pools(
    user: dict[str, Any],
    *,
    is_reserved: bool,
    team_peak_ids: set[str],
    split_cohort_ids: set[str],
) -> dict[str, list[str]]:
    uid = user["id"]
    is_ceo = user["manager_id"] is None

    a_pool = list(TYPE_A_POOL)
    b_pool = list(TYPE_B_POOL)
    c_pool = list(TYPE_C_POOL)

    if is_ceo:
        a_pool = ["EXPENSE_CLAIM", "SPECIAL_DISCOUNT", "LEAVE_SPECIAL"]
        b_pool = [
            "HR_CERTIFICATE",
            "TRAINING_COURSE",
            "DOCUMENT_SEAL",
            "ADVANCE_SMALL",
            "BUSINESS_TRIP",
        ]
        c_pool = [
            "CONTRACT_APPROVAL",
            "CROSS_DEPT_SUPPORT",
            "EQUIPMENT_BORROW",
            "FACILITY_REPAIR",
        ]
        return {"A": a_pool, "B": b_pool, "C": c_pool}

    if is_reserved:
        a_pool = [
            "ROOM_BOOKING",
            "VISITOR_SECURITY_PASS",
            "WFH_REQ",
            "EXPENSE_CLAIM",
            "ATTENDANCE_ADJUSTMENT",
            "SPECIAL_DISCOUNT",
            "REFUND_COMPENSATION",
            "LEAVE",
        ]
    elif uid in team_peak_ids:
        a_pool = [
            "LEAVE",
            "EXPENSE_CLAIM",
            "VISITOR_SECURITY_PASS",
            "WFH_REQ",
            "ROOM_BOOKING",
            "SPECIAL_DISCOUNT",
        ]
    elif uid in split_cohort_ids:
        a_pool = [
            "EXPENSE_CLAIM",
            "REFUND_COMPENSATION",
            "SPECIAL_DISCOUNT",
            "WFH_REQ",
            "LEAVE",
            "ROOM_BOOKING",
        ]
        b_pool = [
            "ADVANCE_SMALL",
            "IT_SUPPORT",
            "OFFICE_SUPPLIES",
            "TRAINING_COURSE",
            "DOCUMENT_SEAL",
            "OVERTIME_REQ",
        ]

    return {"A": a_pool, "B": b_pool, "C": c_pool}


def _candidate_types(pool: list[str], lc: str, used_types: set[str]) -> list[str]:
    candidates = [t for t in pool if t not in used_types]
    if candidates:
        return candidates
    full = FULL_POOLS[lc]
    unused_full = [t for t in full if t not in used_types]
    return unused_full or list(full)


def _leave_window_for(
    tcode: str,
    uid: str,
    seq_counter: int,
    *,
    is_reserved: bool,
    team_peak_ids: set[str],
) -> tuple[int, int] | None:
    if tcode != "LEAVE":
        return None
    if uid in team_peak_ids:
        return (5, 2)
    if not is_reserved:
        return (3 + (seq_counter % 3), 1)
    return None


def _amount_override_for(
    tcode: str, uid: str, split_cohort_ids: set[str]
) -> int | None:
    if uid not in split_cohort_ids:
        return None
    if tcode in ("EXPENSE_CLAIM", "ADVANCE_SMALL"):
        return 8_500_000
    if tcode == "REFUND_COMPENSATION":
        return 2_000_000
    return None


def _choose_open_target(lc: str, seq_counter: int) -> tuple[str, int | None]:
    if lc == "A" and seq_counter % 3 == 0:
        return "PENDING_APPROVAL", 8 + (seq_counter % 12)
    if lc == "B" and seq_counter % 4 == 0:
        return "IN_PROGRESS", 10 + (seq_counter % 10)
    if lc == "C" and seq_counter % 4 == 0:
        return "WAITING_FOR_ACCEPTANCE", 10 + (seq_counter % 10)
    return "COMPLETED", None


def _choose_target_state(
    *,
    lc: str,
    tcode: str,
    item_i: int,
    seq_counter: int,
    is_reserved: bool,
    user: dict[str, Any],
    reserved_ids: set[str],
    open_budget: int,
) -> tuple[str, int | None, int]:
    if (
        not is_reserved
        and item_i == 1
        and tcode == "REFUND_COMPENSATION"
        and seq_counter % 4 == 0
    ):
        return "REJECTED", None, open_budget

    can_stay_open = (
        not is_reserved
        and user["manager_id"] not in reserved_ids
        and open_budget > 0
        and tcode not in ("LEAVE", "LEAVE_SPECIAL", "ROOM_BOOKING")
    )
    if can_stay_open:
        state, due_hours = _choose_open_target(lc, seq_counter)
        if due_hours is not None:
            return state, due_hours, open_budget - 1

    return "COMPLETED", None, open_budget


def _try_place_request(
    *,
    user: dict[str, Any],
    lc: str,
    item_i: int,
    pool: list[str],
    used_types: set[str],
    peers: list[dict[str, Any]],
    pickers: dict[str, Any],
    actors_by_id: dict[str, Actor],
    cohorts: tuple[set[str], set[str], set[str], set[str]],
    seq_counter: int,
    open_budget: int,
    stats: dict[str, Any],
    oracle_adjustments: list[dict[str, Any]],
) -> tuple[int, int]:
    reserved_ids, team_peak_ids, split_cohort_ids, off_hours_cohort_ids = cohorts
    uid = user["id"]
    is_reserved = uid in reserved_ids

    for tcode in _candidate_types(pool, lc, used_types):
        seq_counter += 1
        payload = _build_payload(
            tcode,
            user,
            peers,
            pickers,
            seq=seq_counter,
            leave_window=_leave_window_for(
                tcode,
                uid,
                seq_counter,
                is_reserved=is_reserved,
                team_peak_ids=team_peak_ids,
            ),
            amount_override=_amount_override_for(tcode, uid, split_cohort_ids),
        )
        target_state, due_hours, next_budget = _choose_target_state(
            lc=lc,
            tcode=tcode,
            item_i=item_i,
            seq_counter=seq_counter,
            is_reserved=is_reserved,
            user=user,
            reserved_ids=reserved_ids,
            open_budget=open_budget,
        )
        try:
            req_id, ver, init_status = _create_and_submit(user["actor"], tcode, payload)
            fin_status, _ver = _advance_workflow(
                req_id, ver, init_status, target_state, actors_by_id
            )
        except (OSError, ValueError) as exc:
            stats["errors"].append(f"{user['email']} {tcode}: {exc}")
            continue

        open_budget = next_budget
        ts, computed_due = _compute_history_timing(
            uid=uid,
            tcode=tcode,
            status=fin_status,
            item_i=item_i,
            slot=seq_counter,
            reserved_ids=reserved_ids,
            split_cohort_ids=split_cohort_ids,
            off_hours_cohort_ids=off_hours_cohort_ids,
        )
        final_due = due_hours if due_hours is not None else computed_due
        oracle_adjustments.append(
            {"request_id": req_id, "ts": ts, "due_hours": final_due}
        )
        used_types.add(tcode)
        stats["created_total"] += 1
        stats["by_lifecycle"][lc] += 1
        stats["by_status"][fin_status] += 1
        return seq_counter, open_budget

    stats["errors"].append(f"{user['email']} FAILED lifecycle={lc}")
    return seq_counter, open_budget


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--oracle-dsn", default=os.environ.get("EAS_LOCAL_SUPERUSER_DSN", "")
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reconcile-recent-minutes", type=int, default=0)
    args = ap.parse_args()

    if not args.dry_run and not args.oracle_dsn:
        sys.exit(
            "Missing --oracle-dsn or EAS_LOCAL_SUPERUSER_DSN (local Postgres superuser DSN)."
        )

    actors_by_id, requesters, by_dept = _load_actors()
    cohorts = _build_cohorts(requesters)
    reserved_ids, team_peak_ids, split_cohort_ids, off_hours_cohort_ids = cohorts

    if args.reconcile_recent_minutes > 0:
        if args.dry_run:
            sys.exit("--reconcile-recent-minutes cannot be combined with --dry-run")
        rec_stats = _reconcile_recent_requests(
            args.oracle_dsn,
            args.reconcile_recent_minutes,
            reserved_ids,
            split_cohort_ids,
            off_hours_cohort_ids,
        )
        print(json.dumps(rec_stats, ensure_ascii=False, indent=2))
        return

    existing = _load_existing_per_user()
    pickers = _load_pickers()
    stats: dict[str, Any] = {
        "total_requesters": len(requesters),
        "reserved_clean": len(reserved_ids),
        "created_total": 0,
        "by_lifecycle": {"A": 0, "B": 0, "C": 0},
        "by_status": defaultdict(int),
        "errors": [],
    }
    oracle_adjustments: list[dict[str, Any]] = []
    open_deadline_budget = 50
    seq_counter = 100

    for idx, user in enumerate(requesters):
        uid = user["id"]
        info = existing[uid]
        planned_lcs = _plan_user_lifecycles(info, idx)
        if not planned_lcs:
            continue
        if args.dry_run:
            stats["created_total"] += len(planned_lcs)
            continue

        used_types = set(info["types"])
        peers = by_dept[user["dept_code"]]
        pools = _select_type_pools(
            user,
            is_reserved=uid in reserved_ids,
            team_peak_ids=team_peak_ids,
            split_cohort_ids=split_cohort_ids,
        )
        for item_i, lc in enumerate(planned_lcs):
            seq_counter, open_deadline_budget = _try_place_request(
                user=user,
                lc=lc,
                item_i=item_i,
                pool=pools[lc],
                used_types=used_types,
                peers=peers,
                pickers=pickers,
                actors_by_id=actors_by_id,
                cohorts=cohorts,
                seq_counter=seq_counter,
                open_budget=open_deadline_budget,
                stats=stats,
                oracle_adjustments=oracle_adjustments,
            )

    if not args.dry_run and oracle_adjustments:
        _apply_oracle_adjustments(args.oracle_dsn, oracle_adjustments)

    stats["by_status"] = dict(stats["by_status"])
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

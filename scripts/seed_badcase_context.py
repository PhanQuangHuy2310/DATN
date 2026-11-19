"""Seed 5-7 varied A/B/C requests per employee account with deliberate Bad Case context.

Usage inside `api` container (or host with local Postgres + API env configured):
  docker compose stop worker
  docker compose exec -T -e EAS_LOCAL_SUPERUSER_DSN=... api \
    python scripts/seed_badcase_context.py --json seed_summary.json
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
from api_core.domain import PayloadValidationError
from api_core.domain.routing import RoutingError
from api_core.integrations import requests as ext_requests
from api_core.workflow import attachments, service
from api_core.workflow.errors import CommandError

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
            LEFT JOIN eas.workflow_instance wi ON wi.revision_id = r.current_revision_id AND wi.state = 'ACTIVE'
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
        except (CommandError, OSError, ValueError):
            pickers[tcode] = {}
    return pickers


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
    today = datetime.now(VN_TZ).date()
    dept = user["dept_code"]
    name = user["display_name"]
    other_peers = [p for p in peers if p["id"] != user["id"]]
    handover = other_peers[seq % len(other_peers)]["id"] if other_peers else user["id"]

    if type_code == "WFH_REQ":
        d = today + timedelta(days=3 + (seq % 12))
        return {
            "title": f"Làm việc từ xa xử lý hồ sơ nghiệp vụ {dept} #{seq}",
            "date": d.isoformat(),
            "task_list": f"Hoàn thiện tài liệu và báo cáo nghiệp vụ {dept}",
            "communication_channel": "Microsoft Teams & Email công ty",
        }
    if type_code == "EXPENSE_CLAIM":
        cats = pickers.get("EXPENSE_CLAIM", {}).get("expense_category") or [
            {"value": "OFFICE"}
        ]
        cat = cats[seq % len(cats)]["value"]
        amt = amount_override or (1_200_000 + (seq % 5) * 400_000)
        return {
            "title": f"Thanh toán chi phí nghiệp vụ {dept} đợt {seq}",
            "amount_vnd": amt,
            "expense_category": cat,
            "invoice_number": f"HD-SEED-{dept}-{seq:04d}",
            "beneficiary_account": f"VCB 0123{seq:06d} - {name}",
            "reason": f"Thanh toán chứng từ nghiệp vụ phát sinh của bộ phận {dept}.",
        }
    if type_code == "LEAVE":
        start_off, dur = leave_window or (14 + (seq % 20), 1)
        d1 = today + timedelta(days=start_off)
        d2 = d1 + timedelta(days=max(0, dur - 1))
        return {
            "title": f"Đăng ký nghỉ phép kế hoạch {dept} - {name}",
            "leave_kind": "CO_LUONG",
            "start_date": d1.isoformat(),
            "end_date": d2.isoformat(),
            "handover_user_id": handover,
            "reason": f"Nghỉ phép theo kế hoạch cá nhân và đã sắp xếp bàn giao tại {dept}.",
        }
    if type_code == "LEAVE_SPECIAL":
        d1 = today + timedelta(days=18 + (seq % 10))
        return {
            "title": f"Nghỉ phép chế độ đặc biệt {dept} - {name}",
            "special_leave_type": "KHAC",
            "start_date": d1.isoformat(),
            "end_date": d1.isoformat(),
            "handover_user_id": handover,
            "reason": "Giải quyết công việc gia đình theo chế độ nội bộ công ty.",
        }
    if type_code == "ATTENDANCE_ADJUSTMENT":
        d1 = today - timedelta(days=2 + (seq % 12))
        kinds = ("Đi muộn", "Về sớm", "Quên chấm công")
        return {
            "title": f"Điều chỉnh dữ liệu chấm công {dept} #{seq}",
            "work_date": d1.isoformat(),
            "change_type": kinds[seq % len(kinds)],
            "reason": "Họp với đối tác bên ngoài trước giờ làm việc nên cần xác nhận công.",
        }
    if type_code == "REFUND_COMPENSATION":
        amt = amount_override or (1_500_000 + (seq % 4) * 500_000)
        return {
            "title": f"Đề xuất hoàn tiền giao dịch khách hàng #{seq}",
            "order_code": f"ORD-SEED-{dept}-{seq:04d}",
            "amount_vnd": amt,
            "customer_reference": f"KH-{dept}-{seq:04d}",
            "reason": "Hoàn tiền chênh lệch dịch vụ theo biên bản đối soát khách hàng.",
        }
    if type_code == "SPECIAL_DISCOUNT":
        cust = customer_name or NAMED_CUSTOMERS[seq % len(NAMED_CUSTOMERS)]
        return {
            "title": f"Phê duyệt chiết khấu hợp đồng {cust}",
            "customer_name": cust,
            "deal_value_vnd": 80_000_000,
            "discount_percent": 5,
            "amount_vnd": 4_000_000,
            "reason": "Áp dụng mức chiết khấu chiến lược cho gói gia hạn hợp đồng năm.",
        }
    if type_code == "VISITOR_SECURITY_PASS":
        d1 = today + timedelta(days=10 + (seq % 15))
        return {
            "title": f"Đăng ký thẻ an ninh tiếp đón đối tác {dept}",
            "visitor_name": f"Nguyễn Văn Khách {seq}",
            "visitor_org": "Công ty Đối tác Chiến lược Việt Nam",
            "visit_date": d1.isoformat(),
            "facility_zone": "Khu vực sảnh tiếp khách tầng 3",
            "reason": "Đón đoàn đối tác sang trao đổi tiến độ triển khai dự án quý IV.",
        }
    if type_code == "ROOM_BOOKING":
        rooms = pickers.get("ROOM_BOOKING", {}).get("room_code") or [
            {"value": "MR-HCM-01"}
        ]
        room = rooms[seq % len(rooms)]["value"]
        d1 = today + timedelta(days=12 + (seq % 35))
        hour = 9 + (seq % 7)
        return {
            "title": f"Đặt phòng họp giao ban chuyên môn {dept} #{seq}",
            "room_code": room,
            "booking_date": d1.isoformat(),
            "start_time": f"{hour:02d}:00",
            "end_time": f"{hour + 1:02d}:00",
            "attendees_count": 6,
            "purpose": f"Họp rà soát tiến độ công việc định kỳ của phòng {dept}.",
        }
    if type_code == "ADVANCE_SMALL":
        amt = amount_override or (4_500_000 + (seq % 4) * 500_000)
        return {
            "title": f"Tạm ứng chi phí triển khai {dept} đợt {seq}",
            "amount": amt,
            "currency": "VND",
            "purpose": f"Tạm ứng mua sắm vật tư và chi phí tiếp khách của {dept}.",
            "expected_refund_date": (today + timedelta(days=25)).isoformat(),
        }
    if type_code == "BUSINESS_TRIP":
        d1 = today + timedelta(days=20 + (seq % 20))
        d2 = d1 + timedelta(days=1)
        return {
            "title": f"Đăng ký công tác làm việc với chi nhánh #{seq}",
            "destination": "Đà Nẵng",
            "transportation": "MAY_BAY",
            "start_date": d1.isoformat(),
            "end_date": d2.isoformat(),
            "amount_vnd": 4_200_000,
            "reason": "Làm việc trực tiếp với khách hàng doanh nghiệp tại khu vực miền Trung.",
        }
    if type_code == "IT_SUPPORT":
        return {
            "title": f"Yêu cầu hỗ trợ cài đặt phần mềm {dept} #{seq}",
            "support_category": "PHAN_MEM_OFFICE",
            "urgency": "BINH_THUONG",
            "device_asset_tag": f"LAP-{dept}-{seq:03d}",
            "reason": "Cấp quyền và cài đặt bộ công cụ văn phòng phục vụ báo cáo quý.",
        }
    if type_code == "OFFICE_SUPPLIES":
        return {
            "title": f"Đề nghị cấp văn phòng phẩm định kỳ {dept}",
            "items_list": "Giấy in A4, bút bi xanh, kẹp hồ sơ và sổ ghi chép",
            "quantity": 10,
            "department_id": user["department_id"],
        }
    if type_code == "OVERTIME_REQ":
        return {
            "title": f"Đăng ký làm thêm giờ hoàn tất bàn giao {dept}",
            "work_date": (today + timedelta(days=1)).isoformat(),
            "hours": 2,
            "project_id": f"PRJ-{dept}-2026",
            "deliverables": "Hoàn tất rà soát số liệu và tổng hợp báo cáo tuần.",
        }
    if type_code == "HR_CERTIFICATE":
        return {
            "title": f"Xin giấy xác nhận công tác tại {dept}",
            "certificate_kind": "CONG_TAC",
            "purpose": "Hoàn thiện hồ sơ cá nhân theo yêu cầu thủ tục hành chính.",
        }
    if type_code == "DOCUMENT_SEAL":
        return {
            "title": f"Đề nghị đóng dấu văn bản phối hợp {dept}",
            "document_name": f"Biên bản xác nhận khối lượng {dept} số {seq}",
            "copies": 2,
            "reason": "Đóng dấu pháp nhân để gửi đối tác lưu trữ theo hợp đồng đã ký.",
        }
    if type_code == "TRAINING_COURSE":
        d1 = today + timedelta(days=25 + (seq % 15))
        return {
            "title": f"Đăng ký khóa đào tạo chuyên môn {dept}",
            "course_name": "Quản trị rủi ro & vận hành hệ thống doanh nghiệp",
            "provider": "Học viện Quản trị Doanh nghiệp Việt Nam",
            "start_date": d1.isoformat(),
            "end_date": (d1 + timedelta(days=1)).isoformat(),
            "amount_vnd": 2_500_000,
            "reason": "Nâng cao kỹ năng kiểm soát quy trình và đánh giá nghiệp vụ.",
        }
    if type_code == "ACCESS":
        apps = pickers.get("ACCESS", {}).get("app_code") or [{"value": "CRM"}]
        roles_opt = pickers.get("ACCESS", {}).get("requested_role") or []
        app_val = apps[seq % len(apps)]["value"]
        matching_roles = [
            r for r in roles_opt if r.get("app_code") == app_val
        ] or roles_opt
        role_val = matching_roles[0]["value"] if matching_roles else "CRM_SALES_REP"
        return {
            "title": f"Cấp quyền truy cập hệ thống {app_val} cho {dept}",
            "app_code": app_val,
            "requested_role": role_val,
            "duration_days": 30,
            "purpose": "Phục vụ tra cứu và đối soát số liệu công việc hằng ngày.",
            "reason": "Cần quyền truy cập đọc báo cáo để phối hợp xử lý hồ sơ liên phòng ban.",
        }
    if type_code == "REIMBURSEMENT":
        return {
            "title": f"Quyết toán chi phí tiếp khách phòng {dept} #{seq}",
            "invoice_images": f"receipt_seed_{seq}.png",
            "total_amount": amount_override or 1_800_000,
            "tax_id": "0102030405",
            "merchant": "Công ty Dịch vụ Văn phòng An Bình",
        }
    if type_code == "SALARY_ADVANCE":
        return {
            "title": f"Đề nghị tạm ứng lương đột xuất tháng 11 #{seq}",
            "amount_vnd": amount_override or 3_000_000,
            "reason": "Có kế hoạch chi tiêu gia đình cần xử lý sớm trong tháng.",
        }
    if type_code == "TASK_REQUEST":
        return {
            "title": f"Giao việc rà soát quy trình nội bộ {dept} #{seq}",
            "description": f"Tổng hợp các điểm tồn đọng và lập bảng theo dõi tiến độ cho {dept}.",
            "due_date": (today + timedelta(days=7 + (seq % 10))).isoformat(),
        }
    if type_code == "CROSS_DEPT_SUPPORT":
        return {
            "title": f"Đề nghị hỗ trợ đối soát liên phòng ban {dept} #{seq}",
            "target_department": "OPS",
            "description": "Phối hợp kiểm tra chứng từ và cập nhật trạng thái hồ sơ giữa hai đơn vị.",
            "due_date": (today + timedelta(days=8 + (seq % 10))).isoformat(),
        }
    if type_code == "LAPTOP_PROVISION":
        return {
            "title": f"Đề nghị cấp thiết bị làm việc chuyên dụng {dept}",
            "specs_needed": "Laptop Core i5, RAM 16GB, SSD 512GB",
            "position": f"Chuyên viên {dept}",
            "location": "Văn phòng TP. Hồ Chí Minh",
            "reason": "Bổ sung thiết bị làm việc phục vụ xử lý dữ liệu nghiệp vụ.",
        }
    if type_code == "EQUIPMENT_BORROW":
        cats = pickers.get("EQUIPMENT_BORROW", {}).get("asset_category") or [
            {"value": "AV"}
        ]
        cat = cats[seq % len(cats)]["value"]
        d1 = today + timedelta(days=15 + (seq % 15))
        return {
            "title": f"Mượn thiết bị trình chiếu phục vụ hội thảo {dept}",
            "asset_category": cat,
            "start_date": d1.isoformat(),
            "end_date": (d1 + timedelta(days=1)).isoformat(),
            "quantity": 1,
            "reason": "Sử dụng cho buổi tập huấn quy trình vận hành phòng ban.",
        }
    if type_code == "EQUIPMENT":
        return {
            "title": f"Đề nghị trang bị thiết bị văn phòng {dept} #{seq}",
            "item_name": "Màn hình làm việc 27 inch chống lóa",
            "quantity": 1,
            "amount_vnd": 5_500_000,
            "specs": "Độ phân giải 2K IPS, hỗ trợ USB-C và chân nâng hạ chuẩn công thái học",
            "location": f"Khu vực làm việc {dept} tầng 5",
            "reason": "Thay thế thiết bị đã hết khấu hao để đảm bảo tiến độ xử lý hồ sơ.",
        }
    if type_code == "PROJECT_INITIATION":
        d1 = today + timedelta(days=5)
        return {
            "title": f"Đề xuất khởi tạo sáng kiến cải tiến {dept} #{seq}",
            "objective": "Tự động hóa đối soát chứng từ định kỳ và giảm thời gian xử lý thủ công.",
            "amount_vnd": 15_000_000,
            "start_date": d1.isoformat(),
            "end_date": (d1 + timedelta(days=45)).isoformat(),
        }
    if type_code == "CONTRACT_APPROVAL":
        return {
            "title": f"Phê duyệt hợp đồng dịch vụ bảo trì {dept} #{seq}",
            "contract_title": f"Hợp đồng cung cấp dịch vụ định kỳ {dept} 2026",
            "partner": "Công ty Cổ phần Giải pháp Công nghệ Việt",
            "amount_vnd": 18_000_000,
            "purpose": "Đảm bảo hạ tầng vận hành ổn định và hỗ trợ kỹ thuật 24/7.",
            "contract_reference": f"HDVT-{dept}-{seq:04d}",
        }
    return {
        "title": f"Đề xuất xử lý bảo trì sự cố văn phòng {dept} #{seq}",
        "location": f"Khu vực {dept} tầng 4",
        "issue_type": "Thiết bị điện chiếu sáng và điều hòa văn phòng",
        "photo_evidence": "photo_seed.png",
        "urgency": "BINH_THUONG",
    }


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


def _advance_workflow(
    req_id: str,
    version: int,
    status: str,
    target_state: str,
    actors_by_id: dict[str, Actor],
) -> tuple[str, int, list[tuple[str, datetime]]]:
    """Advance a submitted request cleanly using service layer to `target_state`.

    Supported `target_state`:
      - 'PENDING_APPROVAL': stays at first active approval step.
      - 'REJECTED': rejects at active approval step.
      - 'IN_PROGRESS': approves all steps, then starts execution (Types B/C).
      - 'WAITING_FOR_ACCEPTANCE': approves all steps, starts & submits execution (Type C).
      - 'COMPLETED': drives all the way to terminal COMPLETED.
    """
    lifecycle_events: list[tuple[str, datetime]] = []
    if target_state == "PENDING_APPROVAL":
        return status, version, lifecycle_events

    if target_state == "REJECTED":
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
        if row and row[0] in actors_by_id:
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
            return str(out_r["status"]), int(out_r["lock_version"]), lifecycle_events
        return status, version, lifecycle_events

    # Approve step-by-step while PENDING_APPROVAL
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
        version = int(row[1])
        approver = actors_by_id.get(row[2])
        if not approver:
            break
        res = service.decide_approval(
            actor=approver,
            request_id=req_id,
            body={
                "outcome": "APPROVE",
                "reason": "Đã kiểm tra đầy đủ thông tin, đồng ý phê duyệt theo quy định.",
                "expected_version": version,
            },
            idempotency_key=str(uuid4()),
            correlation_id=str(uuid4()),
        )
        out_r = res.body["request"]
        status = str(out_r["status"])
        version = int(out_r["lock_version"])
        if status != "PENDING_APPROVAL":
            break

    if status != "READY_FOR_EXECUTION":
        return status, version, lifecycle_events

    # Execution phase (Type B or Type C)
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
        return status, version, lifecycle_events
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
        return status, version, lifecycle_events

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
    status = str(sub_res.body["request"]["status"])
    version = int(sub_res.body["request"]["lock_version"])

    if target_state == "WAITING_FOR_ACCEPTANCE" or status != "WAITING_FOR_ACCEPTANCE":
        return status, version, lifecycle_events

    # Acceptance phase (Type C)
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
        return status, version, lifecycle_events
    acceptor = actors_by_id[acc_row[0]]
    acc_res = service.decide_acceptance(
        actor=acceptor,
        request_id=req_id,
        body={
            "outcome": "ACCEPT",
            "reason": "Kết quả bàn giao và chứng từ đối chiếu đạt yêu cầu nghiệm thu.",
            "expected_version": version,
        },
        idempotency_key=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    status = str(acc_res.body["request"]["status"])
    version = int(acc_res.body["request"]["lock_version"])
    return status, version, lifecycle_events


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
    is_open = status in ("PENDING_APPROVAL", "IN_PROGRESS", "WAITING_FOR_ACCEPTANCE")
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
        is_open = status in (
            "PENDING_APPROVAL",
            "IN_PROGRESS",
            "WAITING_FOR_ACCEPTANCE",
        )
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--oracle-dsn", default=os.environ.get("EAS_LOCAL_SUPERUSER_DSN", "")
    )
    ap.add_argument("--json", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reconcile-recent-minutes", type=int, default=0)
    args = ap.parse_args()

    if not args.dry_run and not args.oracle_dsn:
        sys.exit(
            "Missing --oracle-dsn or EAS_LOCAL_SUPERUSER_DSN (local Postgres superuser DSN)."
        )

    actors_by_id, requesters, by_dept = _load_actors()
    reserved_ids, team_peak_ids, split_cohort_ids, off_hours_cohort_ids = (
        _build_cohorts(requesters)
    )

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
        out_json = json.dumps(rec_stats, ensure_ascii=False, indent=2)
        print(out_json)
        if args.json:
            Path(args.json).write_text(out_json, encoding="utf-8")
        return 0

    existing = _load_existing_per_user()
    pickers = _load_pickers()

    stats = {
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
        target_total = 5 + (idx % 3)  # 5, 6, or 7
        need_more = max(0, target_total - info["total"])
        missing_lcs = [lc for lc in ("A", "B", "C") if lc not in info["lifecycles"]]
        if need_more == 0 and not missing_lcs:
            continue

        # Decide exact lifecycle mix for this user's new requests
        planned_lcs: list[str] = list(missing_lcs)
        if info["total"] == 0:
            # Fresh user: strictly guarantee >= 2 A, >= 2 B, >= 1 C (up to 7 total)
            planned_lcs = ["A", "A", "B", "B", "C"]
            if target_total >= 6:
                planned_lcs.append("A" if idx % 2 == 0 else "C")
            if target_total >= 7:
                planned_lcs.append("B" if idx % 2 == 0 else "C")
        else:
            for lc in ("C", "B", "A"):
                if len(planned_lcs) >= max(need_more, len(missing_lcs)):
                    break
                if lc not in planned_lcs:
                    planned_lcs.append(lc)
            while len(planned_lcs) < need_more:
                planned_lcs.append(("A", "B", "C")[len(planned_lcs) % 3])

        is_reserved = uid in reserved_ids
        is_ceo = user["manager_id"] is None
        used_types = set(info["types"])
        peers = by_dept[user["dept_code"]]

        # Build prioritized distinct type pools for each lifecycle
        a_pool = list(TYPE_A_POOL)
        if is_ceo:
            a_pool = ["EXPENSE_CLAIM", "SPECIAL_DISCOUNT", "LEAVE_SPECIAL"]
        elif is_reserved:
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

        b_pool = list(TYPE_B_POOL)
        if is_ceo:
            b_pool = [
                "HR_CERTIFICATE",
                "TRAINING_COURSE",
                "DOCUMENT_SEAL",
                "ADVANCE_SMALL",
                "BUSINESS_TRIP",
            ]
        elif uid in split_cohort_ids:
            b_pool = [
                "ADVANCE_SMALL",
                "IT_SUPPORT",
                "OFFICE_SUPPLIES",
                "TRAINING_COURSE",
                "DOCUMENT_SEAL",
                "OVERTIME_REQ",
            ]

        c_pool = list(TYPE_C_POOL)
        if is_ceo:
            c_pool = [
                "CONTRACT_APPROVAL",
                "CROSS_DEPT_SUPPORT",
                "EQUIPMENT_BORROW",
                "FACILITY_REPAIR",
            ]

        if args.dry_run:
            stats["created_total"] += len(planned_lcs)
            continue

        for item_i, lc in enumerate(planned_lcs):
            pool = a_pool if lc == "A" else (b_pool if lc == "B" else c_pool)
            candidates = [t for t in pool if t not in used_types]
            if not candidates:
                full = (
                    TYPE_A_POOL
                    if lc == "A"
                    else (TYPE_B_POOL if lc == "B" else TYPE_C_POOL)
                )
                candidates = [t for t in full if t not in used_types] or list(full)

            placed = False
            for tcode in candidates:
                seq_counter += 1
                leave_win = (
                    (5, 2)
                    if (tcode == "LEAVE" and uid in team_peak_ids)
                    else (
                        (3 + (seq_counter % 3), 1)
                        if tcode == "LEAVE" and not is_reserved
                        else None
                    )
                )
                amt_override = None
                if (
                    uid in split_cohort_ids
                    and tcode == "EXPENSE_CLAIM"
                    or uid in split_cohort_ids
                    and tcode == "ADVANCE_SMALL"
                ):
                    amt_override = 8_500_000
                elif uid in split_cohort_ids and tcode == "REFUND_COMPENSATION":
                    amt_override = 2_000_000

                payload = _build_payload(
                    tcode,
                    user,
                    peers,
                    pickers,
                    seq=seq_counter,
                    leave_window=leave_win,
                    amount_override=amt_override,
                )

                # Choose desired workflow target status
                target_state = "COMPLETED"
                due_hours: int | None = None
                if (
                    not is_reserved
                    and item_i == 1
                    and tcode == "REFUND_COMPENSATION"
                    and seq_counter % 4 == 0
                ):
                    target_state = "REJECTED"
                elif (
                    not is_reserved
                    and user["manager_id"] not in reserved_ids
                    and open_deadline_budget > 0
                    and tcode not in ("LEAVE", "LEAVE_SPECIAL", "ROOM_BOOKING")
                ):
                    if lc == "A" and seq_counter % 3 == 0:
                        target_state = "PENDING_APPROVAL"
                        due_hours = 8 + (seq_counter % 12)
                        open_deadline_budget -= 1
                    elif lc == "B" and seq_counter % 4 == 0:
                        target_state = "IN_PROGRESS"
                        due_hours = 10 + (seq_counter % 10)
                        open_deadline_budget -= 1
                    elif lc == "C" and seq_counter % 4 == 0:
                        target_state = "WAITING_FOR_ACCEPTANCE"
                        due_hours = 10 + (seq_counter % 10)
                        open_deadline_budget -= 1

                try:
                    req_id, ver, init_status = _create_and_submit(
                        user["actor"], tcode, payload
                    )
                    fin_status, _ver, _ = _advance_workflow(
                        req_id, ver, init_status, target_state, actors_by_id
                    )
                except (
                    CommandError,
                    RoutingError,
                    PayloadValidationError,
                    OSError,
                    ValueError,
                ) as exc:
                    stats["errors"].append(f"{user['email']} {tcode}: {exc}")
                    continue

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

                oracle_adjustments.append(
                    {
                        "request_id": req_id,
                        "ts": ts,
                        "due_hours": due_hours
                        if due_hours is not None
                        else computed_due,
                    }
                )
                used_types.add(tcode)
                stats["created_total"] += 1
                stats["by_lifecycle"][lc] += 1
                stats["by_status"][fin_status] += 1
                placed = True
                break

            if not placed:
                stats["errors"].append(f"{user['email']} FAILED lifecycle={lc}")

    if not args.dry_run and oracle_adjustments:
        _apply_oracle_adjustments(args.oracle_dsn, oracle_adjustments)

    stats["by_status"] = dict(stats["by_status"])
    out_json = json.dumps(stats, ensure_ascii=False, indent=2)
    print(out_json)
    if args.json:
        Path(args.json).write_text(out_json, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

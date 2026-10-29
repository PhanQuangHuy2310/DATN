#!/usr/bin/env python3
"""Enterprise synthetic data generator. Python 3.9+, no external packages.

Run from the project root:
  python enterprise_bigdata_generator.py
  python enterprise_bigdata_generator.py --partition-rows 333333 --master-rows 1000001
  python enterprise_bigdata_generator.py --partition-rows 25000 --master-rows 25000

Default: 3 x 250,000 specialist rows + 1,000,000 independent master rows.
Standard output CSV schema has exactly 21 columns. UTF-8 with BOM.
Each process writes temporary shards in bounded batches; the parent merges
them in fixed order. Memory scales with workers*batch_size, not total rows.
Temporary disk can require roughly twice the final size of the largest file
in addition to other files. Old outputs require explicit --overwrite.
The output directory is exclusively locked for this run; do not run two
instances against it. After a forced kill, remove .generator.lock only after
confirming that no generator process is still using that directory.

BUSINESS ASSUMPTIONS (editable, not verified company policy):
- domain is the business domain of request_type. department is the requesting
  business owner. Financial requests are submitted by finance on behalf of
  teams; other requests may originate in any of the seven departments.
- Risk 1 means lowest simulated risk, never a guarantee of absolute safety.
- Hard rules: over budget or suspected splitting => 5; contract payment
  outside working hours without supporting evidence => 5.
- CEO threshold is an assumed 100 million VND, configurable on the CLI.
- has_receipt means supporting document exists, NOT that it is authentic.
- Invalid-document and sensitive-access scenarios appear in text. Their
  structured signals are absent from the required schema. A tabular-only
  model cannot perfectly learn those cases without upstream text extraction.
- Split suspicion and historical aggregates are simulated upstream features.
  No employee_id, vendor_id, event timestamp or invoice ID exists in this
  schema, so this is NOT an event-linked fraud investigation benchmark.
- A high 30-day count outside office hours is an alert proxy, not proof of
  a burst. No actual historical leave ledger is fabricated or reconstructed.
- Priority is derived from scenario time pressure; it is not an SLA duration.
- About 5% of records receive text perturbations. Financial arithmetic and
  hard policy labels remain valid. There is no random label flipping.
- Master is generated independently, not copied from specialist partitions.
  Independent rows still share template families. Do not treat one partition
  as an independent real-world test set for another. Use held-out wording,
  scenarios, and eventually human-labelled real requests for evaluation.
- Millions of synthetic rows do not guarantee accuracy or generalization.
- Exclude request_id from ML features. NLP inputs should be title/description,
  not request_type/domain/department/lifecycle labels. Evaluate risk models
  with/without upstream suspicion flags to distinguish policy imitation from
  anomaly discovery. Labels are synthetic policy ground truth only.
- Reproducibility: same seed, counts, shard_rows, thresholds and Python version
  reproduce content regardless of worker count or batch size.
"""

import argparse
import csv
import hashlib
import multiprocessing as mp
import os
import random
import shutil
import tempfile
import time
import unicodedata
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

OUTPUT = "ai_service/training/data/partitions"
HEADER = [
    "request_id",
    "domain",
    "department",
    "request_type",
    "lifecycle_template",
    "title",
    "description",
    "amount_vnd",
    "budget_remaining_vnd",
    "has_receipt",
    "num_attachments",
    "user_role",
    "user_tenure_months",
    "past_requests_count",
    "past_rejection_rate",
    "is_off_hours",
    "is_split_amount_suspect",
    "is_over_budget",
    "is_template_matched",
    "priority_level",
    "risk_score",
]

# type: domain, default lifecycle, min/normal max/extreme max (million VND).
SPEC = {
    "leave_annual": ("hr", "A", 0, 0, 0),
    "leave_unpaid": ("hr", "A", 0, 0, 0),
    "overtime": ("hr", "B", 0.2, 8, 30),
    "remote_work": ("hr", "A", 0, 0, 0),
    "travel": ("hr", "B", 0.5, 25, 120),
    "equipment_new": ("it", "B", 2, 45, 300),
    "equipment_repair": ("it", "B", 0.2, 12, 19),
    "access_permission": ("it", "B", 0, 0, 0),
    "vpn_access": ("it", "B", 0, 0, 0),
    "advance_payment": ("finance", "B", 2, 60, 500),
    "expense_reimbursement": ("finance", "B", 0.1, 15, 19),
    "budget_approval": ("finance", "C", 5, 300, 2000),
    "contract_payment": ("finance", "C", 10, 200, 1500),
    "stationery": ("admin", "A", 0.1, 3, 19),
    "vehicle_booking": ("admin", "B", 0, 6, 20),
    "meeting_room": ("admin", "A", 0, 0, 0),
}
FINANCE = tuple(t for t, v in SPEC.items() if v[0] == "finance")
IT = tuple(t for t, v in SPEC.items() if v[0] == "it")
HR_OPS = tuple(t for t, v in SPEC.items() if v[0] in ("hr", "admin"))
PARTITIONS = (
    ("finance_fraud_partition.csv", FINANCE),
    ("hr_operations_partition.csv", HR_OPS),
    ("it_security_partition.csv", IT),
    ("master_requests_large.csv", tuple(SPEC)),
)
DEPTS = ("finance", "hr", "it", "marketing", "sales", "operations", "legal")
CONTEXT = {
    "finance": (
        "kế toán thanh toán",
        "kiểm soát chi phí",
        "quản lý dòng tiền",
        "kế hoạch tài chính",
    ),
    "hr": (
        "tuyển dụng nhân sự",
        "đào tạo nội bộ",
        "chính sách lao động",
        "quản lý hồ sơ nhân sự",
    ),
    "it": (
        "phát triển phần mềm",
        "vận hành hạ tầng",
        "hỗ trợ kỹ thuật",
        "quản trị hệ thống",
    ),
    "marketing": (
        "truyền thông thương hiệu",
        "quảng cáo trực tuyến",
        "nghiên cứu thị trường",
        "tổ chức chiến dịch",
    ),
    "sales": (
        "kinh doanh khách hàng",
        "bán hàng doanh nghiệp",
        "phát triển thị trường",
        "chăm sóc đối tác",
    ),
    "operations": (
        "điều phối vận hành",
        "hậu cần văn phòng",
        "quản lý cơ sở vật chất",
        "điều hành chi nhánh",
    ),
    "legal": (
        "pháp chế hợp đồng",
        "tư vấn tuân thủ",
        "rà soát pháp lý",
        "xử lý hồ sơ pháp chế",
    ),
}
ACTION = {
    "leave_annual": (
        "xin nghỉ phép năm",
        "đăng ký ngày nghỉ phép",
        "đề nghị sử dụng phép còn lại",
        "xin duyệt lịch nghỉ",
    ),
    "leave_unpaid": (
        "xin nghỉ không hưởng lương",
        "đề nghị nghỉ không lương",
        "đăng ký tạm nghỉ không lương",
        "xin duyệt thời gian nghỉ không nhận lương",
    ),
    "overtime": (
        "đăng ký làm thêm giờ",
        "đề nghị duyệt tăng ca",
        "xin làm ngoài giờ",
        "trình kế hoạch OT",
    ),
    "remote_work": (
        "xin làm việc từ xa",
        "đăng ký làm việc tại nhà",
        "đề nghị làm việc online",
        "xin áp dụng lịch WFH",
    ),
    "travel": (
        "đăng ký công tác tại {place}",
        "xin duyệt chuyến đi {place}",
        "đề xuất lịch công tác {place}",
        "trình kế hoạch làm việc tại {place}",
    ),
    "equipment_new": (
        "đề xuất mua {item}",
        "xin cấp mới {item}",
        "đề nghị trang bị {item}",
        "bổ sung {item} cho nhóm",
    ),
    "equipment_repair": (
        "đề nghị sửa {item}",
        "nhờ kiểm tra lỗi {item}",
        "xin bảo trì {item}",
        "trình chi phí khắc phục {item}",
    ),
    "access_permission": (
        "xin cấp quyền {app}",
        "đề nghị mở tài khoản {app}",
        "đăng ký truy cập {app}",
        "nhờ bổ sung quyền dùng {app}",
    ),
    "vpn_access": (
        "đăng ký kết nối VPN",
        "xin quyền VPN nội bộ",
        "nhờ mở truy cập qua VPN",
        "đề nghị cấu hình VPN làm việc từ xa",
    ),
    "advance_payment": (
        "đề nghị tạm ứng kinh phí",
        "xin ứng trước chi phí",
        "trình khoản tạm ứng",
        "đăng ký ứng tiền triển khai",
    ),
    "expense_reimbursement": (
        "đề nghị hoàn lại khoản đã chi",
        "xin thanh toán chi phí đã ứng",
        "trình hồ sơ hoàn ứng",
        "đề nghị quyết toán khoản chi cá nhân",
    ),
    "budget_approval": (
        "trình duyệt ngân sách",
        "đề xuất bổ sung kinh phí",
        "xin phê duyệt dự toán",
        "trình kế hoạch phân bổ ngân sách",
    ),
    "contract_payment": (
        "đề nghị thanh toán hợp đồng",
        "trình chi theo hợp đồng",
        "xin duyệt đợt thanh toán hợp đồng",
        "gửi hồ sơ trả tiền cho nhà cung cấp",
    ),
    "stationery": (
        "xin mua {supply}",
        "đề nghị bổ sung {supply}",
        "đăng ký cấp {supply}",
        "xin duyệt vật tư {supply}",
    ),
    "vehicle_booking": (
        "đăng ký xe công tác",
        "nhờ bố trí xe đưa đón",
        "xin đặt xe theo lịch",
        "đề nghị điều phối xe nội bộ",
    ),
    "meeting_room": (
        "đăng ký phòng họp",
        "nhờ giữ lịch phòng họp",
        "xin đặt phòng họp nội bộ",
        "đề nghị bố trí phòng họp",
    ),
}
REASON = {
    "leave_annual": (
        "để tổ chức lễ cưới",
        "để giải quyết việc gia đình",
        "để đưa người thân đi khám",
        "để nghỉ theo kế hoạch cá nhân",
    ),
    "leave_unpaid": (
        "vì đã hết quỹ phép năm",
        "để chăm sóc người thân dài ngày",
        "để thu xếp việc gia đình",
        "do cần thời gian xử lý việc riêng",
    ),
    "overtime": (
        "để hoàn thiện bàn giao",
        "để đối soát cuối kỳ",
        "để hỗ trợ triển khai hệ thống",
        "để xử lý công việc tồn",
    ),
    "remote_work": (
        "do khó khăn di chuyển",
        "để làm việc tập trung",
        "vì cần chờ sửa điện tại nhà",
        "do có lịch nhận bàn giao căn hộ",
    ),
    "travel": (
        "để khảo sát địa điểm",
        "để gặp đối tác",
        "để nghiệm thu hạng mục",
        "để đào tạo tại chi nhánh",
    ),
    "equipment_new": (
        "để bổ sung chỗ làm cho nhân sự mới",
        "vì thiết bị cũ không đáp ứng",
        "để triển khai hạng mục mới",
        "để trang bị cho khu vực dùng chung",
    ),
    "equipment_repair": (
        "vì thiết bị mất nguồn",
        "do thiết bị hoạt động chập chờn",
        "vì thường xuyên báo lỗi",
        "để khắc phục gián đoạn sử dụng",
    ),
    "access_permission": (
        "để thực hiện nhiệm vụ được giao",
        "để cập nhật hồ sơ",
        "để hỗ trợ bàn giao",
        "để tra cứu dữ liệu phụ trách",
    ),
    "vpn_access": (
        "để hỗ trợ từ xa",
        "để kết nối khi công tác",
        "để truy cập tài nguyên nội bộ",
        "để trực hỗ trợ ngoài văn phòng",
    ),
    "advance_payment": (
        "để đặt cọc dịch vụ",
        "để chuẩn bị triển khai",
        "để chi cho chuyến công tác",
        "để mua vật tư trước đợt thi công",
    ),
    "expense_reimbursement": (
        "cho khoản tiếp khách đã chi",
        "cho tiền di chuyển đã ứng",
        "cho vật tư đã mua",
        "cho chi phí lưu trú đã thanh toán",
    ),
    "budget_approval": (
        "để mở rộng dự án",
        "để bổ sung nguồn lực quý tới",
        "để triển khai kế hoạch mới",
        "để đáp ứng khối lượng phát sinh",
    ),
    "contract_payment": (
        "theo tiến độ thỏa thuận",
        "cho hạng mục đã nghiệm thu",
        "cho đợt bàn giao vừa kết thúc",
        "theo lịch thanh toán đối tác",
    ),
    "stationery": (
        "vì vật tư sắp hết",
        "để chuẩn bị đào tạo",
        "để lưu trữ hồ sơ",
        "để bổ sung cho khu vực làm việc",
    ),
    "vehicle_booking": (
        "để đưa đoàn đi khảo sát",
        "để đón đối tác",
        "để đi giữa các chi nhánh",
        "để giao hồ sơ cho đối tác",
    ),
    "meeting_room": (
        "để họp tiến độ",
        "để trao đổi với đối tác",
        "để đào tạo nội bộ",
        "để thống nhất kế hoạch",
    ),
}
ITEMS = (
    "màn hình Dell 27 inch",
    "laptop văn phòng",
    "máy in laser",
    "máy tính để bàn",
    "thiết bị hội nghị",
    "bộ lưu điện",
    "máy quét tài liệu",
    "màn hình phụ",
)
APPS = (
    "CRM",
    "ERP",
    "kho tài liệu",
    "cổng báo cáo",
    "hệ thống ticket",
    "phần mềm nhân sự",
    "hệ thống quản lý dự án",
)
SUPPLIES = (
    "giấy A4",
    "bút và sổ",
    "bìa hồ sơ",
    "mực in",
    "nhãn tài liệu",
    "kẹp và bì thư",
    "vật tư văn phòng",
)
PLACES = (
    "Hà Nội",
    "Đà Nẵng",
    "Hải Phòng",
    "TP.HCM",
    "Bắc Ninh",
    "Huế",
    "Cần Thơ",
    "Nha Trang",
)
PROJECTS = (
    "Sao Mai",
    "Atlas",
    "Hải Đăng",
    "Orion",
    "Bình Minh",
    "An Phú",
    "Delta",
    "Hòa Bình",
    "Đông Phong",
    "Phoenix",
    "Mùa Thu",
    "Sen Việt",
)
ROLES = ("intern", "junior", "senior", "lead", "manager", "director")
ROLE_POOL = (
    ("intern",) * 8
    + ("junior",) * 28
    + ("senior",) * 32
    + ("lead",) * 16
    + ("manager",) * 12
    + ("director",) * 4
)
DOC_TYPES = set(FINANCE) | {
    "travel",
    "equipment_new",
    "equipment_repair",
    "stationery",
    "vehicle_booking",
}
PRIORITIES = ("low", "medium", "high", "urgent")
PRIORITY_PHRASES = (
    (
        "Có thể xử lý theo lịch thông thường.",
        "Chưa cần xử lý ngay trong tuần này.",
        "Nhờ sắp xếp khi thuận tiện trong tháng.",
    ),
    (
        "Mong phản hồi trong vài ngày tới.",
        "Nhờ xem xét theo kế hoạch tuần này.",
        "Đề nghị xử lý trước lịch làm việc tuần tới.",
    ),
    (
        "Cần phản hồi trong ngày để tránh chậm bàn giao.",
        "Lịch ngày mai đang chờ xác nhận.",
        "Nhờ ưu tiên để kịp cam kết với đối tác.",
    ),
    (
        "Cần xử lý ngay vì công việc bị gián đoạn.",
        "Mong phản hồi trong hai giờ để kịp hạn chót.",
        "Đây là việc phát sinh cần giải quyết ngay.",
    ),
)
PLAIN = str.maketrans(
    {
        chr(i): "".join(
            c
            for c in unicodedata.normalize("NFD", chr(i))
            if unicodedata.category(c) != "Mn"
        )
        for i in range(0x00C0, 0x2000)
    }
)
PLAIN.update(str.maketrans({"đ": "d", "Đ": "D"}))


def perturb(text, mode):
    if mode == 0:
        return text.translate(PLAIN)
    if mode == 1:
        return (
            text.lower()
            .replace("không", "ko")
            .replace("được", "dc")
            .replace("với", "vs")
        )
    return (
        text.replace("đề nghị", "đề ngị")
        .replace("Đề nghị", "Đề ngị")
        .replace(" ", "  ")
    )


def make_record(rng, number, kind, noise_rate, ceo_limit):
    choose = rng.choice
    domain, lifecycle, lo, normal, upper = SPEC[kind]
    department = "finance" if domain == "finance" else choose(DEPTS)
    role = choose(ROLE_POOL)
    tenure = rng.randint(1, 12 if role == "intern" else 36 if role == "junior" else 180)
    amount = (
        0
        if not upper
        else max(
            10000,
            round(
                (
                    rng.uniform(normal, upper)
                    if rng.random() < 0.10
                    else rng.triangular(lo, normal, lo)
                )
                * 100
            )
            * 10000,
        )
    )
    if kind == "vehicle_booking" and rng.random() < 0.4:
        amount = 0
    budget_base = {
        "finance": 900,
        "hr": 150,
        "it": 500,
        "marketing": 350,
        "sales": 300,
        "operations": 600,
        "legal": 150,
    }[department]
    budget = min(
        3000000000, round(rng.lognormvariate(0, 0.8) * budget_base * 100) * 10000
    )
    if rng.random() < 0.025:
        budget = 0
    receipt = int(rng.random() < (0.88 if kind in DOC_TYPES and amount else 0.08))
    count = rng.randint(0, min(60, tenure * 5))
    rejected = round(
        count
        * (rng.betavariate(1, 12) if rng.random() < 0.9 else rng.betavariate(4, 3))
    )
    rate = round(rejected / count, 2) if count else 0.0
    off = int(rng.random() < 0.20)
    matched = int(rng.random() < 0.92)
    split, invalid, sensitive, late = 0, 0, 0, 0
    scenario, note = "ordinary", ""
    u = rng.random()
    if domain == "finance":
        if u < 0.07 and kind in (
            "advance_payment",
            "contract_payment",
            "budget_approval",
        ):
            scenario, split = "split_suspect", 1
            amount = min(ceo_limit - 1, int(ceo_limit * rng.uniform(0.90, 0.995)))
            count = max(count, rng.randint(3, 12))
            note = choose(
                (
                    "Đề nghị chuyển từng đợt riêng trong tuần.",
                    "Hồ sơ đề xuất thanh toán nhiều phần cho cùng hạng mục.",
                    "Nhờ xử lý riêng các khoản gửi liên tiếp cho đối tác.",
                )
            )
        elif u < 0.14:
            scenario, invalid, receipt = "document_mismatch", 1, 1
            note = choose(
                (
                    "Hóa đơn đính kèm lệch tên đơn vị so với hợp đồng.",
                    "Số tiền trên hóa đơn chưa khớp đề nghị thanh toán.",
                    "Mã số thuế trên chứng từ cần đối chiếu lại.",
                )
            )
        elif u < 0.21:
            scenario, off, receipt = "off_hours_missing_doc", 1, 0
            note = "Nhờ xử lý cuối tuần; bộ chứng từ chưa tập hợp đủ."
        elif u < 0.28:
            scenario = "over_budget"
            budget = max(0, amount - rng.randint(1, max(1, amount)))
            note = "Ngân sách còn lại chưa đủ, cần xem xét bổ sung nguồn."
    elif domain == "it":
        if u < 0.10 and kind in ("access_permission", "vpn_access"):
            scenario, sensitive = "sensitive_access", 1
            note = choose(
                (
                    "Xin quyền quản trị trên hệ thống sản xuất.",
                    "Phạm vi truy cập có dữ liệu khách hàng nhạy cảm.",
                    "Đề nghị quyền ghi trực tiếp vào cơ sở dữ liệu sản xuất.",
                )
            )
        elif u < 0.18 and kind == "equipment_new":
            scenario, role, tenure = (
                "intern_expensive_server",
                "intern",
                rng.randint(1, 6),
            )
            amount = rng.randrange(8000, 30001) * 10000
            note = "Đề xuất máy chủ cấu hình cao cho hạng mục được giao."
        elif u < 0.25:
            scenario, off, count = "frequent_off_hours", 1, rng.randint(45, 60)
            note = "Đây là một trong nhiều yêu cầu phát sinh gần đây."
    elif u < 0.12:
        scenario, late = "short_notice", 1
        note = "Yêu cầu phát sinh sát lịch đã chốt, cần xác nhận trước giờ bắt đầu."
    elif u < 0.22:
        scenario, off, count = "frequent_off_hours", 1, rng.randint(45, 60)
        note = "Trong tháng có nhiều đề nghị điều chỉnh lịch làm việc."
    # Preserve coherent integer history after a scenario changes the count.
    rejected = min(count, round(rate * count))
    rate = round(rejected / count, 2) if count else 0.0
    attachments = rng.randint(1, 8) if receipt else choose((0, 0, 0, 0, 1, 2, 3))
    if receipt and rng.random() < 0.06:
        attachments = rng.randint(9, 15)
    over = int(amount > budget)
    pressure = rng.random()
    priority = (
        0 if pressure < 0.22 else 1 if pressure < 0.73 else 2 if pressure < 0.94 else 3
    )
    if late:
        priority = choose((2, 2, 3))
    if scenario == "off_hours_missing_doc":
        priority = 3
    if amount >= ceo_limit or sensitive:
        lifecycle = "C"
    elif lifecycle == "A" and amount > 5000000:
        lifecycle = "B"
    missing = kind in DOC_TYPES and amount > 0 and not receipt
    risk = (
        1
        if kind in ("leave_annual", "remote_work", "meeting_room", "stationery")
        else 2
    )
    if kind in (
        "advance_payment",
        "budget_approval",
        "contract_payment",
        "access_permission",
    ):
        risk = max(risk, 3)
    if tenure <= 3 or (kind == "stationery" and amount > 1000000):
        risk = max(risk, 2)
    if not matched or late or (off and count >= 45) or (count >= 5 and rate >= 0.25):
        risk = max(risk, 3)
    if kind == "overtime" and amount >= 5000000:
        risk = max(risk, 3)
    if (
        missing
        or invalid
        or sensitive
        or amount > normal * 1000000
        or (count >= 5 and rate >= 0.5)
    ):
        risk = max(risk, 4)
    if role in ("intern", "junior") and amount >= 20000000:
        risk = max(risk, 4)
    if over or split or (kind == "contract_payment" and off and missing):
        risk = 5
    if (
        off
        and missing
        and (count >= 45 or (role in ("intern", "junior") and amount >= 20000000))
    ):
        risk = 5
    context, project = choose(CONTEXT[department]), choose(PROJECTS)
    day = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/2026"
    item = (
        "máy chủ cấu hình cao"
        if scenario == "intern_expensive_server"
        else choose(ITEMS)
    )
    action = choose(ACTION[kind]).format(
        item=item, app=choose(APPS), place=choose(PLACES), supply=choose(SUPPLIES)
    )
    reason = choose(REASON[kind])
    title = choose(
        (
            f"{action} cho nhóm {context}",
            f"{action} theo kế hoạch {project}",
            f"{action} - lịch {day}",
            f"Nhờ xem xét: {action}",
            f"{action} phục vụ đợt triển khai",
            f"{project}: {action}",
        )
    )
    title = title[0].upper() + title[1:]
    clauses = [
        choose(
            (
                f"Em thuộc nhóm {context}",
                f"Tôi đại diện bộ phận {context}",
                f"Bên {context}",
                f"Nhóm phụ trách {context}",
            )
        )
        + f", {action} {reason}."
    ]
    if kind in ("leave_annual", "leave_unpaid", "remote_work"):
        clauses.append(f"Dự kiến {rng.randint(1, 7)} ngày, bắt đầu {day}.")
    elif kind == "meeting_room":
        clauses.append(
            f"Dự kiến {rng.randint(3, 25)} người họp lúc {rng.randint(8, 16)}h ngày {day}."
        )
    else:
        clauses.append(f"Thuộc kế hoạch {project}, dự kiến thực hiện {day}.")
    if amount:
        clauses.append(f"Số tiền đề nghị {amount:,} đồng.".replace(",", "."))
    if kind in DOC_TYPES and amount:
        clauses.append(
            "Có chứng từ kèm theo để đối chiếu."
            if receipt
            else "Chứng từ chưa đủ, sẽ bổ sung sau."
        )
    if note:
        clauses.append(note)
    if not matched and rng.random() < 0.6:
        clauses.append("Một số mục biểu mẫu chưa hoàn thiện.")
    clauses.append(choose(PRIORITY_PHRASES[priority]))
    if rng.random() < 0.4:
        clauses.append(
            choose(
                (
                    "Nhờ anh chị kiểm tra giúp.",
                    "Tôi sẽ phối hợp giải trình.",
                    "Nhóm sẵn sàng bổ sung thông tin.",
                    "Mong nhận phản hồi để sắp xếp.",
                )
            )
        )
    # Independent clauses can change order without mixing financial facts.
    if rng.random() < 0.35:
        clauses[1:3] = reversed(clauses[1:3])
    description = " ".join(clauses)
    noise = int(rng.random() < noise_rate)
    if noise:
        mode = rng.randrange(3)
        title, description = perturb(title, mode), perturb(description, mode)
    row = [
        f"REQ-{number:07d}",
        domain,
        department,
        kind,
        lifecycle,
        title,
        description,
        amount,
        budget,
        receipt,
        attachments,
        role,
        tenure,
        count,
        f"{rate:.2f}",
        off,
        split,
        over,
        matched,
        PRIORITIES[priority],
        risk,
    ]
    # Cheap per-row invariants; remain active even with python -O.
    if (
        len(row) != 21
        or (not upper and amount != 0)
        or (receipt and attachments < 1)
        or over != int(amount > budget)
        or ((over or split) and risk != 5)
        or not 1 <= risk <= 5
        or not 0 <= attachments <= 15
        or not 0 <= count <= 60
        or not 1 <= tenure <= 180
        or not 0 <= rate <= 1
        or (count == 0 and rate != 0)
    ):
        raise ValueError(f"Invariant violation: {row[0]}")
    return row, scenario, noise


def write_shard(job):
    part, shard, start, count, types, folder, seed, batch_size, noise, limit = job
    stable_seed = int.from_bytes(
        hashlib.sha256(f"{seed}:{part}:{shard}".encode()).digest()[:8], "big"
    )
    rng = random.Random(stable_seed)
    path = Path(folder) / f"{part:02d}_{shard:06d}.csv"
    risk_counts, priorities, scenarios, type_counts = (
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    noisy_rows, batch = 0, []
    with path.open("w", encoding="utf-8", newline="", buffering=1024 * 1024) as f:
        writer = csv.writer(f)
        for i in range(count):
            row, scenario, changed = make_record(
                rng, start + i, rng.choice(types), noise, limit
            )
            batch.append(row)
            risk_counts[row[-1]] += 1
            priorities[row[-2]] += 1
            type_counts[row[3]] += 1
            scenarios[scenario] += 1
            noisy_rows += changed
            if len(batch) >= batch_size:
                writer.writerows(batch)
                batch.clear()
        if batch:
            writer.writerows(batch)
    return (
        part,
        shard,
        count,
        risk_counts,
        priorities,
        scenarios,
        type_counts,
        noisy_rows,
    )


def run(args):
    total = 3 * args.partition_rows + args.master_rows
    if total > 9999999 or min(args.partition_rows, args.master_rows) < 1:
        raise ValueError("Số dòng phải dương và tổng <= 9.999.999 để giữ ID 7 chữ số")
    if (
        not 0 <= args.noise_rate <= 0.2
        or min(args.workers, args.shard_rows, args.batch_size) < 1
    ):
        raise ValueError(
            "workers/shard-rows/batch-size phải > 0; noise-rate từ 0 đến 0.2"
        )
    if args.ceo_threshold < 20000000:
        raise ValueError("ceo-threshold phải >= 20.000.000 VNĐ")
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / name for name, _ in PARTITIONS]
    lock = out / ".generator.lock"
    # Exclusive-create prevents two cooperating instances clobbering outputs.
    with lock.open("x", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    started = time.perf_counter()
    try:
        if not args.overwrite and any(p.exists() for p in targets):
            raise FileExistsError(
                "File đích đã tồn tại. Dùng --overwrite nếu muốn thay thế."
            )
        print(
            f"Tổng {total:,} dòng | {args.workers} workers | shard {args.shard_rows:,} | batch {args.batch_size:,}",
            flush=True,
        )
        totals = [[Counter(), Counter(), Counter(), Counter(), 0] for _ in PARTITIONS]
        counts = [args.partition_rows] * 3 + [args.master_rows]
        shard_counts = []
        with tempfile.TemporaryDirectory(prefix=".generator_", dir=out) as folder:
            jobs = []
            offset = 1
            for part, ((name, types), n) in enumerate(zip(PARTITIONS, counts)):
                chunks = (n + args.shard_rows - 1) // args.shard_rows
                shard_counts.append(chunks)
                for shard in range(chunks):
                    local = shard * args.shard_rows
                    jobs.append(
                        (
                            part,
                            shard,
                            offset + local,
                            min(args.shard_rows, n - local),
                            types,
                            folder,
                            args.seed,
                            args.batch_size,
                            args.noise_rate,
                            args.ceo_threshold,
                        )
                    )
                offset += n
            # Interleave partitions so the large master starts immediately.
            jobs.sort(key=lambda j: (j[1], j[0]))
            iterator = iter(jobs)
            completed = 0
            with ProcessPoolExecutor(
                max_workers=args.workers, mp_context=mp.get_context("spawn")
            ) as pool:
                pending = set()
                for _ in range(min(len(jobs), 2 * args.workers)):
                    pending.add(pool.submit(write_shard, next(iterator)))
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        part, shard, n, risks, priorities, scenarios, types, noisy = (
                            future.result()
                        )
                        for target, values in zip(
                            totals[part][:4], (risks, priorities, scenarios, types)
                        ):
                            target.update(values)
                        totals[part][4] += noisy
                        completed += n
                        job = next(iterator, None)
                        if job is not None:
                            pending.add(pool.submit(write_shard, job))
                    elapsed = time.perf_counter() - started
                    print(
                        f"\rĐã sinh {completed:,}/{total:,} ({completed / total:.1%}) | {completed / max(elapsed, 0.001):,.0f} dòng/s",
                        end="",
                        flush=True,
                    )
            print("\nĐang ghép file theo thứ tự ID...", flush=True)
            # Only publish after all generation tasks succeed. Each replacement
            # is atomic; the four-file set as a whole is not a transaction.
            for part, target in enumerate(targets):
                merged = Path(folder) / f"merged_{part}.csv"
                with merged.open("w", encoding="utf-8-sig", newline="") as f:
                    csv.writer(f).writerow(HEADER)
                with merged.open("ab") as dest:
                    for shard in range(shard_counts[part]):
                        src = Path(folder) / f"{part:02d}_{shard:06d}.csv"
                        with src.open("rb") as source:
                            shutil.copyfileobj(source, dest, length=1024 * 1024)
                        src.unlink()
                os.replace(merged, target)
        elapsed = time.perf_counter() - started
        print(
            f"\nHoàn tất {total:,} dòng trong {elapsed:.2f}s; {total / elapsed:,.0f} dòng/s (gồm ghi/ghép)."
        )
        for part, (target, n) in enumerate(zip(targets, counts)):
            print(
                f"\n{target.name}: {n:,} dòng; {target.stat().st_size / 1048576:.2f} MiB"
            )
            for label, counter in zip(
                ("risk_score", "priority_level", "scenario", "request_type"),
                totals[part][:4],
            ):
                print(
                    f"  {label}: "
                    + ", ".join(f"{k}={v:,}" for k, v in sorted(counter.items()))
                )
            print(f"  Nhiễu văn bản: {totals[part][4]:,} ({totals[part][4] / n:.2%})")
        print(
            f"\nThư mục: {out}\nDữ liệu giả lập; tốc độ phụ thuộc CPU, ổ đĩa và số workers."
        )
    finally:
        lock.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--partition-rows", type=int, default=250000)
    p.add_argument("--master-rows", type=int, default=1000000)
    p.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    p.add_argument("--shard-rows", type=int, default=25000)
    p.add_argument("--batch-size", type=int, default=1000)
    p.add_argument("--noise-rate", type=float, default=0.05)
    p.add_argument("--ceo-threshold", type=int, default=100000000)
    p.add_argument("--seed", type=int, default=20261003)
    p.add_argument("--output-dir", default=OUTPUT)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    try:
        run(args)
    except (ValueError, FileExistsError) as e:
        p.exit(2, f"Lỗi: {e}\n")


if __name__ == "__main__":
    mp.freeze_support()
    main()

#!/usr/bin/env python3
"""Python 3.9+, standard library only. Run from the project root.

Synthetic benchmark, not evidence of real fraud or production accuracy.
department = requesting business owner; finance requests are owned by finance.
6% text noise by default; never corrupt hard constraints or target labels.
Split suspicion and 30-day history are simulated, not reconstructed events.
priority_level is a priority target, not an elapsed-time/SLA-duration target.
Risk/priority policies and all distributions below are editable assumptions.

Training notes:
- For NLP, use title/description as X; department/request_type as targets.
- Drop request_id from all models. Never use risk_score to predict itself.
- Lifecycle is derived partly from type/amount: exclude it from NLP inputs.
- is_over_budget is a derived signal; split suspicion is an upstream feature.
  Including them in risk classification tests rule imitation, not raw fraud
  discovery. Evaluate with/without these flags if comparing approaches.
- Templates share wording even though exact text pairs are unique. A random
  row split can overestimate generalization. Hold out scenario/template
  families or evaluate on independently written, human-reviewed requests.
- More generated rows do not guarantee better real-world model accuracy.
- To model real bursts/splitting, collect employee_id, vendor_id, timestamps,
  related purchase/order IDs and historical amounts in an event-level dataset.
- The 30-day count alone cannot prove requests arrived in a short burst.
- VAT/invoice authenticity is not assessed by these synthetic receipt flags.
"""

import argparse
import csv
import random
import unicodedata
from collections import Counter
from pathlib import Path

N_SAMPLES = 30000  # Change to 50000, or pass --n-samples 50000.
OUTPUT = "ai_service/training/data/enterprise_requests_dataset_large.csv"
COLUMNS = [
    "request_id",
    "title",
    "description",
    "department",
    "request_type",
    "lifecycle_template",
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

# type: base lifecycle, min/typical max/extreme max in MILLION VND, phrases.
SPECS = {
    "leave_annual": (
        "A",
        0,
        0,
        0,
        ["xin nghỉ phép năm", "đăng ký ngày nghỉ phép", "đề nghị sử dụng phép còn lại"],
    ),
    "leave_unpaid": (
        "A",
        0,
        0,
        0,
        [
            "xin nghỉ không hưởng lương",
            "đăng ký nghỉ không lương",
            "đề nghị tạm nghỉ không nhận lương",
        ],
    ),
    "overtime": (
        "B",
        0.2,
        8,
        25,
        ["đăng ký làm thêm giờ", "xin duyệt tăng ca", "đề xuất làm ngoài giờ"],
    ),
    "remote_work": (
        "A",
        0,
        0,
        0,
        ["xin làm việc từ xa", "đăng ký làm tại nhà", "đề nghị làm việc online"],
    ),
    "travel": (
        "B",
        0.5,
        20,
        100,
        ["đăng ký đi công tác", "xin duyệt chuyến làm việc", "đề xuất lịch công tác"],
    ),
    "equipment_new": (
        "B",
        2,
        40,
        180,
        ["đề xuất mua {item}", "xin cấp mới {item}", "đề nghị trang bị {item}"],
    ),
    "equipment_repair": (
        "B",
        0.2,
        12,
        19,
        [
            "đề nghị sửa {item}",
            "nhờ kiểm tra và bảo trì {item}",
            "xin xử lý lỗi {item}",
        ],
    ),
    "access_permission": (
        "B",
        0,
        0,
        0,
        ["xin cấp quyền {app}", "đăng ký truy cập {app}", "đề nghị mở tài khoản {app}"],
    ),
    "vpn_access": (
        "B",
        0,
        0,
        0,
        [
            "đăng ký kết nối VPN",
            "xin quyền VPN nội bộ",
            "nhờ kích hoạt truy cập qua VPN",
        ],
    ),
    "advance_payment": (
        "B",
        2,
        50,
        400,
        ["đề nghị tạm ứng chi phí", "xin ứng trước kinh phí", "gửi đề xuất tạm ứng"],
    ),
    "expense_reimbursement": (
        "B",
        0.1,
        12,
        19,
        [
            "đề nghị hoàn lại chi phí",
            "xin thanh toán khoản đã chi",
            "gửi hồ sơ hoàn ứng",
        ],
    ),
    "budget_approval": (
        "C",
        5,
        300,
        2000,
        ["trình duyệt ngân sách", "đề xuất bổ sung kinh phí", "xin phê duyệt dự toán"],
    ),
    "contract_payment": (
        "C",
        20,
        200,
        1500,
        [
            "đề nghị thanh toán hợp đồng",
            "trình chi theo hợp đồng",
            "xin duyệt đợt thanh toán hợp đồng",
        ],
    ),
    "stationery": (
        "A",
        0.1,
        3,
        19,
        ["xin mua {supply}", "đề xuất bổ sung {supply}", "đăng ký cấp {supply}"],
    ),
    "vehicle_booking": (
        "A",
        0,
        5,
        15,
        ["đăng ký xe công tác", "xin bố trí xe đưa đón", "đề nghị đặt xe theo lịch"],
    ),
    "meeting_room": (
        "A",
        0,
        0,
        0,
        ["đăng ký phòng họp", "xin đặt phòng họp nội bộ", "nhờ giữ lịch phòng họp"],
    ),
}
REASONS = {
    "leave_annual": [
        "để tổ chức lễ cưới",
        "để giải quyết việc gia đình",
        "để đưa người thân đi khám",
        "để nghỉ ngơi theo kế hoạch",
    ],
    "leave_unpaid": [
        "vì đã hết quỹ phép năm",
        "để xử lý việc riêng kéo dài",
        "để chăm sóc người thân",
        "do cần thời gian thu xếp việc nhà",
    ],
    "overtime": [
        "để hoàn thiện bản bàn giao",
        "để đối soát số liệu cuối kỳ",
        "để xử lý khối lượng công việc tồn",
        "để hỗ trợ triển khai hệ thống",
    ],
    "remote_work": [
        "do đang chờ sửa điện tại nhà",
        "vì cần ở nhà nhận bàn giao căn hộ",
        "do bất tiện di chuyển",
        "để xử lý công việc tập trung",
    ],
    "travel": [
        "để khảo sát địa điểm triển khai",
        "để làm việc trực tiếp với đối tác",
        "để nghiệm thu hạng mục",
        "để tổ chức đào tạo tại chi nhánh",
    ],
    "equipment_new": [
        "vì thiết bị hiện tại không đáp ứng công việc",
        "để bổ sung chỗ làm cho nhân sự mới",
        "để phục vụ giai đoạn triển khai",
        "do cần thêm thiết bị dùng chung",
    ],
    "equipment_repair": [
        "vì thiết bị thường xuyên mất nguồn",
        "do máy hoạt động chập chờn",
        "vì thiết bị báo lỗi khi sử dụng",
        "để khắc phục tình trạng gián đoạn",
    ],
    "access_permission": [
        "để thực hiện nhiệm vụ được phân công",
        "để cập nhật hồ sơ công việc",
        "để tra cứu dữ liệu trong phạm vi phụ trách",
        "để hỗ trợ nhóm trong kỳ bàn giao",
    ],
    "vpn_access": [
        "để kết nối hệ thống khi đi công tác",
        "để hỗ trợ xử lý sự cố từ xa",
        "để làm việc an toàn ngoài văn phòng",
        "để truy cập tài nguyên nội bộ được giao",
    ],
    "advance_payment": [
        "để đặt cọc dịch vụ",
        "để chuẩn bị chi phí triển khai",
        "để thanh toán trước cho nhà cung cấp",
        "để phục vụ chuyến công tác sắp tới",
    ],
    "expense_reimbursement": [
        "cho khoản tiếp khách đã chi",
        "cho chi phí di chuyển đã ứng trước",
        "cho vật tư đã mua phục vụ công việc",
        "cho khoản lưu trú trong chuyến công tác",
    ],
    "budget_approval": [
        "để triển khai hạng mục mới",
        "để bổ sung nguồn lực quý tới",
        "để thực hiện kế hoạch đã thống nhất",
        "để mở rộng phạm vi dự án",
    ],
    "contract_payment": [
        "theo tiến độ thanh toán đã thỏa thuận",
        "cho hạng mục đã hoàn thành",
        "cho đợt nghiệm thu vừa kết thúc",
        "theo lịch thanh toán của đối tác",
    ],
    "stationery": [
        "vì kho vật tư sắp hết",
        "để chuẩn bị đợt đào tạo nội bộ",
        "để phục vụ lưu trữ hồ sơ",
        "để bổ sung cho khu vực làm việc",
    ],
    "vehicle_booking": [
        "để đưa đoàn đi khảo sát",
        "để đón đối tác tới văn phòng",
        "để di chuyển giữa các chi nhánh",
        "để vận chuyển hồ sơ đến đối tác",
    ],
    "meeting_room": [
        "để họp đánh giá tiến độ",
        "để trao đổi với đối tác",
        "để đào tạo nhân sự mới",
        "để thống nhất kế hoạch tuần",
    ],
}
DEPT_CONTEXT = {
    "hr": ["nhóm tuyển dụng", "bộ phận đào tạo nhân sự", "nhóm chính sách lao động"],
    "it": [
        "team phát triển phần mềm",
        "nhóm quản trị hệ thống",
        "bộ phận hỗ trợ kỹ thuật",
    ],
    "finance": [
        "nhóm kế toán thanh toán",
        "bộ phận quản lý tài chính",
        "nhóm kiểm soát chi phí",
    ],
    "marketing": [
        "nhóm truyền thông thương hiệu",
        "team quảng cáo",
        "bộ phận tổ chức chiến dịch",
    ],
    "sales": [
        "nhóm kinh doanh khách hàng",
        "bộ phận bán hàng",
        "team phát triển thị trường",
    ],
    "operations": [
        "nhóm điều phối vận hành",
        "bộ phận hậu cần",
        "nhóm quản lý văn phòng",
    ],
    "legal": ["bộ phận pháp chế", "nhóm rà soát pháp lý", "nhóm tư vấn tuân thủ"],
}
FINANCE = {
    "advance_payment",
    "expense_reimbursement",
    "budget_approval",
    "contract_payment",
}
DOCS = FINANCE | {
    "travel",
    "equipment_new",
    "equipment_repair",
    "stationery",
    "vehicle_booking",
}
SPLIT_TYPES = FINANCE | {"equipment_new", "travel"}
ZERO = {t for t, s in SPECS.items() if s[3] == 0}
ROLES = ["intern", "junior", "senior", "lead", "manager", "director"]
PRIORITY_TEXT = {
    "low": [
        "Có thể xử lý theo lịch thông thường.",
        "Chưa cần xử lý ngay trong tuần này.",
        "Nhờ sắp xếp khi thuận tiện trong tháng.",
    ],
    "medium": [
        "Mong được phản hồi trong vài ngày tới.",
        "Nhờ xử lý theo kế hoạch tuần này.",
        "Đề nghị xem xét trước buổi làm việc tuần tới.",
    ],
    "high": [
        "Cần phản hồi trong ngày để tránh chậm bàn giao.",
        "Lịch triển khai ngày mai đang chờ xác nhận.",
        "Đối tác cần xác nhận sớm để giữ lịch.",
    ],
    "urgent": [
        "Cần xử lý ngay vì công việc đang bị gián đoạn.",
        "Mong phản hồi trong hai giờ để kịp hạn chót.",
        "Đây là việc phát sinh cần giải quyết ngay hôm nay.",
    ],
}


def money(value):
    return f"{value:,}".replace(",", ".") + " đồng"


def noisy(text, rng):
    mode = rng.randrange(3)
    if mode == 0:
        text = "".join(
            c
            for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )
        return text.replace("đ", "d").replace("Đ", "D")
    if mode == 1:
        return (
            text.lower()
            .replace("không", "ko")
            .replace("được", "dc")
            .replace("với", "vs")
        )
    words = text.split()
    indices = [i for i, w in enumerate(words) if len(w) >= 5 and w.isalpha()]
    if indices:
        i = rng.choice(indices)
        w = words[i]
        words[i] = w[:1] + w[2] + w[1] + w[3:]
    return "  ".join(words)


def score_risk(x):
    """Deterministic policy labels; not a fraud adjudication model."""
    t, a = x["request_type"], x["amount_vnd"]
    missing = t in DOCS and a > 0 and not x["has_receipt"]
    if x["is_over_budget"] or x["is_split_amount_suspect"]:
        return 5
    if t == "contract_payment" and x["is_off_hours"] and missing:
        return 5
    if x["is_off_hours"] and x["past_requests_count"] >= 40 and missing:
        return 5
    if (
        x["user_role"] in ("intern", "junior")
        and a >= 20000000
        and missing
        and x["is_off_hours"]
    ):
        return 5
    base = (
        1 if t in {"leave_annual", "remote_work", "meeting_room", "stationery"} else 2
    )
    if t in {
        "advance_payment",
        "budget_approval",
        "contract_payment",
        "access_permission",
    }:
        base = 3
    if a > SPECS[t][2] * 1000000 or missing:
        base = max(base, 4)
    if x["user_role"] in ("intern", "junior") and a >= 20000000:
        base = max(base, 4)
    count, rate = x["past_requests_count"], x["past_rejection_rate"]
    if count >= 5 and rate >= 0.5:
        base = max(base, 4)
    elif count >= 5 and rate >= 0.25:
        base = max(base, 3)
    if not x["is_template_matched"] or (x["is_off_hours"] and count >= 40):
        base = max(base, 3)
    if t == "overtime" and a >= 5000000:
        base = max(base, 3)
    if x["user_tenure_months"] <= 3 or (t == "stationery" and a > 1000000):
        base = max(base, 2)
    return base


def build_text(x, rng, add_noise):
    t = x["request_type"]
    values = {
        "item": rng.choice(
            [
                "màn hình Dell 27 inch",
                "máy tính xách tay",
                "máy in văn phòng",
                "bộ máy tính để bàn",
                "thiết bị hội nghị",
            ]
        ),
        "app": rng.choice(
            [
                "CRM",
                "ERP",
                "kho tài liệu nội bộ",
                "hệ thống báo cáo",
                "cổng quản lý dự án",
            ]
        ),
        "supply": rng.choice(
            [
                "giấy A4",
                "bút và sổ ghi chép",
                "bìa lưu hồ sơ",
                "mực in",
                "vật tư văn phòng",
            ]
        ),
    }
    action = rng.choice(SPECS[t][4]).format(**values)
    context = rng.choice(DEPT_CONTEXT[x["department"]])
    project = rng.choice(
        [
            "Atlas",
            "Sao Mai",
            "An Phú",
            "Delta",
            "Bình Minh",
            "Hải Đăng",
            "Orion",
            "Hòa Bình",
        ]
    )
    day = f"ngày {rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}"
    title = rng.choice(
        [
            f"{action} cho {context}",
            f"{action} - {day}",
            f"{action} theo kế hoạch {project}",
            f"{action} đợt này",
        ]
    )
    title = title[0].upper() + title[1:]
    reason = rng.choice(REASONS[t])
    lead = rng.choice(
        [
            f"Em thuộc {context}",
            f"Tôi đại diện {context}",
            f"Bên {context}",
            f"Nhóm em phụ trách công việc của {context}",
        ]
    )
    parts = [f"{lead}, {action} {reason}."]
    priority = rng.choice(PRIORITY_TEXT[x["priority_level"]])
    if t in {"leave_annual", "leave_unpaid", "remote_work"}:
        parts.append(f"Thời gian dự kiến {rng.randint(1, 5)} ngày, từ {day}.")
    elif t == "meeting_room":
        parts.append(f"Dự kiến {rng.randint(3, 20)} người tham dự vào {day}.")
    elif t == "travel":
        parts.append(
            f"Địa điểm: {rng.choice(['Hà Nội', 'Đà Nẵng', 'Hải Phòng', 'TP.HCM', 'Bắc Ninh'])}; lịch đi {day}."
        )
    else:
        parts.append(f"Hạng mục thuộc kế hoạch {project}, dự kiến {day}.")
    if x["amount_vnd"]:
        parts.append(f"Số tiền đề nghị là {money(x['amount_vnd'])}.")
    if t in DOCS and x["amount_vnd"]:
        parts.append(
            "Em đã đính kèm chứng từ liên quan."
            if x["has_receipt"]
            else "Chứng từ còn thiếu, em xin bổ sung sau."
        )
    if not x["is_template_matched"] and rng.random() < 0.6:
        parts.append("Một số mục trong biểu mẫu chưa điền đủ.")
    # Keep the action and priority cue; vary optional detail without cutting words.
    candidates = parts[1:] + [
        rng.choice(
            [
                "Em sẽ phối hợp bàn giao đầy đủ.",
                "Nhờ anh chị kiểm tra giúp.",
                "Người phụ trách có thể liên hệ để xác minh.",
                "Em sẵn sàng giải trình thêm khi cần.",
            ]
        )
    ]
    desc = parts[0]
    for part in candidates:
        if rng.random() < 0.78 and len(desc + " " + part + " " + priority) <= 370:
            desc += " " + part
    desc += " " + priority
    if add_noise:
        title, desc = noisy(title, rng), noisy(desc, rng)
    if len(desc) > 400:
        desc = " ".join(desc.split())  # Normalize noise-induced doubled spaces.
    if len(desc) > 400:
        desc = desc[:400].rsplit(" ", 1)[0]
    return title, desc


def make_row(t, rng):
    dept = "finance" if t in FINANCE else rng.choice(list(DEPT_CONTEXT))
    role = rng.choices(ROLES, [8, 28, 32, 16, 12, 4])[0]
    tenure = rng.randint(1, 12 if role == "intern" else 36 if role == "junior" else 120)
    lo, typical, upper = SPECS[t][1:4]
    amount = 0
    if upper:
        value = (
            rng.uniform(typical, upper)
            if rng.random() < 0.10
            else rng.triangular(lo, typical, lo)
        )
        amount = max(10000, round(value * 100) * 10000)
    if t == "vehicle_booking" and rng.random() < 0.4:
        amount = 0  # Internal vehicle, no incremental payment.
    # Latent scenario simulation. No real employee/vendor/time grouping exists.
    split = int(t in SPLIT_TYPES and rng.random() < 0.045)
    if split:
        threshold = rng.choice([20000000, 50000000, 100000000])
        amount = round(threshold * rng.uniform(0.90, 0.995) / 10000) * 10000
    dept_budget = {
        "hr": 120,
        "it": 500,
        "finance": 900,
        "marketing": 350,
        "sales": 300,
        "operations": 600,
        "legal": 150,
    }[dept]
    budget = min(
        3000000000, round(rng.lognormvariate(0, 0.8) * dept_budget * 100) * 10000
    )
    if rng.random() < 0.025:
        budget = 0
    receipt = int(rng.random() < (0.88 if t in DOCS and amount else 0.12))
    attachments = (
        rng.randint(1, 6) if receipt else rng.choices([0, 1, 2, 3], [70, 20, 8, 2])[0]
    )
    if receipt and rng.random() < 0.05:
        attachments = rng.randint(7, 10)
    count = rng.randint(0, min(50, tenure * 3))
    if split:
        count = rng.randint(3, 50)
    if rng.random() < 0.04:
        count = rng.randint(40, 50)  # Busy users as well as suspicious scenarios.
    p = rng.betavariate(1, 12) if rng.random() < 0.9 else rng.betavariate(4, 3)
    rejected = sum(rng.random() < p for _ in range(count))
    rate = round(rejected / count, 2) if count else 0.0
    off = int(rng.random() < (0.40 if count >= 40 else 0.18))
    # Priority is driven by simulated time pressure, not by the risk target.
    pressure = rng.choices(["low", "medium", "high", "urgent"], [23, 51, 20, 6])[0]
    lifecycle = SPECS[t][0]
    if amount >= 100000000:
        lifecycle = "C"
    elif lifecycle == "A" and amount > 5000000:
        lifecycle = "B"
    x = {
        "request_id": "",
        "title": "",
        "description": "",
        "department": dept,
        "request_type": t,
        "lifecycle_template": lifecycle,
        "amount_vnd": amount,
        "budget_remaining_vnd": budget,
        "has_receipt": receipt,
        "num_attachments": attachments,
        "user_role": role,
        "user_tenure_months": tenure,
        "past_requests_count": count,
        "past_rejection_rate": rate,
        "is_off_hours": off,
        "is_split_amount_suspect": split,
        "is_over_budget": int(amount > budget),
        "is_template_matched": int(rng.random() < 0.92),
        "priority_level": pressure,
        "risk_score": 0,
    }
    x["risk_score"] = score_risk(x)
    return x


def validate(x):
    def check(ok, message):
        if not ok:
            raise ValueError(f"{x['request_id']}: {message}")

    check(list(x) == COLUMNS, "Sai schema")
    check(
        x["department"] in DEPT_CONTEXT and x["request_type"] in SPECS, "Sai danh mục"
    )
    check(30 <= len(x["description"]) <= 400 and bool(x["title"]), "Sai độ dài văn bản")
    check(
        x["user_role"] in ROLES and 1 <= x["user_tenure_months"] <= 120, "Sai nhân sự"
    )
    check(
        x["priority_level"] in PRIORITY_TEXT and x["lifecycle_template"] in "ABC",
        "Sai nhãn",
    )
    check(
        0 <= x["amount_vnd"] <= 2000000000
        and 0 <= x["budget_remaining_vnd"] <= 3000000000,
        "Sai tiền",
    )
    check(
        x["request_type"] not in ZERO or x["amount_vnd"] == 0,
        "Loại phi tài chính có tiền",
    )
    check(
        x["request_type"] not in FINANCE or x["department"] == "finance",
        "Sai phòng tài chính",
    )
    flags = [
        "has_receipt",
        "is_off_hours",
        "is_split_amount_suspect",
        "is_over_budget",
        "is_template_matched",
    ]
    check(all(x[k] in (0, 1) for k in flags), "Sai cờ nhị phân")
    check(0 <= x["num_attachments"] <= 10, "Sai số tệp")
    check(not x["has_receipt"] or x["num_attachments"] >= 1, "Chứng từ thiếu tệp")
    count, rate = x["past_requests_count"], x["past_rejection_rate"]
    check(0 <= count <= 50 and 0 <= rate <= 1, "Sai lịch sử")
    check(
        rate == 0
        if count == 0
        else any(round(k / count, 2) == rate for k in range(count + 1)),
        "Tỷ lệ không khớp lịch sử",
    )
    check(
        x["is_over_budget"] == int(x["amount_vnd"] > x["budget_remaining_vnd"]),
        "Sai cờ ngân sách",
    )
    check(
        not (x["is_over_budget"] or x["is_split_amount_suspect"])
        or x["risk_score"] == 5,
        "Sai mức 5",
    )
    check(
        1 <= x["risk_score"] <= 5 and x["risk_score"] == score_risk(x), "Sai risk_score"
    )


def generate_dataset(
    n_samples=N_SAMPLES, seed=20261003, noise_rate=0.06, output=OUTPUT
):
    if not 16 <= n_samples <= 99999:
        raise ValueError("n_samples phải từ 16 đến 99999 để giữ ID REQ-xxxxx")
    if not 0.05 <= noise_rate <= 0.08:
        raise ValueError("noise_rate phải trong khoảng 0.05–0.08")
    rng = random.Random(seed)
    types = list(SPECS)
    order = [types[i % len(types)] for i in range(n_samples)]
    rng.shuffle(order)  # Balanced type coverage, not real-world prevalence.
    noise_indices = set(rng.sample(range(n_samples), round(n_samples * noise_rate)))
    rows, seen = [], set()
    for i, t in enumerate(order):
        x = make_row(t, rng)
        x["request_id"] = f"REQ-{i + 1:05d}"
        for attempt in range(100):
            x["title"], x["description"] = build_text(x, rng, i in noise_indices)
            key = (x["title"], x["description"])
            if key not in seen:
                seen.add(key)
                break
        else:
            raise RuntimeError("Không tạo được cặp văn bản mới; cần mở rộng templates")
        validate(x)
        rows.append(x)
        if (i + 1) % max(1, n_samples // 20) == 0 or i + 1 == n_samples:
            print(
                f"\rĐang sinh: {i + 1:,}/{n_samples:,} ({(i + 1) / n_samples:.0%})",
                end="",
                flush=True,
            )
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for x in rows:
            writer.writerow(
                {**x, "past_rejection_rate": f"{x['past_rejection_rate']:.2f}"}
            )
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS or sum(1 for _ in reader) != n_samples:
            raise RuntimeError("Kiểm tra CSV sau ghi thất bại")
    print(
        f"\nĐã lưu: {path.resolve()}\nSeed: {seed}; mẫu có nhiễu văn bản: {len(noise_indices):,}"
    )
    for column in [
        "department",
        "request_type",
        "lifecycle_template",
        "priority_level",
        "risk_score",
    ]:
        print(f"\n{column:<26} | {'Số mẫu':>8} | {'Tỷ lệ':>7}")
        print("-" * 49)
        for value, count in sorted(Counter(x[column] for x in rows).items()):
            print(f"{value!s:<26} | {count:>8,} | {count / n_samples:>6.2%}")
    print("\nKiểm tra ràng buộc: PASS; cặp title/description trùng: 0")
    for flag in ["is_split_amount_suspect", "is_over_budget", "is_off_hours"]:
        print(f"{flag}: {sum(x[flag] for x in rows):,}")
    print("Dữ liệu mô phỏng: điểm ML cao không chứng minh hiệu quả thực tế.")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-samples", type=int, default=N_SAMPLES)
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--noise-rate", type=float, default=0.06)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    generate_dataset(args.n_samples, args.seed, args.noise_rate, args.output)

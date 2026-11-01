"""
Enterprise Policy & Public Web Scraped Data AI Retraining Pipeline:
1. Nạp chính sách doanh nghiệp công nghệ & dữ liệu báo giá / quy chế thực tế
2. Sinh dữ liệu huấn luyện mở rộng (Augmented Synthetic Enterprise Dataset - 8.000 samples)
3. Huấn luyện lại bộ mô hình NLP Phân loại yêu cầu & Mô hình XGBoost Đánh giá Rủi ro
4. Xuất artifacts vào ai_service/models/ và lưu metadata báo cáo đánh giá
"""

import datetime
import json
import os
import pickle
import random
import time

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
POLICIES_FILE = os.path.join(DATA_DIR, "active_enterprise_policy.json")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 1. PROFILE DOANH NGHIỆP PHẦN MỀM THỰC TẾ (150-300 NHÂN SỰ)
ENTERPRISE_DEPARTMENTS = ["TECH", "PROD", "QA", "FIN", "HR", "BIZ", "OPS", "BOD"]

REQUEST_TYPES = [
    "IT_ACCESS_REQUEST",
    "IT_EQUIPMENT_PROCUREMENT",
    "TRAVEL_EXPENSE_CLAIM",
    "FINANCE_PAYMENT_REQUEST",
    "HR_LEAVE_APPLICATION",
    "HR_WFH_REQUEST",
    "GENERAL_FACILITY_BOOKING"
]

SAMPLE_TEMPLATES = {
    "IT_ACCESS_REQUEST": [
        "Đề xuất cấp quyền truy cập {system} môi trường Production cho kỹ sư {role}",
        "Xin cấp tài khoản quản trị AWS Cloud IAM Role Administrator phục vụ triển khai hạ tầng",
        "Yêu cầu mở quyền truy cập cơ sở dữ liệu {system} Read-Only để đối soát dữ liệu báo cáo",
        "Cấp quyền VPN Production Gateway cho nhân sự On-call hỗ trợ sự cố khẩn cấp",
        "Yêu cầu cấp tài khoản GitHub Enterprise và phân quyền Repository Core-Banking"
    ],
    "IT_EQUIPMENT_PROCUREMENT": [
        "Đề xuất mua sắm máy tính xách tay {laptop} từ nhà phân phối {supplier} cho nhân sự mới",
        "Mua bổ sung màn hình đồ họa {monitor} phục vụ thiết kế UX/UI sản phẩm",
        "Đề xuất mua linh kiện nâng cấp RAM 32GB và bàn phím công thái học {accessory}",
        "Mua sắm thiết bị máy chủ server phục vụ cụm Kubernetes thử nghiệm",
        "Đăng ký cấp phát tai nghe chống ồn đàm thoại cho nhóm hỗ trợ khách hàng quốc tế"
    ],
    "TRAVEL_EXPENSE_CLAIM": [
        "Thanh toán chi phí công tác vé máy bay {flight} và khách sạn tham gia Tech Summit",
        "Đề xuất tạm ứng công tác phí khảo sát và triển khai phần mềm cho khách hàng tại {location}",
        "Quyết toán vé máy bay khứ hồi và phụ cấp lưu trú cho chuyến công tác dự án ngân hàng",
        "Đề nghị hoàn ứng chi phí tiếp khách và taxi di chuyển làm việc với đối tác {partner}",
        "Chi phí khách sạn lưu trú 3 đêm tại chi nhánh TP.HCM theo đúng hạn mức công ty"
    ],
    "FINANCE_PAYMENT_REQUEST": [
        "Thanh toán hợp đồng bản quyền dịch vụ điện toán đám mây {cloud_service} quý 2",
        "Đề nghị thanh toán hóa đơn cung cấp thiết bị văn phòng từ công ty {supplier}",
        "Thanh toán chi phí đường truyền Internet Leased Line cáp quang tốc độ cao",
        "Đề xuất chi trả phí dịch vụ kiểm toán độc lập và tư vấn pháp lý hợp đồng",
        "Thanh toán phí gia hạn tên miền, chứng chỉ số SSL và hạ tầng bảo mật Cloudflare"
    ],
    "HR_LEAVE_APPLICATION": [
        "Đơn xin nghỉ phép năm hưởng nguyên lương {days} ngày từ ngày {date}",
        "Xin nghỉ phép chế độ chăm sóc con ốm theo quy định của Luật Lao động và công ty",
        "Đăng ký nghỉ bù sau đợt trực vận hành hệ thống Go-Live cuối tuần qua",
        "Đơn xin nghỉ phép kết hôn theo chế độ phúc lợi dành cho nhân viên chính thức",
        "Xin nghỉ ốm điều trị tại nhà có giấy xác nhận của cơ sở y tế"
    ],
    "HR_WFH_REQUEST": [
        "Đăng ký làm việc từ xa (WFH) 2 ngày trong tuần theo chính sách Hybrid Working",
        "Xin phép WFH thứ Năm và thứ Sáu do nhà có việc gia đình nhưng vẫn đảm bảo tiến độ Sprint",
        "Đăng ký WFH ngày {date} để tập trung viết tài liệu kỹ thuật Architecture Design",
        "Đề xuất WFH thời gian phục hồi sau phẫu thuật nhỏ, cam kết giữ liên lạc qua Slack"
    ],
    "GENERAL_FACILITY_BOOKING": [
        "Đặt phòng họp lớn {room} tổ chức buổi tổng kết Sprint Planning toàn khối công nghệ",
        "Đăng ký sử dụng hội trường Townhall cho sự kiện Demo Day và chia sẻ công nghệ nội bộ",
        "Đặt phòng họp nhóm có màn hình tương tác để họp trực tuyến với đối tác nước ngoài",
        "Đăng ký sử dụng phòng Studio để ghi hình bài giảng đào tạo nhân sự mới"
    ]
}

SYSTEMS = ["AWS Production", "GitHub Enterprise", "PostgreSQL Core", "Jira Cloud", "Kubernetes Staging", "Redis Cluster"]
ROLES = ["Tech Lead", "Senior Backend Dev", "DevOps Engineer", "QA Automation", "Data Analyst"]
LAPTOPS = ["Apple MacBook Pro 14 inch M3 Pro", "Dell XPS 15 9530", "Lenovo ThinkPad T14 Gen 4"]
MONITORS = ["Dell UltraSharp U2723QE 4K", "Dell Professional P2422H"]
ACCESSORIES = ["Logitech MX Master 3S", "Keychron K2 Pro"]
SUPPLIERS = ["FPT Synnex", "Phong Vũ", "CMC Telecom", "Hanoicomputer"]
LOCATIONS = ["TP. Hồ Chí Minh", "Đà Nẵng", "Singapore", "Cần Thơ"]
PARTNERS = ["Ngân hàng VIB", "Tập đoàn Masan", "VNPAY", "FPT Software"]
FLIGHTS = ["Vietnam Airlines HAN-SGN", "Bamboo Airways HAN-DAD"]
ROOMS = ["Phòng Alpha 85 inch", "Phòng Beta", "Hội trường Townhall Viettel Complex"]
CLOUD_SERVICES = ["Amazon Web Services", "Google Cloud Platform", "Atlassian Jira/Confluence", "Slack Business"]


def generate_synthetic_dataset(num_samples: int = 8000) -> pd.DataFrame:
    """Sinh bộ dữ liệu synthetic 8.000 mẫu dựa trên profile công ty phần mềm."""
    print(f"📊 Đang sinh {num_samples} mẫu dữ liệu yêu cầu thực tế của doanh nghiệp IT...")
    data = []

    for i in range(num_samples):
        req_type = random.choice(REQUEST_TYPES)
        template_pattern = random.choice(SAMPLE_TEMPLATES[req_type])

        # Điền dữ liệu biến ngẫu nhiên
        text = template_pattern.format(
            system=random.choice(SYSTEMS),
            role=random.choice(ROLES),
            laptop=random.choice(LAPTOPS),
            monitor=random.choice(MONITORS),
            accessory=random.choice(ACCESSORIES),
            supplier=random.choice(SUPPLIERS),
            location=random.choice(LOCATIONS),
            partner=random.choice(PARTNERS),
            flight=random.choice(FLIGHTS),
            room=random.choice(ROOMS),
            cloud_service=random.choice(CLOUD_SERVICES),
            days=random.randint(1, 5),
            date=f"{random.randint(1, 28)}/{random.randint(1, 12)}/2026"
        )

        # Mapping phòng ban thụ lý
        if req_type in ["IT_ACCESS_REQUEST", "IT_EQUIPMENT_PROCUREMENT"]:
            dept = random.choice(["TECH", "OPS"])
        elif req_type in ["TRAVEL_EXPENSE_CLAIM", "FINANCE_PAYMENT_REQUEST"]:
            dept = random.choice(["FIN", "BIZ", "BOD"])
        elif req_type in ["HR_LEAVE_APPLICATION", "HR_WFH_REQUEST"]:
            dept = "HR"
        else:
            dept = random.choice(["OPS", "HR"])

        # Sinh các feature định lượng rủi ro
        if req_type == "FINANCE_PAYMENT_REQUEST":
            amount_vnd = random.choice([20000000, 50000000, 150000000, 500000000, 1500000000])
            budget_ratio = min(1.0, amount_vnd / 500000000)
            is_out_of_policy = 1 if amount_vnd > 300000000 else 0
            access_risk = 0.1
            sod_conflict = 0
        elif req_type == "IT_ACCESS_REQUEST":
            amount_vnd = 0
            budget_ratio = 0.0
            is_out_of_policy = 1 if "Production" in text or "Administrator" in text else 0
            access_risk = 0.9 if is_out_of_policy else 0.4
            sod_conflict = 1 if "Admin" in text and random.random() < 0.3 else 0
        elif req_type == "TRAVEL_EXPENSE_CLAIM":
            amount_vnd = random.randint(3000000, 35000000)
            budget_ratio = amount_vnd / 200000000
            is_out_of_policy = 1 if amount_vnd > 25000000 else 0
            access_risk = 0.1
            sod_conflict = 0
        elif req_type == "IT_EQUIPMENT_PROCUREMENT":
            amount_vnd = random.choice([2500000, 12500000, 49990000, 89990000])
            budget_ratio = amount_vnd / 300000000
            is_out_of_policy = 1 if amount_vnd > 50000000 else 0
            access_risk = 0.2
            sod_conflict = 0
        else:
            amount_vnd = 0
            budget_ratio = 0.0
            is_out_of_policy = 0
            access_risk = 0.05
            sod_conflict = 0

        # Tính toán điểm rủi ro tổng thể (Ground Truth)
        tenure_months = random.randint(2, 60)
        risk_score = (
            0.35 * budget_ratio
            + 0.30 * access_risk
            + 0.20 * is_out_of_policy
            + 0.15 * sod_conflict
            - (0.05 if tenure_months > 24 else 0.0)
        )
        risk_score = float(np.clip(risk_score, 0.05, 0.98))

        if risk_score < 0.25:
            risk_level = "LOW"
            risk_class = 0
        elif risk_score < 0.55:
            risk_level = "MEDIUM"
            risk_class = 1
        elif risk_score < 0.80:
            risk_level = "HIGH"
            risk_class = 2
        else:
            risk_level = "CRITICAL"
            risk_class = 3

        data.append({
            "title": text,
            "description": f"Yêu cầu xử lý theo quy chế công ty: {text}",
            "request_type_code": req_type,
            "department_code": dept,
            "amount_minor": amount_vnd * 100,
            "budget_ratio": budget_ratio,
            "access_risk": access_risk,
            "is_out_of_policy": is_out_of_policy,
            "sod_conflict": sod_conflict,
            "tenure_months": tenure_months,
            "risk_score": risk_score,
            "risk_class": risk_class,
            "risk_level": risk_level
        })

    df = pd.DataFrame(data)
    csv_path = os.path.join(DATA_DIR, "enterprise_synthetic_dataset.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"   ✓ Đã lưu dataset tại: {csv_path}")
    return df


def train_nlp_models(df: pd.DataFrame) -> dict:
    """Huấn luyện mô hình NLP phân loại loại yêu cầu và phòng ban từ văn bản tiếng Việt."""
    print("\n🧠 1. Huấn luyện mô hình NLP Multi-class Classifier...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True
    )
    X_tfidf = vectorizer.fit_transform(df["title"])

    # 1.1 Phân loại Request Type
    y_type = df["request_type_code"]
    X_train, X_test, y_train, y_test = train_test_split(X_tfidf, y_type, test_size=0.2, random_state=42)
    clf_type = LogisticRegression(max_iter=1000, C=1.5)
    clf_type.fit(X_train, y_train)
    y_pred = clf_type.predict(X_test)
    type_acc = accuracy_score(y_test, y_pred)
    type_f1 = f1_score(y_test, y_pred, average="weighted")
    print(f"   ✓ Request Type Model Accuracy: {type_acc * 100:.2f}%, F1: {type_f1:.4f}")

    # 1.2 Phân loại Department
    y_dept = df["department_code"]
    X_train_d, X_test_d, y_train_d, y_test_d = train_test_split(X_tfidf, y_dept, test_size=0.2, random_state=42)
    clf_dept = LogisticRegression(max_iter=1000, C=1.5)
    clf_dept.fit(X_train_d, y_train_d)
    y_pred_d = clf_dept.predict(X_test_d)
    dept_acc = accuracy_score(y_test_d, y_pred_d)
    print(f"   ✓ Department Model Accuracy: {dept_acc * 100:.2f}%")

    # Lưu artifacts
    with open(os.path.join(MODELS_DIR, "nlp_vectorizer.pkl"), "wb") as f:
        pickle.dump(vectorizer, f)
    with open(os.path.join(MODELS_DIR, "nlp_request_type_model.pkl"), "wb") as f:
        pickle.dump(clf_type, f)
    with open(os.path.join(MODELS_DIR, "nlp_department_model.pkl"), "wb") as f:
        pickle.dump(clf_dept, f)

    return {
        "nlp_request_type_acc": round(type_acc, 4),
        "nlp_request_type_f1": round(type_f1, 4),
        "nlp_department_acc": round(dept_acc, 4)
    }


def train_risk_models(df: pd.DataFrame) -> dict:
    """Huấn luyện mô hình XGBoost Risk Scoring dự đoán mức độ rủi ro phê duyệt."""
    print("\n⚡ 2. Huấn luyện mô hình XGBoost Risk Scoring...")
    feature_cols = [
        "amount_minor",
        "budget_ratio",
        "access_risk",
        "is_out_of_policy",
        "sod_conflict",
        "tenure_months"
    ]
    X = df[feature_cols]
    y = df["risk_class"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        n_estimators=120,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric="mlogloss"
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    risk_acc = accuracy_score(y_test, y_pred)
    risk_f1 = f1_score(y_test, y_pred, average="weighted")
    print(f"   ✓ XGBoost Risk Model Accuracy: {risk_acc * 100:.2f}%, F1: {risk_f1:.4f}")

    # Huấn luyện các sub-model chuyên biệt cho IT, Finance, HR
    sub_models = {}
    for domain, filter_cond in [
        ("finance", df["request_type_code"].isin(["FINANCE_PAYMENT_REQUEST", "TRAVEL_EXPENSE_CLAIM"])),
        ("it", df["request_type_code"].isin(["IT_ACCESS_REQUEST", "IT_EQUIPMENT_PROCUREMENT"])),
        ("hr", df["request_type_code"].isin(["HR_LEAVE_APPLICATION", "HR_WFH_REQUEST"]))
    ]:
        sub_df = df[filter_cond]
        if len(sub_df) > 100:
            m = xgb.XGBClassifier(n_estimators=80, max_depth=4, learning_rate=0.1, random_state=42, eval_metric="mlogloss")
            m.fit(sub_df[feature_cols], sub_df["risk_class"])
            with open(os.path.join(MODELS_DIR, f"risk_model_{domain}.pkl"), "wb") as f:
                pickle.dump(m, f)
            sub_models[f"risk_model_{domain}"] = "trained"

    # Lưu artifacts
    with open(os.path.join(MODELS_DIR, "risk_model.pkl"), "wb") as f:
        pickle.dump(model, f)
    with open(os.path.join(MODELS_DIR, "feature_columns.json"), "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, indent=2)

    return {
        "risk_model_acc": round(risk_acc, 4),
        "risk_model_f1": round(risk_f1, 4),
        "sub_models": sub_models
    }


def main():
    print("🚀 Bắt đầu quá trình Huấn Luyện AI (Retraining AI Pipeline) theo Quy chế Doanh nghiệp Mới...")
    t0 = time.time()

    # 1. Đọc hoặc sinh dataset
    df = generate_synthetic_dataset(num_samples=8000)

    # 2. Huấn luyện NLP Models
    nlp_metrics = train_nlp_models(df)

    # 3. Huấn luyện XGBoost Risk Models
    risk_metrics = train_risk_models(df)

    # 4. Xuất Model Metadata & Báo cáo
    elapsed = round(time.time() - t0, 2)
    meta = {
        "pipeline_version": "v2.5.0-enterprise",
        "trained_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "training_duration_seconds": elapsed,
        "sample_count": len(df),
        "nlp_metrics": nlp_metrics,
        "risk_metrics": risk_metrics,
        "status": "READY_FOR_INFERENCE"
    }
    meta_path = os.path.join(MODELS_DIR, "model_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✨ HOÀN TẤT HUẤN LUYỆN TOÀN BỘ MÔ HÌNH AI TRONG {elapsed}s!")
    print(f"   Metadata đã lưu tại: {meta_path}")
    print(f"   NLP Accuracy: {nlp_metrics['nlp_request_type_acc']*100:.1f}%, XGBoost Accuracy: {risk_metrics['risk_model_acc']*100:.1f}%")


if __name__ == "__main__":
    main()

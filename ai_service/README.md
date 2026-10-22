# 🧠 AI Service — Enterprise Approval System (EAS)

AI Service là microservice thông minh chạy bằng **FastAPI** (port `8001`), phụ trách xử lý ngôn ngữ tự nhiên (NLP), đánh giá rủi ro & gian lận (Risk Scoring), tự động duyệt (Auto-Approve), trích xuất chứng từ (OCR) và tóm tắt hồ sơ (LLM Summarization).

---

## 🏛️ 1. Kiến Trúc & Luồng Dữ Liệu

```
┌────────────────────────────────┐
│   API Gateway (Nginx :8080)    │  (Route /ai/* với Rate Limiting & SSL)
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐       ┌────────────────────────────────┐
│      ai_service (FastAPI)      │◀──────│  api_core (Django :8000)       │
│      Port 8001                 │       │  ai_client.py (Async & Sync)   │
└───────┬──────────────┬─────────┘       └────────────────────────────────┘
        │              │
        ▼              ▼
┌──────────────┐ ┌──────────────┐
│   models/    │ │ data/mock/   │
│  15 trained  │ │ 8 snapshots  │
│  artifacts   │ │  (read-only) │
└──────────────┘ └──────────────┘
```

---

## 🤖 2. 5 Chức Năng AI Chính

### 2.1. Smart Request Classifier (`POST /ai/classify/request`)
- **Mô hình**: TF-IDF Vectorizer + CalibratedClassifier (SGD/Logistic Regression).
- **Đầu vào**: `title` (tiêu đề), `description` (nội dung tiếng Việt tự nhiên).
- **Đầu ra**: 
  - `predicted_request_type`: 1 trong 16 loại yêu cầu (`leave_annual`, `contract_payment`, `equipment_new`,...).
  - `predicted_department`: Phòng ban xử lý (`hr`, `it`, `finance`, `marketing`, `sales`, `operations`, `legal`).
  - `predicted_template`: Biểu mẫu quy trình (`A`: đơn giản, `B`: 2 bước, `C`: 3 bên).
  - Độ tin cậy (`confidence`) và gợi ý quy trình (`workflow_suggestion`).
- **Hiệu năng**: Độ chính xác phân loại > 98%, thời gian suy luận < 15ms.

### 2.2. Risk & Fraud Scoring (`POST /ai/risk/score`)
- **Mô hình**: Ensemble đa tầng 4 mô hình **XGBoost** (`hist` tree method).
  - `risk_model_finance.pkl`: Chuyên sâu rủi ro thanh toán, tạm ứng, vượt ngân sách.
  - `risk_model_hr.pkl`: Chuyên sâu phát hiện bất thường nghỉ phép, tăng ca ngoài giờ.
  - `risk_model_it.pkl`: Chuyên sâu kiểm soát rủi ro leo thang đặc quyền (privilege escalation).
  - `risk_model.pkl` (Master): Xử lý tổng quát cho các nghiệp vụ còn lại.
- **Đặc trưng**: 19 features (amount_log, budget_ratio, is_over_budget, is_split_amount_suspect, past_rejection_rate, off_hours,...).
- **Đầu ra**: `risk_score` (1-5), nhãn rủi ro, độ tin cậy và giải thích nguyên nhân.

### 2.3. Auto-Approve Engine (`POST /ai/auto-approve/evaluate`)
- **Cơ chế**: Kết hợp Rule Engine minh bạch + ngưỡng Risk Threshold.
- **Điều kiện duyệt tự động**:
  1. `lifecycle_template == 'A'` (chỉ áp dụng cho quy trình phê duyệt đơn thuần, không cần thi công/nghiệm thu).
  2. `risk_score <= 2` (thuộc mức rủi ro rất thấp/thấp).
  3. Thỏa mãn business rules theo loại yêu cầu (đối chiếu quỹ phép từ `mock_hr`, phòng trống từ `mock_facilities`).
- **Đầu ra**: `decision` (`auto_approve` hoặc `escalate_to_human`) kèm danh sách lý do chi tiết.

### 2.4. Bóc Tách Hóa Đơn OCR (`POST /ai/ocr/extract-url`)
- **Mô hình**: Dual-engine PaddleOCR tiếng Việt (offline) kết hợp Gemini Vision (online fallback).
- **Đầu ra**: Bóc tách số hóa đơn, ngày phát hành, mã số thuế người bán, tổng tiền thanh toán và text thô.

### 2.5. Tóm Tắt & Phân Tích Hồ Sơ (`POST /ai/summarize/request`)
- **Mô hình**: Google Gemini 1.5 Flash (LLM).
- **Đầu ra**: Tóm tắt 2-3 câu ngắn gọn cho cấp lãnh đạo duyệt nhanh, trích xuất điểm mấu chốt và sắc thái tâm lý (sentiment).

---

## 📁 3. Cấu Trúc Thư Mục

```
ai_service/
├── main.py                     # Entry point FastAPI, middleware, router mounts
├── config.py                   # Pydantic Settings đọc cấu hình môi trường
├── ai_client.py                # Python SDK cho api_core gọi sang (Async/Sync)
├── Dockerfile                  # Container build cho AI Service
├── requirements.txt            # Python dependencies (FastAPI, XGBoost, Scikit-learn,...)
├── README.md                   # ← Tài liệu này
├── AI_ARCHITECTURE.md          # Đặc tả kiến trúc kỹ thuật chi tiết
│
├── models/                     # ★ 15 Pre-trained Model Artifacts
│   ├── nlp_vectorizer.pkl          # TF-IDF tiếng Việt (512 KB)
│   ├── nlp_request_type_model.pkl  # Phân loại 16 request types (1.7 MB)
│   ├── nlp_department_model.pkl    # Phân loại phòng ban (768 KB)
│   ├── nlp_template_model.pkl      # Phân loại Template A/B/C (330 KB)
│   ├── nlp_labels.json             # Nhãn tiếng Việt
│   ├── risk_model.pkl              # XGBoost Master (5.7 MB)
│   ├── risk_model_finance.pkl      # XGBoost Finance (2.5 MB)
│   ├── risk_model_hr.pkl           # XGBoost HR (2.9 MB)
│   ├── risk_model_it.pkl           # XGBoost IT (1.9 MB)
│   ├── domain_model_registry.json  # Mapping domain -> model
│   ├── encoders.json               # One-hot / Label encoders
│   └── feature_cols_*.json         # Danh sách cột đặc trưng từng domain
│
├── data/mock/                  # ★ Snapshots dữ liệu mock đã chuẩn hóa
│   ├── mock_hr.json                # HRIS: phòng ban, nhân viên, ngày phép
│   ├── mock_assets.json            # Quản lý tài sản, thiết bị
│   ├── mock_facilities.json        # Phòng họp, xe công vụ
│   ├── mock_crm.json               # Khách hàng, hợp đồng
│   ├── mock_procurement.json       # Nhà cung cấp, danh mục mua sắm
│   ├── mock_it.json                # Ứng dụng, quyền IAM, dịch vụ ITSM
│   ├── mock_finance.json           # Ngân sách trung tâm chi phí
│   ├── mock_travel.json            # Chính sách công tác
│   └── _manifest.json              # Tổng hợp metadata
│
├── routers/                    # Endpoints định tuyến
│   ├── classify.py                 # POST /ai/classify/request
│   ├── risk.py                     # POST /ai/risk/score
│   ├── auto_approve.py             # POST /ai/auto-approve/evaluate
│   ├── ocr.py                      # POST /ai/ocr/extract-url
│   ├── summarize.py                # POST /ai/summarize/request
│   └── mock_context.py             # GET /ai/mock/* (Tra cứu context snapshot)
│
└── training/                   # Bộ công cụ huấn luyện mô hình
    ├── data/                       # Dataset huấn luyện
    │   ├── enterprise_requests_dataset_large.csv  # 100K mẫu NLP
    │   ├── eapproval_risk_10000.csv               # 10K mẫu Risk
    │   └── partitions/                            # 1.75 triệu mẫu Big Data
    ├── generate_enterprise_requests.py # Sinh dữ liệu mẫu doanh nghiệp
    ├── enterprise_bigdata_generator.py # Sinh partition Big Data 1.75M dòng
    ├── train_nlp_classifier.py         # Huấn luyện mô hình NLP tiếng Việt
    ├── train_risk_model.py             # Huấn luyện mô hình XGBoost Master
    ├── train_domain_models.py          # Huấn luyện 3 mô hình XGBoost Domain
    ├── train_bigdata_models.py         # Huấn luyện trên 1.75M mẫu
    ├── inspect_models.py               # Kiểm tra feature importance & tham số
    ├── test_inference.py               # Test suy luận đa domain
    └── run_training_pipeline.py        # Chạy toàn bộ pipeline tự động
```

---

## 🎓 4. Hướng Dẫn Huấn Luyện Lại Mô Hình (Training Pipelines)

### 4.1. Chạy Toàn Bộ Pipeline Tự Động:
```bash
cd ai_service
python training/run_training_pipeline.py
```

### 4.2. Huấn Luyện Mô Hình NLP Phân Loại Tiếng Việt:
```bash
python training/train_nlp_classifier.py
```
*Kết quả:* Tạo ra 4 file `.pkl` và 1 file `.json` tại thư mục `models/` cùng báo cáo độ chính xác `training/data/nlp_evaluation_report.txt` (độ chính xác > 98%).

### 4.3. Huấn Luyện Mô Hình XGBoost Đa Miền (Finance, HR, IT, Master):
```bash
python training/train_domain_models.py
```
*Kết quả:* Tạo ra `risk_model_finance.pkl`, `risk_model_hr.pkl`, `risk_model_it.pkl` với thuật toán `hist` tối ưu cho dữ liệu bảng lớn.

### 4.4. Kiểm Tra Tham Số & Test Suy Luận (Inference):
```bash
# Kiểm tra kích thước và Top 5 feature quan trọng nhất
python training/inspect_models.py

# Test thử nghiệm 7 tình huống thực tế
python training/test_inference.py
```

---

## 🚀 5. Khởi Động Dịch Vụ

### Chạy Trực Tiếp (Local):
```bash
cd ai_service
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### Chạy Qua Docker Compose:
```bash
docker compose up -d ai-service
```

### Kiểm Tra Swagger UI:
Truy cập: `http://localhost:8001/docs` (khi chạy độc lập) hoặc `http://localhost:8088/docs` (qua API Gateway).

---

## 🔒 6. Cơ Chế Bảo Mật & Kháng Lỗi (Fault-Tolerance)

1. **X-Internal-Secret**: Tất cả endpoint nghiệp vụ yêu cầu header `X-Internal-Secret`. Chỉ `api_core` và các service nội bộ được cung cấp secret này.
2. **Nguyên tắc Least-Privilege**: `ai_service` **không** có thông tin đăng nhập database; chỉ đọc dữ liệu mock qua snapshot JSON được mount `read-only`.
3. **Fallback An Toàn**: Khi AI Service gặp sự cố hoặc quá tải, `api_core` tự động kích hoạt fallback (áp dụng `risk_weight` mặc định, chuyển người duyệt thủ công), đảm bảo hệ thống không bao giờ bị dừng hoạt động.

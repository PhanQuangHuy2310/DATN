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
- **Mô hình**: TF-IDF Vectorizer + Logistic Regression.
- **Đầu vào**: `title` (tiêu đề), `description` (nội dung tiếng Việt tự nhiên).
- **Đầu ra**: 
  - `predicted_request_type`: 1 trong 16 loại yêu cầu (`leave_annual`, `contract_payment`, `equipment_new`,...).
  - `predicted_department`: Phòng ban xử lý (`hr`, `it`, `finance`, `marketing`, `sales`, `operations`, `legal`).
  - `predicted_template`: Biểu mẫu quy trình (`A`: đơn giản, `B`: 2 bước, `C`: 3 bên).
  - Độ tin cậy (`confidence`) và gợi ý quy trình (`workflow_suggestion`).
- **Hiệu năng**: Xem báo cáo huấn luyện trên tập giữ riêng trong `models/model_metadata.json`. Điểm từ dữ liệu tổng hợp không chứng minh độ chính xác trên yêu cầu thật; cần đánh giá thêm bằng dữ liệu người dùng gán nhãn độc lập.

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
├── nlp_text.py                 # Chuẩn hóa văn bản; mã loại cũ → mã catalog v2
│
├── models/                     # ★ Model do training/train.py sinh ra
│   ├── nlp_classifier.pkl          # TF-IDF (từ + ký tự không dấu) → Logistic Regression, 58 loại catalog v2
│   ├── nlp_labels.json             # Catalog (nhóm, bộ phận, template) đi kèm bộ phân loại
│   ├── risk_model.pkl              # XGBoost master (mọi loại)
│   ├── risk_model_finance.pkl      # XGBoost Finance
│   ├── risk_model_hr.pkl           # XGBoost HR
│   ├── risk_model_it.pkl           # XGBoost IT
│   ├── domain_model_registry.json  # Mapping domain -> model
│   ├── encoders.json               # Mã hóa loại yêu cầu / phòng ban / vai trò
│   ├── feature_cols_*.json         # Danh sách cột đặc trưng từng domain
│   └── model_metadata.json         # Metrics của lần train gần nhất
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
└── training/                   # Huấn luyện mô hình (một lệnh duy nhất)
    ├── train.py                    # Train NLP + risk, đánh giá, ghi models/ và báo cáo
    └── data/
        ├── request_corpus.json         # Mẫu câu huấn luyện 58 loại (sinh câu với seed cố định)
        ├── request_eval_realistic.json # Câu viết tay để đánh giá: dev (được xem khi bổ sung dữ liệu) / test (chỉ để báo cáo)
        └── training_report.md          # Báo cáo, train.py ghi đè mỗi lần chạy
```

---

## 🎓 4. Hướng Dẫn Huấn Luyện Lại Toàn Bộ Mô Hình

Tạo môi trường Python 3.11 từ thư mục gốc repo, cài dependencies AI, rồi chạy pipeline thống nhất:

```powershell
py -3.11 -m venv ai_service\.venv-ai
ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-local.txt
# Cài đặt thêm PaddleOCR để chạy nhận dạng hóa đơn tiếng Việt cục bộ (PP-OCRv6):
ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-paddle.txt
ai_service\.venv-ai\Scripts\python.exe ai_service\training\train.py             # toàn bộ (~30 phút)
ai_service\.venv-ai\Scripts\python.exe ai_service\training\train.py --only nlp  # chỉ bộ phân loại (~15 phút)
```

Pipeline train bộ phân loại văn bản rồi bốn mô hình rủi ro (master, Finance, HR, IT) **lần lượt** để giới hạn RAM; XGBoost dùng tối đa 4 threads (`--threads 2` để giảm). Dữ liệu được sinh lại từ `request_corpus.json` với seed cố định: cùng seed cho cùng model. Model cũ chỉ được thay khi mọi bước train xong (ghi vào thư mục tạm rồi mới chuyển sang `models/`).

Dữ liệu huấn luyện là **tổng hợp** từ mẫu câu. Con số đáng tin nhất là độ chính xác trên **câu viết tay split `test`** trong `training/data/training_report.md`, vì các câu này không dùng để train hay để chỉnh dữ liệu. Thêm tình huống mới: thêm câu vào `titles`/`details` của đúng loại trong `request_corpus.json`, kiểm tra bằng split `dev`, rồi chạy lại `train.py`.

### 4.1. Kiểm tra model và kiểm thử chức năng
```powershell
# Nạp model hiện có và chạy thử vài câu
ai_service\.venv-ai\Scripts\python.exe ai_service\training\train.py --check
# Kiểm thử chức năng mọi endpoint trên service đang chạy (chỉ đọc, không ghi DB)
.\.venv\Scripts\python.exe test_ai_benchmark.py
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

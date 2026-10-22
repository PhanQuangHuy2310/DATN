# 🧠 AI Service — Kiến Trúc & Tài Liệu Kỹ Thuật

## Tổng quan

AI Service là microservice FastAPI (port 8001), cung cấp **5 chức năng AI thông minh** cho hệ thống EAS. Service này được gọi nội bộ từ `api_core` (Django) thông qua `ai_client.py`, hoặc route qua API Gateway (`/ai/*`).

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ API Gateway │────▶│ ai_service:8001  │────▶│ Trained Models (.pkl)   │
│ /ai/*       │     │ FastAPI          │     │ models/                 │
└─────────────┘     └────────┬─────────┘     └─────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ api_core:8000    │
                    │ Django           │
                    │ ai_client.py     │
                    └──────────────────┘
```

---

## 📁 Cấu trúc thư mục

```
ai_service/
├── main.py                 # FastAPI entry point, middleware, router mount
├── config.py               # Pydantic settings (env vars)
├── ai_client.py            # Client SDK để api_core gọi vào (async + sync)
├── Dockerfile              # Container image
├── requirements.txt        # Python dependencies
├── AI_ARCHITECTURE.md      # ← File này
│
├── models/                 # ★ Các model đã train — KHÔNG XÓA
│   ├── nlp_vectorizer.pkl          # TF-IDF vectorizer (512KB)
│   ├── nlp_request_type_model.pkl  # NLP classifier — loại yêu cầu (1.7MB)
│   ├── nlp_department_model.pkl    # NLP classifier — phòng ban (768KB)
│   ├── nlp_template_model.pkl      # NLP classifier — template A/B/C (330KB)
│   ├── nlp_labels.json             # Label mappings cho NLP
│   ├── risk_model.pkl              # XGBoost Master (5.7MB)
│   ├── risk_model_finance.pkl      # XGBoost Finance domain (2.5MB)
│   ├── risk_model_hr.pkl           # XGBoost HR domain (2.9MB)
│   ├── risk_model_it.pkl           # XGBoost IT domain (1.9MB)
│   ├── encoders.json               # Label encoders cho risk
│   ├── feature_columns.json        # Feature cols — master model
│   ├── feature_cols_finance.json   # Feature cols — finance domain
│   ├── feature_cols_hr.json        # Feature cols — HR domain
│   ├── feature_cols_it.json        # Feature cols — IT domain
│   └── domain_model_registry.json  # Registry mapping domain → model
│
├── routers/                # API endpoints
│   ├── classify.py         # POST /ai/classify/request
│   ├── risk.py             # POST /ai/risk/score
│   ├── auto_approve.py     # POST /ai/auto-approve/evaluate
│   ├── ocr.py              # POST /ai/ocr/extract-url
│   └── summarize.py        # POST /ai/summarize/request
│
└── training/               # Scripts & data huấn luyện
    ├── data/               # Training datasets
    │   ├── enterprise_requests_dataset_large.csv  # 100K+ mẫu NLP
    │   ├── eapproval_risk_10000.csv               # 10K mẫu risk
    │   └── vietnam_vat_ocr_samples.json           # OCR samples
    ├── train_nlp_classifier.py        # Train NLP models
    ├── train_risk_model.py            # Train XGBoost master
    ├── train_domain_models.py         # Train domain-specific models
    ├── train_bigdata_models.py        # Train trên dataset lớn
    ├── generate_synthetic_data.py     # Tạo dữ liệu tổng hợp
    └── evaluate_model.py             # Đánh giá model performance
```

---

## 🤖 Chi tiết 5 chức năng AI

### 1. Smart Request Classifier (`/ai/classify/request`)

| Thuộc tính | Chi tiết |
|---|---|
| **Mô hình** | TF-IDF Vectorizer + CalibratedClassifier (SGD) |
| **File model** | `nlp_vectorizer.pkl` + `nlp_request_type_model.pkl` + `nlp_department_model.pkl` + `nlp_template_model.pkl` |
| **Dữ liệu train** | ~100.000 mẫu văn bản tiếng Việt |
| **Input** | `title` (tiêu đề) + `description` (mô tả yêu cầu) |
| **Output** | `predicted_request_type` (16 loại), `predicted_department`, `predicted_template` (A/B/C), `confidence` |

**TẠI SAO DÙNG TF-IDF + SGD thay vì LLM:**
- Inference nhanh (< 50ms) — không cần GPU
- Không tốn chi phí API call (Gemini)
- Độ chính xác đủ tốt cho classification task (~92% accuracy)
- LLM chỉ dùng cho summarize (task phức tạp hơn)

**TẠI SAO ĐẶT Ở `models/`:**
- Docker volume mount `./ai_service/models:/app/models` → persist qua restart
- Lazy loading: chỉ load vào RAM khi có request đầu tiên
- Không commit model lớn vào git → dùng .gitignore hoặc Git LFS

### 2. Risk & Fraud Scoring (`/ai/risk/score`)

| Thuộc tính | Chi tiết |
|---|---|
| **Mô hình** | XGBoost Ensemble (4 models) |
| **File model** | `risk_model.pkl` (master) + `risk_model_finance.pkl` + `risk_model_hr.pkl` + `risk_model_it.pkl` |
| **Dữ liệu train** | 50.000+ mẫu (10K base + 40K+ augmented) |
| **Input** | 14 features: request_type, amount, days, requester_level, dept, leave_balance, history... |
| **Output** | `risk_score` (1-5), `risk_label`, `confidence`, `auto_approve_eligible`, `explanation` |

**KIẾN TRÚC MODEL ENSEMBLE — TẠI SAO 4 MODELS:**

```
Input request
    │
    ▼
┌───────────────────┐
│ Domain Router     │  ← Phân loại domain dựa trên request_type
│ (rule-based)      │
└───┬───┬───┬───┬───┘
    │   │   │   │
    ▼   ▼   ▼   ▼
  FIN  HR  IT  Master
  model model model model
    │   │   │   │
    └───┴───┴───┘
         │
         ▼
    Final risk_score
```

- **Finance Model**: Chuyên phát hiện advance_payment bất thường, expense > budget
- **HR Model**: Chuyên phát hiện pattern nghỉ phép bất thường, overtime gian lận
- **IT Model**: Chuyên phát hiện access_permission leo thang quyền (privilege escalation)
- **Master Model**: Fallback cho các domain không có model chuyên biệt

**Routing rules (trong `routers/risk.py`):**
```python
FINANCE_TYPES = {"advance_payment", "expense_reimbursement", "budget_approval", "contract_payment"}
HR_TYPES      = {"leave_annual", "leave_unpaid", "overtime", "remote_work", "travel", ...}
IT_TYPES      = {"equipment_new", "equipment_repair", "access_permission", "vpn_access"}
```

### 3. Auto-Approve (`/ai/auto-approve/evaluate`)

| Thuộc tính | Chi tiết |
|---|---|
| **Mô hình** | Rule-based + Risk threshold |
| **Điều kiện auto-approve** | `lifecycle_template == 'A'` AND `risk_score <= 2` |
| **Input** | request_id, type, template, risk_score, amount, leave_balance, room_available |
| **Output** | `decision` ("auto_approve" / "escalate_to_human"), `reason`, `detail_reasons` |

**TẠI SAO RULE-BASED THAY VÌ ML:**
- Auto-approve cần minh bạch 100% — phải giải thích được tại sao duyệt/không
- Rule dễ audit, dễ thay đổi policy mà không cần retrain model
- Risk score đã được ML model đánh giá rồi → auto-approve chỉ cần kiểm tra threshold

### 4. OCR — Bóc tách hóa đơn (`/ai/ocr/extract-url`)

| Thuộc tính | Chi tiết |
|---|---|
| **Mô hình** | PaddleOCR (Vietnamese) hoặc Gemini Vision |
| **Input** | `image_url` (URL hóa đơn VAT, chứng từ) |
| **Output** | `raw_text`, `extracted_fields` (số HĐ, ngày, MST, tổng tiền), `confidence` |

**TẠI SAO 2 ENGINE:**
- PaddleOCR: offline, miễn phí, nhanh → dùng cho hóa đơn chuẩn
- Gemini Vision: online, chính xác hơn → fallback cho hóa đơn phức tạp/scan mờ

### 5. Summarize — Tóm tắt yêu cầu (`/ai/summarize/request`)

| Thuộc tính | Chi tiết |
|---|---|
| **Mô hình** | Google Gemini 1.5 Flash (LLM) |
| **Input** | title, description, request_type, requester_name, data, risk_score, amount |
| **Output** | `summary`, `key_points`, `sentiment` ("positive"/"neutral"/"negative"), `tokens_used` |

**TẠI SAO DÙNG GEMINI CHO SUMMARIZE:**
- Summarization là generative task → cần LLM
- Gemini 1.5 Flash nhanh, rẻ, hỗ trợ tiếng Việt tốt
- Fallback: nếu API key không có hoặc lỗi → trả về title gốc

---

## 🔗 Tích hợp với API Core

AI Service được gọi từ Django qua `ai_client.py`:

```python
# Trong api_core service layer:
from ai_client import ai_client, ai_client_sync

# Async (ASGI / Celery async task):
result = await ai_client.score_risk(request_type="leave_annual", ...)

# Sync (WSGI / Django views):
result = ai_client_sync.score_risk(request_type="leave_annual", ...)
```

**Xác thực nội bộ:**
- Header `X-Internal-Secret` — secret chia sẻ giữa api_core và ai_service
- Biến môi trường: `INTERNAL_API_SECRET`
- Endpoint `/docs`, `/redoc`, `/health` không cần secret

---

## 🔐 Bảo mật

1. **Không expose port 8001 ra public** — chỉ route qua API Gateway
2. **Internal secret** bảo vệ tất cả AI endpoint
3. **Rate limiting** qua Gateway: 20 req/phút/IP cho `/ai/*`
4. **No PII in logs** — không log request body chứa dữ liệu nhạy cảm
5. **Model files** không commit vào git — volume mount hoặc Git LFS

---

## 🚀 Chạy AI Service

```bash
# Development
cd ai_service
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001

# Docker
docker compose up ai-service

# Train lại model (nếu cần)
cd training
python train_nlp_classifier.py
python train_risk_model.py
python train_domain_models.py
```

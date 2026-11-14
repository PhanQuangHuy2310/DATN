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
│   ├── nlp_classifier.pkl          # TF-IDF + Logistic Regression, 58 loại catalog v2
│   ├── nlp_labels.json             # Catalog (nhóm, bộ phận, template) cho bộ phân loại
│   ├── risk_model.pkl              # XGBoost Master
│   ├── risk_model_finance.pkl      # XGBoost Finance domain
│   ├── risk_model_hr.pkl           # XGBoost HR domain
│   ├── risk_model_it.pkl           # XGBoost IT domain
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
└── training/               # Huấn luyện (một lệnh: train.py)
    ├── train.py            # Train NLP + 4 model risk, đánh giá, ghi models/ và báo cáo
    └── data/
        ├── request_corpus.json          # Mẫu câu huấn luyện 58 loại
        ├── request_eval_realistic.json  # Câu viết tay: dev / test (test chỉ để báo cáo)
        ├── training_report.md           # Báo cáo lần train gần nhất
        └── vietnam_vat_ocr_samples.json # OCR samples
```

---

## 🤖 Chi tiết 5 chức năng AI

### 1. Smart Request Classifier (`/ai/classify/request`)

| Thuộc tính | Chi tiết |
|---|---|
| **Mô hình** | TF-IDF (từ 1-2 gram + ký tự không dấu 2-5 gram) → Logistic Regression; nhóm, bộ phận và template suy ra từ catalog |
| **File model** | `nlp_classifier.pkl` + `nlp_labels.json` |
| **Dữ liệu train** | 34.800 câu tổng hợp từ `training/data/request_corpus.json` (58 loại catalog v2) |
| **Input** | `title` (tiêu đề) + `description` (mô tả yêu cầu) |
| **Output** | `predicted_request_type` (58 loại catalog v2), nhóm, bộ phận, template A/B/C, độ tin cậy, `low_confidence`, 3 khả năng hàng đầu |
| **Độ chính xác** | Xem `training/data/training_report.md`: câu viết tay split `test` (không dùng để train) |

**TẠI SAO DÙNG TF-IDF + Logistic Regression thay vì LLM:**
- Inference nhanh (< 100 ms) — không cần GPU
- Không tốn chi phí API call (Gemini), dữ liệu không rời hệ thống
- Ký tự n-gram không dấu chịu được gõ không dấu và lỗi chính tả
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
FINANCE_TYPES = {
    "advance_payment",
    "expense_reimbursement",
    "budget_approval",
    "contract_payment",
}
HR_TYPES = {"leave_annual", "leave_unpaid", "overtime", "remote_work", "travel", ...}
IT_TYPES = {"equipment_new", "equipment_repair", "access_permission", "vpn_access"}
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

# Train lại model (nếu cần), từ thư mục gốc repo
ai_service\.venv-ai\Scripts\python.exe ai_service\training\train.py
```

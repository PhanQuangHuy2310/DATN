# 🧪 Enterprise Approval System — Test Suite

Thư mục này chứa các bài kiểm thử Tích hợp (Integration Tests) và Đầu-cuối (E2E Tests) cho toàn bộ hệ sinh thái EAS:
- **API Gateway (Nginx)**: Phân phối và bảo mật luồng dữ liệu
- **API Core (Django)**: Nghiệp vụ phê duyệt chính và tích hợp AI Client
- **AI Service (FastAPI)**: 5 dịch vụ AI thông minh và dữ liệu snapshot mock
- **Database (PostgreSQL)**: Schema chính `eas` và 8 schema `mock_*`

---

## 📁 Cấu Trúc Thư Mục

```
tests/
├── run_tests.py                    # Script tự động chạy toàn bộ test suite
├── README.md                       # ← Tài liệu này
├── integration/                    # Kiểm thử tích hợp giữa các thành phần
│   ├── __init__.py
│   └── test_ai_service.py          # Kiểm thử Model, Mock Data, Suy luận & Fallback
└── fixtures/                       # Dữ liệu mẫu phục vụ kiểm thử
```

---

## 🚀 Cách Chạy Test

### 1. Chạy Toàn Bộ Test Suite:
```bash
python tests/run_tests.py
```

### 2. Chạy Riêng Lẻ Test Tích Hợp AI Service & Client:
```bash
python -m unittest tests/integration/test_ai_service.py
```

---

## 📋 Danh Sách Ca Kiểm Thử Đã Triển Khai (`test_ai_service.py`)

| Test Case | Nhóm Kiểm Thử | Mục Tiêu & Kết Quả Kỳ Vọng | Trạng Thái |
|---|---|---|---|
| `test_required_model_files_exist` | Model Artifacts | Xác minh đầy đủ 15 file model và metadata `.pkl` / `.json` | ✅ PASS |
| `test_domain_model_registry_valid` | Model Registry | Xác minh registry chứa đủ 4 domain: finance, hr, it, master | ✅ PASS |
| `test_manifest_and_all_8_schemas_exist` | Mock Data Snapshots | Kiểm tra tính đầy đủ của 8 file snapshot JSON và `_manifest.json` (>100 bản ghi) | ✅ PASS |
| `test_finance_model_high_risk` | XGBoost Inference | Kiểm tra mô hình Finance dự đoán Risk ≥ 4 cho tạm ứng vượt budget không hóa đơn | ✅ PASS |
| `test_hr_model_normal_risk` | XGBoost Inference | Kiểm tra mô hình HR dự đoán Risk ≤ 2 cho nghỉ phép thông thường | ✅ PASS |
| `test_sync_client_score_risk_fallback` | Fault-Tolerance | Kiểm tra client trả về fallback an toàn khi server offline | ✅ PASS |
| `test_sync_client_auto_approve_fallback` | Fault-Tolerance | Kiểm tra client tự động escalate thủ công khi server offline | ✅ PASS |
| `test_sync_client_classify_fallback` | Fault-Tolerance | Kiểm tra client trả về gợi ý mặc định khi server offline | ✅ PASS |

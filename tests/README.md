# 🧪 Enterprise Approval System — Test Suite

Các bài kiểm thử độc lập được giữ thành từng file theo chức năng, cùng nằm trong một thư mục để dễ chạy và bảo trì. Bộ này gồm kiểm thử business, readiness, contract, regression và tích hợp AI; test Django của ứng dụng vẫn nằm trong `api_core/tests/`.

---

## 📁 Cấu Trúc Thư Mục

```
tests/
├── run_tests.py                 # Phát hiện và chạy mọi test_*.py bên dưới
├── README.md
├── fixtures/                    # SQL/JSON fixtures dùng riêng cho tests
├── integration/
│   └── test_ai_service.py       # Kiểm thử tích hợp AI Service và client
├── test_*_catalog.py            # Catalog, readiness và policy
├── test_*_contract.py           # Schema, API payload và frontend contract
├── test_*_regression.py         # Regression query và giao diện
└── test_connection.py           # Kiểm thử cấu hình/kết nối giả lập
```

---

## 🚀 Cách Chạy Test

### 1. Chạy Toàn Bộ Test Suite:
```bash
python tests/run_tests.py
```
Lệnh này chạy các test độc lập trong `tests/`, kể cả các suite business, report, readiness và connection đã được gom về đây. Test Django được chạy riêng bằng `python manage.py test`.

### 2. Chạy Riêng Lẻ Test Tích Hợp AI Service & Client:
```bash
python -m unittest tests/integration/test_ai_service.py
```

Mỗi file `test_*.py` vẫn có thể chạy độc lập bằng `python -m unittest tests.<tên_module>`.

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

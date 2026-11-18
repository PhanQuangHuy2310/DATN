# Đánh giá phân tích quy định bằng mô hình ngôn ngữ lớn (regulation-llm-1, gemini-3.5-flash-lite)

Chạy lúc 2026-11-17 18:50:02 +0700; nhiệt độ 0; mã băm câu lệnh 381e30b1dc9b3dfe. Đáp án 30 kịch bản được băm trước khi có mô-đun này.

| Phương pháp | Kịch bản đạt | Thay đổi bắt buộc tìm đúng | Giữ nguyên đúng | Không liên quan, không đề xuất | Đề xuất ngoài đáp án |
|---|---:|---:|---:|---:|---:|
| Mô hình ngôn ngữ lớn + truy xuất | 25/30 | 21/22 | 7/9 | 1/3 | 4 |
| Mô hình nội bộ process-profile-3 | 18/30 | 10/22 | 9/9 | 3/3 | 7 |
| Luật từ khóa | 17/30 | 9/22 | 8/9 | 3/3 | 7 |

Thống kê: {"retrieval_recall": "29/31", "fallbacks": 0, "latency_ms_p50": 2196.2, "latency_ms_max": 11429.2, "tokens_total": 39507, "proposals_grounded": "29/29", "rejected_by_validator": 1, "atomic_rules_total": 33}

## Chi tiết từng kịch bản (mô hình ngôn ngữ lớn)

| Mã | Kết quả | Đề xuất | Ngoài đáp án |
|---|---|---|---|
| QD-01 | Không đạt | PURCHASE_REQUEST B3→C4; EQUIPMENT C3→C5 | - |
| QD-02 | Đạt | NDA_PRIVACY_CLEARANCE B2→C5; ACCESS B2→C5; DATA_UAT_EXPORT B3→C5 | ACCESS |
| QD-03 | Đạt | ATTENDANCE_ADJUSTMENT A1→B3 | - |
| QD-04 | Đạt | WFH_REQ A1→B3 | - |
| QD-05 | Đạt | ASSET_DISPOSAL C4→C5 | - |
| QD-06 | Không đạt | VISITOR_SECURITY_PASS A1→B2 | VISITOR_SECURITY_PASS |
| QD-07 | Đạt | - | - |
| QD-08 | Đạt | FLASH_SALE_VOUCHER B4→C5 | - |
| QD-09 | Đạt | IT_SUPPORT B1→C5 | - |
| QD-10 | Đạt | ROOM_BOOKING A1→B3 | - |
| QD-11 | Đạt | SERVER_FIREWALL C3→C5 | - |
| QD-12 | Đạt | VEHICLE_BOOKING C2→C4 | - |
| QD-13 | Đạt | - | - |
| QD-14 | Đạt | REFUND_COMPENSATION A2→C4 | - |
| QD-15 | Đạt | TRAINING_COURSE B2→C4 | - |
| QD-16 | Đạt | VISITOR_SECURITY_PASS A1→B3; ACCESS_FACILITY B2→C4 | ACCESS_FACILITY |
| QD-17 | Đạt | - | - |
| QD-18 | Không đạt | SPECIAL_DISCOUNT A3→B3 | - |
| QD-19 | Đạt | REWARD_REQ B3→C4 | - |
| QD-20 | Không đạt | SALARY_ADJUSTMENT B5→C5 | - |
| QD-21 | Đạt | OVERTIME_REQ B2→C4 | - |
| QD-22 | Đạt | FACILITY_REPAIR C2→C4 | - |
| QD-23 | Đạt | BUSINESS_TRIP B3→C4 | - |
| QD-24 | Đạt | - | - |
| QD-25 | Đạt | SAAS_LICENSE_BUY C3→C4 | - |
| QD-26 | Không đạt | VEHICLE_BOOKING C2→C3 | VEHICLE_BOOKING |
| QD-27 | Đạt | WAREHOUSE_TRANSFER B3→C4 | - |
| QD-28 | Đạt | - | - |
| QD-29 | Đạt | SALARY_ADVANCE B2→C4 | - |
| QD-30 | Đạt | RESOURCE_REVOKE C2→C3 | - |

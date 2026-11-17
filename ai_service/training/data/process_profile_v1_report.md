# Báo cáo mô hình hồ sơ quy trình (process-profile-1)

Sinh lúc 2026-11-17 14:36:21 +0700. Dữ liệu: 58 loại yêu cầu trong `process_profiles.json` (nhãn do nhóm cấu hình). Phân bố mẫu vòng đời: {'B': 28, 'C': 22, 'A': 8}; trọng số: {1: 9, 2: 18, 3: 15, 4: 10, 5: 6}.

## 1. Leave-one-out

| Phương pháp | Vòng đời: accuracy | Vòng đời: macro-F1 | Trọng số: MAE | Trọng số: đúng | Trọng số: lệch ≤ 1 |
|---|---:|---:|---:|---:|---:|
| Đoán phổ biến nhất | 48.3% | 0.217 | 1.00 | 25.9% | 74.1% |
| Luật từ khóa viết tay | 62.1% | 0.610 | 0.88 | 31.0% | 82.8% |
| Mô hình (LR + Ridge) | 55.2% | 0.593 | 0.83 | 41.4% | 82.8% |

Ma trận nhầm lẫn vòng đời (hàng = thật A/B/C, cột = dự đoán): [[6, 2, 0], [2, 16, 10], [0, 12, 10]]

Các loại dự đoán sai mẫu vòng đời hoặc lệch trọng số > 1:

- ACCESS: thật ['B', 2], dự đoán ['C', 3]; lý do: số trường biểu mẫu, liên quan dữ liệu nhạy cảm / hạ tầng, cần người thực hiện
- ADVANCE_LARGE: thật ['B', 4], dự đoán ['C', 2]; lý do: cần bàn giao / nghiệm thu, số trường biểu mẫu, ràng buộc pháp lý
- ASSET_DISPOSAL: thật ['C', 4], dự đoán ['C', 2]; lý do: cần bàn giao / nghiệm thu, số trường biểu mẫu, khó đảo ngược
- BUDGET_REALLOCATION: thật ['C', 5], dự đoán ['B', 3]; lý do: cần người thực hiện, có giá trị tiền / ngân sách, thuộc nhóm PROCUREMENT
- BUSINESS_TRIP: thật ['B', 3], dự đoán ['A', 3]; lý do: thuộc nhóm ABSENCE, số trường biểu mẫu, có giá trị tiền / ngân sách
- CONTRACT_APPROVAL: thật ['C', 5], dự đoán ['B', 4]; lý do: ràng buộc pháp lý, thuộc nhóm LEGAL, biểu mẫu có trường số tiền
- DATA_UAT_EXPORT: thật ['B', 3], dự đoán ['C', 3]; lý do: số trường biểu mẫu, liên quan dữ liệu nhạy cảm / hạ tầng, cần người thực hiện
- EMPLOYEE_ONBOARDING: thật ['C', 3], dự đoán ['B', 2]; lý do: cần người thực hiện, thuộc nhóm PEOPLE, ràng buộc pháp lý
- FACILITY_REPAIR: thật ['C', 2], dự đoán ['B', 3]; lý do: cần người thực hiện, liên quan dữ liệu nhạy cảm / hạ tầng, ràng buộc pháp lý
- FLASH_SALE_VOUCHER: thật ['B', 4], dự đoán ['C', 3]; lý do: số trường biểu mẫu, ràng buộc pháp lý, thuộc nhóm SALES
- IT_SUPPORT: thật ['B', 1], dự đoán ['C', 2]; lý do: số trường biểu mẫu, cần bàn giao / nghiệm thu, cần người thực hiện
- LEAVE: thật ['B', 2], dự đoán ['A', 2]; lý do: tác vụ thường nhật, tự phục vụ, thuộc nhóm ABSENCE, biểu mẫu chỉ định người khác
- LEAVE_SPECIAL: thật ['A', 2], dự đoán ['B', 2]; lý do: biểu mẫu có khoảng thời gian, biểu mẫu chỉ định người khác, thuộc nhóm ABSENCE
- MARKETING_CAMPAIGN: thật ['C', 4], dự đoán ['B', 3]; lý do: biểu mẫu có khoảng thời gian, có giá trị tiền / ngân sách, biểu mẫu có trường số tiền
- NDA_PRIVACY_CLEARANCE: thật ['B', 2], dự đoán ['C', 5]; lý do: liên quan dữ liệu nhạy cảm / hạ tầng, ràng buộc pháp lý, số trường biểu mẫu
- OVERTIME_REQ: thật ['B', 2], dự đoán ['C', 2]; lý do: số trường biểu mẫu, ràng buộc pháp lý, có cụm từ "su"
- PROD_DATA_ACCESS: thật ['C', 5], dự đoán ['B', 3]; lý do: cần người thực hiện, liên quan dữ liệu nhạy cảm / hạ tầng, ràng buộc pháp lý
- PROJECT_INITIATION: thật ['C', 4], dự đoán ['B', 4]; lý do: cần người thực hiện, biểu mẫu có khoảng thời gian, đòi hỏi cấp có thẩm quyền cao
- PURCHASE_REQUEST: thật ['B', 3], dự đoán ['C', 3]; lý do: số trường biểu mẫu, ràng buộc pháp lý, cần người thực hiện
- RECRUITMENT_REQ: thật ['C', 4], dự đoán ['B', 4]; lý do: cần người thực hiện, thuộc nhóm PEOPLE, có giá trị tiền / ngân sách
- REFUND_COMPENSATION: thật ['A', 2], dự đoán ['B', 3]; lý do: thuộc nhóm PAYMENT, ràng buộc pháp lý, có giá trị tiền / ngân sách
- SAAS_LICENSE_BUY: thật ['C', 3], dự đoán ['B', 3]; lý do: ràng buộc pháp lý, thuộc nhóm PROCUREMENT, có cụm từ "phan mem"
- SALARY_ADJUSTMENT: thật ['B', 5], dự đoán ['B', 3]; lý do: cần người thực hiện, đòi hỏi cấp có thẩm quyền cao, thuộc nhóm PEOPLE
- SECURITY_INCIDENT_HOTFIX: thật ['C', 5], dự đoán ['C', 2]; lý do: liên quan dữ liệu nhạy cảm / hạ tầng, số trường biểu mẫu, thuộc nhóm SUPPORT
- SERVER_FIREWALL: thật ['C', 3], dự đoán ['B', 4]; lý do: cần người thực hiện, liên quan dữ liệu nhạy cảm / hạ tầng, ràng buộc pháp lý
- SUPPLIER_ONBOARDING: thật ['B', 3], dự đoán ['C', 3]; lý do: số trường biểu mẫu, ràng buộc pháp lý, cần người thực hiện
- TASK_REQUEST: thật ['C', 1], dự đoán ['B', 2]; lý do: cần người thực hiện, có cụm từ "date", có cụm từ "thuc hien"
- TAX_INVOICE_ISSUE: thật ['B', 1], dự đoán ['B', 4]; lý do: cần người thực hiện, ràng buộc pháp lý, thuộc nhóm PAYMENT
- TRAINING_COURSE: thật ['B', 2], dự đoán ['C', 4]; lý do: số trường biểu mẫu, biểu mẫu có khoảng thời gian, thuộc nhóm PEOPLE
- VENDOR_PAYMENT: thật ['C', 5], dự đoán ['B', 2]; lý do: ràng buộc pháp lý, thuộc nhóm PAYMENT, có giá trị tiền / ngân sách

## 2. Kịch bản quy định mới (đáp án chốt trước, kiểm tra SHA-256)

Đạt 7/10 kịch bản; tìm đúng thay đổi bắt buộc 4/8; giữ nguyên đúng 5/5; kịch bản không liên quan không đề xuất 1/1; tổng 5 đề xuất, trong đó 0 đề xuất nằm ngoài đáp án.

| Mã | Kịch bản | Kết quả | Đề xuất của mô hình | Ngoài đáp án |
|---|---|---|---|---|
| QD-01 | Nghiệm thu bắt buộc khi mua sắm | Đạt | PURCHASE_REQUEST B3→C3 | - |
| QD-02 | Bảo vệ dữ liệu cá nhân khách hàng | Không đạt | - | - |
| QD-03 | Đi muộn và quên chấm công (ví dụ của giảng viên) | Đạt | ATTENDANCE_ADJUSTMENT A1→A3 | - |
| QD-04 | Giới hạn làm việc từ xa | Đạt | WFH_REQ A1→A2 | - |
| QD-05 | Hội đồng thanh lý tài sản | Đạt | ASSET_DISPOSAL C4→C5 | - |
| QD-06 | Quy định trang phục (không liên quan) | Đạt | - | - |
| QD-07 | Thẩm định hợp đồng giá trị lớn | Đạt | - | - |
| QD-08 | Đánh giá hiệu quả chương trình khuyến mãi | Không đạt | - | - |
| QD-09 | Sự cố IT trên hệ thống production | Đạt | IT_SUPPORT B1→C3 | - |
| QD-10 | Đặt phòng họp có khách bên ngoài | Không đạt | - | - |

## 3. Giới hạn

- Chỉ có 58 mẫu và nhãn do chính nhóm cấu hình, nên số đo là ước lượng thô, khoảng tin cậy rộng.
- Đề xuất chỉ để quản trị viên duyệt; mô hình không tự sửa cấu hình.
- Đổi mẫu vòng đời cần phát hành cấu hình mới; đổi trọng số được ghi nhật ký kiểm toán.

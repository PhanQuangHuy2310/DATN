# Báo cáo mô hình hồ sơ quy trình (process-profile-2)

Sinh lúc 2026-11-17 14:41:50 +0700. Dữ liệu: 58 loại yêu cầu trong `process_profiles.json` (nhãn do nhóm cấu hình). Phân bố mẫu vòng đời: {'B': 28, 'C': 22, 'A': 8}; trọng số: {1: 9, 2: 18, 3: 15, 4: 10, 5: 6}.

Đầu vào chỉ là nội dung quy trình (tên, mô tả, nhóm nghiệp vụ, các trường biểu mẫu). Người thực hiện, người nghiệm thu, cấp duyệt và các mô tả dạng tóm tắt tuyến duyệt bị loại vì chúng suy ra trực tiếp từ nhãn.

## 1. Leave-one-out

| Phương pháp | Vòng đời: accuracy | Vòng đời: macro-F1 | Trọng số: MAE | Trọng số: đúng | Trọng số: lệch ≤ 1 |
|---|---:|---:|---:|---:|---:|
| Đoán phổ biến nhất | 48.3% | 0.217 | 1.00 | 25.9% | 74.1% |
| Luật từ khóa viết tay | 51.7% | 0.510 | 0.78 | 37.9% | 86.2% |
| Phiên bản 1 (chốt trước; mô tả còn lộ nhãn) | 55.2% | 0.593 | 0.83 | 41.4% | 82.8% |
| Phiên bản 2, C=0.3, có TF-IDF từ | 55.2% | 0.568 | 0.91 | 36.2% | 79.3% |
| Phiên bản 2, C=1.0, có TF-IDF từ (chọn) | 56.9% | 0.592 | 0.91 | 36.2% | 79.3% |
| Phiên bản 2, C=3.0, có TF-IDF từ | 56.9% | 0.590 | 0.91 | 36.2% | 79.3% |
| Phiên bản 2, C=0.3, không TF-IDF từ | 55.2% | 0.566 | 1.00 | 27.6% | 77.6% |
| Phiên bản 2, C=1.0, không TF-IDF từ | 53.4% | 0.555 | 1.00 | 27.6% | 77.6% |
| Phiên bản 2, C=3.0, không TF-IDF từ | 51.7% | 0.533 | 1.00 | 27.6% | 77.6% |

Biến thể được chọn theo macro-F1 vòng đời rồi MAE trọng số trên leave-one-out, nên số của biến thể được chọn hơi lạc quan (chọn 1 trong 6).

Ma trận nhầm lẫn vòng đời của biến thể được chọn (hàng = thật A/B/C, cột = dự đoán): [[5, 2, 1], [2, 15, 11], [0, 9, 13]]

Các loại sai mẫu vòng đời hoặc lệch trọng số > 1:

- ACCESS: thật ['B', 2], dự đoán ['C', 3]; lý do: liên quan dữ liệu nhạy cảm / hạ tầng, số trường biểu mẫu, thuộc nhóm PROVISION
- ADVANCE_LARGE: thật ['B', 4], dự đoán ['C', 2]; lý do: cần bàn giao / nghiệm thu, số trường biểu mẫu, biểu mẫu có trường số tiền
- BUDGET_REALLOCATION: thật ['C', 5], dự đoán ['B', 4]; lý do: cần người thực hiện, biểu mẫu có trường số tiền, thuộc nhóm PROCUREMENT
- BUSINESS_TRIP: thật ['B', 3], dự đoán ['A', 3]; lý do: số trường biểu mẫu, thuộc nhóm ABSENCE, có giá trị tiền / ngân sách
- CONTRACT_APPROVAL: thật ['C', 5], dự đoán ['B', 3]; lý do: ràng buộc pháp lý, thuộc nhóm LEGAL, biểu mẫu có trường số tiền
- DATA_UAT_EXPORT: thật ['B', 3], dự đoán ['C', 3]; lý do: thuộc nhóm WORK, số trường biểu mẫu, liên quan dữ liệu nhạy cảm / hạ tầng
- EMPLOYEE_ONBOARDING: thật ['C', 3], dự đoán ['B', 2]; lý do: cần người thực hiện, thuộc nhóm PEOPLE, có cụm từ "name"
- FACILITY_REPAIR: thật ['C', 2], dự đoán ['B', 2]; lý do: cần người thực hiện, liên quan dữ liệu nhạy cảm / hạ tầng, thuộc nhóm SUPPORT
- FLASH_SALE_VOUCHER: thật ['B', 4], dự đoán ['C', 3]; lý do: số trường biểu mẫu, thuộc nhóm SALES, biểu mẫu có khoảng thời gian
- IT_SUPPORT: thật ['B', 1], dự đoán ['C', 2]; lý do: cần bàn giao / nghiệm thu, số trường biểu mẫu, thuộc nhóm SUPPORT
- LEAVE: thật ['B', 2], dự đoán ['A', 1]; lý do: tác vụ thường nhật, tự phục vụ, số trường biểu mẫu, thuộc nhóm ABSENCE
- LEAVE_SPECIAL: thật ['A', 2], dự đoán ['B', 2]; lý do: biểu mẫu có khoảng thời gian, biểu mẫu chỉ định người khác, có cụm từ "nghi"
- MARKETING_CAMPAIGN: thật ['C', 4], dự đoán ['B', 4]; lý do: biểu mẫu có khoảng thời gian, biểu mẫu có trường số tiền, thuộc nhóm SALES
- NDA_PRIVACY_CLEARANCE: thật ['B', 2], dự đoán ['C', 5]; lý do: liên quan dữ liệu nhạy cảm / hạ tầng, ràng buộc pháp lý, số trường biểu mẫu
- OVERTIME_REQ: thật ['B', 2], dự đoán ['C', 3]; lý do: số trường biểu mẫu, có cụm từ "date", có cụm từ "lam"
- POLICY_ISSUANCE: thật ['B', 4], dự đoán ['B', 2]; lý do: cần người thực hiện, ràng buộc pháp lý, thuộc nhóm LEGAL
- PROD_DATA_ACCESS: thật ['C', 5], dự đoán ['C', 2]; lý do: liên quan dữ liệu nhạy cảm / hạ tầng, số trường biểu mẫu, thuộc nhóm PROVISION
- PROJECT_INITIATION: thật ['C', 4], dự đoán ['B', 3]; lý do: cần người thực hiện, biểu mẫu có khoảng thời gian, biểu mẫu có trường số tiền
- PROMOTION_REQ: thật ['B', 4], dự đoán ['C', 4]; lý do: số trường biểu mẫu, tác động nhân sự, có cụm từ "position"
- PURCHASE_REQUEST: thật ['B', 3], dự đoán ['C', 3]; lý do: số trường biểu mẫu, thuộc nhóm PROCUREMENT, biểu mẫu có trường số tiền
- RECRUITMENT_REQ: thật ['C', 4], dự đoán ['B', 5]; lý do: cần người thực hiện, thuộc nhóm PEOPLE, tác động nhân sự
- REFUND_COMPENSATION: thật ['A', 2], dự đoán ['B', 3]; lý do: thuộc nhóm PAYMENT, biểu mẫu có trường số tiền, có giá trị tiền / ngân sách
- SALARY_ADJUSTMENT: thật ['B', 5], dự đoán ['C', 3]; lý do: số trường biểu mẫu, tác động nhân sự, biểu mẫu có trường số tiền
- SALARY_ADVANCE: thật ['B', 2], dự đoán ['B', 4]; lý do: thuộc nhóm PAYMENT, biểu mẫu có trường số tiền, có cụm từ "ung"
- SECURITY_INCIDENT_HOTFIX: thật ['C', 5], dự đoán ['C', 3]; lý do: liên quan dữ liệu nhạy cảm / hạ tầng, số trường biểu mẫu, thuộc nhóm SUPPORT
- TASK_REQUEST: thật ['C', 1], dự đoán ['B', 2]; lý do: cần người thực hiện, có cụm từ "cau", có cụm từ "yeu cau"
- TAX_INVOICE_ISSUE: thật ['B', 1], dự đoán ['B', 4]; lý do: cần người thực hiện, ràng buộc pháp lý, thuộc nhóm PAYMENT
- TRAINING_COURSE: thật ['B', 2], dự đoán ['C', 4]; lý do: số trường biểu mẫu, biểu mẫu có khoảng thời gian, thuộc nhóm PEOPLE
- VENDOR_PAYMENT: thật ['C', 5], dự đoán ['B', 2]; lý do: ràng buộc pháp lý, thuộc nhóm PAYMENT, biểu mẫu có trường số tiền
- VISITOR_SECURITY_PASS: thật ['A', 1], dự đoán ['C', 3]; lý do: số trường biểu mẫu, thuộc nhóm PROVISION, có cụm từ "sach"

## 2. Kịch bản quy định mới, phiên bản 1 (đáp án QD-01..QD-10 chốt trước)

Đạt 7/10 kịch bản; tìm đúng thay đổi bắt buộc 4/8; giữ nguyên đúng 5/5; kịch bản không liên quan không đề xuất 1/1; tổng 5 đề xuất, 0 đề xuất nằm ngoài đáp án.

| Mã | Kịch bản | Kết quả | Đề xuất (hiện tại → đề xuất) | Lý do | Ngoài đáp án |
|---|---|---|---|---|---|
| QD-01 | Nghiệm thu bắt buộc khi mua sắm | Đạt | PURCHASE_REQUEST B3→C3 | có giá trị tiền / ngân sách, cần người thực hiện, cần bàn giao / nghiệm thu | - |
| QD-02 | Bảo vệ dữ liệu cá nhân khách hàng | Không đạt | - | - | - |
| QD-03 | Đi muộn và quên chấm công (ví dụ của giảng viên) | Đạt | ATTENDANCE_ADJUSTMENT A1→A3 | tác động nhân sự, đòi hỏi cấp có thẩm quyền cao | - |
| QD-04 | Giới hạn làm việc từ xa | Đạt | WFH_REQ A1→A2 | đòi hỏi cấp có thẩm quyền cao | - |
| QD-05 | Hội đồng thanh lý tài sản | Đạt | ASSET_DISPOSAL C4→C5 | có giá trị tiền / ngân sách, khó đảo ngược, đòi hỏi cấp có thẩm quyền cao | - |
| QD-06 | Quy định trang phục (không liên quan) | Đạt | - | - | - |
| QD-07 | Thẩm định hợp đồng giá trị lớn | Đạt | - | - | - |
| QD-08 | Đánh giá hiệu quả chương trình khuyến mãi | Không đạt | - | - | - |
| QD-09 | Sự cố IT trên hệ thống production | Đạt | IT_SUPPORT B1→C3 | cần người thực hiện, liên quan dữ liệu nhạy cảm / hạ tầng, liên quan bên ngoài | - |
| QD-10 | Đặt phòng họp có khách bên ngoài | Không đạt | - | - | - |

## 3. Phiên bản 2 trên tập phát triển QD-01..QD-10

Đạt 5/10 kịch bản; tìm đúng thay đổi bắt buộc 2/8; giữ nguyên đúng 5/5; kịch bản không liên quan không đề xuất 1/1; tổng 5 đề xuất, 3 đề xuất nằm ngoài đáp án.

| Mã | Kịch bản | Kết quả | Đề xuất (hiện tại → đề xuất) | Lý do | Ngoài đáp án |
|---|---|---|---|---|---|
| QD-01 | Nghiệm thu bắt buộc khi mua sắm | Đạt | PURCHASE_REQUEST B3→C3; SUPPLIER_ONBOARDING B3→C3 | có giá trị tiền / ngân sách, cần người thực hiện, cần bàn giao / nghiệm thu; có giá trị tiền / ngân sách, cần người thực hiện, cần bàn giao / nghiệm thu | SUPPLIER_ONBOARDING |
| QD-02 | Bảo vệ dữ liệu cá nhân khách hàng | Không đạt | - | - | - |
| QD-03 | Đi muộn và quên chấm công (ví dụ của giảng viên) | Không đạt | EQUIPMENT_BORROW C2→C1; EQUIPMENT C3→C2 | tác động nhân sự, đòi hỏi cấp có thẩm quyền cao, tác vụ thường nhật, tự phục vụ; tác động nhân sự, đòi hỏi cấp có thẩm quyền cao, tác vụ thường nhật, tự phục vụ | EQUIPMENT_BORROW, EQUIPMENT |
| QD-04 | Giới hạn làm việc từ xa | Không đạt | - | - | - |
| QD-05 | Hội đồng thanh lý tài sản | Đạt | - | - | - |
| QD-06 | Quy định trang phục (không liên quan) | Đạt | - | - | - |
| QD-07 | Thẩm định hợp đồng giá trị lớn | Đạt | - | - | - |
| QD-08 | Đánh giá hiệu quả chương trình khuyến mãi | Không đạt | - | - | - |
| QD-09 | Sự cố IT trên hệ thống production | Đạt | IT_SUPPORT B1→B3 | cần người thực hiện, liên quan dữ liệu nhạy cảm / hạ tầng, liên quan bên ngoài | - |
| QD-10 | Đặt phòng họp có khách bên ngoài | Không đạt | - | - | - |

## 4. Phiên bản 2 trên tập giữ lại QD-11..QD-20 (chấm một lần)

### Mô hình

Đạt 4/10 kịch bản; tìm đúng thay đổi bắt buộc 1/7; giữ nguyên đúng 2/2; kịch bản không liên quan không đề xuất 1/1; tổng 4 đề xuất, 1 đề xuất nằm ngoài đáp án.

| Mã | Kịch bản | Kết quả | Đề xuất (hiện tại → đề xuất) | Lý do | Ngoài đáp án |
|---|---|---|---|---|---|
| QD-11 | Thẩm định an ninh khi cấp server/firewall production | Không đạt | - | - | - |
| QD-12 | Điều xe công vụ đi ngoại tỉnh | Không đạt | - | - | - |
| QD-13 | Định mức văn phòng phẩm (nới lỏng) | Đạt | SUPPLIER_ONBOARDING B3→B2 | cần người thực hiện, đòi hỏi cấp có thẩm quyền cao, tác vụ thường nhật, tự phục vụ | SUPPLIER_ONBOARDING |
| QD-14 | Hoàn tiền, đền bù khách hàng giá trị lớn | Không đạt | REFUND_COMPENSATION A2→A1 | liên quan bên ngoài, đòi hỏi cấp có thẩm quyền cao | - |
| QD-15 | Nghiệm thu kết quả đào tạo chi phí cao | Đạt | TRAINING_COURSE B2→C2 | cần bàn giao / nghiệm thu | - |
| QD-16 | Khách vào khu vực phòng máy chủ | Không đạt | - | - | - |
| QD-17 | Tiệc tất niên (không liên quan) | Đạt | - | - | - |
| QD-18 | Chiết khấu thương mại vượt ngưỡng | Không đạt | SPECIAL_DISCOUNT A3→A2 | ràng buộc pháp lý, liên quan bên ngoài, đòi hỏi cấp có thẩm quyền cao | - |
| QD-19 | Khen thưởng giá trị lớn | Không đạt | - | - | - |
| QD-20 | Hội đồng lương | Đạt | - | - | - |

### Mốc: luật từ khóa với cùng bước tìm loại liên quan

Đạt 5/10 kịch bản; tìm đúng thay đổi bắt buộc 3/7; giữ nguyên đúng 1/2; kịch bản không liên quan không đề xuất 1/1; tổng 5 đề xuất, 1 đề xuất nằm ngoài đáp án.

| Mã | Kịch bản | Kết quả | Đề xuất (hiện tại → đề xuất) | Lý do | Ngoài đáp án |
|---|---|---|---|---|---|
| QD-11 | Thẩm định an ninh khi cấp server/firewall production | Đạt | SERVER_FIREWALL C3→C4 | luật từ khóa | - |
| QD-12 | Điều xe công vụ đi ngoại tỉnh | Không đạt | - | - | - |
| QD-13 | Định mức văn phòng phẩm (nới lỏng) | Đạt | SUPPLIER_ONBOARDING B3→B2 | luật từ khóa | SUPPLIER_ONBOARDING |
| QD-14 | Hoàn tiền, đền bù khách hàng giá trị lớn | Không đạt | - | - | - |
| QD-15 | Nghiệm thu kết quả đào tạo chi phí cao | Đạt | TRAINING_COURSE B2→C2 | luật từ khóa | - |
| QD-16 | Khách vào khu vực phòng máy chủ | Không đạt | - | - | - |
| QD-17 | Tiệc tất niên (không liên quan) | Đạt | - | - | - |
| QD-18 | Chiết khấu thương mại vượt ngưỡng | Đạt | SPECIAL_DISCOUNT A3→A4 | luật từ khóa | - |
| QD-19 | Khen thưởng giá trị lớn | Không đạt | - | - | - |
| QD-20 | Hội đồng lương | Không đạt | SALARY_ADJUSTMENT B5→C5 | luật từ khóa | - |

## 5. Giới hạn

- Chỉ có 58 mẫu, nhãn do chính nhóm cấu hình; nhiều mô tả loại chỉ là câu giữ chỗ nên mô hình chủ yếu dựa vào tên loại, nhóm nghiệp vụ và tên trường. Số đo là ước lượng thô, khoảng tin cậy rộng.
- Đáp án kịch bản do nhóm viết; 10 kịch bản mỗi tập là quá ít để kết luận mạnh.
- Đề xuất chỉ để quản trị viên duyệt; mô hình không tự sửa cấu hình. Chỉ đề xuất NÂNG mẫu vòng đời.

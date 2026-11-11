# Kế hoạch: Tự động gán người theo vòng đời yêu cầu A/B/C (gán đúng lúc, tự thay người vắng, bàn giao, AI theo trọng số)

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-03-04 |
| Ngày mở | 03/11/2026 |
| Trạng thái | ACTIVE — quyết định đã chốt (mục 3), sẵn sàng triển khai |
| Thiết kế gốc | `docs/VONG_DOI_YEU_CAU_VA_TU_DONG_GAN.md` (đã cập nhật theo mục 3) |
| Liên quan | EAS-PLAN-2026-11-03-03 (cổng nhân viên, `leave_sync.py`), `docs/CHUC_NANG_UI_VA_PHAN_QUYEN.md` |

## 1. Mục tiêu

1. Hệ thống tự gán người cho mọi giai đoạn; **không giai đoạn nào cố định cứng**. Admin chỉ đặt **ghim mềm** (người/phòng ban được ưu tiên) và **chính sách khi quá hạn** (nhắc hoặc tự chuyển).
2. Gán **đúng lúc bước bắt đầu**.
3. Người đang giữ việc **vắng** → tự chuyển việc, kể cả khi vắng giữa chừng; có cơ chế **bàn giao công việc** chủ động.
4. AI theo **trọng số (mức rủi ro 1–5)**: 1–2 AI tự chọn người và tự duyệt bước phê duyệt; 3–5 AI chỉ gợi ý, người yêu cầu chọn.
5. Trước khi gửi luôn có **màn xem lại toàn bộ yêu cầu**; không gửi thì là nháp.
6. Mọi phân công hợp lệ (vai trò, phạm vi, SoD) và **giải thích được** trên giao diện.

Không đổi: máy trạng thái A/B/C, trigger SoD, thu hồi quyết định AI trong 24 giờ, uỷ quyền.

## 2. Hiện trạng (đã kiểm tra mã ngày 03/11/2026)

| # | Vấn đề | Bằng chứng | Hệ quả |
|---|---|---|---|
| H1 | Khi gửi, tạo sẵn **mọi** `approval_step` kèm `assignee_id`, đưa luôn người duyệt sau, người thực hiện, người nghiệm thu vào `request_participant` | `api_core/workflow/service.py` `_create_submission_workflow` (~1240–1290) | Người của bước sau bị chốt từ ngày gửi; người bước sau thấy hồ sơ trước khi tới lượt |
| H2 | Vị trí theo chức năng lấy từ `actor_bindings` của `config_release`: **một người cố định mỗi phòng** | `api_core/domain/routing.py` `resolve_route` | Đổi người phải công bố cấu hình mới; không có nhóm; admin không có chỗ ghim |
| H3 | "Vắng" chỉ lấy từ `mock_hr.attendance` hôm nay | `_attendance_status`, `_pick_present_executor` | Người có đơn nghỉ/công tác đã duyệt vẫn nhận việc |
| H4 | Chỉ thay người khi bước kích hoạt | `_substitute_approver` | Vắng giữa chừng → việc đứng chờ |
| H5 | Chuỗi thay thế duyệt: uỷ quyền → cấp trên trực tiếp | `_substitute_approver` | Cấp trên cũng vắng → không ai thay |
| H6 | Quá hạn SLA chỉ nhắc/báo | `api_core/worker.py` `process_sla_batch` | Không có tự chuyển theo cấu hình |
| H7 | Chọn người thực hiện: "ít việc nhất" chỉ khi người dự kiến vắng | `_pick_present_executor` | Không cân tải; không giải thích |
| H8 | Lý do thay người có ghi nhưng không hiển thị | audit `APPROVER_SUBSTITUTED` | Người dùng không biết vì sao việc tới tay mình |
| H9 | AI tự duyệt chỉ loại A, rủi ro ≤ 2 | `api_core/workflow/auto_approval.py` | Chưa áp dụng cho bước phê duyệt loại B/C trọng số 1–2 |
| H10 | Người yêu cầu không xem/đổi/chọn được người phê duyệt; chỉ có hộp xác nhận "Gửi?" | `RequestEditor.jsx`, route preview chỉ hiển thị | Chưa có màn xem lại đầy đủ; chưa có chọn người theo trọng số |
| H11 | Chưa có bàn giao công việc; `handover_user_id` trong đơn nghỉ chỉ là dữ liệu | form `LEAVE`, `LEAVE_SPECIAL` | Người vắng không chủ động chuyển việc được |

## 3. Quyết định đã chốt (chủ dự án, 03/11/2026)

| # | Chủ đề | Quyết định |
|---|---|---|
| D1 | Ghim | **Chỉ có ghim mềm.** Không giai đoạn nào cố định cứng: người/phòng được ghim vắng thì vẫn đi tiếp chuỗi thay thế. |
| D2 | Tính vắng | Vắng **đúng khoảng thời gian trong đơn nghỉ/công tác đã được duyệt** (theo giờ, kể cả nửa ngày). Đơn chưa duyệt hoặc bị từ chối không tính. |
| D3 | Quá hạn SLA | **Admin cài đặt** cho từng loại yêu cầu × từng giai đoạn (duyệt / thực hiện / nghiệm thu): `REMIND` (chỉ nhắc) hoặc `AUTO_TRANSFER` (tự chuyển), kèm ngưỡng thời gian. |
| D4 | Đích chuyển khi vắng/quá hạn | Ưu tiên **người được bàn giao** (bàn giao còn hiệu lực) → **cấp trên trực tiếp** → chuỗi thay thế còn lại. Áp dụng cả người nghiệm thu. |
| D5 | Bàn giao công việc | **Cả hai cách:** (1) đơn nghỉ/công tác được duyệt có người nhận bàn giao → hệ thống tự tạo yêu cầu "Bàn giao công việc" gửi người nhận; (2) nhân viên tự tạo yêu cầu bàn giao bất kỳ lúc nào. Người nhận **chấp nhận** → các giai đoạn đang do người bàn giao phụ trách chuyển sang người nhận (trong thời hạn bàn giao). |
| D6 | Trọng số 1–2 | **AI tự chọn** người cho mọi giai đoạn; **người yêu cầu được đổi** người phê duyệt (trong danh sách hợp lệ). AI **tự duyệt các bước phê duyệt** ở cả loại A, B, C nếu quy định không bắt buộc duyệt tay; thực hiện và nghiệm thu vẫn do người; thu hồi được trong 24 giờ. |
| D7 | Trọng số 3–5 | **AI chỉ gợi ý**; **người yêu cầu chọn/xác nhận** người phê duyệt từ danh sách hợp lệ (gợi ý của AI đánh dấu sẵn). Thực hiện/nghiệm thu: hệ thống tự gán như thường (người duyệt cuối được chọn lại người thực hiện). |
| D8 | Màn xem lại | Điền xong mọi mục → hiện **form tổng hợp toàn bộ yêu cầu** (nội dung, tệp, phân loại A/B/C, trọng số AI, tuyến duyệt và người từng bước). **Gửi** thì mới gửi; **Quay lại chỉnh sửa** được; **không gửi thì lưu nháp** (tự lưu). |
| D9 | "AI chọn người" | Động cơ chấm điểm có giải thích (tải việc 40 / đúng hạn 25 / kinh nghiệm 20 / gần tổ chức 15); LLM không quyết định người. |

Ràng buộc cho D6/D7 (không đổi được bởi người yêu cầu): ứng viên phải đúng vai trò và phạm vi, không phải chính mình, không giữ hai bước của cùng hồ sơ, đang có mặt; mọi lần đổi/chọn ghi nhật ký "người yêu cầu đổi từ X sang Y" và hiển thị cho người duyệt.

Nguyên tắc kỹ thuật:

- **Một hàm "có mặt" duy nhất** dùng cho gán và cho trạng thái làm việc trên UI.
- **Gán/gán lại chỉ qua một hàm** (`assign_step`, `reassign_step`, `reassign_attempt`): kiểm tra hợp lệ, `request_participant`, audit, outbox, `lock_version`.
- Thay đổi DB trong migration **14** (một transaction, chạy lại an toàn, có rollback), kiểm thử trên bản sao live; chủ dự án chạy trên SQL Editor.

## 4. Hạng mục

### Đợt 1 — Nguồn "có mặt" duy nhất (H3; D2)

| # | Việc | Tệp |
|---|---|---|
| 1.1 | `eas.user_availability(p_user, p_from, p_to)` → `(available, reason, back_at)`: `INACTIVE`; `ON_LEAVE` / `ON_TRIP` = đơn **APPROVED** giao với khoảng cần xét (theo giờ); `HANDED_OVER` (đợt 7); `ABSENT_HRM` khi bảng HRM tồn tại | migration 14 |
| 1.2 | `api_core/workflow/availability.py`; thay `_attendance_status`/`_attendance_available` trong `_substitute_approver`, `_pick_present_executor` | `service.py` |
| 1.3 | `eas.get_user_working_status` dùng cùng nguồn | migration 14 |

Nghiệm thu: người có đơn nghỉ đã duyệt 13:00–17:30 hôm nay không được giao bước có hạn rơi vào khoảng đó; đơn chưa duyệt không ảnh hưởng.

### Đợt 2 — Gán đúng lúc + chuỗi thay thế (H1, H5; D1, D4)

| # | Việc | Tệp |
|---|---|---|
| 2.1 | Khi gửi: tính tuyến (vị trí + tier); chỉ gán người bước 1 (hoặc người yêu cầu đã chọn — đợt 6); bước sau `WAITING`, `assignee_id` NULL, giữ `resolver_code` và lựa chọn của người yêu cầu (nếu có) | `_create_submission_workflow`; migration 14: CHECK `state<>'ACTIVE' OR assignee_id IS NOT NULL` |
| 2.2 | `request_participant` chỉ thêm khi người đó thực sự được giao | `service.py` |
| 2.3 | `assign_step()`: người yêu cầu đã chọn (nếu còn hợp lệ, có mặt) → ghim mềm → quy tắc vị trí → chuỗi thay thế: **người được bàn giao** → uỷ quyền → cùng chức năng (chấm điểm) → cấp trên trực tiếp → trưởng phòng → Ban giám đốc → không ai: `unassigned` + báo admin | `api_core/workflow/assignment.py` (mới) |
| 2.4 | Vị trí chức năng = nhóm người có vai trò + phạm vi phòng; `actor_bindings` cũ thành ghim mềm (đợt 4) | `routing.py`, `assignment.py` |
| 2.5 | Người thực hiện gán khi duyệt cuối đồng ý; người nghiệm thu khi chuyển `WAITING_FOR_ACCEPTANCE` | `service.py` |

Nghiệm thu: đổi người giữ chức năng giữa bước 1 và 2 → bước 2 tới người mới; người bước 2 không thấy hồ sơ trước khi tới lượt; mọi test SoD hiện có vẫn đạt.

### Đợt 3 — Gán lại khi vắng giữa chừng (H4)

| # | Việc | Tệp |
|---|---|---|
| 3.1 | Worker `process_assignment_health` (15 phút/lần): bước `ACTIVE`/việc `READY` có người giữ không còn có mặt tới hạn → `reassign_*` có lý do. Không đụng việc `RUNNING` | `worker.py`, `run_outbox_worker` |
| 3.2 | Duyệt đơn nghỉ/công tác → chuyển ngay việc đang chờ người đó có hạn trong khoảng vắng | `leave_sync.py` |
| 3.3 | Khoá tài khoản / thu hồi vai trò → chuyển mọi việc đang mở | `administration/service.mutate` |

### Đợt 4 — Ghim mềm của admin (H2; D1)

| # | Việc | Tệp |
|---|---|---|
| 4.1 | `eas.assignment_rule` (type_id NULL = mọi loại, stage `APPROVAL`/`EXECUTION`/`ACCEPTANCE`, slot, department_id XOR user_id, priority, valid_from/to, created_by, reason). **Không có cột "cứng".** RLS backend, audit | migration 14 |
| 4.2 | API `/api/v1/admin/assignment-rules` (OPS/POLICY_ADMIN, lý do ≥ 10 ký tự, `lock_security`, `admin_event`) | `administration/assignment_rules.py` |
| 4.3 | Tab **"Phân công"** (cổng quản trị, Yêu cầu & Quy trình): danh sách ghim; xem trước "hôm nay hồ sơ loại X bước Y tới ai, vì sao" | `RequestWorkflowsPage.jsx` |
| 4.4 | Chuyển `actor_bindings` hiện hành thành ghim mềm (hành vi ngày triển khai không đổi) | migration 14 (data) |

### Đợt 5 — Chính sách quá hạn do admin cài (H6; D3, D4)

| # | Việc | Tệp |
|---|---|---|
| 5.1 | `eas.sla_escalation_policy` (type_id NULL = mặc định, stage, action `REMIND`/`AUTO_TRANSFER`, sau bao nhiêu % / giờ quá hạn, nhắc lặp mỗi bao lâu). Mặc định toàn hệ thống: `REMIND` | migration 14 |
| 5.2 | Worker áp dụng: `REMIND` → nhắc người giữ + cấp trên; `AUTO_TRANSFER` → `reassign_*` theo D4 (người được bàn giao → cấp trên trực tiếp → chuỗi còn lại) | `worker.py`, `assignment.py` |
| 5.3 | Giao diện admin: mục "Quá hạn" trong tab Phân công (bảng loại × giai đoạn) | `RequestWorkflowsPage.jsx` |

Nghiệm thu: người nghiệm thu quá ngày quy định với chính sách `AUTO_TRANSFER` → chuyển cho người được bàn giao, không có thì cấp trên trực tiếp; `REMIND` → chỉ nhắc.

### Đợt 6 — Người yêu cầu xem lại, chọn/đổi người duyệt theo trọng số (H10; D6, D7, D8)

| # | Việc | Tệp |
|---|---|---|
| 6.1 | API `POST /api/v1/requests/review` (không ghi DB): nhận nội dung nháp → trả trọng số AI (1–5), phân loại, tuyến duyệt, **ứng viên hợp lệ từng bước kèm điểm và người AI chọn/gợi ý**, chế độ `AI_SELECTED` (1–2) hoặc `REQUESTER_CHOOSES` (3–5) | `workflow/views.py`, `assignment.py` |
| 6.2 | Submit nhận `approver_choices: [{step_no, user_id}]`: bắt buộc đủ ở chế độ 3–5, tuỳ chọn ở 1–2; server kiểm tra lại hợp lệ + có mặt, ghi `assignment_decision` với lý do `REQUESTER_CHOSEN` / `REQUESTER_CHANGED` / `AI_SELECTED` | `service.py` |
| 6.3 | Màn **"Xem lại yêu cầu"** sau khi điền xong: toàn bộ thông tin, tệp, phân loại, trọng số AI, từng bước duyệt với người (1–2: AI chọn + nút "Đổi người"; 3–5: danh sách chọn, gợi ý AI đánh dấu). Nút **Gửi** · **Quay lại chỉnh sửa**; thoát không gửi → nháp (tự lưu) | `RequestEditor.jsx` |
| 6.4 | Tab Tiến độ hiển thị nguồn chọn người ("AI chọn", "Người yêu cầu chọn", "Người yêu cầu đổi từ X") | `RequestDetail.jsx` |

Lưu ý: người được người yêu cầu chọn cho bước sau vẫn qua `assign_step` khi bước kích hoạt — vắng thì đi chuỗi thay thế (D1).

### Đợt 7 — Bàn giao công việc (H11; D4, D5)

| # | Việc | Tệp |
|---|---|---|
| 7.1 | Loại yêu cầu mới **`WORK_HANDOVER` — Bàn giao công việc** (loại A): người bàn giao, người nhận, từ–đến, phạm vi (mọi việc đang mở / chọn hồ sơ), ghi chú. Tuyến: **người nhận xác nhận** (bước duyệt duy nhất, người nhận phải hợp lệ cho các vai trò liên quan) | catalog + migration 14 (request_type + config_release) |
| 7.2 | Đơn nghỉ/công tác được duyệt có `handover_user_id` → tự tạo yêu cầu `WORK_HANDOVER` thay người nghỉ (khoảng thời gian = khoảng nghỉ) | `leave_sync.py` |
| 7.3 | Bàn giao hoàn thành → `eas.work_handover` (từ, đến, khoảng, request_id); `reassign_*` mọi bước/việc đang mở của người bàn giao **mà người nhận hợp lệ**; việc người nhận không hợp lệ → chuỗi thay thế; trong thời hạn, việc mới của người bàn giao đi thẳng tới người nhận | `assignment.py`, migration 14 |
| 7.4 | Hết hạn bàn giao: việc **chưa bắt đầu** trả về người ban đầu (nếu có mặt); việc đang làm giữ nguyên | worker |

Nghiệm thu: duyệt đơn nghỉ có người nhận bàn giao → người nhận có yêu cầu "Bàn giao công việc"; chấp nhận → các bước đang chờ người nghỉ chuyển sang người nhận, có lý do `HANDED_OVER`.

### Đợt 8 — AI tự duyệt bước phê duyệt A/B/C trọng số 1–2 (H9; D6)

| # | Việc | Tệp |
|---|---|---|
| 8.1 | Mở rộng điều kiện `try_auto_approve`: trọng số ≤ 2, mọi loại A/B/C, chỉ **bước phê duyệt**; quy định bắt buộc duyệt tay vẫn chặn; nếu người yêu cầu đã đổi người duyệt (D6) thì **không** tự duyệt bước đó | `auto_approval.py`, ai_service policy |
| 8.2 | Thu hồi 24 giờ cho loại B/C: hồ sơ đã sang `READY_FOR_EXECUTION`/`IN_PROGRESS` → về duyệt tay (cần mở rộng trigger `guard_request` cho chuyển trạng thái này, chỉ khi quyết định gần nhất là của AI ≤ 24 giờ) | migration 14, `service.py` |
| 8.3 | Thông báo người thực hiện khi hồ sơ bị thu hồi | outbox |

### Đợt 9 — Chấm điểm + hiển thị lý do (H7, H8; D9)

| # | Việc | Tệp |
|---|---|---|
| 9.1 | `score_candidates()` 4 tiêu chí, trọng số trong `eas.assignment_settings` (admin chỉnh) | `assignment.py`, migration 14 |
| 9.2 | `eas.assignment_decision` (bước/việc, người chọn, ứng viên + điểm, mã lý do, nguồn chọn) | migration 14 |
| 9.3 | Tab Tiến độ: "Đang giữ: X — vì …" + lịch sử gán; thông báo kèm lý do | `RequestDetail.jsx`, outbox |

## 5. Kiểm thử

| Lớp | Nội dung |
|---|---|
| Đơn vị | Có mặt (theo giờ, đơn chưa duyệt, HRM, khoá TK, bàn giao); chuỗi thay thế; chấm điểm; chế độ 1–2 / 3–5; bộ lọc hợp lệ khi người yêu cầu chọn/đổi |
| Tích hợp (bản sao live, Docker) | Ví dụ A/B/C trong docs mục 9; vắng giữa chừng; bàn giao từ đơn nghỉ và tự tạo; quá hạn `REMIND`/`AUTO_TRANSFER`; người yêu cầu chọn người trọng số 3–5; AI tự duyệt B/C trọng số 1–2 rồi thu hồi; hồ sơ cũ đang chạy khi chạy migration |
| Trình duyệt | Màn xem lại: Gửi / Quay lại / thoát → nháp; đổi người duyệt; tab Phân công của admin |
| Hồi quy | `manage.py test`, `tests/run_tests.py`, `npm test`, Playwright portal + `e2e/cross_portal_scenarios.mjs`, ruff, ESLint, build 2 cổng, kiểm tra bundle |
| Migration | 14 chạy 2 lần, rollback, chạy lại trên bản sao mô phỏng SQL Editor; bảng mới bật RLS, `anon` không có quyền |

## 6. Rủi ro và quay lại

| Rủi ro | Giảm thiểu |
|---|---|
| Người yêu cầu chọn "người dễ tính" | Chỉ chọn trong danh sách hợp lệ của đúng vị trí; ghi nhật ký và hiển thị cho người duyệt; báo cáo admin tỉ lệ đổi người theo phòng |
| AI tự duyệt B/C sai | Chỉ trọng số ≤ 2, quy định bắt buộc duyệt tay luôn chặn, thu hồi 24 giờ, admin tắt được theo loại |
| Gán lại dao động | Chỉ khi người giữ không có mặt tới hạn; tối đa 3 lần tự động/bước/ngày |
| Hồ sơ đang chạy | Bước `WAITING` đã có người giữ nguyên; vẫn qua `assign_step` khi kích hoạt |
| Không còn người hợp lệ | Bước `unassigned` + cảnh báo admin; không gán người sai thẩm quyền |
| Hiệu năng | Gán trong giao dịch hiện có bằng truy vấn tập hợp; worker theo lô |
| Quay lại | Rollback 14 dời bảng mới sang `eas_rollback_14_*`; cờ `EAS_JIT_ASSIGNMENT=false`, `EAS_AI_APPROVE_BC=false` quay về hành vi cũ |

## 7. Thứ tự và ước lượng

| Đợt | Ước lượng | Phụ thuộc |
|---|---|---|
| 1 Có mặt | 0,5–1 ngày | — |
| 2 Gán đúng lúc | 1,5–2 ngày | 1 |
| 3 Gán lại khi vắng | 1 ngày | 2 |
| 4 Ghim mềm | 1,5 ngày | 2 |
| 5 Chính sách quá hạn | 1 ngày | 2, 4 |
| 6 Xem lại + chọn người | 2 ngày | 2, 9.1 |
| 7 Bàn giao | 1,5–2 ngày | 2, 3 |
| 8 AI duyệt B/C 1–2 | 1 ngày | 2, 6 |
| 9 Chấm điểm + lý do | 1–1,5 ngày | 2 |

Tổng khoảng 11–13 ngày làm việc. Thứ tự làm đề xuất: 1 → 2 → 9 → 3 → 6 → 4 → 5 → 7 → 8.

## 8. Nhật ký tiến trình

- 03/11/2026: mở kế hoạch; hiện trạng H1–H11 kiểm tra trên mã.
- 03/11/2026: chủ dự án chốt D1–D9 (ghim mềm; vắng theo đơn đã duyệt; admin cài nhắc/tự chuyển; bàn giao 2 cách; trọng số 1–2 AI chọn + tự duyệt phê duyệt A/B/C, người yêu cầu đổi được; 3–5 AI gợi ý, người yêu cầu chọn; màn xem lại trước khi gửi).

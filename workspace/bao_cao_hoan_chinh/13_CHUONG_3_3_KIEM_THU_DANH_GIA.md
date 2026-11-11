# 3.3. KIỂM THỬ VÀ ĐÁNH GIÁ KẾT QUẢ

## 3.3.1. Xây dựng kịch bản kiểm thử chức năng

**Chiến lược.** Kiểm thử theo mô hình kim tự tháp, gồm năm tầng:
1. **Kiểm thử đơn vị và dịch vụ backend** (Django test runner, CSDL kiểm thử tạm thời): logic định tuyến, máy trạng thái, phân quyền, kiểm toán, worker.
2. **Kiểm thử tích hợp và hợp đồng** (`tests/run_tests.py`):
   - hợp đồng lược đồ CSDL với mã nguồn (truy vấn không trỏ cột không tồn tại);
   - danh mục loại yêu cầu;
   - cấu hình triển khai;
   - hợp đồng API của ứng dụng Flutter và dịch vụ AI.
3. **Kiểm thử CSDL** (`03_database_regression_DEV_ONLY.sql`): kiểm trực tiếp trigger, ràng buộc và chính sách trên bản sao.
4. **Kiểm thử giao diện** (Node test runner) cho chính sách vai trò, ma trận quyền, hệ thiết kế; và **kiểm thử đầu-cuối** (Playwright) trên trình duyệt.
5. **Kiểm thử liên thông trên dữ liệu sao chép từ hệ thống thật**: luồng ghi chạy trên bản sao PostgreSQL cục bộ; trên hệ thống thật chỉ chạy kiểm thử chỉ đọc.

Mỗi sơ đồ tuần tự ở Chương 2 ghi mã kịch bản (TCxxx) mà nó phục vụ; ma trận truy vết ở Phụ lục B. Mọi bộ kiểm thử chạy tự động trong cổng chất lượng GitHub Actions ở mỗi lần đẩy mã.

**Bảng 3.2. Kết quả kiểm thử tự động** (chạy lại ngày 04/11/2026 trên mã nguồn hiện tại)

| Bộ kiểm thử | Lệnh | Số ca | Kết quả | Thời gian |
|---|---|---|---|---|
| Backend `api_core` | `python manage.py test api_core` | 340 | **340 đạt** (gồm cả `test_schema_v2_consolidation`, `NoDirectMockAccessTests`, `TaxonomyTests`, giữ chỗ & ưu tiên BGĐ, leo thang SoD/lãnh đạo cao nhất) | 18,2 s |
| Tích hợp và hợp đồng | `python tests/run_tests.py` | 153 | **152 đạt, 1 bỏ qua** (cần môi trường riêng) | 5,4 s |
| Giao diện (đơn vị) | `npm test` (web_client) | 69 | **69 đạt** (gồm cả `formatters.test.mjs`) | 0,3 s |
| Độ phủ mã backend | `coverage run --source=api_core manage.py test` | — | **62%** dòng lệnh (10.543 dòng, 3.989 chưa phủ) | — |

**Kết quả kiểm thử đầu-cuối và liên thông** (lần chạy gần nhất ngày 03/11/2026, ghi trong `changelogs/`):

| Bộ kiểm thử | Kết quả |
|---|---|
| Playwright — cổng truy cập và menu (`portal.spec.js`) | 15/15 đạt |
| Playwright — kiểm toán đợt 1 (`batch1_audit.spec.js`) | 4/4 đạt |
| Kịch bản liên thông hai cổng trên trình duyệt (bản sao dữ liệu thật) | 21/21 đạt |
| Kiểm thử API đầu-cuối 8 giai đoạn (bản sao dữ liệu thật + Django + dịch vụ AI) | 45/45 đạt |
| Kiểm thử chỉ đọc trên hệ thống thật | 48/48 đạt |
| Tách quyền quản trị trên hệ thống thật | Tài khoản quản trị: vào được cổng quản trị, bị từ chối ở cổng nhân viên. 136/136 tài khoản còn lại: bị từ chối ở cổng quản trị và ở 13 API quản trị (403) |

**Hạn chế đã biết.**
- Hai bộ Playwright cũ `ui.spec.js` (17/18 lỗi) và `smoke.spec.js` (1/3 lỗi) viết theo giao diện trước khi tái cấu trúc menu, nên không còn phản ánh giao diện hiện tại. Hai bộ này cần viết lại; lỗi **không** phản ánh lỗi chức năng.
- Độ phủ thấp nhất ở lớp view (`workflow/views.py` 51%); logic nghiệp vụ nằm ở lớp dịch vụ và trigger nên được kiểm kỹ hơn.

## 3.3.2. Kiểm thử các luồng nghiệp vụ chính và luồng ngoại lệ

Mỗi dòng ứng với **hàm kiểm thử có thật** trong mã nguồn. Cột "Kiểm thử" ghi tên tệp, theo sau là `::` và tên hàm đã lược tiền tố `test_`. Khi cùng một tệp, các ô sau ghi `…::` thay cho tên tệp.

**Bảng 3.3. Kịch bản luồng nghiệp vụ**

| Mã | Kịch bản | Kết quả mong đợi | Kiểm thử | Kết quả |
|---|---|---|---|---|
| TC-F01 | Đơn của nhân viên lên quản lý trực tiếp; đơn của quản lý lên quản lý của họ | Đúng người duyệt | `test_request_workflow_scenarios::subordinate_request_goes_up_to_direct_manager`, `manager_request_routes_to_own_manager_not_subordinate` | Đạt |
| TC-F02 | Số tiền lớn | Thêm cấp duyệt | `…::large_amount_escalates_up_the_chain` | Đạt |
| TC-F03 | Duyệt xong giao người thực hiện, rồi về người yêu cầu nghiệm thu | Đúng chuỗi người xử lý | `…::approved_work_is_assigned_down_to_executor_and_back_to_requester` | Đạt |
| TC-F04 | Người duyệt cuối chỉ định người thực hiện | Chỉ ở bước cuối, chỉ người hợp lệ | `…::final_approver_assigns_direct_report_as_executor`, `cannot_assign_someone_who_is_not_a_direct_report`, `assignment_only_at_last_approval_step` | Đạt |
| TC-F05 | Từ chối | Kết thúc; các bước còn lại bị bỏ qua | `…::approver_reject_is_terminal_and_skips_remaining_steps` | Đạt |
| TC-F06 | Yêu cầu bổ sung | Hồ sơ trả về người yêu cầu | `…::approver_needs_info_returns_request_to_requester` | Đạt |
| TC-F07 | Nghiệm thu yêu cầu làm lại | Về người thực hiện cũ; nghiệm thu không có kết quả "từ chối" | `…::acceptor_rework_returns_to_previous_step_executor`, `acceptor_has_no_terminal_reject_outcome` | Đạt |
| TC-F08 | Thiếu lý do khi từ chối, bổ sung, làm lại hoặc huỷ | Bị từ chối | `test_workflow_service::approval_requires_reason_for_negative_outcomes`, `rework_requires_actionable_reason`, `cancellation_requires_reason` | Đạt |
| TC-F09 | Gửi không có khoá chống lặp; gửi lặp | Từ chối trước khi vào dịch vụ; lần lặp trả lại kết quả cũ | `test_workflow_api::submit_requires_idempotency_key_before_service`, `submit_exposes_replay_and_correlation_headers` | Đạt |
| TC-F10 | Xung đột nghiệp vụ hoặc phiên bản | Phong bì lỗi ổn định `409` | `test_workflow_api::domain_conflict_uses_stable_error_envelope`; `test_workflow_service::execution_rejects_invalid_version_and_short_result` | Đạt |
| TC-F11 | Tệp đổi đuôi; tệp có mã độc; máy quét ngừng | Nhận diện theo nội dung; chặn khi nhiễm hoặc khi máy quét lỗi | `test_storage::sniffs_content_instead_of_trusting_extension`, `scanner_fails_closed_for_malware_and_outage` | Đạt |
| TC-F12 | Loại yêu cầu bị tắt, thiếu quy chế hoặc không có quyền tạo | Không cho tạo | `tests/test_request_catalog_availability.py` (6 ca) | Đạt |
| TC-F13 | AI: trọng số 2 được tài khoản AI duyệt; trọng số 3 không gọi AI; AI chuyển cho người; AI không truy cập được | Đúng nhánh; luôn có người dự phòng | `test_request_workflow_scenarios::weight_two_is_approved_by_ai_system_account`, `weight_three_never_calls_ai`, `ai_escalation_leaves_human_approver`, `worker_falls_back_to_human_when_api_is_unreachable` | Đạt |
| TC-F14 | Thu hồi tự duyệt: trong và sau 24 giờ; trên quyết định của người; người yêu cầu tự thu hồi; AI không duyệt lại | Chỉ người duyệt trong phạm vi, trong 24 giờ, chỉ với quyết định của AI | `test_ai_auto_approve_revoke` (10 ca) | Đạt |
| TC-F15 | Học quy định: sinh luật đúng; dịch vụ AI bỏ qua luật mới hoặc giữ phiên bản cũ; dịch vụ không truy cập được | Chỉ áp dụng khi kiểm chứng được; lỗi thì thử lại | `test_ai_learning` (11 ca, gồm `verified_when_engine_enforces_rule`, `rejected_when_engine_ignores_rule`, `unreachable_service_is_retryable`) | Đạt |
| TC-F16 | Quy chế mới được ban hành | Áp dụng cho lần gửi kế tiếp | `test_request_workflow_scenarios::published_workflow_release_applies_to_next_submission` | Đạt |

Hai luồng sau đã được kiểm trong các kịch bản liên thông (45/45 và 21/21) nhưng **chưa có ca kiểm thử đơn vị riêng**, cần bổ sung:
- tích hợp bị tắt thì máy chủ khoá loại yêu cầu (`409 INTEGRATION_UNAVAILABLE`);
- rút đơn tranh chấp với duyệt cuối.

## 3.3.3. Kiểm thử phê duyệt đa cấp, phân quyền và kiểm soát quy định nội bộ

| Mã | Kịch bản | Kiểm thử | Kết quả |
|---|---|---|---|
| TC-P01 | Ngưỡng tiền thiết bị; luật theo số ngày; luật theo ứng dụng nhạy cảm | `test_domain::equipment_thresholds`, `days_gt_routing`, `app_code_in_routing` | Đạt |
| TC-P02 | Vi phạm tách nhiệm; người yêu cầu bị phân giải làm người thực hiện | `test_domain::rejects_separation_of_duties_violation`, `requester_cannot_resolve_as_executor` | Đạt |
| TC-P03 | Luật sai: toán tử lạ, ngưỡng âm hoặc lẻ, luật mặc định không ở cuối, trùng mã, vị trí lạ | `test_domain::rejects_operator_not_supported_by_database_contract`, `rejects_fractional_and_negative_route_thresholds`, `rejects_default_that_is_not_final`, `rejects_duplicate_rule_ids_and_unknown_actor_slots` | Đạt |
| TC-P04 | Ủy quyền còn hiệu lực; người duyệt vắng không ủy quyền thì chuyển quản lý; khoảng thời gian chồng nhau; người nhận không phải người duyệt | `test_approval_delegation` (17 ca) | Đạt |
| TC-P05 | Chống IDOR: lịch sử dùng chung kiểm quyền với chi tiết; siêu dữ liệu tệp | `test_history_views::history_reuses_detail_authorization`; `test_ops_and_config::attachment_metadata_anti_idor` | Đạt |
| TC-P06 | Nhật ký quản trị lọc theo phạm vi vai trò; danh sách vận hành kiểm phạm vi trong truy vấn | `test_role_scope_alignment` (3 ca) | Đạt |
| TC-P07 | Ma trận quyền module trong CSDL là nguồn quyết định | `test_actor_permissions` (3 ca); `web_client/e2e/access-matrix.test.mjs`, `role-policy.test.mjs` | Đạt |
| TC-P08 | Thu hồi vai trò giữ lịch sử và vô hiệu phiên; không gán quyền hay vô hiệu hoá được tài khoản hệ thống | `test_administration::revoke_keeps_history_and_invalidates_session`, `cannot_grant_roles_to_system_account`, `cannot_disable_system_account` | Đạt |
| TC-P09 | Bản quy chế đã ban hành không sửa được; kiểm tra quy chế | `test_ops_and_config::config_release_publish_immutable_published`, `config_release_validate_endpoint`; `tests/test_policy_publication.py` (8 ca) | Đạt |
| TC-P10 | Điều chuyển: kiểm loại đích và lý do; luồng HTTP đầy đủ | `test_ops_and_config::reassign_actor_validates_target_kind_and_reason`, `reassign_actor_http_flow` | Đạt |
| TC-P11 | Bộ luật AI: chỉ Policy Admin ban hành; trùng phiên bản bị từ chối; chỉ phiên bản đang hoạt động được đẩy sang AI | `test_request_workflow_scenarios::other_roles_cannot_publish_ai_rules`, `duplicate_version_is_rejected`, `inactive_version_is_not_pushed_to_ai` | Đạt |
| TC-P12 | Gán đồng thời vai trò quản trị và vai trò nghiệp vụ | Trigger CSDL của migration 11, kiểm thủ công trên bản sao | Đạt (thủ công) |

**Bảo mật xác thực** (`test_authn.py`, 26 ca; `test_security_middleware.py`, 9 ca; `tests/test_login_throttle.py`, 4 ca):
- sai mật khẩu nhiều lần → `429 LOGIN_RATE_LIMITED` kèm `Retry-After` (`test_authn::login_rate_limit_returns_retry_after`; giới hạn theo tài khoản và theo IP: `tests/test_login_throttle.py`);
- thông báo lỗi chung, tài khoản không tồn tại vẫn tốn một lần băm (chống dò thời gian): `login_is_generic_and_creates_versioned_session`, `unknown_account_still_pays_one_password_hash`;
- phiên bị thu hồi, đăng xuất và hết hạn rỗi đều bị chặn: `me_fails_closed_for_revoked_session`, `logout_revokes_server_side_session`, `session_idle_timeout_fails_closed_without_extending_absolute_ttl`;
- header bảo mật có mặt;
- chặn đường dẫn nội bộ;
- tài liệu API của dịch vụ AI bị ẩn ở production (`tests/test_ai_service_exposure.py`).

## 3.3.4. Kiểm thử hiệu năng và khả năng đáp ứng của hệ thống

**Phương pháp.** Đo thời gian thực bằng `time.perf_counter`:
- (a) truy vấn CSDL thật, chỉ đọc, 30 lần mỗi loại, từ máy phát triển đặt tại Việt Nam tới Supabase (Sydney);
- (b) suy luận mô hình AI trong tiến trình, 200 lần mỗi mô hình.

| Phép đo | Trung vị | p95 |
|---|---|---|
| CSDL: `SELECT 1` (thời gian khứ hồi mạng) | 249 ms | 261 ms |
| CSDL: danh sách 50 hồ sơ (join loại) | 250 ms | 297 ms |
| CSDL: chi tiết hồ sơ (join phiên bản) | 251 ms | 294 ms |
| AI: phân loại văn bản (TF-IDF + Logistic Regression) | 0,26 ms | 0,37 ms |
| AI: chấm rủi ro XGBoost (mô hình tổng quát) | 0,19 ms | 0,26 ms |

**Đánh giá.**
- Thời gian **tính toán** của CSDL và của mô hình AI rất nhỏ. Mô hình AI đáp ứng mục tiêu ≤ 300 ms với dư địa lớn.
- Thời gian truy vấn bị chi phối gần như hoàn toàn bởi **độ trễ mạng tới vùng Sydney** (~250 ms mỗi lượt khứ hồi). Một thao tác ghi nghiệp vụ gồm nhiều câu lệnh trong cùng giao dịch, nên khi máy chủ ứng dụng đặt ở Việt Nam, thời gian phản hồi sẽ ở mức vài trăm mili-giây đến khoảng 2 giây.
- **Giải pháp cho triển khai thật:** đặt máy chủ ứng dụng **cùng vùng** với CSDL (độ trễ nội vùng thường dưới 5 ms), hoặc chọn vùng CSDL gần người dùng (ví dụ Singapore). Trình duyệt chỉ chịu một lượt khứ hồi tới máy chủ ứng dụng.
- Phép đo tải đồng thời (vd 500 người dùng) chưa thực hiện. Đây là việc phải làm trước khi đưa vào sử dụng, với công cụ như k6 hoặc Locust, đo p95 tại cổng.

## 3.3.5. Kiểm thử Mobile và độ trễ trong quá trình phê duyệt

- **Kiểm thử hợp đồng API của ứng dụng Flutter** (`tests/test_flutter_contract.py`): các đường dẫn và trường dữ liệu mà ứng dụng sử dụng (`auth/*`, `requests`, `notifications`) phải tồn tại và đúng định dạng phía máy chủ. Kết quả: đạt.
- Ứng dụng dùng cùng API với web, nên độ trễ mỗi thao tác bằng độ trễ của API (§3.3.4).
- Chưa thực hiện kiểm thử trên thiết bị thật và kiểm thử giao diện di động tự động. Thao tác duyệt trên di động là hướng phát triển, nên nội dung "độ trễ trong quá trình phê duyệt trên di động" chưa đo được.

## 3.3.6. Kiểm thử tính toàn vẹn và khả năng truy vết của Audit Log

| Mã | Kịch bản | Kiểm thử | Kết quả |
|---|---|---|---|
| TC-A01 | Chuẩn hoá RFC 8785 khớp toàn bộ vector chuẩn của CSDL; chuẩn hoá Unicode | `test_audit::matches_all_database_canonical_vectors`, `normalizes_unicode_and_rejects_non_string_keys` (vector trong `demo_canonical_hash_vectors.json`) | Đạt |
| TC-A02 | Kiểm chứng chuỗi nguyên vẹn | `test_reporting_and_cli::audit_verify_hash_chain_success` | Đạt |
| TC-A03 | Kiểm chứng khi có bản ghi bị sửa | `test_reporting_and_cli::audit_verify_hash_chain_tamper_detected` (trả `FAIL` "Hash mismatch") | Đạt |
| TC-A04 | Lệnh `audit_verify` trả đúng mã thoát; API kiểm chứng | `…::audit_verify_command_exit_codes`, `request_audit_verify_endpoint` | Đạt |
| TC-A05 | Sửa phiên bản hồ sơ, quyết định hoặc quy chế đã ban hành, kể cả bằng role sở hữu schema | `03_database_regression_DEV_ONLY.sql`: "Revision immutable even for schema owner", "Decision immutable even for schema owner", "Published release immutable" | Đạt |
| TC-A06 | Tải tệp: tên tệp được mã hoá an toàn, kiểu nội dung nguy hiểm bị hạ cấp | `test_attachment_download_headers` (2 ca) | Đạt |
| TC-A07 | Xoá dữ liệu cá nhân khi đang có lệnh giữ pháp lý | `test_reporting_and_cli::privacy_case_blocked_by_retention_hold` | Đạt |
| TC-A08 | Nạp danh tính phát hiện vòng lặp quan hệ quản lý | `test_reporting_and_cli::identity_import_detects_cycles` | Đạt |

## 3.3.7. Đánh giá kết quả so với mục tiêu đề tài

**Bảng 3.4. Đánh giá theo mục tiêu**

| Mục tiêu | Kết quả đạt được | Mức độ |
|---|---|---|
| Chuẩn hoá vòng đời yêu cầu theo 3 mẫu | 58 loại đang hoạt động (A 9, B 27, C 22); máy trạng thái 9 trạng thái cưỡng chế hai lớp | Đạt |
| Phê duyệt đa cấp cấu hình được, không sửa mã | Luật định tuyến 4 toán tử, 1–5 cấp, phiên bản quy chế bất biến, xem trước tuyến | Đạt |
| Kiểm soát nội bộ (tách nhiệm, bốn mắt) | Cưỡng chế khi định tuyến, khi điều chuyển và ở CSDL; tách tài khoản quản trị | Đạt |
| Nhật ký kiểm toán bất biến | Chuỗi băm RFC 8785 + SHA-256, bảng chỉ-ghi-thêm, API kiểm chứng | Đạt; mốc kiểm soát ra kho ngoài chưa làm |
| SLA và cảnh báo | Chặng SLA, nhắc 50%, vi phạm 100%, outbox tin cậy | Đạt; leo thang mức 2 chưa làm |
| Ủy quyền và thay người vắng mặt | Ủy quyền có thời hạn; thay quản lý khi vắng | Đạt; nguồn chấm công cần triển khai trên hệ thống thật |
| AI hỗ trợ | Phân loại, rủi ro tham khảo, tóm tắt, tự duyệt có kiểm soát và thu hồi, học quy định | Đạt; mô hình huấn luyện trên dữ liệu tổng hợp; nhận dạng hoá đơn chưa đưa vào biểu mẫu |
| Bảo mật | Argon2, chống dò mật khẩu, phiên an toàn, CSRF, chống IDOR, quét mã độc, header bảo mật, RLS | Đạt |
| Đa nền tảng | Web hai cổng; mobile theo dõi | Đạt một phần (mobile chưa có thao tác duyệt) |
| Chất lượng phần mềm | 507 ca kiểm thử tự động đạt, cổng chất lượng CI 7 job | Đạt; độ phủ 62% cần nâng |

## 3.3.8. Đánh giá khả năng ứng dụng thực tế và hướng phát triển

**Khả năng ứng dụng.** Hệ thống chạy được ngay cho doanh nghiệp quy mô vừa và nhỏ:
- cấu hình quy trình bằng dữ liệu;
- phân quyền theo phòng ban;
- nhật ký kiểm toán có thể kiểm chứng;
- triển khai bằng Docker Compose cùng dịch vụ CSDL quản lý.

Trước khi dùng thật cần:
1. đặt máy chủ ứng dụng cùng vùng CSDL;
2. kiểm thử tải;
3. gán vai trò kiểm toán cho bộ phận kiểm soát;
4. triển khai nguồn chấm công;
5. nạp dữ liệu nhân sự thật.

**Hướng phát triển** (theo thứ tự ưu tiên):

| # | Hướng phát triển | Lý do |
|---|---|---|
| 1 | Xuất mốc kiểm soát chuỗi băm ra kho chỉ-ghi bên ngoài theo lịch | Chống trường hợp quản trị viên CSDL thay cả chuỗi |
| 2 | Duyệt kép bắt buộc cho xoá dữ liệu cá nhân; API tạo / giải toả lệnh giữ pháp lý | Hoàn thiện nguyên tắc bốn mắt và Nghị định 13/2023 |
| 3 | Khi người yêu cầu trùng vị trí duyệt: tự thay bằng quản lý trực tiếp thay vì từ chối gửi | Thuận tiện cho cấp quản lý tự lập đề nghị |
| 4 | Leo thang SLA mức 2 (≥ 150%); gửi thêm quản lý khi vi phạm; chế độ tự chuyển | Giảm hồ sơ ứ đọng |
| 5 | Giới hạn số tệp và dung lượng mỗi hồ sơ; bắt buộc tệp bằng chứng cho mẫu C | Chống lạm dụng tài nguyên; bằng chứng nghiệm thu |
| 6 | Tự duyệt có kiểm soát cho mẫu B/C rủi ro thấp; xem lại toàn bộ trước khi gửi; AI gợi ý người duyệt | Theo quyết định nghiệp vụ ngày 03/11/2026 |
| 7 | Huấn luyện lại phân loại trên đủ 58 loại và dữ liệu thật; tính đủ đặc trưng rủi ro từ dữ liệu thật; theo dõi tỷ lệ thu hồi tự duyệt | Đưa AI từ mức minh hoạ lên mức dùng thật |
| 8 | Đưa nhận dạng hoá đơn vào biểu mẫu (điền sẵn, đối chiếu số tiền) | Giảm nhập liệu |
| 9 | Mobile: duyệt nhanh, thông báo đẩy, đăng nhập sinh trắc | Phê duyệt khi di chuyển |
| 10 | SLA theo giờ làm việc và ngày lễ; phê duyệt song song; chữ ký số | Mở rộng nghiệp vụ |

## KẾT LUẬN

Đồ án đã phân tích, thiết kế và xây dựng hoàn chỉnh EAS, hệ thống tự động hoá quy trình xử lý yêu cầu nội bộ đa cấp có kiểm soát tuân thủ. Hệ thống:
- chuẩn hoá 58 loại yêu cầu theo ba mẫu vòng đời;
- định tuyến phê duyệt bằng luật cấu hình được, có phiên bản;
- cưỡng chế máy trạng thái và tách nhiệm ở cả tầng ứng dụng lẫn tầng CSDL;
- lưu vết toàn bộ thao tác bằng chuỗi băm kiểm chứng được;
- tích hợp AI theo nguyên tắc an toàn: chỉ tự động hoá vùng rủi ro thấp đã được quy định cho phép, có thể thu hồi, và luôn có người dự phòng.

Kết quả được kiểm chứng bằng 507 ca kiểm thử tự động cùng các kịch bản liên thông trên dữ liệu sao chép từ hệ thống thật.

Các giới hạn được nêu trung thực:
- mô hình AI huấn luyện trên dữ liệu tổng hợp;
- hiệu năng phụ thuộc vị trí triển khai;
- một số cơ chế kiểm soát nâng cao (mốc kiểm toán ngoài, duyệt kép xoá dữ liệu) và tính năng di động là hướng phát triển.

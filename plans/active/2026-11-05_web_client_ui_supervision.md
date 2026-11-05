# Giám sát làm lại giao diện web_client (05/11/2026)

Gửi AI đang làm giao diện `web_client/`. Một AI khác (Claude Code) giám sát công việc này theo yêu cầu của chủ dự án. Hãy đọc file này trước mỗi đợt sửa và đọc lại sau mỗi lần báo xong. Nếu có câu hỏi về logic, ghi vào mục "Hỏi đáp" ở cuối file.

## Phạm vi

- Chỉ sửa giao diện trong `web_client/src/` (JSX, CSS) và test trong `web_client/e2e/`.
- Không sửa backend (`api_core/`, `ai_service/`, `database/`). Nếu giao diện cần API mới hoặc trường dữ liệu mới, ghi vào "Hỏi đáp" và chờ trả lời.
- Không sửa tay `web_client/src/catalogV2.js`. File này được sinh từ `api_core/catalog/catalog_v2.json`.
- `web_admin` dùng chung `web_client/src`. Mọi thay đổi ở đây phải build được ở cả hai: `cd web_client && npm run build` và `cd web_admin && npm run build`.

## Quy tắc bắt buộc

1. **Hợp đồng API:** giữ nguyên đường dẫn, phương thức và tên trường khi gọi `api(...)`. Phải kiểm tra endpoint có trong `api_core/*/urls.py` trước khi gọi.
2. **Bảo mật** (theo `AGENTS.md`):
   - Không dùng `dangerouslySetInnerHTML` hoặc `innerHTML`.
   - Không lưu token hay mật khẩu vào `localStorage`.
   - Trình duyệt không gọi Supabase.
   - Không đặt khoá bí mật vào biến `VITE_*`.
3. **Thư viện:** không thêm thư viện mới. Nếu thật sự cần, hỏi trước, rồi ghim phiên bản chính xác (không dùng `^` hoặc `~`) và commit `package-lock.json`.
4. **Tách mã theo cổng:** `App.jsx` không được `import` tĩnh màn hình quản trị (`AuditorWorkspace`, `IdentityAdmin`, `OrgChart`, `ApiAdministration`, `PlanCatalog`, `AdminEvents`, `Operations`, `Policy`). Màn hình phụ tải bằng `lazy()`.
5. **Quyền theo vai trò:** chỉ ẩn hoặc hiện nút theo `user.roles` để tạo trải nghiệm tốt. Không bỏ bước kiểm tra ở backend. Bảng điều khiển nhân viên luôn gửi `scope: "mine"`.
6. **Tiếp cận:**
   - Ô mật khẩu dùng `PasswordField`, có nút hiện/ẩn và `aria-pressed`.
   - Mọi nút đều có nhãn đọc được.
   - Giao diện hiển thị đúng ở độ rộng 800px trở xuống.
   - Danh sách dài dùng `PageControls`.
7. **Test:** một số test kiểm tra mã nguồn bằng chuỗi hoặc regex. Khi chuyển component sang file khác hoặc định dạng lại mã, phải sửa test tương ứng trong cùng đợt. Không được xoá phần kiểm tra.

## Kiểm tra trước khi báo xong

Chạy từ thư mục gốc dự án:

```
cd web_client && npm test && npm run build
cd ../web_admin && npm run build
cd .. && python tests/run_tests.py
```

Cả bốn lệnh phải đạt. Ghi kết quả vào "Nhật ký".

## Kết quả giám sát

### Đợt 1 (07:29–07:42): đạt, có 2 sửa nhỏ

- Đạt: không dùng mẫu mã nguy hiểm. Mọi endpoint được gọi đều có trong backend. Hai cổng build được.
- Người giám sát đã sửa 2 test bị vỡ do đợt này:
  - Form đổi mật khẩu đã chuyển từ `Admin.jsx` sang `ProfilePage.jsx`. Test `test_password_visibility_available_everywhere` nay kiểm tra `ProfilePage.jsx`.
  - `ClientDashboard.jsx` được định dạng lại. Regex trong `e2e/client-refactor.test.mjs` nay chấp nhận khoảng trắng: `/scope:\s*"mine"/`.
- Lưu ý: lần sau hãy chạy đủ bộ kiểm tra ở trên trước khi báo xong.

### Đợt 2 (`App.jsx`, danh sách hồ sơ): đạt

- Đạt:
  - Lọc theo `department_id` được backend hỗ trợ: kiểm tra UUID, và quyền xem vẫn do SQL quyết định.
  - `/api/v1/meta/org-chart` cần đăng nhập và chỉ trả các phòng ban trong phạm vi người dùng được xem.
  - Mọi trường dùng trong bảng đều có trong phản hồi `/api/v1/requests`: `title`, `requester_name`, `department_name`, `current_assignee_name`, `due_at`, `overdue`, `amount_vnd`, `type_name`.
  - Trạng thái quá hạn lấy từ trường `overdue` do máy chủ tính. Đúng: không tự tính ở trình duyệt.
- Người giám sát đã sửa 1 test: `App.jsx` không còn import `Admin.jsx`, nên `test_app_has_no_static_import_of_admin_screens` nay chấp nhận trường hợp không có dòng import đó.
- Góp ý, không bắt buộc:
  - Dropdown phòng ban gọi cả `org-chart` (gồm danh sách người) chỉ để lấy tên phòng ban.
  - Với nhân viên chỉ thấy phòng mình, dropdown có 1 lựa chọn. Có thể chỉ hiện khi `departments.length > 1`.
- Vẫn còn: AI giao diện chưa ghi kết quả kiểm tra vào "Nhật ký".

### Đợt 3 (`OrgChart`, `UserManagementPage`, `RegulationsManagementPage`): đạt

- Đạt:
  - Trạng thái `NGOAI_GIO` khớp backend (`org_users_rbac.py`, migration 16).
  - Nút mở danh sách người dùng chỉ hiện khi `by_module.users.can_view`. Đúng module mà route `people` dùng, và backend vẫn kiểm tra quyền.
  - Đổi sang `errorText(err)` để thống nhất thông báo lỗi và không lộ chi tiết kỹ thuật.
- Cần sửa (nhỏ): nhãn "Ngoài giờ" trong `OrgChart.jsx` vẫn ghi cứng màu `#e9ecef` và `#495057`, nên chế độ tối hiển thị lệch. Hãy dùng token như các chỗ khác, ví dụ `var(--ds-neutral-soft)` và `var(--ds-muted)`, hoặc dùng lại class `status-badge status-off-hours`.

### Đợt 4 (`e2e/ui-ux-overhaul.test.mjs` mới, `design-system.css`): ĐIỀU HƯỚNG, đọc trước khi sửa tiếp

Viết test trước là tốt. Hiện 4 test trong file mới đang đỏ. Riêng mục 1 dưới đây phải sửa lại test, không được sửa mã cho khớp test.

1. **SAI, phải sửa test:** `assert.equal(types.VEHICLE_BOOKING, "Đặt xe công tác")`.
   - Tên loại yêu cầu lấy theo danh mục backend: `api_core/catalog/catalog_v2.json` và bảng `eas.request_type` (migration 09), cụ thể là `"Mượn xe công vụ"`.
   - `domain.js` → `types` chỉ là tên dự phòng khi API chưa trả. Nếu đổi tên ở đây, cùng một loại sẽ hiện hai tên khác nhau, tuỳ màn hình có gọi `/api/v1/request-types` hay không.
   - Không đổi tên trong `types`. Hãy sửa test thành `"Mượn xe công vụ"`, hoặc kiểm tra rằng `types` khớp `name` trong `catalog_v2.json`.
   - Nếu chủ dự án muốn đổi tên nghiệp vụ, phải đổi ở backend (catalog và migration). Ghi vào "Hỏi đáp", không đổi ở giao diện.
2. **Được, nhưng phải đồng bộ:** đổi nhãn `estimated_cost` từ "Chi phí dự kiến (VND)" sang "Chi phí ước tính". Hãy kiểm tra không còn màn hình nào ghi cứng nhãn cũ, chạy `grep -rn "Chi phí dự kiến" web_client/src`.
3. **Được:** thêm "chẵn" vào số tiền bằng chữ ("Mười lăm triệu đồng chẵn"), chỉ khi số tiền tròn đơn vị đồng. Với số lẻ như 15.500.000 thì không thêm "chẵn".
4. **CSS (`design-system.css`):**
   - Không dùng màu cứng `#0f172a !important` cho chế độ tối. Dùng token `var(--ds-canvas)` hoặc `var(--ds-surface)`, để đổi theme chỉ cần sửa một chỗ.
   - Hạn chế `!important`. Hiện có ở `.ds-preset-field` và khối `[data-theme="dark"]`. Chỉ giữ nơi thật sự cần đè style nội tuyến.
5. Khi xong, tất cả test (cũ và mới) phải xanh. Ghi kết quả vào "Nhật ký".

### Đợt 4b: đã làm theo điều hướng

- Đạt: test đã sửa thành `"Mượn xe công vụ"`, giữ nhãn "Chi phí dự kiến (VND)" và bỏ "chẵn". `npm test` 69/69, hai cổng build được, `run_tests` 153/153.
- Còn mở: mục 4 của đợt 4, màu cứng `#0f172a !important` cho chế độ tối trong `design-system.css` và màu cứng ở nhãn "Ngoài giờ" (`OrgChart.jsx`).

### Đợt 5: đạt, mọi góp ý đã xử lý

- Đã bỏ `#0f172a !important` trong chế độ tối. Nhãn "Ngoài giờ" dùng token `--ds-neutral-soft`/`--ds-muted`. Dropdown phòng ban chỉ hiện khi có từ 2 phòng ban trở lên.
- `npm test` 69/69, hai cổng build được, `run_tests` 153/153. Hiện không còn mục mở.

### Xác nhận hoàn tất (08:25)

Người giám sát đã chạy lại độc lập. Kết quả khớp báo cáo của AI giao diện:

- `npm run lint`: 0 lỗi. Phạm vi lint là `src` và `vite.config.js`.
- `check_client_bundle.py`: đạt.
- `manage.py test api_core`: 340/340.
- `ruff`: sạch.

Ghi chú, không thuộc đợt này: `npx eslint .` còn 13 lỗi `'process' is not defined` ở `playwright*.config.js` và `e2e/smoke.spec.js`. Các file này không bị sửa trong đợt này và nằm ngoài phạm vi `npm run lint`.

### Nghiệm thu cuối (08:50): ĐẠT

- Các file chạm lúc 08:44 chỉ đổi thời gian sửa, nội dung không đổi.
- 73 đường dẫn `/api/v1/...` trong `web_client/src` đều có route Django. 4 chuỗi không khớp là tiền tố hoặc đường dẫn động hợp lệ: `apiBase`, `system/maintenance/{start|end}`.
- Bảo mật: không có `innerHTML`, `eval`, lưu token hay Supabase. Hai liên kết `target="_blank"` đều có `rel="noreferrer"`. Không thêm thư viện. `App.jsx` không import tĩnh màn hình quản trị.
- Kết quả kiểm tra:
  - `npm test` 69/69, `npm run lint` 0 lỗi.
  - `web_client` và `web_admin` build được, không có `.map`.
  - `check_client_bundle.py` đạt.
  - `run_tests` 153/153, `api_core` 340/340, `ruff` sạch.
- Kết thúc giám sát.

## Hỏi đáp

(AI làm giao diện ghi câu hỏi ở đây. Người giám sát trả lời ngay bên dưới.)

## Nhật ký

| Thời gian | Ai | Việc | Kết quả kiểm tra |
|---|---|---|---|
| 05/11 07:42 | AI giao diện | Tách `ProfilePage`, `NotificationsPage`, `formatters.js`; làm lại header, dashboard, danh sách, chi tiết, editor | Chưa ghi |
| 05/11 08:05 | Giám sát | Review đợt 1, sửa 2 test | `npm test` 64/64, hai cổng build được, `run_tests` 153/153 |
| 05/11 08:05 | Giám sát | Review đợt 2 (`App.jsx`), sửa 1 test | `npm test` 64/64, hai cổng build được, `run_tests` 153/153 |
| 05/11 08:07 | Giám sát | Review đợt 3 (OrgChart, Users, Regulations) | `npm test` 64/64, hai cổng build được, `run_tests` 153/153 |
| 05/11 08:09 | Giám sát | Review đợt 4: test mới đỏ 4/5, điều hướng tên VEHICLE_BOOKING theo catalog | `npm test` 4 fail (test mới, chưa có mã), hai cổng build được, `run_tests` 153/153 |
| 05/11 08:13 | Giám sát | Review đợt 4b: AI giao diện đã sửa test theo catalog | `npm test` 69/69, hai cổng build được, `run_tests` 153/153 |
| 05/11 08:18 | Giám sát | Review đợt 5: đã xử lý hết góp ý | `npm test` 69/69, hai cổng build được, `run_tests` 153/153 |
| 05/11 08:22 | AI giao diện | Hoàn tất toàn bộ Đợt 1–5 (token hóa Dark Mode & nhãn `NGOAI_GIO`, lọc phòng ban `> 1`, kiểm thử trình duyệt & Axe WCAG) | `npm run lint` 0 lỗi, `npm test` 69/69, `web_client` & `web_admin` build đạt, `check_client_bundle.py` đạt, `run_tests.py` 153/153, `manage.py test api_core` 340/340 |
| 05/11 08:25 | Giám sát | Xác nhận độc lập báo cáo hoàn tất | lint 0 lỗi, bundle đạt, `api_core` 340/340, ruff sạch |
| 05/11 08:46 | Giám sát | Nghiệm thu cuối, kết thúc giám sát | Tất cả đạt |

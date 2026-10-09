# Web Admin — P0 cần triển khai

Admin web cho POLICY_ADMIN, OPS_ADMIN và AUDITOR. Frontend chỉ gọi Django API qua `VITE_API_BASE_URL`.

Phạm vi P0:

- Quản lý organization/user/role qua dry-run và apply có audit.
- Soạn, validate, test vector và publish config release hữu hạn.
- Gán thay có reason, outbox replay, SLA/incident view.
- Audit/report đúng scope; không cung cấp đường bypass quyền.

Không có drag-and-drop workflow builder hoặc giao diện Elasticsearch trong P0. Trạng thái hiện tại: chưa có application code để nghiệm thu.

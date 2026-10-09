# EAS Web Client

React client P0 cho requester và approver. Client chỉ gọi Django API cùng origin; không chứa Supabase key.

```bash
npm ci
npm run build
```

Luồng đã dựng: CSRF/login, session profile, danh sách/chi tiết, tạo draft, upload file riêng tư, submit LEAVE/ACCESS/EQUIPMENT và approval decision. Browser E2E với staging thật vẫn là gate `NOT RUN`.

# 🚀 Hướng Dẫn Sử Dụng Agent Skills

> Tài liệu này mô tả tất cả các **Skills**, **Subagents** và **Slash Commands** mà bạn có thể sử dụng khi làm việc với Antigravity Agent.

---

## 📑 Mục Lục

- [Cách Kích Hoạt Skill](#cách-kích-hoạt-skill)
- [Nhóm 1: Lên Ý Tưởng & Lập Kế Hoạch](#nhóm-1-lên-ý-tưởng--lập-kế-hoạch)
- [Nhóm 2: Thiết Kế & Kiến Trúc](#nhóm-2-thiết-kế--kiến-trúc)
- [Nhóm 3: Phát Triển & Triển Khai Code](#nhóm-3-phát-triển--triển-khai-code)
- [Nhóm 4: Kiểm Thử & Debug](#nhóm-4-kiểm-thử--debug)
- [Nhóm 5: Review & Chất Lượng Code](#nhóm-5-review--chất-lượng-code)
- [Nhóm 6: Bảo Mật & Hiệu Năng](#nhóm-6-bảo-mật--hiệu-năng)
- [Nhóm 7: Vận Hành & Triển Khai Production](#nhóm-7-vận-hành--triển-khai-production)
- [Nhóm 8: Tài Liệu & Git](#nhóm-8-tài-liệu--git)
- [Nhóm 9: Cấu Hình & Tùy Chỉnh Agent](#nhóm-9-cấu-hình--tùy-chỉnh-agent)
- [Subagents (Agent Phụ)](#subagents-agent-phụ)
- [Slash Commands (Lệnh Tắt)](#slash-commands-lệnh-tắt)

---

## Cách Kích Hoạt Skill

Bạn **không cần gọi tên skill** một cách tường minh. Chỉ cần mô tả yêu cầu của bạn bằng ngôn ngữ tự nhiên, agent sẽ tự động nhận diện và kích hoạt skill phù hợp. Tuy nhiên, bạn cũng có thể **yêu cầu trực tiếp** bằng cách đề cập đến tên hoặc mô tả của skill.

**Ví dụ:**
- ✅ *"Hãy review code cho tôi trước khi merge"* → Tự động kích hoạt `code-review-and-quality`
- ✅ *"Phân tích bảo mật cho module authentication"* → Tự động kích hoạt `security-and-hardening`
- ✅ *"Hãy phỏng vấn tôi để hiểu rõ yêu cầu"* → Tự động kích hoạt `interview-me`

---

## Nhóm 1: Lên Ý Tưởng & Lập Kế Hoạch

### 💡 Idea Refine — *Tinh chỉnh ý tưởng*
| | |
|---|---|
| **Mô tả** | Biến ý tưởng thô thành concept sắc nét, có thể hành động được thông qua tư duy phân kỳ và hội tụ có cấu trúc. |
| **Khi nào dùng** | Khi ý tưởng còn mơ hồ, cần stress-test giả định, hoặc muốn mở rộng lựa chọn trước khi chốt phương án. |
| **Cách kích hoạt** | *"Hãy giúp tôi ideate tính năng X"*, *"Refine ý tưởng này"*, *"Stress-test kế hoạch của tôi"* |

### 🎯 Interview Me — *Phỏng vấn để hiểu yêu cầu*
| | |
|---|---|
| **Mô tả** | Trích xuất điều người dùng **thực sự muốn** thay vì điều họ **nghĩ họ nên muốn**, thông qua phỏng vấn từng câu hỏi một cho đến khi đạt ~95% tin cậy về ý định. |
| **Khi nào dùng** | Khi yêu cầu chưa đủ rõ ràng (*"build cho tôi X"* mà không nói rõ *cho ai*, *tại sao*), hoặc khi bạn muốn được hỏi kỹ trước khi bắt đầu. |
| **Cách kích hoạt** | *"Phỏng vấn tôi"*, *"Grill me"*, *"Hỏi tôi để hiểu rõ hơn"* |

### 📋 Planning & Task Breakdown — *Chia nhỏ công việc*
| | |
|---|---|
| **Mô tả** | Phân tách công việc thành các task có thứ tự, có thể triển khai được. |
| **Khi nào dùng** | Khi có spec hoặc yêu cầu rõ ràng và cần chia thành các task cụ thể. Khi task quá lớn để bắt đầu, cần ước lượng scope, hoặc có thể làm song song. |
| **Cách kích hoạt** | *"Lên kế hoạch triển khai feature X"*, *"Chia nhỏ task này"*, *"Estimate scope cho tôi"* |

### 📝 Spec-Driven Development — *Viết spec trước khi code*
| | |
|---|---|
| **Mô tả** | Tạo specification chi tiết trước khi bắt đầu code. |
| **Khi nào dùng** | Khi bắt đầu dự án mới, feature mới, hoặc thay đổi đáng kể mà chưa có spec. Khi yêu cầu không rõ ràng hoặc chỉ là ý tưởng mơ hồ. |
| **Cách kích hoạt** | *"Viết spec cho feature X"*, *"Tạo specification trước khi code"* |

---

## Nhóm 2: Thiết Kế & Kiến Trúc

### 🔌 API & Interface Design — *Thiết kế API ổn định*
| | |
|---|---|
| **Mô tả** | Hướng dẫn thiết kế API và interface ổn định, bền vững. |
| **Khi nào dùng** | Khi thiết kế REST/GraphQL endpoints, định nghĩa type contracts giữa các module, hoặc thiết lập ranh giới giữa frontend và backend. |
| **Cách kích hoạt** | *"Thiết kế API cho module user"*, *"Review interface design"*, *"Tạo type contracts"* |

### 🎨 Frontend UI Engineering — *Xây dựng UI chất lượng production*
| | |
|---|---|
| **Mô tả** | Xây dựng UI chất lượng production-ready, không giống "AI-generated". |
| **Khi nào dùng** | Khi xây dựng hoặc chỉnh sửa giao diện người dùng, tạo component, implement layout, quản lý state. |
| **Cách kích hoạt** | *"Xây UI cho trang dashboard"*, *"Tạo component card đẹp"*, *"Implement responsive layout"* |

---

## Nhóm 3: Phát Triển & Triển Khai Code

### 🧱 Incremental Implementation — *Triển khai từng bước*
| | |
|---|---|
| **Mô tả** | Deliver thay đổi theo từng bước nhỏ, có kiểm soát. |
| **Khi nào dùng** | Khi implement feature hoặc thay đổi liên quan đến nhiều file. Khi sắp viết lượng code lớn, hoặc task quá lớn để ship một lần. |
| **Cách kích hoạt** | *"Triển khai feature X từng bước"*, *"Implement incrementally"* |

### 📖 Source-Driven Development — *Dựa trên documentation chính thức*
| | |
|---|---|
| **Mô tả** | Mọi quyết định implementation đều dựa trên documentation chính thức, có trích dẫn nguồn. |
| **Khi nào dùng** | Khi muốn code đúng chuẩn, không dùng pattern lỗi thời. Khi build với framework hoặc library mà tính đúng đắn quan trọng. |
| **Cách kích hoạt** | *"Implement theo đúng docs chính thức"*, *"Check best practices từ official docs"* |

### 🔧 Code Simplification — *Đơn giản hóa code*
| | |
|---|---|
| **Mô tả** | Đơn giản hóa code để dễ đọc hơn mà không thay đổi behavior. |
| **Khi nào dùng** | Khi refactor code cho rõ ràng hơn. Khi code hoạt động nhưng khó đọc, khó maintain, hoặc khó mở rộng. |
| **Cách kích hoạt** | *"Simplify code này"*, *"Refactor cho dễ đọc hơn"*, *"Giảm complexity"* |

### 🔄 Deprecation & Migration — *Quản lý deprecated code*
| | |
|---|---|
| **Mô tả** | Quản lý quá trình deprecation và migration giữa các hệ thống. |
| **Khi nào dùng** | Khi xóa hệ thống/API/feature cũ, migrate người dùng sang implementation mới, hoặc quyết định maintain hay sunset code hiện tại. |
| **Cách kích hoạt** | *"Migrate từ API v1 sang v2"*, *"Deprecate module cũ"*, *"Lên kế hoạch migration"* |

---

## Nhóm 4: Kiểm Thử & Debug

### 🧪 Test-Driven Development — *Phát triển hướng test*
| | |
|---|---|
| **Mô tả** | Viết test trước, implement sau. Chứng minh code hoạt động đúng. |
| **Khi nào dùng** | Khi implement logic, fix bug, hoặc thay đổi behavior. Khi cần chứng minh code work, khi có bug report, hoặc sắp modify chức năng hiện có. |
| **Cách kích hoạt** | *"Viết test cho function X"*, *"TDD cho feature mới"*, *"Thêm test coverage"* |

### 🐛 Debugging & Error Recovery — *Debug có hệ thống*
| | |
|---|---|
| **Mô tả** | Hướng dẫn debug root-cause có hệ thống thay vì đoán mò. |
| **Khi nào dùng** | Khi test fail, build lỗi, behavior không đúng kỳ vọng, hoặc gặp lỗi bất ngờ. |
| **Cách kích hoạt** | *"Debug lỗi này"*, *"Tìm root cause"*, *"Tại sao test fail?"* |

### 🌐 Browser Testing with DevTools — *Test trên trình duyệt thật*
| | |
|---|---|
| **Mô tả** | Test trực tiếp trên trình duyệt thật qua Chrome DevTools MCP. |
| **Khi nào dùng** | Khi cần inspect DOM, bắt console errors, phân tích network requests, profile performance, hoặc verify visual output. |
| **Cách kích hoạt** | *"Check console errors trên browser"*, *"Inspect DOM element"*, *"Profile performance trên Chrome"* |
| **Yêu cầu** | Cần cấu hình `chrome-devtools` MCP server |

### 🤔 Doubt-Driven Development — *Review đối kháng*
| | |
|---|---|
| **Mô tả** | Mọi quyết định non-trivial đều được review đối kháng (adversarial review) trước khi chấp nhận. |
| **Khi nào dùng** | Khi tính đúng đắn quan trọng hơn tốc độ, khi làm việc với code lạ, khi stakes cao (production, security, irreversible operations). |
| **Cách kích hoạt** | *"Double-check quyết định này"*, *"Review đối kháng"*, *"Stress-test approach này"* |

---

## Nhóm 5: Review & Chất Lượng Code

### ✅ Code Review & Quality — *Review đa chiều*
| | |
|---|---|
| **Mô tả** | Tiến hành code review đa chiều: correctness, readability, architecture, security, performance. |
| **Khi nào dùng** | Trước khi merge bất kỳ thay đổi nào. Khi review code của chính mình, agent khác, hoặc đồng nghiệp. |
| **Cách kích hoạt** | *"Review code trước khi merge"*, *"Đánh giá chất lượng code"*, *"Check code quality"* |

---

## Nhóm 6: Bảo Mật & Hiệu Năng

### 🔒 Security & Hardening — *Bảo mật ứng dụng*
| | |
|---|---|
| **Mô tả** | Gia cố code chống lại các lỗ hổng bảo mật. |
| **Khi nào dùng** | Khi xử lý user input, authentication, data storage, hoặc tích hợp bên ngoài. Khi build feature nhận untrusted data, quản lý user sessions, hoặc tương tác với third-party services. |
| **Cách kích hoạt** | *"Audit bảo mật cho module auth"*, *"Harden endpoint này"*, *"Check security vulnerabilities"* |

### ⚡ Performance Optimization — *Tối ưu hiệu năng*
| | |
|---|---|
| **Mô tả** | Tối ưu hiệu năng ứng dụng dựa trên profiling và đo lường. |
| **Khi nào dùng** | Khi có yêu cầu hiệu năng, nghi ngờ performance regression, hoặc Core Web Vitals/load times cần cải thiện. |
| **Cách kích hoạt** | *"Tối ưu performance cho query này"*, *"Profile bottleneck"*, *"Cải thiện load time"* |

---

## Nhóm 7: Vận Hành & Triển Khai Production

### 🚀 Shipping & Launch — *Chuẩn bị launch production*
| | |
|---|---|
| **Mô tả** | Chuẩn bị mọi thứ cho production launch: checklist, monitoring, staged rollout, rollback strategy. |
| **Khi nào dùng** | Khi chuẩn bị deploy lên production, cần pre-launch checklist, setup monitoring, hoặc lập kế hoạch rollout. |
| **Cách kích hoạt** | *"Chuẩn bị launch production"*, *"Tạo pre-launch checklist"*, *"Lên kế hoạch rollout"* |

### 🔧 CI/CD & Automation — *Tự động hóa pipeline*
| | |
|---|---|
| **Mô tả** | Thiết lập và cấu hình CI/CD pipeline tự động. |
| **Khi nào dùng** | Khi setup hoặc chỉnh sửa build/deployment pipelines, tự động hóa quality gates, cấu hình test runners, hoặc thiết lập deployment strategies. |
| **Cách kích hoạt** | *"Setup CI/CD pipeline"*, *"Cấu hình GitHub Actions"*, *"Tự động hóa deployment"* |

### 📊 Observability & Instrumentation — *Giám sát ứng dụng*
| | |
|---|---|
| **Mô tả** | Instrument code để production behavior hiển thị và chẩn đoán được. |
| **Khi nào dùng** | Khi thêm logging, metrics, tracing, hoặc alerting. Khi ship feature chạy production và cần bằng chứng nó hoạt động. |
| **Cách kích hoạt** | *"Thêm logging cho module X"*, *"Setup tracing"*, *"Cấu hình alerting"* |

---

## Nhóm 8: Tài Liệu & Git

### 📄 Documentation & ADRs — *Ghi chú kiến trúc*
| | |
|---|---|
| **Mô tả** | Ghi lại các quyết định kiến trúc (Architecture Decision Records) và documentation. |
| **Khi nào dùng** | Khi đưa ra quyết định kiến trúc, thay đổi public APIs, ship features, hoặc cần ghi lại context cho tương lai. |
| **Cách kích hoạt** | *"Tạo ADR cho quyết định X"*, *"Viết documentation"*, *"Ghi lại architectural decision"* |

### 🌿 Git Workflow & Versioning — *Quy trình Git*
| | |
|---|---|
| **Mô tả** | Cấu trúc git workflow practices: commit, branch, resolve conflicts. |
| **Khi nào dùng** | Khi commit, branching, resolving conflicts, hoặc tổ chức work across multiple streams. |
| **Cách kích hoạt** | *"Commit theo conventional commits"*, *"Tạo branch strategy"*, *"Resolve merge conflict"* |

---

## Nhóm 9: Cấu Hình & Tùy Chỉnh Agent

### ⚙️ Context Engineering — *Tối ưu context cho agent*
| | |
|---|---|
| **Mô tả** | Tối ưu setup context cho agent để output chất lượng hơn. |
| **Khi nào dùng** | Khi bắt đầu session mới, khi agent output kém chất lượng, khi chuyển task, hoặc cần cấu hình rules files. |
| **Cách kích hoạt** | *"Cấu hình context cho project"*, *"Setup rules cho agent"* |

### 🛠️ AGY Customizations — *Tùy chỉnh Antigravity*
| | |
|---|---|
| **Mô tả** | Hướng dẫn toàn diện về hệ thống tùy chỉnh Antigravity: skills, rules, plugins, hooks, MCP servers. |
| **Khi nào dùng** | Khi cần tạo skill mới, viết rules, cấu hình plugin, hoặc hiểu cách customization hoạt động. |
| **Cách kích hoạt** | *"Tạo custom skill"*, *"Viết rule mới"*, *"Hướng dẫn cấu hình AGY"* |

### 📱 Android CLI — *Công cụ Android*
| | |
|---|---|
| **Mô tả** | Sử dụng `android` CLI để tạo project, chạy app, quản lý AVD, SDK, và tra cứu documentation Android. |
| **Khi nào dùng** | Khi phát triển ứng dụng Android, cần tạo project mới, chạy trên device/emulator, hoặc quản lý SDK. |
| **Cách kích hoạt** | *"Tạo Android project"*, *"Chạy app trên emulator"*, *"Cài đặt Android SDK"* |

---

## Subagents (Agent Phụ)

Subagents là các agent chuyên biệt có thể được gọi ra để xử lý các nhiệm vụ cụ thể. Chúng hoạt động như các chuyên gia trong lĩnh vực riêng.

| Subagent | Vai trò | Khi nào dùng | Cách kích hoạt |
|---|---|---|---|
| 🔍 **Code Reviewer** | Senior code reviewer đánh giá 5 chiều: correctness, readability, architecture, security, performance | Trước khi merge code | *"Review kỹ code này"* |
| 🛡️ **Security Auditor** | Security engineer chuyên phát hiện lỗ hổng, threat modeling, secure coding | Khi cần audit bảo mật, phân tích threat | *"Audit bảo mật cho API này"* |
| 🧪 **Test Engineer** | QA engineer chuyên test strategy, viết test, phân tích coverage | Khi cần thiết kế test suite, viết test, đánh giá test quality | *"Thiết kế test suite cho module X"* |
| ⚡ **Web Performance Auditor** | Performance engineer chuyên Core Web Vitals, loading, rendering, network | Khi cần audit performance web, phân tích CWV | *"Audit web performance"* |

---

## Slash Commands (Lệnh Tắt)

Slash commands là các phím tắt bạn có thể gõ trực tiếp trong chat UI.

### `/goal` — Chạy task dài hạn
> Dùng khi muốn agent chạy task dài (ví dụ: qua đêm) và muốn agent thật kỹ lưỡng, không dừng cho đến khi hoàn thành mục tiêu.

**Ví dụ:** Gõ `/goal` rồi mô tả: *"Refactor toàn bộ module auth để dùng JWT, bao gồm tests"*

### `/schedule` — Lên lịch hoặc hẹn giờ
> Dùng khi muốn chạy một instruction theo lịch định kỳ hoặc đặt timer một lần.

**Ví dụ:** Gõ `/schedule` rồi mô tả: *"Mỗi ngày lúc 9h sáng, check health của API"*

### `/grill-me` — Phỏng vấn để chốt kế hoạch
> Dùng khi muốn align kế hoạch thông qua phỏng vấn tương tác để giải quyết các design decisions.

**Ví dụ:** Gõ `/grill-me` trước khi bắt đầu một feature phức tạp.

### `/learn` — Dạy agent ghi nhớ
> Dùng khi đã sửa lỗi cho agent hoặc giải quyết một setup phức tạp và muốn agent nhớ hành vi này cho các task sau.

**Ví dụ:** Sau khi sửa cách agent format code, gõ `/learn` để agent ghi nhớ.

---

## 🎯 Bảng Tham Chiếu Nhanh

| Bạn muốn... | Dùng Skill / Command |
|---|---|
| Brainstorm ý tưởng | `idea-refine` |
| Được hỏi kỹ về yêu cầu | `interview-me` hoặc `/grill-me` |
| Viết spec trước khi code | `spec-driven-development` |
| Chia nhỏ task | `planning-and-task-breakdown` |
| Thiết kế API | `api-and-interface-design` |
| Build UI đẹp | `frontend-ui-engineering` |
| Code từng bước nhỏ | `incremental-implementation` |
| Viết test trước | `test-driven-development` |
| Debug lỗi | `debugging-and-error-recovery` |
| Review code | `code-review-and-quality` + **Code Reviewer** subagent |
| Audit bảo mật | `security-and-hardening` + **Security Auditor** subagent |
| Tối ưu performance | `performance-optimization` + **Web Performance Auditor** subagent |
| Setup CI/CD | `ci-cd-and-automation` |
| Chuẩn bị launch | `shipping-and-launch` |
| Thêm monitoring/logging | `observability-and-instrumentation` |
| Ghi lại quyết định | `documentation-and-adrs` |
| Quản lý git workflow | `git-workflow-and-versioning` |
| Refactor cho sạch | `code-simplification` |
| Migrate hệ thống cũ | `deprecation-and-migration` |
| Task dài chạy qua đêm | `/goal` |
| Lên lịch định kỳ | `/schedule` |
| Agent nhớ preference | `/learn` |

---

> [!TIP]
> **Mẹo:** Bạn có thể kết hợp nhiều skill trong một workflow. Ví dụ: bắt đầu bằng `interview-me` → `spec-driven-development` → `planning-and-task-breakdown` → `incremental-implementation` → `test-driven-development` → `code-review-and-quality` → `shipping-and-launch`.

> [!NOTE]
> Tất cả các skill đều được kích hoạt **tự động** dựa trên ngữ cảnh yêu cầu của bạn. Bạn không cần nhớ tên chính xác — chỉ cần mô tả những gì bạn muốn làm!


---

# 📋 NHẬT KÝ THỰC HIỆN CÁC GIAI ĐOẠN DỰ ÁN (PHASE 0 - PHASE 7)

## 1. Giai đoạn 0 (Phase 0): Audit Dự Án, Sửa Lỗi Nền Tảng & Đồng Bộ Plans
- Rà soát toàn bộ tài liệu đặc tả SRS, kiến trúc micro-service, và file SQL Migration.
- Dọn dẹp các bảng trùng lặp, chuẩn hóa các trường dữ liệu và bảo đảm không làm mất bất kỳ dữ liệu nghiệp vụ nào.
- Cập nhật tài liệu quy hoạch phát triển hệ thống quản trị 9 chức năng trong `plans/active/2026-11-03_admin_9_features_roadmap.md`.

## 2. Giai đoạn 1 (Phase 1): Thiết Kế File SQL Migration Supabase
- Tạo file migration an toàn tuyệt đối: `supabase/migrations/20261103_admin_full_upgrade.sql`.
- Tạo và mở rộng các bảng: `departments`, `app_user` (kèm `avatar_url`, `role_id`, `department_id`), `user_leave_and_trips` (chấm công, công tác, nghỉ phép), `role_permissions`, `user_custom_permissions`, `mock_apis` (8 APIs nội bộ), và `system_versions_changelog`.
- Cung cấp đầy đủ Seed Data tiếng Việt với cơ chế `ON CONFLICT DO NOTHING`.

## 3. Giai đoạn 2 (Phase 2): Master Layout, Sidebar & Header Đồng Bộ
- Thống nhất bảng màu (Deep Corporate Blue `#1E40AF` & `#1E3A8A`), font chữ (Roboto cho body, Montserrat cho tiêu đề), bo góc và bóng mờ trên cả `web_admin` và `web_client`.
- Hỗ trợ chế độ Sáng / Tối (Dark / Light Mode) mượt mà với `theme-toggle-btn`.
- Sidebar dạng 2 trạng thái: Mở rộng (Expanded) và Thu gọn (Collapsed) ghi nhớ `localStorage`.
- Header đồng bộ với Avatar người dùng, Chức vụ, Nút đăng xuất, Chuông thông báo (Notification Bell), Thanh tìm kiếm nhanh (Global Search) và Tiêu đề Header luôn đổi theo đúng chức năng đang mở.

## 4. Giai đoạn 3 (Phase 3): Module "Tổng Quan" & "Yêu Cầu & Quy Trình"
- **Chức năng 1 (Tổng quan):** Bộ lọc 4 chu kỳ (Ngày / Tuần / Tháng / Năm), 4 thẻ KPI (Tổng yêu cầu, Tỷ lệ duyệt thành công, Bị từ chối, Đang xử lý), Biểu đồ xu hướng, Top phòng ban, Top nhân viên và Thống kê thời gian xử lý SLA theo chu kỳ A/B/C.
- **Chức năng 2 (Yêu cầu & Quy trình):** Bảng Kanban trực quan 3 cột (Quy trình A - Duyệt nhanh tự động / Quy trình B - Duyệt tiêu chuẩn / Quy trình C - Duyệt chặt chẽ đa cấp), cho phép điều chỉnh trọng số rủi ro (1-5) và cấp độ phê duyệt (1-5).

## 5. Giai đoạn 4 (Phase 4): Sơ Đồ Công Ty, Quản Lý Người Dùng & Ma Trận Phân Quyền
- **Chức năng 3 (Sơ đồ công ty):** Cây sơ đồ tổ chức trực quan (Visual Org Chart Tree), hiển thị Trưởng phòng ban, số lượng nhân sự, và modal danh sách nhân sự trực thuộc khi nhấp vào khối phòng ban.
- **Chức năng 4 (Người dùng & Trạng thái):** Tính toán trạng thái làm việc thời gian thực (Đang làm việc trong khung giờ 08:00 - 17:30 T2-T6; Nghỉ làm; Đi công tác; Đang làm ngoài giờ). Nhấp vào tổng số yêu cầu mở modal chi tiết 5 giai đoạn (`DRAFT`, `PENDING_APPROVAL`, `IN_EXECUTION`, `PENDING_ACCEPTANCE`, `COMPLETED` / `REJECTED`).
- **Chức năng 5 (Ma trận phân quyền RBAC):** Bảng ma trận ma trận 10 nhóm chức năng, hỗ trợ phân quyền theo Chức vụ (Vai trò) và cấp quyền tùy biến theo từng Cá nhân nhân viên với `PermissionGuard`.

## 6. Giai đoạn 5 (Phase 5): Quy Định Công Ty & Quản Trị AI (Semantic Versioning & Auto-Lock)
- **Chức năng 6 (Quy định công ty):** Quản lý quy định nội bộ, áp dụng Semantic Versioning tự động (Sửa tăng Minor `v1.0 -> v1.1`, Thêm/Xóa tăng Major `v1.1 -> v2.0`).
- **Chức năng 7 (Quản trị AI):** Đồng bộ Knowledge Graph sang `ai_service`, mô phỏng giả lập đánh giá rủi ro yêu cầu trước khi huấn luyện thật, tiến trình huấn luyện 4 bước (Pre-processing -> Embedding -> KG Update -> Health Check).
- **Cơ chế Khóa tự động (Client Auto-Lock):** Khi AI đang học quy định mới, `web_client` tự động chuyển sang màn hình bảo trì, hiển thị tiến độ và đếm ngược cho người dùng thoát ra an toàn, tự động mở khóa khi hoàn tất.

## 7. Giai đoạn 6 (Phase 6): Quản Lý API (Circuit Breaker) & Phiên Bản Hệ Thống
- **Chức năng 8 (Quản lý API & Circuit Breaker):** Quản lý 8 API hệ thống nội bộ (HR, Finance, IT, CRM, Assets, Facilities, Procurement, Travel), xem JSON payload mẫu, tự động liên kết biểu mẫu phụ thuộc. Khi Quản trị viên ngắt kết nối API, toàn bộ biểu mẫu liên quan trên cả `web_admin` và `web_client` chuyển sang trạng thái "Tạm ngưng", hiển thị banner cảnh báo và khóa nút gửi. Backend chặn nộp đơn với HTTP 503.
- **Chức năng 9 (Phiên bản hệ thống & Audit Changelog):** 4 thẻ Specification hệ thống, Timeline nhật ký kiểm toán có lọc theo loại thay đổi, modal xem Before/After Diff so sánh trạng thái trước và sau, hỗ trợ xuất file Audit JSON.

## 8. Giai đoạn 7 (Phase 7): Kiểm Thử Tổng Thể (E2E Audit) & Hoàn Tất Definition of Done
- Rà soát toàn bộ 9 chức năng trên `web_admin` và `web_client`, kiểm tra chéo 6 luồng nghiệp vụ cốt lõi.
- Xác nhận Definition of Done: 64/64 Unit tests pass trong 193ms, 0 lỗi TypeScript/ESLint/Linter, thời gian build Vite 294ms (client) & 324ms (admin).

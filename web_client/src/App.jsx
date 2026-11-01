import { useEffect, useState } from "react";
import { api, initializeCsrf } from "./api.js";
import ToastCenter from "./components/ToastCenter.jsx";
import { PageControls } from "./components/ux.jsx";
import { canNavigate } from "./rolePolicy.js";
import RoleTasks from "./components/RoleTasks.jsx";
import AuditorWorkspace from "./components/AuditorWorkspace.jsx";
import { date, errorText, roles, statuses, types, typeLevels } from "./domain.js";
import {
  ActionForm,
  Badge,
  ResourceState,
  useResource,
} from "./components/ui.jsx";
import RequestEditor from "./components/RequestEditor.jsx";
import RequestDetail from "./components/RequestDetail.jsx";
import IdentityAdmin from "./components/IdentityAdmin.jsx";
import OrgChart from "./components/OrgChart.jsx";
import ApiAdministration from "./components/ApiAdministration.jsx";
import PlanCatalog from "./components/PlanCatalog.jsx";
import WorkflowDiagrams from "./components/WorkflowDiagrams.jsx";
import {
  AdminEvents,
  Notifications,
  Operations,
  Policy,
  Profile,
} from "./components/Admin.jsx";
function getRealtimeGreeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Chào buổi sáng!";
  if (hour >= 12 && hour < 18) return "Chào buổi chiều!";
  return "Chào buổi tối!";
}

function Login({ onLogin, portal = "client" }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [greeting, setGreeting] = useState(getRealtimeGreeting);

  useEffect(() => {
    const timer = setInterval(() => setGreeting(getRealtimeGreeting()), 60000);
    return () => clearInterval(timer);
  }, []);

  async function submit(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      await initializeCsrf();
      const result = await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      await onLogin(result.user);
    } catch (err) {
      if (err?.code === "INVALID_CREDENTIALS" || err?.message?.includes("INVALID_CREDENTIALS") || String(err?.code).includes("CREDENTIALS") || err?.status === 401) {
        setError("Thông tin đăng nhập không hợp lệ.");
      } else {
        setError(errorText(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="auth-shell auth-split-layout">
      <div className="auth-split-card">
      {/* Left Pane: Branding / Hero matching design */}
      <section className="auth-hero-pane" aria-label="Giới thiệu hệ thống">
        <div className="auth-hero-arcs-wrap" aria-hidden="true">
          <svg className="auth-hero-arcs" viewBox="0 0 500 500">
            <circle cx="40" cy="460" r="180" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
            <circle cx="40" cy="460" r="290" fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="1.5" />
            <circle cx="40" cy="460" r="400" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="1.5" />
            <circle cx="40" cy="460" r="520" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1.5" />
          </svg>
        </div>

        <div className="auth-hero-content">
          <div className="auth-hero-brand">
            <img src="/logo_white.png" alt="EAS Logo" className="auth-hero-logo-img" />
          </div>
          <h1 className="auth-hero-title">
            {portal === "admin" ? "Enterprise Admin" : "Enterprise Approval"}
          </h1>
          <p className="auth-hero-subtitle">
            {portal === "admin"
              ? "Cổng quản trị hệ thống và kiểm soát bảo mật"
              : "Hệ thống phê duyệt và quản lý quy trình doanh nghiệp"}
          </p>
          <button
            type="button"
            className="auth-hero-btn"
            onClick={() => setShowInfoModal(true)}
          >
            <span>Tìm hiểu thêm</span>
          </button>
        </div>
      </section>

      {/* Right Pane: Login Form matching design */}
      <section className="auth-form-pane" aria-label="Màn hình đăng nhập">
        <div className="auth-card-clean">
          <div className="auth-header">
            <div className="auth-form-brand">
              <img src="/logo.png" alt="EAS Logo" className="auth-form-logo-img" />
            </div>
            <h1 className="auth-greeting">
              {greeting}
              <span className="sr-only"> - {portal === "admin" ? "Đăng nhập Quản trị hệ thống" : "Đăng nhập EAS Portal"}</span>
            </h1>
          </div>

          <form onSubmit={submit} noValidate>
            <fieldset disabled={busy} className="auth-fieldset">
              {error && (
                <div role="alert" className="auth-error-banner">
                  {error}
                </div>
              )}

              <div className="auth-field-group">
                <label htmlFor="login-username" className="sr-only">
                  Tên đăng nhập hoặc Email
                </label>
                <div className="auth-input-wrapper">
                  <span className="auth-field-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="2" y="4" width="20" height="16" rx="2" />
                      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L1 7" />
                    </svg>
                  </span>
                  <input
                    id="login-username"
                    name="username"
                    type="text"
                    placeholder="Email Address"
                    autoComplete="username"
                    required
                    className="auth-pill-input"
                  />
                </div>
              </div>

              <div className="auth-field-group">
                <label htmlFor="login-password" className="sr-only">
                  Mật khẩu
                </label>
                <div className="auth-input-wrapper">
                  <span className="auth-field-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                  </span>
                  <input
                    id="login-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Mật khẩu"
                    autoComplete="current-password"
                    required
                    className="auth-pill-input auth-password-input"
                  />
                  <button
                    type="button"
                    className="auth-password-toggle"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? "Ẩn ký tự" : "Hiện ký tự"}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="auth-btn-primary"
                aria-label="Đăng nhập"
              >
                {busy ? "Đang xác thực…" : "Login"}
              </button>

              <button
                type="button"
                className="auth-forgot-link"
                onClick={() => setShowForgotModal(true)}
              >
                Forgot Password
              </button>
            </fieldset>
          </form>
        </div>
      </section>
      </div>

      {/* Modals */}
      {showInfoModal && (
        <div className="auth-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="info-modal-title">
          <div className="auth-modal-card">
            <div className="auth-modal-header">
              <h3 id="info-modal-title">{portal === "admin" ? "Enterprise Admin Portal" : "Enterprise Approval System"}</h3>
              <button type="button" className="auth-modal-close" onClick={() => setShowInfoModal(false)} aria-label="Đóng">✕</button>
            </div>
            <div className="auth-modal-body">
              <p><strong>EAS (Enterprise Approval System)</strong> là nền tảng quản trị và phê duyệt quy trình điện tử doanh nghiệp:</p>
              <ul>
                <li><strong>ISO 9001 & CMMI:</strong> Số hóa toàn diện quy trình đề xuất, luồng phê duyệt đa cấp và quản lý tài sản, nhân sự.</li>
                <li><strong>ISO/IEC 27001 & SOC 2:</strong> Phân quyền RBAC nghiêm ngặt, cơ chế chống vượt quyền (Separation of Duties), kiểm toán bất biến (Audit Trail).</li>
                <li><strong>AI Service:</strong> Tự động phân tích rủi ro, kiểm tra tuân thủ chính sách và tóm tắt nội dung tức thì.</li>
              </ul>
            </div>
            <div className="auth-modal-footer">
              <button type="button" className="auth-btn-primary auth-modal-btn" onClick={() => setShowInfoModal(false)}>Đã hiểu</button>
            </div>
          </div>
        </div>
      )}

      {showForgotModal && (
        <div className="auth-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="forgot-modal-title">
          <div className="auth-modal-card">
            <div className="auth-modal-header">
              <h3 id="forgot-modal-title">Cấp lại mật khẩu</h3>
              <button type="button" className="auth-modal-close" onClick={() => setShowForgotModal(false)} aria-label="Đóng">✕</button>
            </div>
            <div className="auth-modal-body">
              <p>Để đảm bảo an toàn thông tin theo tiêu chuẩn <strong>ISO/IEC 27001</strong>, hệ thống không cấp phát lại mật khẩu qua email tự động.</p>
              <p>Vui lòng liên hệ <strong>Bộ phận Quản trị Vận hành (IT Ops / Security Desk)</strong> để được hỗ trợ xác minh danh tính và cấp lại mật khẩu:</p>
              <div className="auth-support-box">
                <p><strong>Hotline:</strong> Máy lẻ 108 (Phòng CNTT)</p>
                <p><strong>Email:</strong> sec-ops@tantrieu.local</p>
                <p><strong>Giờ làm việc:</strong> 08:00 - 18:00 (Thứ 2 - Thứ 6)</p>
              </div>
            </div>
            <div className="auth-modal-footer">
              <button type="button" className="auth-btn-primary auth-modal-btn" onClick={() => setShowForgotModal(false)}>Đóng</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

const menu = [
  ["home", "Tổng quan", "◫"],
  ["mine", "Yêu cầu của tôi", "▤", "REQUESTER"],
  ["approval", "Chờ tôi phê duyệt", "✓", "APPROVER"],
  ["execution", "Công việc thực hiện", "▣", "EXECUTOR"],
  ["acceptance", "Chờ nghiệm thu", "◇", "ACCEPTOR"],
  ["history", "Hồ sơ liên quan", "◷"],
  ["flow-diagrams", "Sơ đồ luồng", "◇"],
  ["policy", "Cấu hình quy trình", "⚙", "POLICY_ADMIN"],
  ["plan-catalog", "Danh mục loại yêu cầu", "▦"],
  ["ops", "Theo dõi vận hành", "⇄", "OPS_ADMIN"],
  ["identity", "Danh tính & phân quyền", "◎", "OPS_ADMIN"],
  ["org-chart", "Sơ đồ tổ chức", "🏛"],
  ["api-admin", "Quản lý API", "⌘", "OPS_ADMIN"],
  ["audit", "Kiểm toán hồ sơ", "⌕", "AUDITOR"],
  ["events", "Nhật ký quản trị", "≡", "AUDITOR"],
  ["notifications", "Thông báo", "○"],
  ["profile", "Tài khoản cá nhân", "◎"],
];
function RequestList({ page, user, onOpen, onNew, revision, canCreate = true }) {
  const [status, setStatus] = useState(""),
    [type, setType] = useState(""),
    [offset, setOffset] = useState(0),
    [limit, setLimit] = useState(20),
    [query, setQuery] = useState(""),
    [debouncedQuery, setDebouncedQuery] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedQuery(query.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [query]);
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (debouncedQuery) params.set("q", debouncedQuery);
  if (["mine", "approval", "execution", "acceptance"].includes(page))
    params.set("tab", page);
  if (status) params.set("status", status);
  if (type) params.set("type_code", type);
  if (from) params.set("created_from", from + "T00:00:00+07:00");
  if (to) params.set("created_to", to + "T23:59:59.999999+07:00");
  const availableTypes = useResource("/api/v1/request-types");
  const r = useResource(
    `/api/v1/${page === "ops" ? "ops/requests" : "requests"}?${params}&_revision=${revision}`,
  );
  const items = r.data?.items || [],
    filtered = items;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CỔNG DỊCH VỤ EAS / QUẢN LÝ HỒ SƠ</p>
          <h1>{menu.find((m) => m[0] === page)?.[1]}</h1>
          <p className="muted">
            Theo dõi tiến độ, xử lý công việc và tra cứu lịch sử.
          </p>
        </div>
        {canCreate && user.roles.includes("REQUESTER") && (
          <button type="button" onClick={onNew}>+ Tạo yêu cầu mới</button>
        )}
      </div>
      <section className="request-summary-strip" aria-label="Thống kê hồ sơ trên trang">
        {[
          ["Tất cả", "", "◫"],
          ["Cần bổ sung", "NEEDS_INFO", "!"],
          ["Chờ duyệt", "PENDING_APPROVAL", "⌛"],
          ["Đang thực hiện", "IN_PROGRESS", "⇄"],
          ["Hoàn thành", "COMPLETED", "✓"],
          ["Bản nháp", "DRAFT", "▤"],
        ].map(([label, code, icon]) => (
          <button key={label} type="button"
            className={`request-mini-stat ${status === code ? "current" : ""}`}
            onClick={() => {setStatus(code);setOffset(0);}}
            aria-pressed={status === code}>
            <span className="mini-stat-icon" aria-hidden="true">{icon}</span>
            <span className="mini-stat-label">{label}</span>
            <strong>{code ? items.filter((item) => item.status === code).length : items.length}</strong>
            <small>hồ sơ</small>
          </button>
        ))}
      </section>
      <section className="panel filter-panel">
        <div className="filters">
          <label>
            Tìm kiếm yêu cầu
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm theo mã đơn, tiêu đề, người gửi..."
            />
          </label>
          <label>
            Loại yêu cầu
            <select
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Tất cả loại</option>
              {(availableTypes.data?.items || []).map(({code, name}) => (
                <option key={code} value={code}>
                  {name || types[code] || code}
                </option>
              ))}
            </select>
          </label>
          <label>
            Trạng thái
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Tất cả trạng thái</option>
              {Object.entries(statuses).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {page !== "ops" && (
            <>
              <label>
                Từ ngày
                <input
                  type="date"
                  value={from}
                  onChange={(e) => {
                    setFrom(e.target.value);
                    setOffset(0);
                  }}
                />
              </label>
              <label>
                Đến ngày
                <input
                  type="date"
                  value={to}
                  min={from}
                  onChange={(e) => {
                    setTo(e.target.value);
                    setOffset(0);
                  }}
                />
              </label>
            </>
          )}
        </div>
        <div className="section-head">
          <small className="muted">
            Dữ liệu hiển thị theo phạm vi được cấp quyền
          </small>
          <div className="actions">
            <button
              className="link"
              onClick={() => {
                setStatus("");
                setType("");
                setOffset(0);
                setQuery("");
                setFrom("");
                setTo("");
              }}
            >
              Đặt lại bộ lọc
            </button>
            <button type="button" className="secondary" onClick={r.reload}>
              Làm mới
            </button>
          </div>
        </div>
      </section>
      <ResourceState resource={r}>
        {page === "ops" ? (
          <Operations items={filtered} onRefresh={r.reload} />
        ) : (
          <section className="panel table-panel" id="request-results">
            <div className="table-wrap">
              <table className="responsive-records">
                <thead>
                  <tr>
                    <th>Mã & Tiêu đề</th>
                    <th>Nghiệp vụ</th>
                    <th>Người gửi & Phòng ban</th>
                    <th>Trạng thái & Cập nhật</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((i) => (
                    <tr key={i.id}>
                      <td data-label="Mã & Tiêu đề" className="request-title-cell">
                        <span className="request-code">{i.code}</span>
                        <strong className="request-title">{i.title || i.code}</strong>
                      </td>
                      <td data-label="Nghiệp vụ">
                        <div className="type-badge-inline">
                          <span className="type-icon">
                            {i.type_code === "LEAVE"
                              ? "◷"
                              : i.type_code === "ACCESS"
                                ? "◇"
                                : "▣"}
                          </span>
                          <span>{types[i.type_code] || i.type_code}</span>
                        </div>
                        <small className="muted" style={{display: "block"}}>
                          Rủi ro {i.risk_weight || typeLevels[i.type_code]?.risk_weight || 3}/5 · Duyệt {i.approval_level || typeLevels[i.type_code]?.approval_level || 1} cấp
                        </small>
                      </td>
                      <td data-label="Người gửi & Phòng ban" className="request-sender-cell">
                        <strong className="sender-name">{i.requester_name || "—"}</strong>
                        <span className="sender-dept muted">{i.department_name || "—"}</span>
                      </td>
                      <td data-label="Trạng thái & Cập nhật">
                        <Badge value={i.status} />
                        <small className="muted" style={{display: "block", marginTop: "4px"}}>{date(i.updated_at)}</small>
                      </td>
                      <td data-label="Thao tác">
                        <button type="button" className="link" onClick={() => onOpen(i.id)}>
                          Xem chi tiết →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!filtered.length && (
              <div className="empty">
                <h3>Không có hồ sơ phù hợp</h3>
                <p>Thử thay đổi bộ lọc hoặc quay lại sau.</p>
              </div>
            )}
          </section>
        )}
        <PageControls offset={offset} limit={limit} nextOffset={r.data?.next_offset}
          count={filtered.length} title="hồ sơ" targetId="request-results"
          onPage={setOffset} onLimit={setLimit} />
      </ResourceState>
    </>
  );
}
function Overview({ navigate, onOpen, user }) {
  const [period] = useState(() => {
    const end = new Date();
    return new URLSearchParams({
      created_from: new Date(end.getTime() - 30 * 86400000).toISOString(),
      created_to: end.toISOString(),
    }).toString();
  });
  const r = useResource("/api/v1/reports/requests?" + period);
  const recent = useResource("/api/v1/requests?limit=5&offset=0");
  const report = r.data?.report;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">KHÔNG GIAN LÀM VIỆC</p>
          <h1>Tổng quan xử lý yêu cầu</h1>
          <p className="muted">
            Thống kê theo phạm vi dữ liệu bạn được phép xem.
          </p>
        </div>
      </div>
      <ResourceState resource={r}>
        {report && (
          <>
            <p className="muted">
              Kỳ báo cáo: {date(report.period?.from)} —{" "}
              {date(report.period?.to)}
            </p>
            <div className="stats-grid">
              {[
                ["Đã gửi", report.submitted],
                ["Đã phê duyệt", report.approved],
                ["Đã hoàn thành", report.completed],
                [
                  "Tỷ lệ hoàn thành",
                  report.completed_rate == null
                    ? "—"
                    : Math.round(report.completed_rate * 100) + "%",
                ],
              ].map(([label, value]) => (
                <article className="stat" key={label}>
                  <span>{label}</span>
                  <strong>{value ?? 0}</strong>
                  <small>Trong kỳ báo cáo</small>
                </article>
              ))}
            </div>
            <section className="panel">
              <h2>Phân bố trạng thái</h2>
              <p className="muted">
                Báo cáo không tính bản nháp; xem bản nháp trong Yêu cầu của tôi.
              </p>
              <div className="status-grid">
                {Object.entries(statuses).map(([key, label]) => (
                  <div key={key}>
                    <Badge value={key} />
                    <strong aria-label={label}>
                      {key === "DRAFT" ? "—" : report.by_status?.[key] || 0}
                    </strong>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </ResourceState>
      <RoleTasks user={user} navigate={navigate} />
      <div className="dashboard-board">
        <section className="panel" aria-label="Hồ sơ cập nhật gần đây">
          <div className="section-head">
            <div><h2>Hồ sơ mới cập nhật</h2><p className="muted">Danh sách thực tế trong phạm vi bạn được phép xem.</p></div>
            <button type="button" className="secondary" onClick={() => navigate("history")}>Xem danh sách →</button>
          </div>
          <ResourceState resource={recent}>
            {recent.data?.items?.length ? (
              <ul className="dashboard-list">
                {recent.data.items.map((item) => <li key={item.id}>
                  <div>
                    <strong>{item.code} {item.title ? `· ${item.title}` : `· ${types[item.type_code] || item.type_code}`}</strong>
                    <small>{item.requester_name ? `${item.requester_name} (${item.department_name || "—"}) · ` : ""}{date(item.updated_at)}</small>
                    <Badge value={item.status}/>
                  </div>
                  <button type="button" className="link" onClick={() => onOpen(item.id)}>Xem chi tiết →</button>
                </li>)}
              </ul>
            ) : <p className="muted">Chưa có hồ sơ trong phạm vi quyền xem.</p>}
          </ResourceState>
        </section>
        <aside className="panel">
          <h2>Truy cập nhanh</h2>
          <p className="muted">Đi thẳng đến khu vực làm việc, hệ thống tự cuộn về phần thao tác.</p>
          <div className="dashboard-quick">
            <button type="button" onClick={() => navigate("mine")}>▤ Yêu cầu của tôi →</button>
            <button type="button" className="secondary" onClick={() => navigate("notifications")}>◉ Trung tâm thông báo →</button>
            <button type="button" className="secondary" onClick={() => navigate("history")}>◷ Tra cứu hồ sơ →</button>
          </div>
        </aside>
      </div>
      <section className="welcome-banner">
        <div>
          <h2>Công việc rõ ràng. Tiến độ minh bạch.</h2>
          <p>Mỗi quyết định được lưu lại xuyên suốt vòng đời yêu cầu.</p>
        </div>
        <button type="button" onClick={() => navigate("history")}>
          Xem hồ sơ liên quan →
        </button>
      </section>
    </>
  );
}
function renderWorkspaceContent({
  editor,
  selected,
  page,
  user,
  revision,
  navigate,
  setSelected,
  setEditor,
  setRevision,
  portal,
}) {
  if (editor) {
    return (
      <RequestEditor
        key={editor.id || "new"}
        initial={editor.id ? editor : undefined}
        onCancel={() => setEditor(null)}
        onDone={(id) => {
          setEditor(null);
          setSelected(id);
          setRevision((v) => v + 1);
        }}
      />
    );
  }
  if (selected) {
    return (
      <RequestDetail
        initialTab={page === "audit" ? "audit" : "info"}
        key={selected}
        id={selected}
        user={user}
        onBack={() => setSelected(null)}
        onEdit={setEditor}
        onChanged={() => setRevision((v) => v + 1)}
      />
    );
  }
  switch (page) {
    case "home":
      return <Overview navigate={navigate} onOpen={setSelected} user={user} />;
    case "audit":
      return <AuditorWorkspace onOpen={(id) => setSelected(id)} />;
    case "identity":
      return <IdentityAdmin onNavigateOrgChart={() => navigate("org-chart")} />;
    case "org-chart":
      return <OrgChart navigate={navigate} />;
    case "api-admin":
      return <ApiAdministration />;
    case "plan-catalog":
      return <PlanCatalog />;
    case "flow-diagrams":
      return <><div className="page-heading"><div><p className="eyebrow">EAS / QUY TRÌNH</p><h1>Sơ đồ luồng</h1><p className="muted">Tra cứu các sơ đồ xử lý và vòng đời yêu cầu.</p></div></div><WorkflowDiagrams /></>;
    case "policy":
      return (
        <Policy
          canManageAccess={user.roles.includes("OPS_ADMIN")}
          onManageAccess={() => navigate("identity")}
        />
      );
    case "notifications":
      return <Notifications onOpen={setSelected} />;
    case "profile":
      return <Profile user={user} />;
    case "events":
      return <AdminEvents />;
    default:
      return (
        <RequestList
          key={page}
          page={page}
          user={user}
          revision={revision}
          canCreate={portal !== "admin"}
          onOpen={setSelected}
          onNew={() => setEditor({})}
        />
      );
  }
}

const ADMIN_ROLES = ["OPS_ADMIN", "POLICY_ADMIN", "AUDITOR"];
const ADMIN_PAGES = new Set(["flow-diagrams", "home", "policy", "plan-catalog", "ops", "identity", "org-chart", "api-admin", "audit", "events", "notifications", "profile"]);
const CLIENT_PAGES = new Set(["flow-diagrams", "home", "mine", "approval", "execution", "acceptance", "history", "org-chart", "notifications", "profile"]);

function AdminOverview({ navigate, user }) {
  return (
    <section className="admin-home">
      <div className="page-heading"><div><p className="eyebrow">EAS CONTROL CENTER</p><h1>Quản trị hệ thống</h1><p className="muted">Điều hành phân quyền, quy trình, tích hợp và kiểm toán trên cổng riêng.</p></div></div>
      <div className="admin-tiles">
        {[["identity", "Danh tính & phân quyền", "Quản lý tài khoản và phạm vi truy cập", "◎"], ["org-chart", "Sơ đồ tổ chức", "Cơ cấu Ban Giám Đốc và 7 phòng ban", "🏛"], ["policy", "Cấu hình quy trình", "Quản lý và công bố quy chế", "⚙"], ["ops", "Vận hành hệ thống", "Theo dõi tiến trình xử lý hồ sơ", "◷"], ["events", "Nhật ký quản trị", "Tra cứu sự kiện và lịch sử thay đổi", "≡"]].filter(([key]) => canNavigate(user.roles, key, user.capabilities)).map(([key, label, detail, icon]) => (
          <button key={key} type="button" className="panel admin-tile" onClick={() => navigate(key)}><span>{icon}</span><strong>{label}</strong><small>{detail}</small></button>
        ))}
      </div>
    </section>
  );
}
function Workspace({ user, onLogout, portal = "client" }) {
  const [page, setPage] = useState("home"),
    [selected, setSelected] = useState(null),
    [editor, setEditor] = useState(null),
    [revision, setRevision] = useState(0),
    [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const main = document.getElementById("main");
      main?.scrollIntoView({ behavior: "smooth", block: "start" });
      const heading = main?.querySelector("h1");
      if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
    });
    return () => cancelAnimationFrame(frame);
  }, [page, selected, editor]);
  function navigate(next) {
    if (next !== "org-chart" && !canNavigate(user.roles, next, user.capabilities)) return;
    const allowedPages = portal === "admin" ? ADMIN_PAGES : (portal === "client" ? CLIENT_PAGES : new Set(menu.map((x) => x[0])));
    if (!allowedPages.has(next)) return;
    setPage(next);
    setSelected(null);
    setEditor(null);
    setMenuOpen(false);
  }
  return (
    <div className="app-shell">
      {menuOpen && <button type="button" className="nav-backdrop" aria-label="Đóng menu" onClick={() => setMenuOpen(false)} />}
      <aside className={"sidebar " + (menuOpen ? "open" : "")}>
        <a className="brand" href="#main" onClick={(event) => { event.preventDefault(); navigate("home"); }}>
          <img src="/logo.png" alt="EAS Logo" className="brand-logo-img" />
          <span>
            {portal === "admin" ? "EAS Admin" : "EAS Portal"}<small>{portal === "admin" ? "SYSTEM CONTROL" : "ENTERPRISE APPROVAL"}</small>
          </span>
        </a>
        {portal !== "admin" && user.roles.includes("REQUESTER") && (
          <button
            className="create-button"
            onClick={() => {
              setSelected(null);
              setEditor({});
              setMenuOpen(false);
            }}
          >
            + Tạo yêu cầu mới
          </button>
        )}
        <nav aria-label="Điều hướng chính">
          {[
            ["KHÔNG GIAN LÀM VIỆC", ["home", "mine", "history", "flow-diagrams", "org-chart"]],
            ["PHÊ DUYỆT & THỰC HIỆN", ["approval", "execution", "acceptance"]],
            ["QUẢN TRỊ HỆ THỐNG", ["policy", "plan-catalog", "ops", "identity", "org-chart", "api-admin", "audit", "events"]],
            ["TÀI KHOẢN & TIỆN ÍCH", ["notifications", "profile"]],
          ].map(([group, keys]) => {
            const allowedPages = portal === "admin" ? ADMIN_PAGES : (portal === "client" ? CLIENT_PAGES : new Set(menu.map((x) => x[0])));
            const visible = menu.filter((m) => keys.includes(m[0]) && allowedPages.has(m[0]) && (m[0] === "org-chart" || canNavigate(user.roles, m[0], user.capabilities)));
            return visible.length ? (
              <div key={group} className="nav-group">
                <p className="nav-caption">{group}</p>
                {visible.map(([key, title, icon]) => (
                  <button key={key}
                    className={page === key && !selected && !editor ? "nav-item active" : "nav-item"}
                    aria-current={page === key && !selected && !editor ? "page" : undefined}
                    onClick={() => navigate(key)}>
                    <span aria-hidden="true">{icon}</span>{title}
                  </button>
                ))}
              </div>
            ) : null;
          })}
        </nav>
        <div className="sidebar-footer">
          <strong>Quy trình có kiểm soát</strong>
          <small>Phê duyệt · Thực hiện · Nghiệm thu</small>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="secondary menu-toggle"
            aria-label="Mở điều hướng"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            ☰
          </button>
          <span className="muted">
            Cổng dịch vụ / {menu.find((m) => m[0] === page)?.[1]}
          </span>
          <div className="topbar-right">
            <button
              className="secondary"
              onClick={() => navigate("notifications")}
            >
              Thông báo
            </button>
            <button
              className="avatar"
              onClick={() => navigate("profile")}
              aria-label="Hồ sơ cá nhân"
            >
              {user.display_name?.slice(0, 1) || "U"}
            </button>
            <div>
              <strong>{user.display_name}</strong>
              <small>{user.roles.map((r) => roles[r] || r).join(" · ")}</small>
            </div>
            <ActionForm onSubmit={onLogout} submitLabel="Đăng xuất" />
          </div>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          {portal === "admin" && page === "home" ? <AdminOverview navigate={navigate} user={user} /> : renderWorkspaceContent({
            editor,
            selected,
            page,
            user,
            revision,
            navigate,
            setSelected,
            setEditor,
            setRevision,
            portal,
          })}
        </main>
        <footer className="page-footer">
          EAS · {portal === "admin" ? "Trung tâm quản trị hệ thống" : "Hệ thống phê duyệt yêu cầu doanh nghiệp"}
        </footer>
      </div>
    </div>
  );
}
let _bootstrapSessionPromise = null;

function fetchInitialSession() {
  if (!_bootstrapSessionPromise) {
    _bootstrapSessionPromise = initializeCsrf()
      .then(() => api("/api/v1/auth/me", { headers: { "X-Auth-Optional": "1" } }))
      .finally(() => {
        setTimeout(() => {
          _bootstrapSessionPromise = null;
        }, 50);
      });
  }
  return _bootstrapSessionPromise;
}

export default function App({ portal = (import.meta.env.VITE_EAS_PORTAL || "unified") }) {
  const [user, setUser] = useState(undefined),
    [error, setError] = useState("");
  async function load(loginUser) {
    if (loginUser?.must_change_password) {
      setUser({ ...loginUser, roles: [] });
      return;
    }
    try {
      setUser((await api("/api/v1/auth/me")).user);
    } catch (e) {
      if (e.message === "PASSWORD_CHANGE_REQUIRED")
        setUser({ roles: [], must_change_password: true });
      else if (e.status === 401 || e.status === 403) setUser(null);
      else setError(errorText(e));
    }
  }
  useEffect(() => {
    let active = true;
    fetchInitialSession()
      .then((r) => {
        if (active) setUser(r?.user || null);
      })
      .catch((e) => {
        if (active) {
          if (e.message === "PASSWORD_CHANGE_REQUIRED")
            setUser({ roles: [], must_change_password: true });
          else if (e.status === 401 || e.status === 403) setUser(null);
          else setError(errorText(e));
        }
      });
    return () => {
      active = false;
    };
  }, []);
  async function logout() {
    await api("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setUser(null);
  }
  const screen = (() => {
  if (error)
    return (
      <main id="main" className="auth-shell">
        <section className="panel">
          <h1>Không thể kết nối hệ thống</h1>
          <p className="error" role="alert">
            {error}
          </p>
          <button type="button" onClick={async () => {
            setError("");
            try {
              await initializeCsrf();
              const result = await api("/api/v1/auth/me", { headers: { "X-Auth-Optional": "1" } });
              setUser(result?.user || null);
            } catch (e) { setError(errorText(e)); }
          }}>Kết nối lại</button>
        </section>
      </main>
    );
  if (user === undefined)
    return (
      <main id="main" className="empty" aria-live="polite">
        Đang khởi tạo EAS Portal…
      </main>
    );
  if (user?.must_change_password)
    return (
      <main id="main" className="content">
        <h1>Đổi mật khẩu để tiếp tục</h1>
        <p>Tài khoản đang sử dụng mật khẩu tạm.</p>
        <Profile user={user} onChanged={() => { void load(); }} />
        <ActionForm onSubmit={logout} submitLabel="Đăng xuất" />
      </main>
    );
  if (user && portal === "admin" && !user.roles?.some((role) => ADMIN_ROLES.includes(role))) {
    return <main className="auth-shell"><section className="panel"><h1>Không có quyền quản trị</h1><p>Tài khoản không được cấp quyền sử dụng trung tâm quản trị.</p><ActionForm onSubmit={logout} submitLabel="Đăng xuất" /></section></main>;
  }
  if (user && portal === "client" && user.roles?.every((role) => ADMIN_ROLES.includes(role))) {
    return <main className="auth-shell"><section className="panel"><h1>Tài khoản quản trị</h1><p>Tài khoản quản trị sử dụng cổng quản trị hệ thống riêng; không tạo hoặc xử lý yêu cầu trên cổng nhân viên.</p><a href={import.meta.env.VITE_ADMIN_PORTAL_URL || `${window.location.protocol}//${window.location.hostname}:${window.location.port === "8080" ? "8081" : "5174"}`}>Mở trung tâm quản trị</a><ActionForm onSubmit={logout} submitLabel="Đăng xuất" /></section></main>;
  }
  return user ? (
    <Workspace user={user} onLogout={logout} portal={portal} />
  ) : (
    <Login onLogin={load} portal={portal} />
  );
  })();
  return <><ToastCenter />{screen}</>;
}

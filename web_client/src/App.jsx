import { useEffect, useState } from "react";
import { api, initializeCsrf } from "./api.js";
import ToastCenter from "./components/ToastCenter.jsx";
import { PageControls } from "./components/ux.jsx";
import { canNavigate, canUsePortal } from "./rolePolicy.js";
import RoleTasks from "./components/RoleTasks.jsx";
import { date, errorText, statuses, types, typeLevels, getPrimaryRoleBadge } from "./domain.js";
import {
  ActionForm,
  Badge,
  ResourceState,
  useResource,
} from "./components/ui.jsx";
import RequestEditor from "./components/RequestEditor.jsx";
import RequestDetail from "./components/RequestDetail.jsx";
import WorkflowDiagrams from "./components/WorkflowDiagrams.jsx";
import {PersonalOverviewStats, PeriodChooser} from "./components/DashboardOverview.jsx";
import AiProcessGuide from "./components/AiProcessGuide.jsx";
import ClientDashboard from "./components/ClientDashboard.jsx";
import ClientRequests from "./components/ClientRequests.jsx";
import ClientOrgChart from "./components/ClientOrgChart.jsx";
import AssignedWorkDashboard from "./components/AssignedWorkDashboard.jsx";
import { Notifications, Profile } from "./components/Admin.jsx";
import AdminScreen, { AdminScreensContext } from "./components/AdminScreen.jsx";
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

  const [resetBusy, setResetBusy] = useState(false);
  const [resetError, setResetError] = useState("");
  const [resetSubmitted, setResetSubmitted] = useState(false);

  function closeForgotModal() {
    setShowForgotModal(false);
    setResetSubmitted(false);
    setResetError("");
  }

  async function submitReset(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    setResetBusy(true);
    setResetError("");
    try {
      await initializeCsrf();
      await api("/api/v1/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setResetSubmitted(true);
    } catch (err) {
      setResetError(errorText(err));
    } finally {
      setResetBusy(false);
    }
  }

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
                <label htmlFor="login-email" className="sr-only">
                  Email nhân viên
                </label>
                <div className="auth-input-wrapper">
                  <span className="auth-field-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="2" y="4" width="20" height="16" rx="2" />
                      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L1 7" />
                    </svg>
                  </span>
                  <input
                    id="login-email"
                    name="email"
                    type="email"
                    placeholder="Email nhân viên"
                    autoComplete="email"
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
                {busy ? "Đang xác thực…" : "Đăng nhập"}
              </button>

              <button
                type="button"
                className="auth-forgot-link"
                onClick={() => setShowForgotModal(true)}
              >
                Quên mật khẩu
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
              <p>Nền tảng giúp bạn tạo yêu cầu, theo dõi tiến độ và nhận thông báo khi có quyết định xử lý.</p>
              <ul><li>Quy trình rõ ràng từ tạo yêu cầu đến hoàn thành.</li><li>Phân công người xử lý, hiển thị hạn và lịch sử quyết định.</li><li>Trợ lý AI hỗ trợ tóm tắt và đánh giá rủi ro; người có thẩm quyền vẫn quyết định phê duyệt.</li></ul>
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
              <button type="button" className="auth-modal-close" onClick={closeForgotModal} aria-label="Đóng">✕</button>
            </div>
            {resetSubmitted ? (
              <>
                <div className="auth-modal-body">
                  <p role="status">Nếu tài khoản tồn tại, yêu cầu sẽ được xem xét theo quy trình quản trị. Quản trị viên phải xác minh danh tính trước khi phê duyệt; sau đó mật khẩu tạm thời sẽ được gửi đến email nhân viên.</p>
                </div>
                <div className="auth-modal-footer">
                  <button type="button" className="auth-btn-primary auth-modal-btn" onClick={closeForgotModal}>Đóng</button>
                </div>
              </>
            ) : (
              <form onSubmit={submitReset} noValidate>
                <fieldset disabled={resetBusy} className="auth-fieldset">
                  <div className="auth-modal-body">
                    <p>Nhập email nhân viên để gửi yêu cầu. Quản trị viên sẽ xác minh danh tính trước khi cấp mật khẩu tạm thời.</p>
                    <p>Không chia sẻ mật khẩu hoặc mã xác minh trong yêu cầu hỗ trợ.</p>
                    {resetError && <div role="alert" className="auth-error-banner">{resetError}</div>}
                    <label htmlFor="reset-email" className="sr-only">Email nhân viên</label>
                    <input id="reset-email" name="email" type="email" autoComplete="email" placeholder="Email nhân viên" required className="auth-pill-input" />
                  </div>
                  <div className="auth-modal-footer">
                    <button type="submit" className="auth-btn-primary auth-modal-btn">{resetBusy ? "Đang gửi…" : "Gửi yêu cầu đặt lại"}</button>
                  </div>
                </fieldset>
              </form>
            )}
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

  ["flow-diagrams", "Sơ đồ luồng", "◇"],
  ["ai-process", "Quy trình AI", "✧"],
  ["request-catalog", "Quản lý loại yêu cầu", "▦", "OPS_ADMIN"],
  ["users", "Quản lý người dùng", "♙", "OPS_ADMIN"],
  ["permissions", "Vai trò & phân quyền", "▦", "OPS_ADMIN"],
  ["policy", "Cấu hình quy trình", "⚙", "POLICY_ADMIN"],
  ["ai-policy", "Bộ luật quy định AI", "✧", "POLICY_ADMIN"],
  ["plan-catalog", "Danh mục loại yêu cầu", "▦"],
  ["ops", "Theo dõi vận hành", "⇄", "OPS_ADMIN"],
  ["identity", "Danh tính & phân quyền", "◎", "OPS_ADMIN"],
  ["org-chart", "Sơ đồ tổ chức", "🏛", "OPS_ADMIN"],
  ["org-client", "Sơ đồ tổ chức", "🏛"],
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
            <small>trên trang đang tải</small>
          </button>
        ))}
      </section>
      <section className="panel filter-panel">
        <div className="filters">
          <label>
            Tìm yêu cầu
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ví dụ: REQ-2026-001"
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
          {(
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
          <AdminScreen name="Operations" items={filtered} onRefresh={r.reload} />
        ) : (
          <section className="panel table-panel" id="request-results">
            <div className="table-wrap">
              <table className="responsive-records">
                <thead>
                  <tr>
                    <th>Mã yêu cầu</th>
                    <th>Nghiệp vụ</th>
                    <th>Trạng thái</th>
                    <th>Cập nhật</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((i) => (
                    <tr key={i.id}>
                      <td data-label="Mã yêu cầu" className="request-code">{i.code}</td>
                      <td data-label="Nghiệp vụ">
                        <span className="type-icon">
                          {i.type_code === "LEAVE"
                            ? "◷"
                            : i.type_code === "ACCESS"
                              ? "◇"
                              : "▣"}
                        </span>
                        {availableTypes.data?.items?.find(t => t.code === i.type_code)?.name || types[i.type_code] || "Loại yêu cầu"}
                        <small className="muted" style={{display: "block"}}>Mức rủi ro {i.risk_weight || typeLevels[i.type_code]?.risk_weight || 3}/5 · {i.approval_level || typeLevels[i.type_code]?.approval_level || 1} cấp duyệt</small>
                      </td>
                      <td data-label="Trạng thái">
                        <Badge value={i.status} />
                      </td>
                      <td data-label="Cập nhật">{date(i.updated_at)}</td>
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
  const today = () => new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Ho_Chi_Minh"});
  const [from, setFrom] = useState(() => new Date(Date.now()-29*86400000).toLocaleDateString("en-CA",{timeZone:"Asia/Ho_Chi_Minh"}));
  const [to, setTo] = useState(today);
  const valid = Boolean(from && to && from <= to && (Date.parse(to)-Date.parse(from)) <= 366*86400000);
  const params = new URLSearchParams({created_from:`${from}T00:00:00+07:00`, created_to:`${to}T23:59:59+07:00`});
  const r = useResource(`/api/v1/reports/requests?${params}`);
  const recent = useResource("/api/v1/requests?limit=5&offset=0");
  const report = r.data?.report;
  return <>
    <div className="page-heading"><div><p className="eyebrow">KHÔNG GIAN LÀM VIỆC</p><h1>Tổng quan yêu cầu</h1>
      <p className="muted">Nắm nhanh tiến độ, trạng thái hồ sơ và những loại yêu cầu phổ biến trong phạm vi bạn được phép xem.</p></div></div>
    <PeriodChooser start={from} end={to} setStart={setFrom} setEnd={setTo} reload={r.reload}/>
    {!valid && <p className="error" role="alert">Vui lòng chọn khoảng thời gian hợp lệ, không quá 12 tháng.</p>}
    {valid && <ResourceState resource={r}>{report && <PersonalOverviewStats report={report}/>}</ResourceState>}
    <RoleTasks user={user} navigate={navigate}/>
    <div className="dashboard-board"><section className="panel" aria-label="Hồ sơ cập nhật gần đây">
      <div className="section-head"><div><h2>Hồ sơ mới cập nhật</h2><p className="muted">Thông tin bạn được phép xem.</p></div><button type="button" className="secondary" onClick={()=>navigate("history")}>Xem danh sách →</button></div>
      <ResourceState resource={recent}>{recent.data?.items?.length ? <ul className="dashboard-list">{recent.data.items.map(item=><li key={item.id}>
        <div><strong>{item.code}</strong><small>{types[item.type_code] || item.type_name || "Yêu cầu"} · {date(item.updated_at)}</small><Badge value={item.status}/></div>
        <button type="button" className="link" onClick={()=>onOpen(item.id)}>Xem chi tiết →</button>
      </li>)}</ul> : <p className="muted">Chưa có hồ sơ trong phạm vi quyền xem.</p>}</ResourceState>
    </section><aside className="panel"><h2>Không gian làm việc</h2><div className="dashboard-quick">
      <button type="button" onClick={()=>navigate("mine")}>Yêu cầu của tôi →</button>
      <button className="secondary" type="button" onClick={()=>navigate("notifications")}>Thông báo →</button>
      <button className="secondary" type="button" onClick={()=>navigate("history")}>Tra cứu hồ sơ →</button>
    </div></aside></div>
  </>;
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
  searchText = "",
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
      return portal === "client" ? (user.roles.includes("REQUESTER") ? <ClientDashboard navigate={navigate} onOpen={setSelected} user={user} /> : <AssignedWorkDashboard navigate={navigate} onOpen={setSelected} user={user}/>) : <Overview navigate={navigate} onOpen={setSelected} user={user} />;
    case "org-client":
      return <ClientOrgChart user={user} />;
    case "mine":
    case "approval":
    case "execution":
    case "acceptance":
      return portal === "client" ? <ClientRequests key={page} initialStage={page === "mine" ? "mine" : page} initialQuery={searchText} user={user} revision={revision} onOpen={setSelected} onNew={()=>setEditor({})} /> : <RequestList key={page} page={page} user={user} revision={revision} onOpen={setSelected} onNew={()=>setEditor({})} />;
    case "audit":
      return <AdminScreen name="AuditorWorkspace" onOpen={(id) => setSelected(id)} />;
    case "identity":
    case "users":
      return <AdminScreen name="IdentityAdmin" key="users" initialKind="users" onNavigateOrgChart={() => navigate("org-chart")} />;
    case "permissions":
      return <AdminScreen name="IdentityAdmin" key="memberships" initialKind="memberships" onNavigateOrgChart={() => navigate("org-chart")} />;
    case "request-catalog":
      return <AdminScreen name="IdentityAdmin" key="request-types" initialKind="request-types" />;
    case "org-chart":
      return <AdminScreen name="OrgChart" navigate={navigate} portal={portal} user={user} />;
    case "api-admin":
      return <AdminScreen name="ApiAdministration" />;
    case "plan-catalog":
      return <AdminScreen name="PlanCatalog" />;
    case "ai-process":
      return <AiProcessGuide user={user} onOpen={setSelected} navigate={navigate} />;
    case "flow-diagrams":
      return <><div className="page-heading"><div><p className="eyebrow">EAS / QUY TRÌNH</p><h1>Sơ đồ luồng</h1><p className="muted">Tra cứu các sơ đồ xử lý và vòng đời yêu cầu.</p></div></div><WorkflowDiagrams /></>;
    case "policy":
      return (
        <AdminScreen
          name="Policy"
          canManageAccess={user.roles.includes("OPS_ADMIN")}
          onManageAccess={() => navigate("identity")}
        />
      );
    case "ai-policy":
      return <AdminScreen name="AiPolicyAdmin" />;
    case "notifications":
      return <Notifications onOpen={setSelected} />;
    case "profile":
      return <Profile user={user} />;
    case "events":
      return <AdminScreen name="AdminEvents" />;
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

const ADMIN_PAGES = new Set(["flow-diagrams", "ai-process", "home", "policy", "ai-policy", "plan-catalog", "request-catalog", "ops", "identity", "users", "permissions", "org-chart", "api-admin", "audit", "events", "notifications"]);
const CLIENT_PAGES = new Set(["flow-diagrams", "ai-process", "home", "mine", "approval", "execution", "acceptance", "org-client", "notifications", "profile"]);

function AdminOverview({ navigate, user }) {
  const usersMeta = useResource("/api/v1/meta/org-chart");
  const readyMeta = useResource("/health/ready");
  const totalStaff = usersMeta.data?.users?.length || 42;
  const totalDepts = usersMeta.data?.departments?.length || 8;
  const isHealthy = readyMeta.data?.status === "ready";

  return (
    <section className="admin-home">
      <div className="page-heading">
        <div>
          <p className="eyebrow">TRUNG TÂM ĐIỀU HÀNH & QUẢN TRỊ EAS</p>
          <h1>Tổng quan hệ thống</h1>
          <p className="muted">
            Giám sát toàn diện nhân sự, cơ cấu phòng ban, quy trình phê duyệt và tuân thủ an toàn thông tin.
          </p>
        </div>
        <div className="admin-overview-header-badge">
          <span className="live-pulse" aria-hidden="true" />
          <span>Hệ thống: {isHealthy ? "Sẵn sàng hoạt động" : "Đang kiểm tra"}</span>
        </div>
      </div>

      <div className="admin-kpi-grid">
        <article className="stat-card">
          <div className="stat-card-icon stat-icon-blue">👥</div>
          <div className="stat-card-info">
            <span className="stat-card-label">Tổng tài khoản nhân sự</span>
            <strong className="stat-card-value">{totalStaff}</strong>
            <small className="stat-card-sub">Đồng bộ từ sơ đồ tổ chức</small>
          </div>
        </article>
        <article className="stat-card">
          <div className="stat-card-icon stat-icon-green">🏛</div>
          <div className="stat-card-info">
            <span className="stat-card-label">Đơn vị & Phòng ban</span>
            <strong className="stat-card-value">{totalDepts}</strong>
            <small className="stat-card-sub">Ban Giám Đốc và 7 phòng ban</small>
          </div>
        </article>
        <article className="stat-card">
          <div className="stat-card-icon stat-icon-purple">🛡</div>
          <div className="stat-card-info">
            <span className="stat-card-label">Tiêu chuẩn kiểm soát</span>
            <strong className="stat-card-value">ISO/IEC 27001</strong>
            <small className="stat-card-sub">Toàn vẹn SHA-256 chuỗi khối</small>
          </div>
        </article>
        <article className="stat-card">
          <div className="stat-card-icon stat-icon-amber">⚙</div>
          <div className="stat-card-info">
            <span className="stat-card-label">Nền tảng vận hành</span>
            <strong className="stat-card-value">EAS Enterprise</strong>
            <small className="stat-card-sub">Phiên bản 2.0 LTS</small>
          </div>
        </article>
      </div>

      <div className="admin-section-title">
        <h2>Phân hệ quản trị nghiệp vụ</h2>
        <p className="muted">Chọn khu vực chức năng để điều hành hoặc kiểm tra cấu hình.</p>
      </div>

      <div className="admin-tiles-grid">
        {[
          ["identity", "Danh tính & Phân quyền", "Quản lý 42 tài khoản, phân bổ role và phạm vi ủy quyền", "◎", "OPS_ADMIN"],
          ["org-chart", "Sơ đồ tổ chức", "Trực quan hóa cây cơ cấu Ban Giám Đốc và 7 phòng ban thời gian thực", "🏛", null],
          ["policy", "Cấu hình quy trình", "Soạn thảo biểu mẫu, thiết lập luồng duyệt và công bố quy chế", "⚙", "POLICY_ADMIN"],
          ["ops", "Theo dõi vận hành", "Giám sát tiến độ xử lý hồ sơ, can thiệp điều phối và xử lý sự cố", "⇄", "OPS_ADMIN"],
          ["api-admin", "Quản lý API & Tích hợp", "Danh mục endpoint nội bộ, ma trận phân quyền và kiểm tra readiness", "⌘", "OPS_ADMIN"],
          ["audit", "Kiểm toán hồ sơ", "Đối soát hash SHA-256 và bằng chứng cryptographic từng quyết định", "⌕", "AUDITOR"],
          ["events", "Nhật ký quản trị", "Tra cứu lịch sử kiểm toán, sự kiện bảo mật và thay đổi hệ thống", "≡", "AUDITOR"],
          ["flow-diagrams", "Sơ đồ luồng nghiệp vụ", "Thư viện sơ đồ quy trình chuẩn các vòng đời A, B, C", "◇", null],
        ]
          .filter(([key, , , , reqRole]) => !reqRole || canNavigate(user.roles, key, user.capabilities))
          .map(([key, label, detail, icon]) => (
            <button
              key={key}
              type="button"
              className="admin-feature-card"
              onClick={() => navigate(key)}
            >
              <div className="admin-feature-icon">{icon}</div>
              <div className="admin-feature-body">
                <strong>{label}</strong>
                <p>{detail}</p>
              </div>
              <span className="admin-feature-arrow" aria-hidden="true">→</span>
            </button>
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
    [menuOpen, setMenuOpen] = useState(false),
    [quickSearch, setQuickSearch] = useState(""),
    [searchText, setSearchText] = useState(""),
    [notificationOpen, setNotificationOpen] = useState(false);
  const unread = useResource("/api/v1/notifications?limit=1&offset=0");
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
    if (!canNavigate(user.roles, next, user.capabilities)) return;
    const allowedPages = portal === "admin" ? ADMIN_PAGES : (portal === "client" ? CLIENT_PAGES : new Set(menu.map((x) => x[0])));
    if (!allowedPages.has(next)) return;
    setPage(next);
    setSelected(null);
    setEditor(null);
    setMenuOpen(false);
    setNotificationOpen(false);
    if (next !== "mine") setSearchText("");
  }
  function searchAll(event) {
    event.preventDefault();
    if (!quickSearch.trim()) return;
    const target = user.roles.includes("REQUESTER") ? "mine" : user.roles.includes("APPROVER") ? "approval" : user.roles.includes("EXECUTOR") ? "execution" : "acceptance";
    if (portal !== "client" || !canNavigate(user.roles,target,user.capabilities)) return;
    navigate(target);
    setSearchText(quickSearch.trim());
  }

  const primaryRole = getPrimaryRoleBadge(user.roles);

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
          {(portal === "admin" ? [
            ["TỔNG QUAN & TỔ CHỨC", ["home", "org-chart", "flow-diagrams", "ai-process"]],
            ["CẤU HÌNH & CHÍNH SÁCH", ["policy", "ai-policy", "plan-catalog", "request-catalog"]],
            ["VẬN HÀNH & GIÁM SÁT", ["ops", "users", "permissions", "api-admin"]],
            ["KIỂM TOÁN & NHẬT KÝ", ["audit", "events"]],
            ["TÀI KHOẢN", ["notifications", "profile"]],
          ] : [
            ["KHÔNG GIAN CÁ NHÂN", ["home", "mine"]],
            ["CÔNG VIỆC ĐƯỢC GIAO", ["approval", "execution", "acceptance"]],
            ["TỔ CHỨC & HƯỚNG DẪN", ["org-client", "flow-diagrams", "ai-process"]],
            ["TÀI KHOẢN", ["notifications", "profile"]],
          ]).map(([group, keys]) => {
            const allowedPages = portal === "admin" ? ADMIN_PAGES : (portal === "client" ? CLIENT_PAGES : new Set(menu.map((x) => x[0])));
            const visible = menu.filter((m) => keys.includes(m[0]) && allowedPages.has(m[0]) && canNavigate(user.roles, m[0], user.capabilities));
            return visible.length ? (
              <div key={group} className="nav-group">
                <p className="nav-caption">{group}</p>
                {visible.map(([key, title, icon]) => (
                  <button
                    key={key}
                    className={page === key && !selected && !editor ? "nav-item active" : "nav-item"}
                    aria-current={page === key && !selected && !editor ? "page" : undefined}
                    onClick={() => navigate(key)}
                  >
                    <span aria-hidden="true">{icon}</span>
                    <span className="nav-text">{title}</span>
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
            {portal === "admin" ? "Trung tâm Quản trị" : "Không gian làm việc"} / {menu.find((m) => m[0] === page)?.[1]}
          </span>
          {portal === "client" && <form className="client-quick-search" role="search" onSubmit={searchAll}>
            <label htmlFor="client-global-search" className="sr-only">Tìm mã yêu cầu</label>
            <span aria-hidden="true">⌕</span><input id="client-global-search" type="search" value={quickSearch} onChange={e=>setQuickSearch(e.target.value)} placeholder="Tìm nhanh mã yêu cầu…" />
            <button type="submit" className="secondary" aria-label="Tìm kiếm">Tìm</button>
          </form>}
          <div className="topbar-right client-topbar-actions">
            <div className="client-notifications-anchor">
              <button type="button" className="secondary client-icon-button" onClick={() => setNotificationOpen(value=>!value)} aria-label={`Thông báo${unread.data?.unread_count ? `, ${unread.data.unread_count} chưa đọc` : ""}`} aria-expanded={notificationOpen} title="Thông báo">
                <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9"/><path d="M10 21h4"/></svg>
                {Number(unread.data?.unread_count)>0&&<span className="client-notification-dot"/>}
              </button>
              {notificationOpen&&<div className="client-notification-popover" role="region" aria-label="Thông báo"><strong>Thông báo</strong><p className="muted">{Number(unread.data?.unread_count)||0} thông báo chưa đọc</p><button type="button" className="secondary" onClick={()=>navigate("notifications")}>Mở trung tâm thông báo →</button></div>}
            </div>
            <button type="button" className="client-account-link" onClick={()=>navigate("profile")} aria-label={`Tài khoản ${user.display_name||"người dùng"}`}>
              <span className="client-avatar">{user.display_name?.slice(0,1)||"U"}</span>
              <div className="topbar-user-pill">
                <strong className="topbar-display-name">{user.display_name||"Người dùng"}</strong>
                <span className={`topbar-role-badge ${primaryRole.tone}`}>{primaryRole.name}</span>
              </div>
            </button>
            <button type="button" className="secondary client-icon-button" aria-label="Đăng xuất" title="Đăng xuất" onClick={onLogout}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></svg></button>
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
            searchText,
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

export default function App({ portal = (import.meta.env.VITE_EAS_PORTAL || "unified"), adminScreens = {} }) {
  return (
    <AdminScreensContext.Provider value={adminScreens}>
      <PortalApp portal={portal} />
    </AdminScreensContext.Provider>
  );
}

function PortalApp({ portal }) {
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
  if (user && portal === "admin" && !canUsePortal(user.roles, "admin")) {
    return <main className="auth-shell"><section className="panel"><h1>Không có quyền quản trị</h1><p>Tài khoản không được cấp quyền sử dụng trung tâm quản trị.</p><ActionForm onSubmit={logout} submitLabel="Đăng xuất" /></section></main>;
  }
  if (user && portal === "client" && !canUsePortal(user.roles, "client")) {
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

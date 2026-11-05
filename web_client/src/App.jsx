import { Suspense, lazy, useEffect, useState } from "react";
import { PermissionProvider } from "./hooks/usePermission.jsx";
import { api, initializeCsrf } from "./api.js";
import ToastCenter from "./components/ToastCenter.jsx";
import { PageControls } from "./components/ux.jsx";
import { canNavigate, canUsePortal } from "./rolePolicy.js";
import { PERMISSIONS_CHANGED, createRefresher } from "./sessionRefresh.js";
import RoleTasks from "./components/RoleTasks.jsx";
import { date, errorText, statuses, types, typeLevels, getPrimaryRoleBadge } from "./domain.js";
import {
  ActionForm,
  Badge,
  ResourceState,
  useResource,
} from "./components/ui.jsx";
import {PersonalOverviewStats, PeriodChooser} from "./components/DashboardOverview.jsx";
import ClientRequests from "./components/ClientRequests.jsx";
import Notifications from "./components/NotificationsPage.jsx";
import Profile from "./components/ProfilePage.jsx";
import { SystemUpdateDialog, SystemUpdateHistory } from "./components/SystemUpdates.jsx";
import AdminScreen, { AdminScreensContext } from "./components/AdminScreen.jsx";
import { ApiBaseContext, WORKSPACE_API } from "./apiBase.js";
import ClientRequestsHub from "./components/ClientRequestsHub.jsx";
import { formatVnd } from "./formatters.js";

function AdminDashboard(props) {
  return <AdminScreen name="AdminDashboard" {...props} />;
}
// Screens opened after the first page load are split into their own chunks.
const RequestEditor = lazy(() => import("./components/RequestEditor.jsx"));
const RequestDetail = lazy(() => import("./components/RequestDetail.jsx"));
const WorkflowDiagrams = lazy(() => import("./components/WorkflowDiagrams.jsx"));
const AiProcessGuide = lazy(() => import("./components/AiProcessGuide.jsx"));
const ClientOrgChart = lazy(() => import("./components/ClientOrgChart.jsx"));
const DelegationSettings = lazy(() => import("./components/DelegationSettings.jsx"));
import TeamDashboard from "./components/TeamDashboard.jsx";
import { GlobalSearch, NotificationBell } from "./components/AppHeader.jsx";
import { PageHeader, ShellSkeleton, TableSkeleton } from "./components/design.jsx";
function getRealtimeGreeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Chào buổi sáng!";
  if (hour >= 12 && hour < 18) return "Chào buổi chiều!";
  return "Chào buổi tối!";
}

function Login({ onLogin, portal = "client", aiStatus }) {
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
    const email = String(values.email || "").trim().toLowerCase();

<<<<<<< HEAD
    // The server validates portal access from current role memberships;
    // email addresses are not authorization policies.
    if (portal === "client" && aiStatus?.client_maintenance_lock) {
      setError(`Hệ thống đang cập nhật quy định mới (Đang ở bước: ${aiStatus?.current_step_label || "Đang đồng bộ..."}). Bạn sẽ đăng nhập lại được sau khi quá trình cập nhật hoàn tất.`);
      return;
=======
    // Strict portal separation check
    if (portal === "admin") {
      if (email !== "admin@eas.com") {
        setError("Tài khoản nhân viên không được phép đăng nhập vào Cổng Quản trị (8081). Vui lòng sử dụng Cổng Nhân viên (8080).");
        return;
      }
    } else if (portal === "client") {
      if (email === "admin@eas.com") {
        setError(`Từ chối truy cập: Tài khoản Quản trị viên hệ thống không được phép đăng nhập vào Cổng Nhân viên. Vui lòng đăng nhập tại Cổng Quản trị (${ADMIN_PORTAL_URL}).`);
        return;
      }
      if (aiStatus?.client_maintenance_lock) {
        setError(`Hệ thống đang cập nhật quy định mới (Đang ở bước: ${aiStatus?.current_step_label || "Đang đồng bộ..."}). Bạn sẽ đăng nhập lại được ngay khi quá trình cập nhật hoàn tất.`);
        return;
      }
>>>>>>> origin/main
    }

    setBusy(true);
    setError("");
    try {
      await initializeCsrf();
      const result = await api("/api/v1/auth/login", {
        method: "POST",
        headers: { "X-EAS-Portal": portal },
        body: JSON.stringify({ ...values, email, portal }),
      });
      await onLogin(result.user);
    } catch (err) {
      if (err?.serverMessage) {
        setError(err.serverMessage);
      } else if (err?.code === "INVALID_CREDENTIALS" || err?.message?.includes("INVALID_CREDENTIALS") || String(err?.code).includes("CREDENTIALS") || err?.status === 401) {
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

              {portal === "client" && aiStatus?.client_maintenance_lock && (
                <div className="login-maintenance-box" role="status">
                  <strong>AI đang học quy định mới {aiStatus.target_regulation_version ? `(${aiStatus.target_regulation_version})` : ""}</strong>
                  <span>{aiStatus.current_step_label || "Đang đồng bộ quy định…"}</span>
                  <div className="m-progress-track"><div className="m-progress-fill" style={{ width: `${aiStatus.progress_percent ?? 0}%` }} /></div>
                  <small>Bạn sẽ đăng nhập lại được ngay khi quá trình cập nhật tự động hoàn tất.</small>
                </div>
              )}
              <button
                type="submit"
                disabled={busy || (portal === "client" && aiStatus?.client_maintenance_lock)}
                className="auth-btn-primary"
                aria-label="Đăng nhập"
              >
                {busy
                  ? "Đang xác thực…"
                  : (portal === "client" && aiStatus?.client_maintenance_lock)
                  ? `Hệ thống đang bảo trì (${aiStatus?.progress_percent ?? 0}%)`
                  : "Đăng nhập"}
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
  ["requests", "Yêu cầu & Quy trình", "▤"],
  ["people", "Người dùng", "♙"],
  ["regulations-view", "Quy định", "⚙"],
  ["mine", "Yêu cầu của tôi", "▤"],
  ["approval", "Chờ phê duyệt", "✓"],
  ["execution", "Công việc thực hiện", "▣"],
  ["acceptance", "Chờ nghiệm thu", "◇"],
  ["team", "Tổng quan phòng ban", "▥"],
  ["team-employees", "Nhân viên phòng ban", "♙"],
  ["org-client", "Sơ đồ tổ chức", "⌂"],
  ["flow-diagrams", "Sơ đồ luồng", "⇢"],
  ["ai-process", "Quy trình AI", "✧"],
  ["profile", "Tài khoản cá nhân", "◎"],
  ["notifications", "Thông báo", "○"],
  ["ops", "Theo dõi vận hành", "⇄"],
  ["users", "Quản lý người dùng", "♙"],
  ["departments", "Phòng ban", "▦"],
  ["permissions", "Ma trận phân quyền", "▩"],
  ["org-chart", "Sơ đồ tổ chức", "⌂"],
  ["request-catalog", "Danh mục yêu cầu", "▤"],
  ["policy", "Quy chế & quy trình", "⚙"],
  ["ai-policy", "Bộ luật quy định AI", "✧"],
  ["ai-rules", "Luật AI thủ công", "✧"],
  ["release-workspace", "Phiên bản cấu hình quy trình", "⚙"],
  ["sla", "SLA & thông báo", "◷"],
  ["audit", "Nhật ký kiểm toán", "⌕"],
  ["system", "Cấu hình hệ thống", "⛭"],
  // Legacy keys kept for the unified development portal and deep links.
  ["identity", "Danh tính & phân quyền", "◎"],
  ["plan-catalog", "Danh mục loại yêu cầu", "▦"],
  ["api-admin", "Quản lý API", "⌘"],
  ["events", "Nhật ký quản trị", "≡"],
];
export function pageToModuleCode(key, portal = "admin") {
  // Employee-portal pages that share a key with an admin module (AI guide,
  // department roster) are governed by workflow roles, not admin modules.
  if (portal !== "admin" && (key === "ai-process" || key === "team-employees")) return null;
  switch (key) {
    case "home":
    case "dashboard":
      return "dashboard";
    case "requests":
      return "requests_workflows";
    case "people":
      return "users";
    case "regulations-view":
      return "regulations";
    case "mine":
    case "requests_workflows":
    case "request-catalog":
    case "release-workspace":
    case "ops":
    case "approval":
    case "execution":
    case "acceptance":
      return "requests_workflows";
    case "org_chart":
    case "org-chart":
    case "org-client":
    case "departments":
      return "org_chart";
    case "users":
    case "identity":
    case "team-employees":
      return "users";
    case "permissions":
      return "permissions";
    case "regulations":
    case "policy":
      return "regulations";
    case "ai_engine":
    case "ai-policy":
    case "ai-process":
    case "ai-rules":
      return "ai_engine";
    case "api_management":
    case "api-admin":
      return "api_management";
    case "system_versions":
    case "system":
    case "sla":
    case "audit":
    case "events":
      return "system_versions";
    default:
      return null;
  }
}

const ADMIN_LABELS = {
  home: "Tổng quan",
  dashboard: "Tổng quan",
  ops: "Theo dõi vận hành",
  "request-catalog": "Yêu cầu & Quy trình",
  requests_workflows: "Yêu cầu & Quy trình",
  "org-chart": "Sơ đồ công ty",
  org_chart: "Sơ đồ công ty",
  departments: "Phòng ban",
  users: "Người dùng",
  identity: "Danh tính & phạm vi quyền",
  "release-workspace": "Phiên bản cấu hình quy trình",
  "ai-rules": "Luật AI thủ công",
  permissions: "Phân quyền",
  policy: "Quy định",
  regulations: "Quy định",
  "ai-policy": "Quản trị AI",
  "ai-process": "Quản trị AI",
  ai_engine: "Quản trị AI",
  "api-admin": "Quản lý API",
  api_management: "Quản lý API",
  system: "Phiên bản hệ thống",
  system_versions: "Phiên bản hệ thống",
  sla: "Thông báo SLA",
  audit: "Nhật ký kiểm toán",
  team: "Báo cáo phòng ban",
};
// Same 5 business modules as the admin portal; each item shows only when the
// admin granted "Xem" on its module (system modules never appear here).
const CLIENT_NAV = [
  ["GIÁM SÁT", ["home"]],
  ["LUỒNG CÔNG VIỆC", ["requests"]],
  ["TỔ CHỨC & NHÂN SỰ", ["org-client", "people"]],
  ["TRI THỨC", ["regulations-view"]],
  ["QUẢN LÝ PHÒNG BAN", ["team", "team-employees"]],
  ["TÀI KHOẢN", ["profile"]],
];
const ADMIN_NAV = [
  ["GIÁM SÁT", ["home"]],
  ["LUỒNG CÔNG VIỆC", ["request-catalog"]],
  ["TỔ CHỨC & NHÂN SỰ", ["org-chart", "users", "permissions"]],
  ["TRI THỨC & AI", ["policy", "ai-policy"]],
  ["HỆ THỐNG", ["api-admin", "system"]],
];
function pageLabel(key, portal) {
  return (portal === "admin" && ADMIN_LABELS[key]) || menu.find((m) => m[0] === key)?.[1] || "";
}

function renderNavIcon(key, fallback) {
  const p = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true" };
  switch (key) {
    case "home":
      return (
        <svg {...p}>
          <rect x="3" y="3" width="7" height="7" rx="2" />
          <rect x="14" y="3" width="7" height="7" rx="2" />
          <rect x="14" y="14" width="7" height="7" rx="2" />
          <rect x="3" y="14" width="7" height="7" rx="2" />
        </svg>
      );
    case "mine":
      return (
        <svg {...p}>
          <rect x="2" y="7" width="20" height="14" rx="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      );
    case "approval":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="10" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "execution":
      return (
        <svg {...p}>
          <line x1="8" y1="6" x2="21" y2="6" />
          <line x1="8" y1="12" x2="21" y2="12" />
          <line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" />
          <line x1="3" y1="12" x2="3.01" y2="12" />
          <line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
      );
    case "acceptance":
      return (
        <svg {...p}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "team":
    case "team-employees":
      return (
        <svg {...p}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case "org-client":
    case "org-chart":
      return (
        <svg {...p}>
          <rect x="9" y="3" width="6" height="4" rx="1" />
          <rect x="2" y="17" width="6" height="4" rx="1" />
          <rect x="16" y="17" width="6" height="4" rx="1" />
          <path d="M12 7v5m0 0H5v5m7-5h7v5" />
        </svg>
      );
    case "flow-diagrams":
      return (
        <svg {...p}>
          <circle cx="18" cy="6" r="3" />
          <circle cx="6" cy="18" r="3" />
          <path d="M6 15V9a4 4 0 0 1 4-4h5" />
        </svg>
      );
    case "ai-process":
    case "ai-policy":
      return (
        <svg {...p}>
          <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
        </svg>
      );
    case "profile":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="10" r="3" />
          <path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662" />
        </svg>
      );
    case "notifications":
      return (
        <svg {...p}>
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
      );
    case "ops":
      return (
        <svg {...p}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    case "users":
      return (
        <svg {...p}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      );
    case "departments":
      return (
        <svg {...p}>
          <polygon points="12 2 2 7 12 12 22 7 12 2" />
          <polyline points="2 17 12 22 22 17" />
          <polyline points="2 12 12 17 22 12" />
        </svg>
      );
    case "permissions":
      return (
        <svg {...p}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      );
    case "request-catalog":
    case "plan-catalog":
      return (
        <svg {...p}>
          <path d="m12 3-9 4.5 9 4.5 9-4.5-9-4.5Z" />
          <path d="m3 12 9 4.5 9-4.5" />
          <path d="m3 16.5 9 4.5 9-4.5" />
        </svg>
      );
    case "policy":
      return (
        <svg {...p}>
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      );
    case "sla":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case "audit":
    case "events":
      return (
        <svg {...p}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <circle cx="11.5" cy="14.5" r="2.5" />
          <path d="m16 18-2-2" />
        </svg>
      );
    case "api-admin":
      return (
        <svg {...p}>
          <rect x="2" y="2" width="20" height="8" rx="2" />
          <rect x="2" y="14" width="20" height="8" rx="2" />
          <line x1="6" y1="6" x2="6.01" y2="6" />
          <line x1="6" y1="18" x2="6.01" y2="18" />
        </svg>
      );
    case "system":
      return (
        <svg {...p}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    default:
      return fallback;
  }
}
function RequestList({ page, user, onOpen, onNew, revision, canCreate = true }) {
  const [status, setStatus] = useState(""),
    [type, setType] = useState(""),
    [departmentId, setDepartmentId] = useState(""),
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
  if (departmentId) params.set("department_id", departmentId);
  if (from) params.set("created_from", from + "T00:00:00+07:00");
  if (to) params.set("created_to", to + "T23:59:59.999999+07:00");
  const availableTypes = useResource("/api/v1/request-types");
  const orgMeta = useResource(page === "ops" ? "" : "/api/v1/meta/org-chart");
  const departments = orgMeta.data?.departments || [];
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
            Theo dõi tiến độ, người gửi, phòng ban, người đang phụ trách và hạn xử lý SLA của từng hồ sơ.
          </p>
        </div>
        {canCreate && user.roles.includes("REQUESTER") && (
          <button type="button" onClick={onNew}>+ Tạo yêu cầu mới</button>
        )}
      </div>
      <section className="request-summary-strip" aria-label="Thống kê hồ sơ hiển thị">
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
            <small>hồ sơ hiển thị</small>
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
              placeholder="Mã REQ, tiêu đề hoặc tên người gửi…"
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
          {departments.length > 1 && (
            <label>
              Phòng ban
              <select
                value={departmentId}
                onChange={(e) => {
                  setDepartmentId(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">Tất cả phòng ban</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
          )}
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
            Dữ liệu hiển thị theo phạm vi được cấp quyền · Đang hiển thị <strong>{filtered.length}</strong> hồ sơ
          </small>
          <div className="actions">
            <button
              className="link"
              onClick={() => {
                setStatus("");
                setType("");
                setDepartmentId("");
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
      <ResourceState resource={r} skeleton={<TableSkeleton rows={5} cols={6} />}>
        {page === "ops" ? (
          <AdminScreen name="Operations" items={filtered} onRefresh={r.reload} />
        ) : (
          <section className="panel table-panel" id="request-results">
            <div className="table-wrap">
              <table className="responsive-records">
                <thead>
                  <tr>
                    <th>Mã yêu cầu</th>
                    <th>Tiêu đề &amp; Nghiệp vụ</th>
                    <th>Người gửi / Phòng ban</th>
                    <th>Trạng thái</th>
                    <th>Người đang xử lý</th>
                    <th>Hạn / Cập nhật</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((i) => {
                    const typeName = availableTypes.data?.items?.find((t) => t.code === i.type_code)?.name || i.type_name || types[i.type_code] || "Loại yêu cầu";
                    return (
                      <tr key={i.id} className={i.overdue ? "is-overdue" : ""}>
                        <td data-label="Mã yêu cầu" className="request-code">{i.code}</td>
                        <td data-label="Tiêu đề & Nghiệp vụ">
                          {i.title ? (
                            <>
                              <strong>{i.title}</strong>
                              <span className="ds-cell-sub">
                                {typeName}
                                {i.amount_vnd > 0 ? ` · ${formatVnd(i.amount_vnd)}` : ""}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="type-icon">
                                {i.type_code === "LEAVE"
                                  ? "◷"
                                  : i.type_code === "ACCESS"
                                    ? "◇"
                                    : "▣"}
                              </span>
                              {typeName}
                              <small className="muted" style={{display: "block"}}>
                                Mức rủi ro {i.risk_weight || typeLevels[i.type_code]?.risk_weight || 3}/5 · {i.approval_level || typeLevels[i.type_code]?.approval_level || 1} cấp duyệt
                              </small>
                            </>
                          )}
                        </td>
                        <td data-label="Người gửi / Phòng ban">
                          {i.requester_name || "—"}
                          {i.department_name && <span className="ds-cell-sub">{i.department_name}</span>}
                        </td>
                        <td data-label="Trạng thái">
                          <Badge value={i.status} />
                        </td>
                        <td data-label="Người đang xử lý">{i.current_assignee_name || "—"}</td>
                        <td data-label="Hạn / Cập nhật" className={i.overdue ? "overdue" : ""}>
                          {i.due_at ? `${date(i.due_at)}${i.overdue ? " · Quá hạn" : ""}` : date(i.updated_at)}
                        </td>
                        <td data-label="Thao tác">
                          <button type="button" className="link" onClick={() => onOpen(i.id)}>
                            Xem chi tiết →
                          </button>
                        </td>
                      </tr>
                    );
                  })}
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
  const canOpenAsAdmin = user.roles.includes("AUDITOR");
  const mod = pageToModuleCode(page, portal);
  if (mod && user?.permissions?.by_module && user.permissions.by_module[mod]) {
    if (!user.permissions.by_module[mod].can_view) {
      return (
        <div className="access-denied-view panel" style={{ textAlign: "center", padding: "4rem 2rem", margin: "2rem auto", maxWidth: "600px" }}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🚫</div>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>Không có quyền truy cập</h2>
          <p className="muted" style={{ marginBottom: "1.5rem" }}>
            Tài khoản của bạn chưa được cấp quyền Xem cho chức năng <strong>{pageLabel(page, portal)}</strong>. Vui lòng liên hệ Quản trị viên để được cấp quyền.
          </p>
          <button type="button" className="primary" onClick={() => navigate("home")}>
            Quay về trang Tổng quan
          </button>
        </div>
      );
    }
  }
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
        initialTab={page === "audit" ? "activity" : "info"}
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
      if (portal === "admin") return <AdminDashboard navigate={navigate} />;
      return portal === "client" ? (
        <ApiBaseContext.Provider value={WORKSPACE_API}><WorkspaceDashboard navigate={navigate} workspace /></ApiBaseContext.Provider>
      ) : <Overview navigate={navigate} onOpen={setSelected} user={user} />;
    case "requests":
      return <ClientRequestsHub user={user} revision={revision} onOpen={setSelected} onNew={(init) => { setSelected(null); setEditor(init || {}); }} />;
    case "people":
      return <ApiBaseContext.Provider value={WORKSPACE_API}><WorkspaceUsers onNavigateOrgChart={() => navigate("org-client")} /></ApiBaseContext.Provider>;
    case "regulations-view":
      return <ApiBaseContext.Provider value={WORKSPACE_API}><WorkspaceRegulations /></ApiBaseContext.Provider>;
    case "org-client":
      return portal === "client" ? (
        <ApiBaseContext.Provider value={WORKSPACE_API}><WorkspaceOrgChart navigate={navigate} portal="client" user={user} /></ApiBaseContext.Provider>
      ) : <ClientOrgChart user={user} />;
    case "team":
      return <TeamDashboard onOpen={portal === "admin" && !canOpenAsAdmin ? undefined : setSelected} />;
    case "team-employees":
      return <TeamDashboard mode="employees" onOpen={setSelected} />;
    case "mine":
    case "approval":
    case "execution":
    case "acceptance":
      return portal === "client" ? <ClientRequests key={page} initialStage={page === "mine" ? "mine" : page} initialQuery={searchText} user={user} revision={revision} onOpen={setSelected} onNew={()=>setEditor({})} /> : <RequestList key={page} page={page} user={user} revision={revision} onOpen={setSelected} onNew={()=>setEditor({})} />;
    case "audit":
      return portal === "admin" ? <AdminScreen name="AuditLogPage" onOpen={setSelected} /> : <AdminScreen name="AuditorWorkspace" onOpen={(id) => setSelected(id)} />;
    case "events":
      return <AdminScreen name="AdminEvents" />;
    case "users":
      return <AdminScreen name="UserManagementPage" onNavigateOrgChart={() => navigate("org-chart")} />;
    case "identity":
      return portal === "admin" ? (
        <AdminScreen name="IdentityAdmin" key="identity" initialKind="users" onNavigateOrgChart={() => navigate("org-chart")} />
      ) : (
        <AdminScreen name="UserManagementPage" onNavigateOrgChart={() => navigate("org-chart")} />
      );
    case "release-workspace":
      return <AdminScreen name="PolicyWorkspace" canManageAccess={user.roles.includes("OPS_ADMIN")} onManageAccess={() => navigate("identity")} />;
    case "ai-rules":
      return <AdminScreen name="AiPolicyAdmin" />;
    case "departments":
      return <AdminScreen name="OrgChart" navigate={navigate} portal={portal} user={user} />;
    case "permissions":
      return <AdminScreen name="RolePermissionMatrixPage" />;
    case "request-catalog":
    case "requests_workflows":
      return <AdminScreen name="RequestWorkflowsPage" />;
    case "org-chart":
      return <AdminScreen name="OrgChart" navigate={navigate} portal={portal} user={user} />;
    case "api-admin":
    case "mock_apis":
    case "api_management":
      return <AdminScreen name="ApiAdministration" />;
    case "plan-catalog":
      return <AdminScreen name="PlanCatalog" />;
    case "ops":
      return <AdminScreen name="OperationsPage" key={searchText} initialQuery={searchText} onOpen={canOpenAsAdmin ? setSelected : undefined} />;
    case "sla":
      return <AdminScreen name="SlaNotificationsPage" navigate={navigate} />;
    case "system":
    case "system_versions":
    case "versions":
      return <AdminScreen name="SystemVersionsPage" />;
    case "ai-process":
    case "ai_engine":
      return portal === "admin" ? (
        <AdminScreen name="AiEngineManagementPage" />
      ) : (
        <AiProcessGuide user={user} portal={portal} onOpen={setSelected} navigate={navigate} />
      );
    case "flow-diagrams":
      return <><PageHeader eyebrow="QUY TRÌNH" title="Sơ đồ luồng" description="Tra cứu các sơ đồ xử lý và vòng đời yêu cầu."/><WorkflowDiagrams /></>;
    case "policy":
    case "regulations":
      return portal === "admin" ? (
        <AdminScreen name="RegulationsManagementPage" />
      ) : (
        <AdminScreen name="Policy" canManageAccess={user.roles.includes("OPS_ADMIN")} onManageAccess={() => navigate("identity")} />
      );
    case "ai-policy":
      return portal === "admin" ? <AdminScreen name="AiEngineManagementPage" /> : <AdminScreen name="AiPolicyAdmin" />;
    case "notifications":
      return (
        <>
          <SystemUpdateHistory />
          <Notifications onOpen={portal === "admin" && !canOpenAsAdmin ? undefined : setSelected} />
        </>
      );
    case "profile":
      return (
        <>
          <Profile user={user} />
          {user.roles.includes("APPROVER") && <DelegationSettings />}
        </>
      );
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

const navKeys = (groups) => groups.flatMap(([, keys]) => keys);
const ADMIN_PAGES = new Set([...navKeys(ADMIN_NAV), "ops", "sla", "audit", "identity", "departments", "notifications"]);
const CLIENT_PAGES = new Set([...navKeys(CLIENT_NAV), "notifications"]);
const UNIFIED_NAV = [...CLIENT_NAV, ...ADMIN_NAV.map(([group, keys]) => [group, keys.filter((key) => !navKeys(CLIENT_NAV).includes(key))])];

/** Overview for administrators without OPS scope (policy admins, auditors). */
export function AdminOverview({ navigate, user }) {
  const tiles = [
    ["policy", "Quy chế & quy trình", "Soạn thảo biểu mẫu, luồng duyệt, SLA và công bố quy chế", "⚙"],
    ["audit", "Nhật ký kiểm toán", "Xác minh chuỗi nhật ký hồ sơ và tra cứu thay đổi quản trị", "⌕"],
    ["team", "Báo cáo phòng ban", "Số liệu hồ sơ theo phòng ban trong phạm vi kiểm toán", "▥"],
    ["ai-process", "Quy trình AI", "Lịch sử đánh giá AI của hồ sơ được phép xem", "✧"],
  ].filter(([key]) => canNavigate(user.roles, key, user.capabilities));
  return <section className="admin-home">
    <PageHeader eyebrow="TRUNG TÂM QUẢN TRỊ" title="Tổng quan quản trị" description="Chọn khu vực chức năng theo vai trò quản trị được cấp." />
    <div className="admin-tiles-grid">{tiles.map(([key, label, detail, icon]) => (
      <button key={key} type="button" className="admin-feature-card" onClick={() => navigate(key)}>
        <div className="admin-feature-icon" aria-hidden="true">{icon}</div>
        <div className="admin-feature-body"><strong>{label}</strong><p>{detail}</p></div>
        <span className="admin-feature-arrow" aria-hidden="true">→</span>
      </button>))}
    </div>
  </section>;
}

function readFlag(key) { try { return window.localStorage.getItem(key) === "1"; } catch { return false; } }
// Screens shared with the admin portal, opened in the employee portal through
// /api/v1/workspace (module rights granted by the admin). Loaded on demand.
const WorkspaceDashboard = lazy(() => import("./components/AdminPages.jsx").then((m) => ({ default: m.AdminDashboard })));
const WorkspaceUsers = lazy(() => import("./components/UserManagementPage.jsx"));
const WorkspaceRegulations = lazy(() => import("./components/RegulationsManagementPage.jsx"));
const WorkspaceOrgChart = lazy(() => import("./components/OrgChart.jsx"));
const ADMIN_PORTAL_URL = import.meta.env.VITE_ADMIN_PORTAL_URL || "http://localhost:8081";

function writeFlag(key, value) { try { window.localStorage.setItem(key, value ? "1" : "0"); } catch { /* storage unavailable */ } }

function Workspace({ user, onLogout, portal = "client", theme = "light", toggleTheme = () => {} }) {
  const [page, setPage] = useState("home"),
    [selected, setSelected] = useState(null),
    [editor, setEditor] = useState(null),
    [revision, setRevision] = useState(0),
    [menuOpen, setMenuOpen] = useState(false),
    [searchText, setSearchText] = useState(""),
    [collapsed, setCollapsed] = useState(() => readFlag("eas.sidebarCollapsed")),
    [closedGroups, setClosedGroups] = useState(() => new Set());
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const main = document.getElementById("main");
      main?.scrollIntoView({ behavior: "smooth", block: "start" });
      const heading = main?.querySelector("h1");
      if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
    });
    return () => cancelAnimationFrame(frame);
  }, [page, selected, editor]);
  const allowedPages = portal === "admin" ? ADMIN_PAGES : (portal === "client" ? CLIENT_PAGES : new Set(menu.map((x) => x[0])));
  const groups = portal === "admin" ? ADMIN_NAV : portal === "client" ? CLIENT_NAV : UNIFIED_NAV;
  function navigate(next, query = "") {
    if (!canNavigate(user.roles, next, user.capabilities)) return;
    if (!allowedPages.has(next)) return;
    const mod = pageToModuleCode(next, portal);
    if (mod && portal === "client" && !user?.permissions?.by_module?.[mod]?.can_view) return;
    if (mod && user?.permissions?.by_module && user.permissions.by_module[mod]) {
      if (!user.permissions.by_module[mod].can_view) return;
    }
    setPage(next);
    setSelected(null);
    setEditor(null);
    setMenuOpen(false);
    setSearchText(query);
  }
  function openRequest(id) {
    setEditor(null);
    setSelected(id);
    setMenuOpen(false);
  }
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (event) => { if (event.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);
  function toggleCollapsed() {
    setCollapsed((value) => { writeFlag("eas.sidebarCollapsed", !value); return !value; });
  }
  function toggleGroup(name) {
    setClosedGroups((prev) => { const next = new Set(prev); if (next.has(name)) next.delete(name); else next.add(name); return next; });
  }
  const primaryRole = getPrimaryRoleBadge(user.roles);
  const currentGroup = groups.find(([, keys]) => keys.includes(page))?.[0];
  const activeTitle = editor ? (editor.id ? "Chỉnh sửa hồ sơ" : "Tạo yêu cầu mới") : selected ? "Chi tiết hồ sơ" : pageLabel(page, portal);
  const crumbs = [portal === "admin" ? "Quản trị" : "Không gian làm việc", currentGroup, pageLabel(page, portal), editor ? (editor.id ? "Chỉnh sửa hồ sơ" : "Tạo yêu cầu") : selected ? "Chi tiết hồ sơ" : null].filter(Boolean);
  // OPS admins only see request metadata (UC05), so admin search lands on the operations table.
  const adminSearch = portal === "admin" && user.roles.includes("OPS_ADMIN");
  const canSearch = portal !== "admin" || adminSearch;

  return (
    <PermissionProvider user={user}>
      <div className={"app-shell" + (collapsed ? " sidebar-collapsed" : "")}>
      {menuOpen && <button type="button" className="nav-backdrop" aria-label="Đóng menu" onClick={() => setMenuOpen(false)} />}
      <aside className={"sidebar " + (menuOpen ? "open" : "")} aria-label="Thanh điều hướng">
        <button type="button" className="secondary ds-icon-button sidebar-close" aria-label="Đóng điều hướng" onClick={() => setMenuOpen(false)}>×</button>
        <button
          type="button"
          className="sidebar-edge-toggle"
          onClick={toggleCollapsed}
          aria-pressed={collapsed}
          aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
          title={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {collapsed ? <path d="m9 18 6-6-6-6" /> : <path d="m15 18-6-6 6-6" />}
          </svg>
        </button>
        <a className="brand" href="#main" onClick={(event) => { event.preventDefault(); navigate("home"); }}>
          <img src="/logo.png" alt="EAS Logo" className="brand-logo-img" />
          <span>
            {portal === "admin" ? "EAS Admin" : "EAS Portal"}<small>{portal === "admin" ? "QUẢN TRỊ HỆ THỐNG" : "PHÊ DUYỆT DOANH NGHIỆP"}</small>
          </span>
        </a>
        {portal !== "admin" && (user?.permissions?.by_module?.requests_workflows ? Boolean(user.permissions.by_module.requests_workflows.can_create) : user.roles.includes("REQUESTER")) && (
          <div className="sidebar-create-wrap">
            <button
              type="button"
              className="create-button"
              title="Tạo yêu cầu mới"
              onClick={() => { setSelected(null); setEditor({}); setMenuOpen(false); }}
            >
              <span className="create-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </span>
              <span className="create-label">Tạo yêu cầu mới</span>
            </button>
          </div>
        )}
        <nav aria-label="Điều hướng chính" className="sidebar-nav">
          {groups.map(([group, keys]) => {
            const visible = keys.map((key) => menu.find((m) => m[0] === key)).filter((m) => {
              if (!m) return false;
              if (!allowedPages.has(m[0])) return false;
              if (!canNavigate(user.roles, m[0], user.capabilities)) return false;
              const mod = pageToModuleCode(m[0], portal);
              // Employee portal: a module page appears only after the admin grants "Xem".
              if (mod && portal === "client") return Boolean(user?.permissions?.by_module?.[mod]?.can_view);
              if (mod && user?.permissions?.by_module && user.permissions.by_module[mod]) {
                return Boolean(user.permissions.by_module[mod].can_view);
              }
              return true;
            });
            if (!visible.length) return null;
            const isClosed = closedGroups.has(group);
            return (
              <div key={group} className={"nav-group" + (isClosed ? " is-collapsed" : "")}>
                <button type="button" className="nav-caption" aria-expanded={!isClosed} onClick={() => toggleGroup(group)}>
                  <span>{group}</span><span className="nav-caption-chevron" aria-hidden="true">▾</span>
                </button>
                {(!isClosed || collapsed) && visible.map(([key, , icon]) => {
                  const active = page === key && !selected && !editor;
                  const title = pageLabel(key, portal);
                  return (
                    <button key={key} type="button" title={collapsed ? title : undefined} className={active ? "nav-item active" : "nav-item"}
                      aria-current={active ? "page" : undefined} onClick={() => navigate(key)}>
                      <span className="nav-icon" aria-hidden="true">{renderNavIcon(key, icon)}</span>
                      <span className="nav-text">{title}</span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>
        <button type="button" className="secondary sidebar-collapse" onClick={toggleCollapsed} aria-pressed={collapsed}
          aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}>{collapsed ? "»" : "« Thu gọn"}</button>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button type="button" className="secondary menu-toggle" aria-label="Mở điều hướng" onClick={() => setMenuOpen(!menuOpen)}>☰</button>
            <div className="topbar-page-identity">
              <span className="topbar-page-title">{activeTitle}</span>
              <nav className="ds-breadcrumb" aria-label="Vị trí hiện tại"><ol>
                {crumbs.map((crumb, index) => <li key={crumb} aria-current={index === crumbs.length - 1 ? "page" : undefined}>{crumb}</li>)}
              </ol></nav>
            </div>
          </div>
          {canSearch && <GlobalSearch portal={portal} onOpen={(id, item) => {
            if (adminSearch) {
              // Metadata-only scope: open the operations row instead of the restricted detail.
              if (user.roles.includes("AUDITOR")) openRequest(id); else navigate("ops", item?.code || "");
            } else openRequest(id);
          }} onNavigate={navigate} />}
          <div className="topbar-right client-topbar-actions">
            <button
              type="button"
              className="secondary ds-icon-button theme-toggle-btn"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Chuyển sang giao diện Sáng" : "Chuyển sang giao diện Tối"}
              title={theme === "dark" ? "Chuyển sang giao diện Sáng" : "Chuyển sang giao diện Tối"}
            >
              {theme === "dark" ? (
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
            {portal !== "admin" && user.working_status && (
              <span className={`working-status-badge ws-${String(user.working_status.code).toLowerCase()}`} title={user.working_status.detail}>
                {user.working_status.label}
              </span>
            )}
            <NotificationBell onOpen={portal === "admin" && !user.roles.includes("AUDITOR") ? () => navigate("notifications") : openRequest} onViewAll={() => navigate("notifications")} />
            <button type="button" className="client-account-link" disabled={portal === "admin"} onClick={() => navigate("profile")} aria-label={`Tài khoản ${user.display_name || "người dùng"}`}>
              <span className="client-avatar">{user.display_name?.slice(0, 1) || "U"}</span>
              <div className="topbar-user-pill">
                <strong className="topbar-display-name">{user.display_name || "Người dùng"}</strong>
                <span className={`topbar-role-badge ${primaryRole.tone}`}>{user.job_title || primaryRole.name}</span>
                {user.department_name && <small className="topbar-department">{user.department_name}</small>}
              </div>
            </button>
            <button type="button" className="secondary ds-icon-button" aria-label="Đăng xuất" title="Đăng xuất" onClick={onLogout}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></svg></button>
          </div>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <Suspense fallback={<output className="ds-loading" aria-busy="true"><span className="sr-only">Đang tải trang…</span><span className="ds-skeleton" aria-hidden="true"><span className="ds-skeleton-line" style={{ width: "60%" }} /><span className="ds-skeleton-line" style={{ width: "90%" }} /></span></output>}>
          {renderWorkspaceContent({
            editor,
            selected,
            page,
            user,
            revision,
            navigate,
            setSelected: openRequest,
            setEditor,
            setRevision,
            portal,
            searchText,
          })}
          </Suspense>
        </main>
        <footer className="page-footer">
          EAS · {portal === "admin" ? "Trung tâm quản trị hệ thống" : "Hệ thống phê duyệt yêu cầu doanh nghiệp"}
        </footer>
      </div>
    </div>
    </PermissionProvider>
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
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("eas.theme") || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    } catch {
      return "light";
    }
  });
  useEffect(() => {
    try {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("eas.theme", theme);
    } catch {}
  }, [theme]);
  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return (
    <AdminScreensContext.Provider value={adminScreens}>
      <PortalApp portal={portal} theme={theme} toggleTheme={toggleTheme} />
    </AdminScreensContext.Provider>
  );
}


function useAiMaintenanceState() {
  const [aiStatus, setAiStatus] = useState({
    client_maintenance_lock: false,
    sync_status: "COMPLETED",
    active_regulation_version: "v1.0",
    target_regulation_version: "v1.0",
    progress_percent: 100,
    current_step_index: 4,
    current_step_label: "",
    steps_detail: [],
  });

  useEffect(() => {
    let active = true;
    let pending = null;
    let inFlight = false;
    let failureStreak = 0;
    let lastAttempt = 0;
    let controller = null;
    const fetchStatus = async () => {
      if (!active || inFlight) return;
      inFlight = true;
      lastAttempt = Date.now();
      let maintenance = false;
      controller = new AbortController();
      try {
        const res = await fetch("/api/v1/system/ai-status", {
          cache: "no-store", signal: controller.signal,
        });
        if (!res.ok) throw new Error(`AI_STATUS_HTTP_${res.status}`);
        const data = await res.json();
        maintenance = Boolean(data.client_maintenance_lock);
        failureStreak = 0;
        if (active) setAiStatus(data);
      } catch {
        // Preserve the last known state; 503 is an outage, not a new AI step.
        failureStreak = Math.min(6, failureStreak + 1);
      } finally {
        inFlight = false;
        controller = null;
        if (active) {
          const interval = document.visibilityState === "hidden" ? 120000
            : failureStreak ? Math.min(300000, 15000 * 2 ** failureStreak)
              : maintenance ? 3000 : 45000;
          pending = window.setTimeout(fetchStatus, interval);
        }
      }
    };
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      // Do not bypass the outage backoff on every tab focus.
      if (failureStreak && Date.now() - lastAttempt < 30000) return;
      window.clearTimeout(pending);
      if (!inFlight) void fetchStatus();
    };
    void fetchStatus();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      active = false;
      window.clearTimeout(pending);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return aiStatus;
}

function ClientMaintenanceOverlay({ aiStatus, onLogout }) {
  const [countdown, setCountdown] = useState(3);
  const targetV = aiStatus?.target_regulation_version || "mới";
  const progress = aiStatus?.progress_percent ?? 0;
  const currentStep = aiStatus?.current_step_index || 1;
  const stepLabel = aiStatus?.current_step_label || "Đang đồng bộ dữ liệu quy định...";

  useEffect(() => {
    if (countdown <= 0) {
      onLogout();
      return;
    }
    const timer = setTimeout(() => {
      setCountdown((c) => c - 1);
    }, 1000);
    return () => clearTimeout(timer);
  }, [countdown, onLogout]);

  return (
    <div className="client-maintenance-backdrop" role="dialog" aria-modal="true">
      <div className="client-maintenance-card">
        <div className="maintenance-icon-badge">
          <div className="maintenance-radar-pulse"></div>
          <span className="maintenance-robot-icon">🤖</span>
        </div>

        <h2 className="client-maintenance-title">
          Hệ thống đang cập nhật và huấn luyện AI theo quy định mới
          <span className="client-maintenance-version"> (Phiên bản {targetV})</span>
        </h2>

        <p className="client-maintenance-desc">
          Vui lòng thoát ra và đăng nhập lại sau ít phút. Hệ thống đang đồng bộ tri thức và khóa truy cập người dùng để đảm bảo tính nhất quán dữ liệu.
        </p>

        <div className="client-maintenance-steps">
          <div className={`m-step-item ${currentStep >= 1 ? (currentStep > 1 ? "done" : "active") : ""}`}>
            <div className="m-step-dot">{currentStep > 1 ? "✓" : "1"}</div>
            <span>Đồng bộ</span>
          </div>
          <div className="m-step-line"></div>
          <div className={`m-step-item ${currentStep >= 2 ? (currentStep > 2 ? "done" : "active") : ""}`}>
            <div className="m-step-dot">{currentStep > 2 ? "✓" : "2"}</div>
            <span>Học quy định</span>
          </div>
          <div className="m-step-line"></div>
          <div className={`m-step-item ${currentStep >= 3 ? (currentStep > 3 ? "done" : "active") : ""}`}>
            <div className="m-step-dot">{currentStep > 3 ? "✓" : "3"}</div>
            <span>Áp dụng</span>
          </div>
          <div className="m-step-line"></div>
          <div className={`m-step-item ${currentStep >= 4 ? "done" : ""}`}>
            <div className="m-step-dot">{currentStep >= 4 ? "✓" : "4"}</div>
            <span>Hoàn tất</span>
          </div>
        </div>

        <div className="client-maintenance-progress-box">
          <div className="m-progress-header">
            <span className="m-step-label">{stepLabel}</span>
            <span className="m-percent">{progress}%</span>
          </div>
          <div className="m-progress-track">
            <div className="m-progress-fill" style={{ width: `${progress}%` }}></div>
          </div>
        </div>

        <div className="client-maintenance-footer">
          <p className="client-countdown-notice">
            Tự động đưa bạn ra màn hình chờ sau <strong>{countdown} giây</strong>...
          </p>
          <button type="button" className="btn-primary btn-logout-now" onClick={onLogout}>
            Thoát ra ngay (Đăng xuất)
          </button>
        </div>
      </div>
    </div>
  );
}

function PortalApp({ portal, theme, toggleTheme }) {
  const [user, setUser] = useState(undefined),
    [error, setError] = useState("");
  const aiStatus = useAiMaintenanceState();
  // Only the open learning job locks users; a failed run (ERROR) keeps the old rules and stays unlocked.
  const aiMaintenanceActive = Boolean(aiStatus?.client_maintenance_lock);
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
  const signedIn = Boolean(user && !user.must_change_password);
  useEffect(() => {
    if (!signedIn) return undefined;
    const refresher = createRefresher(() => {
      api("/api/v1/auth/me", { headers: { "X-Auth-Optional": "1" } })
        .then((r) => r?.user && setUser(r.user))
        .catch((e) => {
          if (e.status === 401) setUser(null);
        });
    });
    const onVisible = () => document.visibilityState === "visible" && refresher.trigger();
    window.addEventListener("focus", refresher.trigger);
    window.addEventListener(PERMISSIONS_CHANGED, refresher.trigger);
    document.addEventListener("visibilitychange", onVisible);
    // Rights granted or revoked by the admin show up within ~15 s on an open tab.
    const poll = setInterval(() => document.visibilityState === "visible" && refresher.trigger(), 15000);
    return () => {
      clearInterval(poll);
      refresher.dispose();
      window.removeEventListener("focus", refresher.trigger);
      window.removeEventListener(PERMISSIONS_CHANGED, refresher.trigger);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [signedIn]);
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
          // During an AI learning lock the login page shows the progress bar,
          // so a reload must land there instead of a generic connection error.
          else if (e.status === 401 || e.status === 403 || e.message === "SYSTEM_UNDER_MAINTENANCE") setUser(null);
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
              // Explicit user action is allowed to probe immediately after an outage.
              await initializeCsrf({ forceProbe: true });
              const result = await api("/api/v1/auth/me", {
                forceProbe: true, headers: { "X-Auth-Optional": "1" },
              });
              setUser(result?.user || null);
            } catch (e) { setError(errorText(e)); }
          }}>Kết nối lại</button>
        </section>
      </main>
    );
  if (user === undefined)
    return (
      <main id="main" aria-live="polite">
        <ShellSkeleton />
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
  if (user && portal === "admin" && (!canUsePortal(user.roles, "admin"))) {
    return (
      <main className="auth-shell">
        <section className="panel">
          <h1>Không có quyền quản trị</h1>
          <p>Tài khoản nhân viên không được phép sử dụng Cổng Quản trị (8081). Vui lòng sử dụng Cổng Nhân viên (8080).</p>
          <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
            <a
              href={import.meta.env.VITE_CLIENT_PORTAL_URL || `${window.location.protocol}//${window.location.hostname}:8080`}
              className="btn-primary"
              style={{ display: "inline-flex", alignItems: "center", textDecoration: "none", padding: "8px 16px", borderRadius: "6px" }}
            >
              Mở Cổng Nhân viên
            </a>
            <ActionForm onSubmit={logout} submitLabel="Đăng xuất" />
          </div>
        </section>
      </main>
    );
  }
  // Administrative identities use only the Admin portal even when historic
  // workflow grants remain; enforced independently on every backend API.
  if (user && portal === "client" && !canUsePortal(user.roles, "client")) {
    return (
      <main className="auth-shell">
        <section className="panel">
          <h1>Tài khoản quản trị</h1>
          <p>Tài khoản có quyền quản trị chỉ được sử dụng Cổng Quản trị. Vui lòng chuyển sang cổng phù hợp.</p>
          <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
            <a
              href={import.meta.env.VITE_ADMIN_PORTAL_URL || `${window.location.protocol}//${window.location.hostname}:8081`}
              className="btn-primary"
              style={{ display: "inline-flex", alignItems: "center", textDecoration: "none", padding: "8px 16px", borderRadius: "6px" }}
            >
              Mở Cổng Quản trị
            </a>
            <ActionForm onSubmit={logout} submitLabel="Đăng xuất" />
          </div>
        </section>
      </main>
    );
  }
  return user ? (
    <>
      <Workspace user={user} onLogout={logout} portal={portal} theme={theme} toggleTheme={toggleTheme} aiStatus={aiStatus} />
      {portal === "client" && aiMaintenanceActive ? (
        <ClientMaintenanceOverlay aiStatus={aiStatus} onLogout={logout} />
      ) : (
        <SystemUpdateDialog key={user.id} />
      )}
    </>
  ) : (
    <Login onLogin={load} portal={portal} aiStatus={aiStatus} />
  );
  })();
  return <><ToastCenter />{screen}</>;
}

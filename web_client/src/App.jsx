import { useEffect, useState } from "react";
import { api, initializeCsrf } from "./api.js";
import { PasswordField, PageControls } from "./components/ux.jsx";
import { canNavigate } from "./rolePolicy.js";
import RoleTasks from "./components/RoleTasks.jsx";
import AuditorWorkspace from "./components/AuditorWorkspace.jsx";
import { date, errorText, roles, statuses, types } from "./domain.js";
import {
  ActionForm,
  Badge,
  ResourceState,
  useResource,
} from "./components/ui.jsx";
import RequestEditor from "./components/RequestEditor.jsx";
import RequestDetail from "./components/RequestDetail.jsx";
import IdentityAdmin from "./components/IdentityAdmin.jsx";
import ApiAdministration from "./components/ApiAdministration.jsx";
import PlanCatalog from "./components/PlanCatalog.jsx";
import {
  AdminEvents,
  Notifications,
  Operations,
  Policy,
  Profile,
} from "./components/Admin.jsx";
function Login({ onLogin }) {
  return (
    <main id="main" className="auth-shell">
      <section className="auth-intro">
        <div className="brand-mark">E</div>
        <p className="eyebrow">ENTERPRISE APPROVAL SYSTEM</p>
        <h1>
          Mọi yêu cầu.
          <br />
          Một quy trình rõ ràng.
        </h1>
        <p>
          Kết nối đề xuất, phê duyệt và thực hiện trong một không gian làm việc.
        </p>
        <div className="login-steps">
          01 · Đề xuất　　02 · Phê duyệt　　03 · Hoàn thành
        </div>
      </section>
      <section className="panel auth-card">
        <p className="eyebrow">CHÀO MỪNG TRỞ LẠI</p>
        <h2>Đăng nhập EAS Portal</h2>
        <p className="muted">Sử dụng tài khoản doanh nghiệp của bạn.</p>
        <ActionForm
          submitLabel="Đăng nhập"
          onSubmit={async (values) => {
            await initializeCsrf();
            const result = await api("/api/v1/auth/login", {
              method: "POST",
              body: JSON.stringify(values),
            });
            await onLogin(result.user);
          }}
        >
          <label>
            Tên đăng nhập
            <input name="username" autoComplete="username" required />
          </label>
          <PasswordField label="Mật khẩu" name="password" autoComplete="current-password" required />
        </ActionForm>
      </section>
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
  ["policy", "Cấu hình quy trình", "⚙", "POLICY_ADMIN"],
  ["plan-catalog", "Danh mục 18 loại đơn", "▦"],
  ["ops", "Theo dõi vận hành", "⇄", "OPS_ADMIN"],
  ["identity", "Danh tính & phân quyền", "◎", "OPS_ADMIN"],
  ["api-admin", "Quản lý API", "⌘", "OPS_ADMIN"],
  ["audit", "Kiểm toán hồ sơ", "⌕", "AUDITOR"],
  ["events", "Nhật ký quản trị", "≡", "AUDITOR"],
  ["notifications", "Thông báo", "○"],
  ["profile", "Tài khoản cá nhân", "◎"],
];
function RequestList({ page, user, onOpen, onNew, revision }) {
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
        {user.roles.includes("REQUESTER") && (
          <button onClick={onNew}>+ Tạo yêu cầu mới</button>
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
            Tìm mã yêu cầu (toàn bộ dữ liệu)
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
            <button className="secondary" onClick={r.reload}>
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
                        {types[i.type_code] || i.type_code}
                      </td>
                      <td data-label="Trạng thái">
                        <Badge value={i.status} />
                      </td>
                      <td data-label="Cập nhật">{date(i.updated_at)}</td>
                      <td data-label="Thao tác">
                        <button className="link" onClick={() => onOpen(i.id)}>
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
            <button className="secondary" onClick={() => navigate("history")}>Xem danh sách →</button>
          </div>
          <ResourceState resource={recent}>
            {recent.data?.items?.length ? (
              <ul className="dashboard-list">
                {recent.data.items.map((item) => <li key={item.id}>
                  <div><strong>{item.code}</strong><small>{types[item.type_code] || item.type_code} · {date(item.updated_at)}</small><Badge value={item.status}/></div>
                  <button className="link" onClick={() => onOpen(item.id)}>Xem chi tiết →</button>
                </li>)}
              </ul>
            ) : <p className="muted">Chưa có hồ sơ trong phạm vi quyền xem.</p>}
          </ResourceState>
        </section>
        <aside className="panel">
          <h2>Truy cập nhanh</h2>
          <p className="muted">Đi thẳng đến khu vực làm việc, hệ thống tự cuộn về phần thao tác.</p>
          <div className="dashboard-quick">
            <button onClick={() => navigate("mine")}>▤ Yêu cầu của tôi →</button>
            <button className="secondary" onClick={() => navigate("notifications")}>◉ Trung tâm thông báo →</button>
            <button className="secondary" onClick={() => navigate("history")}>◷ Tra cứu hồ sơ →</button>
          </div>
        </aside>
      </div>
      <section className="welcome-banner">
        <div>
          <h2>Công việc rõ ràng. Tiến độ minh bạch.</h2>
          <p>Mỗi quyết định được lưu lại xuyên suốt vòng đời yêu cầu.</p>
        </div>
        <button onClick={() => navigate("history")}>
          Xem hồ sơ liên quan →
        </button>
      </section>
    </>
  );
}
function Workspace({ user, onLogout }) {
  const [page, setPage] = useState("home"),
    [selected, setSelected] = useState(null),
    [editor, setEditor] = useState(null),
    [revision, setRevision] = useState(0),
    [selectedTab, setSelectedTab] = useState("info"),
    [unreadCount, setUnreadCount] = useState(0),
    [notificationRevision, setNotificationRevision] = useState(0),
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
  useEffect(() => {
    let active = true;
    async function refreshUnread() {
      try {
        const response = await api("/api/v1/notifications?limit=1");
        if (active) setUnreadCount(response.unread_count || 0);
      } catch {
        // The inbox remains accessible. No misleading unread count on DB errors.
        if (active) setUnreadCount(0);
      }
    }
    refreshUnread();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refreshUnread();
    }, 30000);
    return () => { active = false; clearInterval(timer); };
  }, [notificationRevision]);
  function openRequest(id, tab = "info") {
    setSelectedTab(tab);
    setSelected(id);
  }
  function navigate(next) {
    if (!canNavigate(user.roles, next, user.capabilities)) return;
    setPage(next);
    setSelected(null);
    setSelectedTab("info");
    setEditor(null);
    setMenuOpen(false);
  }
  return (
    <div className="app-shell">
      {menuOpen && <button className="nav-backdrop" aria-label="Đóng menu" onClick={() => setMenuOpen(false)} />}
      <aside className={"sidebar " + (menuOpen ? "open" : "")}>
        <a className="brand" href="#main" onClick={() => navigate("home")}>
          <span className="brand-mark">E</span>
          <span>
            EAS Portal<small>ENTERPRISE APPROVAL</small>
          </span>
        </a>
        {user.roles.includes("REQUESTER") && (
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
            ["KHÔNG GIAN LÀM VIỆC", ["home", "mine", "history"]],
            ["PHÊ DUYỆT & THỰC HIỆN", ["approval", "execution", "acceptance"]],
            ["QUẢN TRỊ HỆ THỐNG", ["policy", "ops", "identity", "api-admin", "audit", "events"]],
            ["TÀI KHOẢN & TIỆN ÍCH", ["notifications", "profile"]],
          ].map(([group, keys]) => {
            const visible = menu.filter((m) => keys.includes(m[0]) && canNavigate(user.roles, m[0], user.capabilities));
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
              Thông báo {unreadCount > 0 && <span className="unread-badge" aria-label={`${unreadCount} thông báo chưa đọc`}>{unreadCount > 99 ? "99+" : unreadCount}</span>}
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
          {editor ? (
            <RequestEditor
              key={editor.id || "new"}
              initial={editor.id ? editor : undefined}
              onCancel={() => setEditor(null)}
              onDone={(id) => {
                setEditor(null);
                openRequest(id, "progress");
                setRevision((v) => v + 1);
              }}
            />
          ) : selected ? (
            <RequestDetail
              initialTab={selectedTab === "progress" ? "progress" : page === "audit" ? "audit" : "info"}
              key={`${selected}:${selectedTab}`}
              id={selected}
              user={user}
              onBack={() => setSelected(null)}
              onEdit={setEditor}
              onChanged={() => setRevision((v) => v + 1)}
            />
          ) : page === "home" ? (
            <Overview navigate={navigate} onOpen={(id) => openRequest(id)} user={user} />
          ) : page === "audit" ? (
            <AuditorWorkspace onOpen={(id) => openRequest(id)} />
          ) : page === "identity" ? (
            <IdentityAdmin />
          ) : page === "api-admin" ? (
            <ApiAdministration />
          ) : page === "plan-catalog" ? (
            <PlanCatalog />
          ) : page === "policy" ? (
            <Policy canManageAccess={user.roles.includes("OPS_ADMIN")} onManageAccess={() => navigate("identity")} />
          ) : page === "notifications" ? (
            <Notifications onOpen={(id) => openRequest(id, "progress")}
              onRead={() => setNotificationRevision((value) => value + 1)} />
          ) : page === "profile" ? (
            <Profile user={user} />
          ) : page === "events" ? (
            <AdminEvents />
          ) : (
            <RequestList
              key={page}
              page={page}
              user={user}
              revision={revision}
              onOpen={(id) => openRequest(id)}
              onNew={() => setEditor({})}
            />
          )}
        </main>
        <footer className="page-footer">
          EAS · Hệ thống phê duyệt yêu cầu doanh nghiệp
        </footer>
      </div>
    </div>
  );
}
export default function App() {
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
    initializeCsrf()
      .then(() => api("/api/v1/auth/me"))
      .then((r) => {
        if (active) setUser(r.user);
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
  if (error)
    return (
      <main id="main" className="auth-shell">
        <section className="panel">
          <h1>Không thể kết nối hệ thống</h1>
          <p className="error" role="alert">
            {error}
          </p>
          <button onClick={() => window.location.reload()}>Thử lại</button>
        </section>
      </main>
    );
  if (user === undefined)
    return (
      <main id="main" className="empty" role="status">
        Đang khởi tạo EAS Portal…
      </main>
    );
  if (user?.must_change_password)
    return (
      <main id="main" className="content">
        <h1>Đổi mật khẩu để tiếp tục</h1>
        <p>Tài khoản đang sử dụng mật khẩu tạm.</p>
        <Profile user={user} onChanged={() => load()} />
        <ActionForm onSubmit={logout} submitLabel="Đăng xuất" />
      </main>
    );
  return user ? (
    <Workspace user={user} onLogout={logout} />
  ) : (
    <Login onLogin={load} />
  );
}

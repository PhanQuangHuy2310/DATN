import { useState } from "react";
import { useApiBase } from "../apiBase.js";
import { canBrowseDepartmentRoster } from "../rolePolicy.js";
import { CardGridSkeleton } from "./design.jsx";
import { useResource, ResourceState } from "./ui.jsx";

const DEPT_COLORS = {
  BOD: { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af", badge: "#2563eb", icon: "🏛️" },
  TECH: { bg: "#f0fdf4", border: "#22c55e", text: "#166534", badge: "#16a34a", icon: "💻" },
  HR: { bg: "#fdf4ff", border: "#d946ef", text: "#86198f", badge: "#c026d3", icon: "👥" },
  FIN: { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", badge: "#b45309", icon: "💰" },
  BIZ: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b", badge: "#dc2626", icon: "💼" },
  MKT: { bg: "#fff1f2", border: "#f43f5e", text: "#be123c", badge: "#e11d48", icon: "📢" },
  OPS: { bg: "#ecfeff", border: "#06b6d4", text: "#155e75", badge: "#0891b2", icon: "⚙️" },
  LEGAL: { bg: "#f5f3ff", border: "#8b5cf6", text: "#5b21b6", badge: "#7c3aed", icon: "⚖️" },
  // Compatibility fallbacks
  DEPT_IT: { bg: "#f0fdf4", border: "#22c55e", text: "#166534", badge: "#16a34a", icon: "💻" },
  DEPT_HR: { bg: "#fdf4ff", border: "#d946ef", text: "#86198f", badge: "#c026d3", icon: "👥" },
  DEPT_FIN: { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", badge: "#b45309", icon: "💰" },
  DEPT_SALES: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b", badge: "#dc2626", icon: "📈" },
  DEPT_OPS: { bg: "#ecfeff", border: "#06b6d4", text: "#155e75", badge: "#0891b2", icon: "⚙️" },
};

export default function OrgChart({ navigate, portal = "client", user }) {
  const apiBase = useApiBase();
  const treeRes = useResource(`${apiBase}/org-chart-tree`);
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [rosterSearch, setRosterSearch] = useState("");
  const [searchNotice, setSearchNotice] = useState("");
  const [zoom, setZoom] = useState(1);
  const canSeeAllRosters =
    portal === "admin" || Boolean(user?.permissions?.by_module?.users?.can_view);
  const canOpenUsers = Boolean(navigate) && canSeeAllRosters;
  const usersRoute = portal === "admin" ? "users" : "people";

  const summary = treeRes.data?.summary || {
    total_departments: 0,
    total_employees: 0,
    working_count: 0,
    leave_count: 0,
    trip_count: 0,
  };

  const departments = treeRes.data?.departments || [];
  // Rosters: admins and users-module viewers see every department; a direct
  // manager sees only their own department; other employees see structure.
  const isDepartmentManager = !canSeeAllRosters && canBrowseDepartmentRoster(user, departments);
  const canOpenDepartment = (dept) =>
    canSeeAllRosters || (isDepartmentManager && String(dept?.id) === String(user?.department_id));
  const bodDept = departments.find((d) => d.code === "BOD") || departments[0];
  const childDepts = departments.filter((d) => d.code !== "BOD");

  // Filter check
  const isMatch = (dept) => {
    if (!searchTerm.trim()) return false;
    const q = searchTerm.toLowerCase();
    const matchName = dept.name?.toLowerCase().includes(q);
    if (!canOpenDepartment(dept)) return matchName;
    const matchMgr = dept.manager_name?.toLowerCase().includes(q);
    const matchEmp = (dept.employees || []).some(
      (e) => e.full_name?.toLowerCase().includes(q) || e.email?.toLowerCase().includes(q)
    );
    return matchName || matchMgr || matchEmp;
  };

  const handleOpenRoster = (dept) => {
    if (!canOpenDepartment(dept)) return;
    setRosterSearch("");
    setSelectedNode(dept);
  };

  const matchesMember = (member, query) =>
    [member.full_name, member.email].some((value) => String(value || "").toLocaleLowerCase("vi-VN").includes(query));
  const handleSearchMembers = () => {
    if (!isDepartmentManager || !searchTerm.trim()) return;
    const query = searchTerm.trim().toLocaleLowerCase("vi-VN");
    const department = departments.find((dept) => canOpenDepartment(dept) &&
      (dept.employees || []).some((member) => matchesMember(member, query)));
    if (!department) {
      setSearchNotice("Không tìm thấy thành viên phù hợp trong phòng ban của bạn.");
      return;
    }
    setSearchNotice("");
    setRosterSearch(query);
    setSelectedNode(department);
  };
  const rosterMembers = (selectedNode?.employees || []).filter((member) =>
    !rosterSearch || matchesMember(member, rosterSearch));

  return (
    <div className="org-chart-workspace">
      {/* Page Header */}
      <div className="page-heading org-chart-header">
        <div>
          <p className="eyebrow">{portal === "admin" ? "QUẢN TRỊ TỔ CHỨC" : "CƠ CẤU DOANH NGHIỆP"}</p>
          <h1>SƠ ĐỒ TỔ CHỨC CÔNG TY</h1>
          <p className="muted">
            Cơ cấu hình cây trực quan từ Ban Giám Đốc xuống các phòng ban chức năng. Dữ liệu thời gian thực đồng bộ trực tiếp từ CSDL.
          </p>
        </div>
        <div className="org-chart-actions" style={{ display: "flex", gap: "10px" }}>
          {canOpenUsers && (
            <button
              type="button"
              className="primary"
              onClick={() => navigate(usersRoute)}
            >
              {portal === "admin" ? "+ Quản lý người dùng" : "Danh sách nhân sự →"}
            </button>
          )}
          <button
            type="button"
            className="secondary"
            onClick={() => treeRes.reload?.()}
            disabled={treeRes.refreshing}
            title="Tải lại dữ liệu mới nhất từ CSDL"
          >
            {treeRes.refreshing ? "Đang đồng bộ…" : "🔄 Làm mới sơ đồ"}
          </button>
        </div>
      </div>

      {/* Control & Statistics Bar */}
      <div className="panel org-chart-toolbar">
        <div className="org-chart-stats">
          <span className="stat-pill stat-total">
            Tổng nhân sự: <strong>{summary.total_employees}</strong>
          </span>
          <span className="stat-pill stat-depts">
            Phòng ban: <strong>{summary.total_departments}</strong>
          </span>
          <span
            className="stat-pill stat-working"
            style={{ background: "var(--ds-success-soft)", color: "var(--ds-ink)", borderColor: "var(--ds-success)" }}
          >
            🟢 Đang làm: <strong>{summary.working_count}</strong>
          </span>
          <span
            className="stat-pill stat-leave"
            style={{ background: "var(--ds-warning-soft)", color: "var(--ds-ink)", borderColor: "var(--ds-warning)" }}
          >
            🟡 Nghỉ làm: <strong>{summary.leave_count}</strong>
          </span>
          <span
            className="stat-pill stat-trip"
            style={{ background: "var(--ds-primary-soft)", color: "var(--ds-ink)", borderColor: "var(--ds-primary)" }}
          >
            🔵 Công tác: <strong>{summary.trip_count}</strong>
          </span>
        </div>

        <div className="org-chart-tools">
          <form className="org-search-wrap" role="search" onSubmit={(e) => { e.preventDefault(); handleSearchMembers(); }}>
            <span className="org-search-icon" aria-hidden="true">🔍</span>
            <input
              type="search"
              aria-label="Tìm kiếm trong sơ đồ tổ chức"
              placeholder={canSeeAllRosters ? "Tìm kiếm phòng ban, nhân sự, chức danh..." : isDepartmentManager ? "Tìm phòng ban hoặc nhân viên phòng bạn…" : "Tìm kiếm phòng ban…"}
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setSearchNotice(""); }}
              className="org-search-input"
            />
            {isDepartmentManager && <button type="submit" className="secondary" disabled={!searchTerm.trim()}>Tìm thành viên</button>}
            {searchNotice && <span className="muted" role="status">{searchNotice}</span>}
          </form>

          <div className="org-zoom-controls">
            <button type="button" onClick={() => setZoom((z) => Math.max(0.6, z - 0.1))} title="Thu nhỏ">
              −
            </button>
            <span className="zoom-text">{Math.round(zoom * 100)}%</span>
            <button type="button" onClick={() => setZoom((z) => Math.min(1.4, z + 0.1))} title="Phóng to">
              +
            </button>
            <button type="button" onClick={() => setZoom(1)} title="Đặt lại tỉ lệ 100%">
              Đặt lại
            </button>
          </div>
        </div>
      </div>

      {/* Main Diagram Area with Scaling */}
      <ResourceState resource={treeRes} skeleton={<CardGridSkeleton count={6} />}>
        <div className="org-canvas-viewport">
          <div
            className="org-tree-root"
            style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}
          >
            {/* LEVEL 1: BAN GIÁM ĐỐC (TOP LEVEL) */}
            {bodDept && (
              <div className="org-level-top" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  className={`org-node-box org-box-director ${isMatch(bodDept) ? "org-highlight" : ""}`}
                  style={{
                    background: "#eff6ff",
                    borderColor: "#3b82f6",
                    minWidth: "320px",
                    padding: "16px 20px",
                    cursor: canOpenDepartment(bodDept) ? "pointer" : "default",
                    boxShadow: "0 8px 24px rgba(37, 99, 235, 0.15)",
                    position: "relative",
                  }}
                  role={canOpenDepartment(bodDept) ? "button" : undefined}
                  tabIndex={canOpenDepartment(bodDept) ? 0 : undefined}
                  onClick={() => handleOpenRoster(bodDept)}
                  onKeyDown={(e) => { if (canOpenDepartment(bodDept) && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); handleOpenRoster(bodDept); } }}
                  title={canOpenDepartment(bodDept) ? "Bấm để xem danh sách nhân sự Ban Giám Đốc" : "Thông tin cơ cấu phòng ban"}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontSize: "1.2rem" }}>🏛️</span>
                    <span className="badge" style={{ background: "#2563eb", color: "#ffffff", fontWeight: 700 }}>
                      {bodDept.employee_count} nhân sự
                    </span>
                  </div>
                  <div className="org-node-title" style={{ color: "#1e3a8a", fontSize: "16px", fontWeight: 800 }}>
                    {bodDept.name}
                  </div>
                  <div style={{ fontSize: "12px", color: "#475569", marginTop: "4px" }}>
                    Tổng Giám Đốc: <strong>{bodDept.manager_name || "Chưa bổ nhiệm"}</strong>
                  </div>
                  {canOpenDepartment(bodDept) && (
                    <div style={{ fontSize: "11px", color: "#475569", marginTop: "4px" }}>
                      Bấm để xem danh sách Ban Lãnh Đạo →
                    </div>
                  )}
                </div>

                {/* Vertical Stem connector down to horizontal bus */}
                <div
                  style={{
                    width: "3px",
                    height: "36px",
                    background: "#94a3b8",
                    margin: "0 auto",
                  }}
                />
              </div>
            )}

            {/* LEVEL 2: 5 SUB-DEPARTMENTS ROW */}
            <div className="org-depts-container" style={{ position: "relative", marginTop: "0" }}>
              {/* Horizontal Bus Line linking all child departments */}
              <div
                style={{
                  height: "3px",
                  background: "#94a3b8",
                  width: "calc(100% - 140px)",
                  margin: "0 auto 0 auto",
                }}
              />

              <div
                className="org-depts-grid"
                style={{
                  display: "grid",
                  // M11: wrap instead of squeezing 7-8 departments into one row.
                  gridTemplateColumns: "repeat(auto-fit, minmax(235px, 1fr))",
                  gap: "16px",
                  paddingTop: "0",
                }}
              >
                {childDepts.map((dept) => {
                  const colors = DEPT_COLORS[dept.code] || {
                    bg: "#f8fafc",
                    border: "#94a3b8",
                    text: "#1e293b",
                    badge: "#475569",
                    icon: "📁",
                  };
                  const matched = isMatch(dept);

                  return (
                    <div
                      key={dept.id || dept.code}
                      className="org-dept-column"
                      style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 0 }}
                    >
                      {/* Vertical drop line from bus to department card */}
                      <div
                        style={{
                          width: "3px",
                          height: "28px",
                          background: "#94a3b8",
                        }}
                      />

                      {/* Department Header Card */}
                      <button
                        type="button"
                        className={`org-dept-header-card ${matched ? "org-highlight" : ""}`}
                        style={{
                          backgroundColor: colors.bg,
                          borderColor: colors.border,
                          borderWidth: "2px",
                          borderStyle: "solid",
                          borderRadius: "12px",
                          padding: "16px",
                          width: "100%",
                          minWidth: 0,
                          textAlign: "left",
                          cursor: canOpenDepartment(dept) ? "pointer" : "default",
                          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.06)",
                          transition: "all 0.2s ease",
                        }}
                        onClick={() => handleOpenRoster(dept)}
                        aria-disabled={!canOpenDepartment(dept)}
                        title={canOpenDepartment(dept) ? `Bấm để xem toàn bộ ${dept.employee_count} nhân viên phòng ${dept.name}` : "Thông tin cơ cấu phòng ban"}
                      >
                        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "8px", marginBottom: "8px" }}>
                          <span style={{ fontSize: "1.2rem" }}>{colors.icon}</span>
                          <span
                            className="badge"
                            style={{
                              backgroundColor: colors.badge,
                              color: "#ffffff",
                              fontSize: "12.5px",
                              fontWeight: 700,
                              padding: "3px 10px",
                              borderRadius: "10px",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {dept.employee_count} nhân sự
                          </span>
                        </div>

                        <div
                          className="org-dept-title"
                          style={{
                            color: colors.text,
                            fontWeight: 700,
                            fontSize: "14.5px",
                            lineHeight: "1.35",
                            marginBottom: "6px",
                          }}
                        >
                          {dept.name}
                        </div>

                        <div style={{ fontSize: "13px", color: "#475569" }}>
                          Trưởng phòng:{" "}
                          <strong style={{ color: colors.text }}>
                            {dept.manager_name || "Chưa phân công"}
                          </strong>
                        </div>

                        <div style={{ marginTop: "10px", paddingTop: "8px", borderTop: `1px solid ${colors.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12.5px", color: "#475569" }}>
                          <span>{canOpenDepartment(dept) ? "Xem danh sách" : "Cơ cấu phòng ban"}</span>
                          {canOpenDepartment(dept) && <span>→</span>}
                        </div>
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </ResourceState>

      {/* ROSTER MODAL: LIST OF ALL EMPLOYEES IN SELECTED DEPARTMENT */}
      {selectedNode && (
        <div className="org-modal-backdrop" role="presentation" onClick={(e) => e.target === e.currentTarget && setSelectedNode(null)} onKeyDown={(e) => e.key === "Escape" && setSelectedNode(null)}>
          <div
            className="org-modal-card"
            style={{ maxWidth: "640px" }}
            role="dialog"
            aria-modal="true"
          >
            <div className="org-modal-header">
              <div>
                <h3 id="org-modal-title" style={{ fontSize: "18px", fontWeight: 700, color: "var(--ds-ink)" }}>
                  {selectedNode.name} ({selectedNode.code})
                </h3>
                <p className="muted" style={{ margin: "4px 0 0", fontSize: "13px" }}>
                  Trưởng phòng: <strong>{selectedNode.manager_name || "—"}</strong> • Tổng số:{" "}
                  <strong>{selectedNode.employee_count}</strong> nhân sự
                </p>
              </div>
              <button
                type="button"
                className="org-modal-close"
                onClick={() => setSelectedNode(null)}
                aria-label="Đóng"
              >
                ✕
              </button>
            </div>

            <div className="org-modal-body" style={{ maxHeight: "420px", overflowY: "auto", padding: "16px 20px" }}>
              {rosterMembers.length === 0 ? (
                <div className="empty muted" style={{ padding: "32px 0", textAlign: "center" }}>
                  {rosterSearch ? "Không có thành viên phù hợp." : "Hiện chưa có nhân sự nào được phân bổ vào phòng ban này."}
                </div>
              ) : (
                <div className="org-roster-list" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {rosterMembers.map((u) => {
                    const isLeave = u.working_status_code === "NGHI_LAM";
                    const isTrip = u.working_status_code === "CONG_TAC";
                    const isOffHours = u.working_status_code === "NGOAI_GIO";

                    return (
                      <div
                        key={u.id}
                        className="org-roster-item"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 14px",
                          borderRadius: "8px",
                          background: "var(--ds-canvas)",
                          border: "1px solid var(--ds-line)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <div
                            className="org-roster-avatar"
                            style={{
                              width: "36px",
                              height: "36px",
                              borderRadius: "50%",
                              background: "var(--ds-neutral-soft)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontWeight: 700,
                              color: "var(--ds-ink)",
                            }}
                          >
                            {(u.full_name || "U").slice(0, 1).toUpperCase()}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "13.5px", color: "var(--ds-ink)" }}>
                              {u.full_name}
                            </div>
                            <div style={{ fontSize: "12px", color: "var(--ds-muted)" }}>
                              <span>{u.job_title || "Nhân viên"}</span> • <span>{u.email}</span>
                            </div>
                          </div>
                        </div>

                        <div className="org-roster-status">
                          {isTrip ? (
                            <span
                              className="status-tag trip"
                              style={{
                                background: "var(--ds-primary-soft)",
                                color: "var(--ds-primary)",
                                padding: "3px 8px",
                                borderRadius: "4px",
                                fontSize: "11.5px",
                                fontWeight: 600,
                              }}
                            >
                              🔵 Công tác
                            </span>
                          ) : isLeave ? (
                            <span
                              className="status-tag leave"
                              style={{
                                background: "var(--ds-warning-soft)",
                                color: "var(--ds-warning)",
                                padding: "3px 8px",
                                borderRadius: "4px",
                                fontSize: "11.5px",
                                fontWeight: 600,
                              }}
                            >
                              🟡 Nghỉ làm
                            </span>
                          ) : isOffHours ? (
                            <span
                              className="status-tag off-hours"
                              style={{
                                background: "var(--ds-neutral-soft)",
                                color: "var(--ds-muted)",
                                padding: "3px 8px",
                                borderRadius: "4px",
                                fontSize: "11.5px",
                                fontWeight: 600,
                              }}
                            >
                              ⚪ {u.working_status_label || "Ngoài giờ"}
                            </span>
                          ) : (
                            <span
                              className="status-tag active"
                              style={{
                                background: "var(--ds-success-soft)",
                                color: "var(--ds-success)",
                                padding: "3px 8px",
                                borderRadius: "4px",
                                fontSize: "11.5px",
                                fontWeight: 600,
                              }}
                            >
                              🟢 Đang làm
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div
              className="org-modal-footer"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "16px 20px",
                borderTop: "1px solid var(--ds-line)",
              }}
            >
              <span className="muted" style={{ fontSize: "13px" }}>
                {rosterSearch ? "Tìm thấy" : "Tổng cộng"}: <strong>{rosterMembers.length}</strong> nhân sự
              </span>
              {canOpenUsers && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setSelectedNode(null);
                    navigate(usersRoute);
                  }}
                >
                  {portal === "admin"
                    ? "Quản lý trong Người dùng & Trạng thái làm việc →"
                    : "Mở danh sách Người dùng →"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

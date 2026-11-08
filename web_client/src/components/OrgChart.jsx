import { useState } from "react";
import Icon from "./Icon.jsx";
import { useApiBase } from "../apiBase.js";
import { CardGridSkeleton } from "./design.jsx";
import { useResource, ResourceState } from "./ui.jsx";

const DEPT_COLORS = {
  BOD: { bg: "var(--eas-signal-soft)", border: "var(--eas-signal)", text: "var(--eas-signal)", badge: "var(--eas-signal)", icon: "building" },
  TECH: { bg: "var(--eas-ok-soft)", border: "var(--eas-ok)", text: "var(--eas-ok)", badge: "var(--eas-ok)", icon: "server" },
  HR: { bg: "var(--eas-hover)", border: "var(--eas-ink-600)", text: "var(--eas-ink-600)", badge: "var(--eas-ink-600)", icon: "people" },
  FIN: { bg: "var(--eas-warn-soft)", border: "var(--eas-warn)", text: "var(--eas-warn)", badge: "var(--eas-warn)", icon: "card" },
  BIZ: { bg: "var(--eas-danger-soft)", border: "var(--eas-danger)", text: "var(--eas-danger)", badge: "var(--eas-danger)", icon: "briefcase" },
  MKT: { bg: "var(--eas-danger-soft)", border: "var(--eas-danger)", text: "var(--eas-danger)", badge: "var(--eas-danger)", icon: "megaphone" },
  OPS: { bg: "var(--eas-hover)", border: "var(--eas-ink-600)", text: "var(--eas-ink-600)", badge: "var(--eas-ink-600)", icon: "settings" },
  LEGAL: { bg: "var(--eas-hover)", border: "var(--eas-ink-600)", text: "var(--eas-ink-600)", badge: "var(--eas-ink-600)", icon: "scale" },
  // Compatibility fallbacks
  DEPT_IT: { bg: "var(--eas-ok-soft)", border: "var(--eas-ok)", text: "var(--eas-ok)", badge: "var(--eas-ok)", icon: "server" },
  DEPT_HR: { bg: "var(--eas-hover)", border: "var(--eas-ink-600)", text: "var(--eas-ink-600)", badge: "var(--eas-ink-600)", icon: "people" },
  DEPT_FIN: { bg: "var(--eas-warn-soft)", border: "var(--eas-warn)", text: "var(--eas-warn)", badge: "var(--eas-warn)", icon: "card" },
  DEPT_SALES: { bg: "var(--eas-danger-soft)", border: "var(--eas-danger)", text: "var(--eas-danger)", badge: "var(--eas-danger)", icon: "trend" },
  DEPT_OPS: { bg: "var(--eas-hover)", border: "var(--eas-ink-600)", text: "var(--eas-ink-600)", badge: "var(--eas-ink-600)", icon: "settings" },
};

export default function OrgChart({ navigate, portal = "client", user }) {
  const apiBase = useApiBase();
  const treeRes = useResource(`${apiBase}/org-chart-tree`);
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [zoom, setZoom] = useState(1);
  const canOpenUsers =
    Boolean(navigate) &&
    (portal === "admin" || Boolean(user?.permissions?.by_module?.users?.can_view));
  const usersRoute = portal === "admin" ? "users" : "people";

  const summary = treeRes.data?.summary || {
    total_departments: 8,
    total_employees: 136,
    working_count: 135,
    leave_count: 0,
    trip_count: 1,
  };

  const departments = treeRes.data?.departments || [];
  const bodDept = departments.find((d) => d.code === "BOD") || departments[0];
  const childDepts = departments.filter((d) => d.code !== "BOD");

  // Filter check
  const isMatch = (dept) => {
    if (!searchTerm.trim()) return false;
    const q = searchTerm.toLowerCase();
    const matchName = dept.name?.toLowerCase().includes(q);
    const matchMgr = dept.manager_name?.toLowerCase().includes(q);
    const matchEmp = (dept.employees || []).some(
      (e) => e.full_name?.toLowerCase().includes(q) || e.email?.toLowerCase().includes(q)
    );
    return matchName || matchMgr || matchEmp;
  };

  const handleOpenRoster = (dept) => {
    setSelectedNode(dept);
  };

  return (
    <div className="org-chart-workspace">
      {/* Page Header */}
      <div className="page-heading org-chart-header">
        <div>
          <p className="eyebrow">{portal === "admin" ? "QUẢN TRỊ TỔ CHỨC" : "CƠ CẤU DOANH NGHIỆP"}</p>
          <h1>Sơ đồ tổ chức công ty</h1>
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
            title="Tải lại dữ liệu mới nhất"
          >
            {treeRes.refreshing ? "Đang đồng bộ…" : "Làm mới sơ đồ"}
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
            style={{ background: "var(--ds-success-soft)", color: "var(--ds-success)", borderColor: "var(--ds-success)" }}
          >
            <span className="status-dot is-green" aria-hidden="true" />Đang làm: <strong>{summary.working_count}</strong>
          </span>
          <span
            className="stat-pill stat-leave"
            style={{ background: "var(--ds-warning-soft)", color: "var(--ds-warning)", borderColor: "var(--ds-warning)" }}
          >
            <span className="status-dot is-amber" aria-hidden="true" />Nghỉ làm: <strong>{summary.leave_count}</strong>
          </span>
          <span
            className="stat-pill stat-trip"
            style={{ background: "var(--ds-primary-soft)", color: "var(--ds-primary)", borderColor: "var(--ds-primary)" }}
          >
            <span className="status-dot is-blue" aria-hidden="true" />Công tác: <strong>{summary.trip_count}</strong>
          </span>
        </div>

        <div className="org-chart-tools">
          <div className="org-search-wrap">
            <span className="org-search-icon" aria-hidden="true"><Icon name="search" size={14} /></span>
            <input
              type="search"
              placeholder="Tìm kiếm phòng ban, nhân sự, chức danh..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="org-search-input"
            />
          </div>

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
                    background: "var(--eas-signal-soft)",
                    borderColor: "var(--eas-signal)",
                    minWidth: "320px",
                    padding: "16px 20px",
                    cursor: "pointer",
                    boxShadow: "0 8px 24px rgba(37, 99, 235, 0.15)",
                    position: "relative",
                  }}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleOpenRoster(bodDept)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && handleOpenRoster(bodDept)}
                  title="Xem danh sách nhân sự Ban Giám đốc"
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span style={{ fontSize: "1.2rem" }}><Icon name="building" size={14} /></span>
                    <span className="badge" style={{ background: "var(--eas-signal)", color: "var(--eas-surface)", fontWeight: 700 }}>
                      {bodDept.employee_count} nhân sự
                    </span>
                  </div>
                  <div className="org-node-title" style={{ color: "var(--eas-signal)", fontSize: "16px", fontWeight: 800 }}>
                    {bodDept.name}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--eas-ink-600)", marginTop: "4px" }}>
                    Tổng Giám Đốc: <strong>{bodDept.manager_name || "Chưa bổ nhiệm"}</strong>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--eas-ink-500)", marginTop: "4px" }}>
                    Bấm để xem danh sách Ban Lãnh Đạo →
                  </div>
                </div>

                {/* Vertical Stem connector down to horizontal bus */}
                <div
                  style={{
                    width: "3px",
                    height: "36px",
                    background: "var(--eas-ink-500)",
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
                  background: "var(--eas-ink-500)",
                  width: "calc(100% - 140px)",
                  margin: "0 auto 0 auto",
                }}
              />

              <div
                className="org-depts-grid"
                style={{
                  display: "grid",
                  gridTemplateColumns: `repeat(${childDepts.length || 5}, 1fr)`,
                  gap: "16px",
                  paddingTop: "0",
                }}
              >
                {childDepts.map((dept) => {
                  const colors = DEPT_COLORS[dept.code] || {
                    bg: "var(--eas-surface-sunken)",
                    border: "var(--eas-ink-500)",
                    text: "var(--eas-ink-900)",
                    badge: "var(--eas-ink-600)",
                    icon: "folder",
                  };
                  const matched = isMatch(dept);

                  return (
                    <div
                      key={dept.id || dept.code}
                      className="org-dept-column"
                      style={{ display: "flex", flexDirection: "column", alignItems: "center" }}
                    >
                      {/* Vertical drop line from bus to department card */}
                      <div
                        style={{
                          width: "3px",
                          height: "28px",
                          background: "var(--eas-ink-500)",
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
                          minWidth: "210px",
                          textAlign: "left",
                          cursor: "pointer",
                          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.06)",
                          transition: "all 0.2s ease",
                        }}
                        onClick={() => handleOpenRoster(dept)}
                        title={`Bấm để xem toàn bộ ${dept.employee_count} nhân viên phòng ${dept.name}`}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                          <Icon name={colors.icon} size={18} />
                          <span
                            className="badge"
                            style={{
                              backgroundColor: colors.badge,
                              color: "var(--eas-surface)",
                              fontSize: "12px",
                              fontWeight: 700,
                              padding: "2px 8px",
                              borderRadius: "10px",
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
                            fontSize: "13.5px",
                            lineHeight: "1.3",
                            marginBottom: "6px",
                          }}
                        >
                          {dept.name}
                        </div>

                        <div style={{ fontSize: "12px", color: "var(--eas-ink-600)" }}>
                          Trưởng phòng:{" "}
                          <strong style={{ color: colors.text }}>
                            {dept.manager_name || "Chưa phân công"}
                          </strong>
                        </div>

                        <div style={{ marginTop: "10px", paddingTop: "8px", borderTop: `1px solid ${colors.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "var(--eas-ink-500)" }}>
                          <span>Xem danh sách</span>
                          <span>→</span>
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
                <Icon name="x" size={16} />
              </button>
            </div>

            <div className="org-modal-body" style={{ maxHeight: "420px", overflowY: "auto", padding: "16px 20px" }}>
              {(!selectedNode.employees || selectedNode.employees.length === 0) ? (
                <div className="empty muted" style={{ padding: "32px 0", textAlign: "center" }}>
                  Hiện chưa có nhân sự nào được phân bổ vào phòng ban này.
                </div>
              ) : (
                <div className="org-roster-list" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {selectedNode.employees.map((u) => {
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
                              <span className="status-dot is-blue" aria-hidden="true" />Công tác
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
                              <span className="status-dot is-amber" aria-hidden="true" />Nghỉ làm
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
                              <span className="status-dot is-gray" aria-hidden="true" />{u.working_status_label || "Ngoài giờ"}
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
                              <span className="status-dot is-green" aria-hidden="true" />Đang làm
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
                Tổng cộng: <strong>{selectedNode.employees?.length || 0}</strong> nhân sự
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

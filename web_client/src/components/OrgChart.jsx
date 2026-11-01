import { useState, useMemo } from "react";
import { useResource } from "./ui.jsx";

const DEPT_CONFIGS = {
  HR: {
    code: "HR",
    name: "NHÂN SỰ (HR)",
    theme: "blue",
    bg: "#eaf3ff",
    border: "#4b8fe2",
    headerBg: "#cfe2ff",
    textColor: "#084298",
    badgeBg: "#0d6efd",
  },
  FIN: {
    code: "FIN",
    name: "TÀI CHÍNH - KẾ TOÁN (FIN)",
    theme: "green",
    bg: "#e8f8ed",
    border: "#42b86c",
    headerBg: "#d1e7dd",
    textColor: "#0f5132",
    badgeBg: "#198754",
  },
  TECH: {
    code: "TECH",
    name: "KỸ THUẬT - CNTT (IT)",
    theme: "amber",
    bg: "#fff6eb",
    border: "#f0932b",
    headerBg: "#ffe5d0",
    textColor: "#8f4400",
    badgeBg: "#e67e22",
  },
  BIZ: {
    code: "BIZ",
    name: "KINH DOANH (SALES)",
    theme: "red",
    bg: "#ffeaec",
    border: "#eb4d4b",
    headerBg: "#f8d7da",
    textColor: "#842029",
    badgeBg: "#dc3545",
  },
  MKT: {
    code: "MKT",
    name: "MARKETING (MKT)",
    theme: "purple",
    bg: "#f5eeff",
    border: "#9c5de8",
    headerBg: "#e2d4f8",
    textColor: "#4a1584",
    badgeBg: "#6f42c1",
  },
  OPS: {
    code: "OPS",
    name: "VẬN HÀNH - MUA SẮM (OPS)",
    theme: "cyan",
    bg: "#e6f8fa",
    border: "#22a6b3",
    headerBg: "#cff4fc",
    textColor: "#055160",
    badgeBg: "#0dcaf0",
  },
  LEGAL: {
    code: "LEGAL",
    name: "PHÁP CHẾ (LEGAL)",
    theme: "yellow",
    bg: "#fffde6",
    border: "#f1c40f",
    headerBg: "#fff3cd",
    textColor: "#664d03",
    badgeBg: "#ffc107",
  },
};

const ORDERED_DEPT_KEYS = ["HR", "FIN", "TECH", "BIZ", "MKT", "OPS", "LEGAL"];

export default function OrgChart({ navigate, portal = "client", user }) {
  const metaRes = useResource("/api/v1/meta/org-chart");
  const usersRes = useResource("/api/v1/admin/users?limit=300");
  const deptsRes = useResource("/api/v1/admin/departments?limit=100");
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [zoom, setZoom] = useState(1);

  // Compute live hierarchical chart data
  const chartData = useMemo(() => {
    const users = usersRes.data?.items || [];
    const departments = deptsRes.data?.items || [];

    // Map user id -> user object
    const userMap = new Map();
    users.forEach((u) => userMap.set(u.id, u));

    // Calculate subordinate counts
    const subCount = new Map();
    users.forEach((u) => {
      if (u.manager_id) {
        subCount.set(u.manager_id, (subCount.get(u.manager_id) || 0) + 1);
      }
    });

    // Map department id -> dept object
    const deptMap = new Map();
    departments.forEach((d) => deptMap.set(d.id, d));

    const giamDoc = [];
    const admin = [];
    const phoGiamDoc = [];

    // Initialize department groups
    const deptGroups = {};
    ORDERED_DEPT_KEYS.forEach((k) => {
      deptGroups[k] = {
        config: DEPT_CONFIGS[k],
        code: k,
        deptId: null,
        total: 0,
        truongNhom: [],
        nhanVien: [],
      };
    });

    // Find actual department IDs
    departments.forEach((d) => {
      if (deptGroups[d.code]) {
        deptGroups[d.code].deptId = d.id;
        deptGroups[d.code].name = d.name;
      } else if (d.code !== "BOD") {
        // Any other newly created custom department
        deptGroups[d.code] = {
          config: {
            code: d.code,
            name: d.name,
            theme: "custom",
            bg: "#f8f9fa",
            border: "#6c757d",
            headerBg: "#e9ecef",
            textColor: "#212529",
            badgeBg: "#495057",
          },
          code: d.code,
          deptId: d.id,
          total: 0,
          truongNhom: [],
          nhanVien: [],
        };
      }
    });

    // Sort users into roles
    users.forEach((u) => {
      if (!u.is_active) return;
      const dept = deptMap.get(u.department_id);
      const deptCode = dept?.code;

      if (deptCode === "BOD") {
        if (u.username === "hung.nguyen" || u.manager_id === null) {
          giamDoc.push(u);
        } else if (u.username === "ngoc.tran") {
          phoGiamDoc.push(u);
        } else {
          admin.push(u);
        }
      } else if (deptCode && deptGroups[deptCode]) {
        const group = deptGroups[deptCode];
        group.total += 1;
        const hasSubordinates = (subCount.get(u.id) || 0) > 0;
        if (hasSubordinates) {
          group.truongNhom.push(u);
        } else {
          group.nhanVien.push(u);
        }
      }
    });

    return {
      giamDoc,
      admin,
      phoGiamDoc,
      departments: deptGroups,
      totalEmployees: users.filter((u) => u.is_active).length,
    };
  }, [usersRes.data, deptsRes.data]);

  // Search filter matching
  const isMatch = (memberList) => {
    if (!searchTerm.trim()) return false;
    const term = searchTerm.toLowerCase();
    return (memberList || []).some(
      (u) =>
        u.display_name?.toLowerCase().includes(term) ||
        u.username?.toLowerCase().includes(term)
    );
  };

  const handleOpenRoster = (title, subtitle, members, themeColor) => {
    setSelectedNode({ title, subtitle, members, themeColor });
  };

  const reloadData = () => {
    metaRes.reload?.();
    usersRes.reload?.();
    deptsRes.reload?.();
  };

  return (
    <div className="org-chart-workspace">
      {/* Page Header */}
      <div className="page-heading org-chart-header">
        <div>
          <p className="eyebrow">{portal === "admin" ? "QUẢN TRỊ TỔ CHỨC" : "CƠ CẤU DOANH NGHIỆP"}</p>
          <h1>SƠ ĐỒ TỔ CHỨC CÔNG TY</h1>
          <p className="muted">
            Trực quan hóa cơ cấu Ban Giám Đốc và 7 phòng ban. Dữ liệu thời gian
            thực tự động cập nhật khi cấp mới hoặc sửa tài khoản.
          </p>
        </div>
        <div className="org-chart-actions">
          {portal === "admin" && user?.roles?.includes("OPS_ADMIN") && navigate && (
            <button
              type="button"
              className="primary"
              onClick={() => navigate("identity")}
            >
              + Cấp tài khoản mới
            </button>
          )}
          <button
            type="button"
            className="secondary"
            onClick={reloadData}
            disabled={usersRes.refreshing}
            title="Tải lại dữ liệu mới nhất từ CSDL"
          >
            {usersRes.refreshing ? "Đang đồng bộ…" : "🔄 Làm mới sơ đồ"}
          </button>
        </div>
      </div>

      {/* Control & Statistics Bar */}
      <div className="panel org-chart-toolbar">
        <div className="org-chart-stats">
          <span className="stat-pill stat-total">
            Tổng nhân sự: <strong>{chartData.totalEmployees}</strong>
          </span>
          <span className="stat-pill stat-bod">
            Ban Giám Đốc:{" "}
            <strong>
              {chartData.giamDoc.length +
                chartData.admin.length +
                chartData.phoGiamDoc.length}
            </strong>
          </span>
          <span className="stat-pill stat-depts">
            Phòng ban:{" "}
            <strong>{Object.keys(chartData.departments).length}</strong>
          </span>
        </div>

        <div className="org-chart-tools">
          <div className="org-search-wrap">
            <span className="org-search-icon" aria-hidden="true">
              🔍
            </span>
            <input
              type="search"
              placeholder="Tìm kiếm nhân sự, vị trí…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="org-search-input"
            />
          </div>

          <div className="org-zoom-controls">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(0.6, z - 0.1))}
              title="Thu nhỏ"
            >
              −
            </button>
            <span className="zoom-text">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(1.4, z + 0.1))}
              title="Phóng to"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              title="Đặt lại tỉ lệ 100%"
            >
              Đặt lại
            </button>
          </div>
        </div>
      </div>

      {/* Main Diagram Area with Scaling */}
      <div className="org-canvas-viewport">
        <div
          className="org-tree-root"
          style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}
        >
          {/* SƠ ĐỒ TỔ CHỨC CÔNG TY Main Banner */}
          <div className="org-main-title">
            <h2>SƠ ĐỒ TỔ CHỨC CÔNG TY</h2>
          </div>

          {/* LEVEL 1: GIÁM ĐỐC */}
          <div className="org-level-top">
            <button
              type="button"
              className={`org-node-box org-box-director ${
                isMatch(chartData.giamDoc) ? "org-highlight" : ""
              }`}
              onClick={() =>
                handleOpenRoster(
                  "GIÁM ĐỐC",
                  "Ban Tổng Giám Đốc",
                  chartData.giamDoc,
                  "#0d6efd"
                )
              }
              aria-label="Xem chi tiết Giám Đốc"
            >
              <div className="org-node-title">GIÁM ĐỐC</div>
              <div className="org-node-count-badge">
                {chartData.giamDoc.length}
              </div>
              <div className="org-node-person">
                {chartData.giamDoc[0]?.display_name || "Chưa có"}
              </div>
            </button>

            {/* Vertical connector from Director */}
            <div className="org-stem-down" />
          </div>

          {/* LEVEL 2: ADMIN & PHÓ GIÁM ĐỐC */}
          <div className="org-level-sub-exec">
            {/* Horizontal connector bar between Admin, Center Stem, and Deputy Director */}
            <div className="org-exec-bridge" />

            <div className="org-exec-row">
              {/* ADMIN (Hành chính) */}
              <button
                type="button"
                className={`org-node-box org-box-admin ${
                  isMatch(chartData.admin) ? "org-highlight" : ""
                }`}
                onClick={() =>
                  handleOpenRoster(
                    "ADMIN (Hành chính)",
                    "Bộ phận Hành chính & Vận hành Hệ thống",
                    chartData.admin,
                    "#0d6efd"
                  )
                }
                aria-label="Xem chi tiết Admin"
              >
                <div className="org-node-title">ADMIN</div>
                <div className="org-node-subtitle">(Hành chính)</div>
                <div className="org-node-count-badge">
                  {chartData.admin.length}
                </div>
              </button>

              {/* Space for central vertical trunk */}
              <div className="org-exec-gap" />

              {/* PHÓ GIÁM ĐỐC */}
              <button
                type="button"
                className={`org-node-box org-box-deputy ${
                  isMatch(chartData.phoGiamDoc) ? "org-highlight" : ""
                }`}
                onClick={() =>
                  handleOpenRoster(
                    "PHÓ GIÁM ĐỐC",
                    "Ban Tổng Giám Đốc",
                    chartData.phoGiamDoc,
                    "#0d6efd"
                  )
                }
                aria-label="Xem chi tiết Phó Giám Đốc"
              >
                <div className="org-node-title">PHÓ GIÁM ĐỐC</div>
                <div className="org-node-count-badge">
                  {chartData.phoGiamDoc.length}
                </div>
                <div className="org-node-person">
                  {chartData.phoGiamDoc[0]?.display_name || "Trần Thị Bích Ngọc"}
                </div>
              </button>
            </div>

            {/* Central trunk line down to departments bus */}
            <div className="org-trunk-down" />
          </div>

          {/* LEVEL 3: 7 DEPARTMENTS ROW */}
          <div className="org-depts-container">
            {/* Horizontal Bus Line linking all 7 departments */}
            <div className="org-depts-bus-line" />

            <div className="org-depts-grid">
              {ORDERED_DEPT_KEYS.map((key) => {
                const dept = chartData.departments[key];
                if (!dept) return null;
                const cfg = dept.config;
                const deptMatch =
                  isMatch(dept.truongNhom) || isMatch(dept.nhanVien);

                return (
                  <div key={key} className="org-dept-column">
                    {/* Vertical drop line from bus to department card */}
                    <div className="org-dept-drop-line" />

                    {/* Department Header Card */}
                    <button
                      type="button"
                      className={`org-dept-header-card org-dept-${cfg.theme} ${
                        deptMatch ? "org-highlight" : ""
                      }`}
                      style={{
                        backgroundColor: cfg.bg,
                        borderColor: cfg.border,
                        color: cfg.textColor,
                      }}
                      onClick={() =>
                        handleOpenRoster(
                          cfg.name,
                          `Toàn bộ nhân sự phòng ban (${dept.total} nhân sự)`,
                          [...dept.truongNhom, ...dept.nhanVien],
                          cfg.badgeBg
                        )
                      }
                      aria-label={`Xem chi tiết phòng ban ${cfg.name}`}
                    >
                      <div className="org-dept-title">{cfg.name}</div>
                      <div
                        className="org-dept-badge"
                        style={{ backgroundColor: cfg.badgeBg }}
                      >
                        {dept.total}
                      </div>
                    </button>

                    {/* Stem down to Sub-positions */}
                    <div className="org-branch-stem" />

                    {/* LEVEL 4: TRƯỞNG NHÓM */}
                    <button
                      type="button"
                      className={`org-sub-node org-node-lead ${
                        isMatch(dept.truongNhom) ? "org-highlight" : ""
                      }`}
                      style={{
                        backgroundColor: cfg.bg,
                        borderColor: cfg.border,
                        color: cfg.textColor,
                      }}
                      onClick={() =>
                        handleOpenRoster(
                          `TRƯỞNG NHÓM · ${cfg.name}`,
                          "Quản lý / Trưởng nhóm",
                          dept.truongNhom,
                          cfg.badgeBg
                        )
                      }
                      aria-label={`Xem chi tiết Trưởng nhóm ${cfg.name}`}
                    >
                      <div className="org-sub-title">TRƯỞNG NHÓM</div>
                      <div
                        className="org-sub-badge"
                        style={{ backgroundColor: cfg.badgeBg }}
                      >
                        {dept.truongNhom.length}
                      </div>
                      {dept.truongNhom.length > 0 && (
                        <div className="org-sub-preview">
                          {dept.truongNhom[0]?.display_name}
                          {dept.truongNhom.length > 1 &&
                            ` (+${dept.truongNhom.length - 1})`}
                        </div>
                      )}
                    </button>

                    {/* Vertical connector down to Nhân viên */}
                    <div className="org-sub-link-line" />

                    {/* LEVEL 5: NHÂN VIÊN (Phó phòng đã được bỏ hoàn toàn) */}
                    <button
                      type="button"
                      className={`org-sub-node org-node-staff ${
                        isMatch(dept.nhanVien) ? "org-highlight" : ""
                      }`}
                      style={{
                        backgroundColor: cfg.bg,
                        borderColor: cfg.border,
                        color: cfg.textColor,
                      }}
                      onClick={() =>
                        handleOpenRoster(
                          `NHÂN VIÊN · ${cfg.name}`,
                          "Nhân viên phòng ban",
                          dept.nhanVien,
                          cfg.badgeBg
                        )
                      }
                      aria-label={`Xem chi tiết Nhân viên ${cfg.name}`}
                    >
                      <div className="org-sub-title">NHÂN VIÊN</div>
                      <div
                        className="org-sub-badge"
                        style={{ backgroundColor: cfg.badgeBg }}
                      >
                        {dept.nhanVien.length}
                      </div>
                      <div className="org-sub-preview">
                        {dept.nhanVien.length} nhân sự
                      </div>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Member Roster Modal */}
      {selectedNode && (
        <div
          className="org-modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedNode(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setSelectedNode(null);
          }}
          role="presentation"
        >
          <div
            className="org-modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="org-modal-title"
          >
            <div className="org-modal-header">
              <div>
                <h3
                  id="org-modal-title"
                  style={{ color: selectedNode.themeColor }}
                >
                  {selectedNode.title}
                </h3>
                <p className="muted">{selectedNode.subtitle}</p>
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

            <div className="org-modal-body">
              {selectedNode.members.length === 0 ? (
                <div className="empty muted" style={{ padding: "32px 0" }}>
                  Hiện chưa có nhân sự nào được phân bổ vào vị trí này.
                </div>
              ) : (
                <div className="org-roster-list">
                  {selectedNode.members.map((u) => (
                    <div key={u.id} className="org-roster-item">
                      <div className="org-roster-avatar">
                        {(u.display_name || u.username || "E")
                          .slice(0, 1)
                          .toUpperCase()}
                      </div>
                      <div className="org-roster-info">
                        <strong>{u.display_name}</strong>
                        <small className="org-roster-uname">
                          @{u.username}
                        </small>
                      </div>
                      <div className="org-roster-status">
                        <span className="status-tag active">Hoạt động</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="org-modal-footer">
              <span className="muted">
                Tổng cộng: <strong>{selectedNode.members.length}</strong> nhân
                sự
              </span>
              {navigate && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setSelectedNode(null);
                    navigate("identity");
                  }}
                >
                  Quản lý trong Danh tính & phân quyền →
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

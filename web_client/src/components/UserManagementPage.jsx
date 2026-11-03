import { useState, useMemo } from "react";
import { useApiBase } from "../apiBase.js";
import { api } from "../api.js";
import { useResource, ResourceState } from "./ui.jsx";
import { usePermission } from "../hooks/usePermission.jsx";

export default function UserManagementPage({ onNavigateOrgChart }) {
  const apiBase = useApiBase();
  const userPerms = usePermission("users");
  const canCreate = userPerms.canCreate;
  const canUpdate = userPerms.canUpdate;
  const canDelete = userPerms.canDelete;

  // Search & filters
  const [searchTerm, setSearchTerm] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // Data fetching
  const usersRes = useResource(
    `${apiBase}/users-management?limit=200&t=${refreshKey}`
  );
  const rolesRes = useResource(`${apiBase}/rbac/roles`);
  const deptsRes = useResource(`${apiBase}/departments?limit=100`);

  // Modals state
  const [selectedUserForDetail, setSelectedUserForDetail] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [leaveModalUser, setLeaveModalUser] = useState(null);
  const [leaveType, setLeaveType] = useState("BUSINESS_TRIP");
  const [leaveReason, setLeaveReason] = useState("Công tác khách hàng ngoại tỉnh");
  const [leaveSubmitting, setLeaveSubmitting] = useState(false);

  const [editUserModal, setEditUserModal] = useState(null);
  const [isNewUser, setIsNewUser] = useState(false);
  const [userFormData, setUserFormData] = useState({
    full_name: "",
    email: "",
    job_title: "",
    role_id: "",
    department_id: "",
    password: "",
  });
  const [userSubmitting, setUserSubmitting] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg, type = "success") => {
    setToastMessage({ msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Open 5-stage drilldown modal
  const handleOpenDrilldown = async (user) => {
    setSelectedUserForDetail(user);
    setLoadingDetail(true);
    try {
      const res = await api(`${apiBase}/users-management/${user.id}/requests-detail`);
      setDetailData(res);
    } catch (err) {
      showToast("Không thể tải chi tiết hồ sơ: " + (err.message || err), "error");
    } finally {
      setLoadingDetail(false);
    }
  };

  // Quick leave/trip status update
  const handleLeaveTripSubmit = async (action) => {
    if (!leaveModalUser) return;
    setLeaveSubmitting(true);
    try {
      const payload = {
        action,
        type: leaveType,
        reason: leaveReason,
      };
      const res = await api(
        `${apiBase}/users-management/${leaveModalUser.id}/leave-trip`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
      showToast(
        action === "CANCEL_TODAY"
          ? `Đã xóa lịch trình hôm nay của ${leaveModalUser.full_name}, trạng thái trở về Đang làm!`
          : `Đã cập nhật trạng thái của ${leaveModalUser.full_name} thành: ${res.status_label}!`,
        "success"
      );
      setLeaveModalUser(null);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      showToast("Lỗi cập nhật trạng thái: " + (err.message || err), "error");
    } finally {
      setLeaveSubmitting(false);
    }
  };

  // Toggle user lock
  const handleToggleLock = async (user) => {
    if (!window.confirm(`Bạn có chắc muốn ${user.is_active ? "KHÓA" : "MỞ KHÓA"} tài khoản ${user.full_name}?`)) {
      return;
    }
    try {
      await api(`${apiBase}/users-management/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      showToast(`Đã ${user.is_active ? "khóa" : "mở khóa"} người dùng thành công!`, "success");
      setRefreshKey((k) => k + 1);
    } catch (err) {
      showToast("Lỗi thay đổi trạng thái tài khoản: " + (err.message || err), "error");
    }
  };

  // Save add/edit user
  const handleSaveUser = async (e) => {
    e.preventDefault();
    setUserSubmitting(true);
    try {
      if (isNewUser) {
        await api(`${apiBase}/users-management`, {
          method: "POST",
          body: JSON.stringify(userFormData),
        });
        showToast("Tạo người dùng mới thành công!", "success");
      } else {
        await api(`${apiBase}/users-management/${editUserModal.id}`, {
          method: "PATCH",
          body: JSON.stringify(userFormData),
        });
        showToast("Cập nhật thông tin người dùng thành công!", "success");
      }
      setEditUserModal(null);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      showToast("Lỗi lưu người dùng: " + (err.message || err), "error");
    } finally {
      setUserSubmitting(false);
    }
  };

  // Filtered list
  const userList = useMemo(() => {
    const raw = usersRes.data?.items || [];
    return raw.filter((u) => {
      if (searchTerm) {
        const q = searchTerm.toLowerCase();
        const matchName = u.full_name?.toLowerCase().includes(q);
        const matchEmail = u.email?.toLowerCase().includes(q);
        const matchCode = u.employee_code?.toLowerCase().includes(q);
        if (!matchName && !matchEmail && !matchCode) return false;
      }
      if (deptFilter && u.department_id !== deptFilter) {
        return false;
      }
      if (statusFilter) {
        if (statusFilter === "INACTIVE" && u.is_active) return false;
        if (statusFilter !== "INACTIVE") {
          if (!u.is_active) return false;
          if (u.working_status_code !== statusFilter) return false;
        }
      }
      return true;
    });
  }, [usersRes.data, searchTerm, deptFilter, statusFilter]);

  // Overall status counts
  const summaryCounts = useMemo(() => {
    const items = usersRes.data?.items || [];
    let working = 0, leave = 0, trip = 0, locked = 0;
    items.forEach((u) => {
      if (!u.is_active) locked++;
      else if (u.working_status_code === "CONG_TAC") trip++;
      else if (u.working_status_code === "NGHI_LAM") leave++;
      else working++;
    });
    return { total: items.length, working, leave, trip, locked };
  }, [usersRes.data]);

  return (
    <div className="users-management-page">
      {/* Toast Notification */}
      {toastMessage && (
        <div className={`notification-toast ${toastMessage.type}`} role="alert">
          {toastMessage.msg}
        </div>
      )}

      {/* Page Header */}
      <div className="page-heading">
        <div>
          <p className="eyebrow">TỔ CHỨC & NHÂN SỰ</p>
          <h1>Quản lý Người dùng & Trạng thái làm việc</h1>
          <p className="muted">
            Theo dõi trạng thái làm việc thực tế (08:00 - 17:30 T2-T6), quản lý chức danh và tra cứu tiến độ 5 giai đoạn hồ sơ.
          </p>
        </div>
        <div className="page-heading-actions">
          {onNavigateOrgChart && (
            <button
              type="button"
              className="secondary"
              onClick={onNavigateOrgChart}
              title="Xem Sơ đồ cây tổ chức công ty"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="3" width="6" height="4" rx="1" />
                <rect x="2" y="17" width="6" height="4" rx="1" />
                <rect x="16" y="17" width="6" height="4" rx="1" />
                <path d="M12 7v5m0 0H5v5m7-5h7v5" />
              </svg>
              <span>Xem Sơ đồ tổ chức</span>
            </button>
          )}
          {canCreate && (
            <button
              type="button"
              className="primary"
              onClick={() => {
                setIsNewUser(true);
                setUserFormData({
                  full_name: "",
                  email: "",
                  job_title: "Chuyên viên",
                  role_id: rolesRes.data?.items?.[2]?.id || "",
                  department_id: deptsRes.data?.items?.[0]?.id || "",
                  password: "User@123456",
                });
                setEditUserModal({});
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span>Thêm người dùng</span>
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards: Real-time Status Breakdown */}
      <div className="kpi-grid-4">
        <div className="kpi-card" role="button" tabIndex={0} onClick={() => setStatusFilter("")} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setStatusFilter("")} style={{ cursor: "pointer" }}>
          <div className="kpi-title">Tổng nhân sự</div>
          <div className="kpi-value text-blue">{summaryCounts.total}</div>
          <div className="kpi-subtitle">Toàn bộ nhân sự hệ thống</div>
        </div>
        <div className="kpi-card" role="button" tabIndex={0} onClick={() => setStatusFilter("DANG_LAM")} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setStatusFilter("DANG_LAM")} style={{ cursor: "pointer" }}>
          <div className="kpi-title">Đang làm việc</div>
          <div className="kpi-value text-green">{summaryCounts.working}</div>
          <div className="kpi-subtitle">Tại văn phòng (08:00 - 17:30)</div>
        </div>
        <div className="kpi-card" role="button" tabIndex={0} onClick={() => setStatusFilter("NGHI_LAM")} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setStatusFilter("NGHI_LAM")} style={{ cursor: "pointer" }}>
          <div className="kpi-title">Nghỉ làm / Vắng</div>
          <div className="kpi-value text-amber">{summaryCounts.leave}</div>
          <div className="kpi-subtitle">Phép, không lương, đi muộn/sớm</div>
        </div>
        <div className="kpi-card" role="button" tabIndex={0} onClick={() => setStatusFilter("CONG_TAC")} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setStatusFilter("CONG_TAC")} style={{ cursor: "pointer" }}>
          <div className="kpi-title">Đi công tác</div>
          <div className="kpi-value text-cyan">{summaryCounts.trip}</div>
          <div className="kpi-subtitle">Đã duyệt Business Trip</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="table-filter-bar">
        <div className="search-input-wrap">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="search"
            placeholder="Tìm theo họ tên, email, mã nhân viên..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <select
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          className="filter-select"
        >
          <option value="">— Tất cả phòng ban —</option>
          {(deptsRes.data?.items || []).map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.code})
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="filter-select"
        >
          <option value="">— Tất cả trạng thái —</option>
          <option value="DANG_LAM">🟢 Đang làm việc</option>
          <option value="NGHI_LAM">🟡 Nghỉ phép / Vắng</option>
          <option value="CONG_TAC">🔵 Đi công tác</option>
          <option value="INACTIVE">🔴 Bị khóa</option>
        </select>

        {(searchTerm || deptFilter || statusFilter) && (
          <button
            type="button"
            className="secondary text-btn"
            onClick={() => {
              setSearchTerm("");
              setDeptFilter("");
              setStatusFilter("");
            }}
          >
            Đặt lại lọc
          </button>
        )}
      </div>

      {/* Main Table */}
      <ResourceState resource={usersRes}>
        <div className="table-wrap">
          <table className="user-management-table">
            <thead>
              <tr>
                <th>Nhân viên</th>
                <th>Chức danh / Vai trò</th>
                <th>Phòng ban</th>
                <th>Trạng thái làm việc</th>
                <th style={{ textAlign: "center" }}>Hồ sơ tham gia</th>
                <th style={{ textAlign: "right" }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {userList.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "3rem", color: "#64748b" }}>
                    Không tìm thấy nhân viên nào phù hợp với bộ lọc.
                  </td>
                </tr>
              ) : (
                userList.map((u) => {
                  const isLocked = !u.is_active;
                  const isWorking = u.working_status_code === "DANG_LAM";
                  const isLeave = u.working_status_code === "NGHI_LAM";
                  const isTrip = u.working_status_code === "CONG_TAC";

                  return (
                    <tr key={u.id} className={isLocked ? "row-locked" : ""}>
                      {/* Name & Avatar */}
                      <td>
                        <div className="user-profile-cell">
                          <div className={`user-avatar-circle ${isWorking ? "border-green" : isLeave ? "border-amber" : isTrip ? "border-blue" : "border-gray"}`}>
                            {u.full_name?.charAt(0) || "U"}
                          </div>
                          <div>
                            <div className="user-full-name">
                              <strong>{u.full_name}</strong>
                              {isLocked && <span className="badge badge-locked">Đã khóa</span>}
                            </div>
                            <div className="user-meta-sub">
                              <span>{u.employee_code || "—"}</span> • <span>{u.email}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Job Title / Role */}
                      <td>
                        <div className="role-badge-cell">
                          <span className="badge badge-role">{u.role_name || u.role_code}</span>
                          <div className="job-title-sub">{u.job_title || "Nhân viên"}</div>
                        </div>
                      </td>

                      {/* Department */}
                      <td>
                        <span className="dept-tag">{u.department_name || "—"}</span>
                      </td>

                      {/* Real-time Status Badge */}
                      <td>
                        <div className="status-badge-container">
                          {isLocked ? (
                            <span className="status-badge status-locked">
                              <span className="dot dot-red"></span> Tài khoản khóa
                            </span>
                          ) : isWorking ? (
                            <span className="status-badge status-working" title={u.working_status_detail}>
                              <span className="dot dot-green"></span> Đang làm
                            </span>
                          ) : isLeave ? (
                            <span className="status-badge status-leave" title={u.working_status_detail}>
                              <span className="dot dot-amber"></span> Nghỉ làm
                            </span>
                          ) : (
                            <span className="status-badge status-trip" title={u.working_status_detail}>
                              <span className="dot dot-blue"></span> Công tác
                            </span>
                          )}
                          <div className="status-detail-hint">
                            {isLocked ? "Không thể đăng nhập" : u.working_status_detail}
                          </div>
                        </div>
                      </td>

                      {/* 5-Stage Requests Drilldown Trigger */}
                      <td style={{ textAlign: "center" }}>
                        <button
                          type="button"
                          className="drilldown-badge-btn"
                          onClick={() => handleOpenDrilldown(u)}
                          title="Bấm để xem chi tiết 5 giai đoạn hồ sơ tham gia"
                        >
                          <span className="drilldown-count">{u.total_involved_requests || 0}</span>
                          <span className="drilldown-label">hồ sơ</span>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="m9 18 6-6-6-6" />
                          </svg>
                        </button>
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: "right" }}>
                        <div className="action-buttons-wrap">
                          {/* Quick Leave / Trip Update */}
                          <button
                            type="button"
                            className="btn-icon-subtle"
                            onClick={() => {
                              setLeaveModalUser(u);
                              setLeaveType("BUSINESS_TRIP");
                              setLeaveReason("Công tác đối tác ngoại tỉnh");
                            }}
                            title="Cập nhật đơn nghỉ / công tác (Đổi trạng thái tức thì)"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                              <line x1="16" y1="2" x2="16" y2="6" />
                              <line x1="8" y1="2" x2="8" y2="6" />
                              <line x1="3" y1="10" x2="21" y2="10" />
                            </svg>
                          </button>

                          {/* Edit user button */}
                          {canUpdate && (
                            <button
                              type="button"
                              className="btn-icon-subtle"
                              onClick={() => {
                                setIsNewUser(false);
                                setUserFormData({
                                  full_name: u.full_name || "",
                                  email: u.email || "",
                                  job_title: u.job_title || "",
                                  role_id: u.role_id || "",
                                  department_id: u.department_id || "",
                                  password: "",
                                });
                                setEditUserModal(u);
                              }}
                              title="Chỉnh sửa thông tin"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M12 20h9" />
                                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                              </svg>
                            </button>
                          )}

                          {/* Lock / Unlock button */}
                          {canDelete && (
                            <button
                              type="button"
                              className={`btn-icon-subtle ${isLocked ? "text-green" : "text-red"}`}
                              onClick={() => handleToggleLock(u)}
                              title={isLocked ? "Mở khóa tài khoản" : "Khóa tài khoản"}
                            >
                              {isLocked ? (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                  <path d="M7 11V7a5 5 0 0 1 9.9-1" />
                                </svg>
                              ) : (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                                </svg>
                              )}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </ResourceState>

      {/* MODAL 1: 5-Stage Requests Drill-down Drawer */}
      {selectedUserForDetail && (
        <div className="drawer-overlay" role="presentation" onClick={(e) => e.target === e.currentTarget && setSelectedUserForDetail(null)} onKeyDown={(e) => e.key === "Escape" && setSelectedUserForDetail(null)}>
          <div className="drawer-panel" role="dialog" aria-modal="true">
            <div className="drawer-header">
              <div>
                <p className="eyebrow">HỒ SƠ THAM GIA</p>
                <h2>{selectedUserForDetail.full_name}</h2>
                <p className="muted">
                  {selectedUserForDetail.job_title} • {selectedUserForDetail.department_name} • {selectedUserForDetail.email}
                </p>
              </div>
              <button
                type="button"
                className="drawer-close-btn"
                onClick={() => setSelectedUserForDetail(null)}
              >
                ✕
              </button>
            </div>

            <div className="drawer-content">
              {loadingDetail ? (
                <div style={{ textAlign: "center", padding: "3rem" }}>Đang tải danh sách hồ sơ...</div>
              ) : (
                <>
                  {/* 5 Stages KPI Grid */}
                  <div className="stage-cards-grid">
                    <div className="stage-card stage-1">
                      <div className="stage-num">Giai đoạn 1</div>
                      <div className="stage-title">Yêu cầu</div>
                      <div className="stage-count">
                        {detailData?.summary?.stage_1_yeu_cau || 0}
                      </div>
                    </div>
                    <div className="stage-card stage-2">
                      <div className="stage-num">Giai đoạn 2</div>
                      <div className="stage-title">Phê duyệt</div>
                      <div className="stage-count">
                        {detailData?.summary?.stage_2_phe_duyet || 0}
                      </div>
                    </div>
                    <div className="stage-card stage-3">
                      <div className="stage-num">Giai đoạn 3</div>
                      <div className="stage-title">Thực hiện</div>
                      <div className="stage-count">
                        {detailData?.summary?.stage_3_thuc_hien || 0}
                      </div>
                    </div>
                    <div className="stage-card stage-4">
                      <div className="stage-num">Giai đoạn 4</div>
                      <div className="stage-title">Nghiệm thu</div>
                      <div className="stage-count">
                        {detailData?.summary?.stage_4_nghiem_thu || 0}
                      </div>
                    </div>
                    <div className="stage-card stage-5">
                      <div className="stage-num">Giai đoạn 5</div>
                      <div className="stage-title">Hoàn thành</div>
                      <div className="stage-count">
                        {detailData?.summary?.stage_5_hoan_thanh || 0}
                      </div>
                    </div>
                  </div>

                  {/* Requests Table */}
                  <h3 style={{ marginTop: "1.5rem", marginBottom: "0.75rem", fontSize: "1rem" }}>
                    Danh sách yêu cầu tham gia ({detailData?.items?.length || 0})
                  </h3>
                  <div className="table-wrap" style={{ maxHeight: "350px", overflowY: "auto" }}>
                    <table className="stage-detail-table">
                      <thead>
                        <tr>
                          <th>Mã yêu cầu</th>
                          <th>Tiêu đề & Tóm tắt</th>
                          <th>Phân loại</th>
                          <th>Giai đoạn hiện tại</th>
                          <th>Vai trò tham gia</th>
                          <th>Ngày tạo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(!detailData?.items || detailData.items.length === 0) ? (
                          <tr>
                            <td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>
                              Nhân viên này chưa tham gia hồ sơ nào trong hệ thống.
                            </td>
                          </tr>
                        ) : (
                          detailData.items.map((r) => (
                            <tr key={r.request_id || r.id}>
                              <td>
                                <strong>{r.request_code || r.code}</strong>
                              </td>
                              <td>
                                <div style={{ fontWeight: 500 }}>{r.title}</div>
                                {r.summary && <div className="muted" style={{ fontSize: "0.75rem" }}>{r.summary}</div>}
                              </td>
                              <td>
                                <span className={`badge-category category-${r.category_code?.toLowerCase()}`}>
                                  {r.category_name || "Phổ thông"}
                                </span>
                              </td>
                              <td>
                                <span className="stage-tag">
                                  {r.current_stage_label}
                                </span>
                              </td>
                              <td>
                                <span className="badge badge-role-involved">
                                  {r.user_role_in_request}
                                </span>
                              </td>
                              <td style={{ whiteSpace: "nowrap", fontSize: "0.8rem", color: "#64748b" }}>
                                {r.created_at ? new Date(r.created_at).toLocaleDateString("vi-VN") : "—"}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Quick Leave / Trip Update */}
      {leaveModalUser && (
        <div className="modal-backdrop" role="presentation" onClick={(e) => e.target === e.currentTarget && setLeaveModalUser(null)} onKeyDown={(e) => e.key === "Escape" && setLeaveModalUser(null)}>
          <div className="modal-card" role="dialog" aria-modal="true" style={{ maxWidth: "520px" }}>
            <div className="modal-head">
              <h2>Cập nhật trạng thái làm việc</h2>
              <button type="button" className="secondary ds-icon-button" onClick={() => setLeaveModalUser(null)}>
                ✕
              </button>
            </div>
            <p className="muted" style={{ marginTop: "0.25rem", marginBottom: "1rem" }}>
              Nhân viên: <strong>{leaveModalUser.full_name}</strong> ({leaveModalUser.email})
            </p>

            <div className="form-group">
              <label htmlFor="usermanagementpage-field-648">Loại hình đăng ký (Được duyệt ngay để kiểm thử logic):</label>
              <select id="usermanagementpage-field-648"
                value={leaveType}
                onChange={(e) => setLeaveType(e.target.value)}
                className="input-select"
              >
                <option value="BUSINESS_TRIP">🔵 Công tác (Business Trip) → Badge Xanh dương</option>
                <option value="PAID_LEAVE">🟡 Nghỉ phép có lương (Paid Leave) → Badge Vàng</option>
                <option value="UNPAID_LEAVE">🟡 Nghỉ không lương (Unpaid Leave) → Badge Vàng</option>
                <option value="LATE_IN">🟡 Đi muộn (Late In) → Badge Vàng</option>
                <option value="EARLY_OUT">🟡 Về sớm (Early Out) → Badge Vàng</option>
              </select>
            </div>

            <div className="form-group" style={{ marginTop: "1rem" }}>
              <label htmlFor="usermanagementpage-field-663">Lý do / Nội dung tóm tắt:</label>
              <input id="usermanagementpage-field-663"
                type="text"
                value={leaveReason}
                onChange={(e) => setLeaveReason(e.target.value)}
                placeholder="Nhập lý do nghỉ hoặc điểm đến công tác..."
                className="input-text"
              />
            </div>

            <div className="modal-actions" style={{ marginTop: "1.5rem", display: "flex", justifyContent: "space-between" }}>
              <button
                type="button"
                className="secondary"
                disabled={leaveSubmitting}
                onClick={() => handleLeaveTripSubmit("CANCEL_TODAY")}
                title="Hủy các lịch trình hôm nay để trở về trạng thái Đang làm việc mặc định"
              >
                🔄 Xóa đơn hôm nay (về Đang làm)
              </button>

              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  disabled={leaveSubmitting}
                  onClick={() => setLeaveModalUser(null)}
                >
                  Hủy
                </button>
                <button
                  type="button"
                  className="primary"
                  disabled={leaveSubmitting}
                  onClick={() => handleLeaveTripSubmit("CREATE")}
                >
                  {leaveSubmitting ? "Đang lưu..." : "Áp dụng ngay"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: Add / Edit User Modal */}
      {editUserModal && (
        <div className="modal-backdrop" role="presentation" onClick={(e) => e.target === e.currentTarget && setEditUserModal(null)} onKeyDown={(e) => e.key === "Escape" && setEditUserModal(null)}>
          <div className="modal-card" role="dialog" aria-modal="true" style={{ maxWidth: "560px" }}>
            <div className="modal-head">
              <h2>{isNewUser ? "Thêm người dùng mới" : "Chỉnh sửa người dùng"}</h2>
              <button type="button" className="secondary ds-icon-button" onClick={() => setEditUserModal(null)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveUser}>
              <div className="form-group" style={{ marginTop: "1rem" }}>
                <label htmlFor="usermanagementpage-field-720">Họ và tên *</label>
                <input id="usermanagementpage-field-720"
                  type="text"
                  required
                  value={userFormData.full_name}
                  onChange={(e) => setUserFormData({ ...userFormData, full_name: e.target.value })}
                  placeholder="Ví dụ: Nguyễn Văn An"
                  className="input-text"
                />
              </div>

              <div className="form-group" style={{ marginTop: "0.75rem" }}>
                <label htmlFor="usermanagementpage-field-732">Email công vụ *</label>
                <input id="usermanagementpage-field-732"
                  type="email"
                  required
                  disabled={!isNewUser}
                  value={userFormData.email}
                  onChange={(e) => setUserFormData({ ...userFormData, email: e.target.value })}
                  placeholder="an.nguyen@eas.com"
                  className="input-text"
                />
              </div>

              {isNewUser && (
                <div className="form-group" style={{ marginTop: "0.75rem" }}>
                  <label htmlFor="usermanagementpage-field-746">Mật khẩu khởi tạo *</label>
                  <input id="usermanagementpage-field-746"
                    type="password"
                    required
                    value={userFormData.password}
                    onChange={(e) => setUserFormData({ ...userFormData, password: e.target.value })}
                    className="input-text"
                  />
                </div>
              )}

              <div className="form-grid-2" style={{ marginTop: "0.75rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label htmlFor="usermanagementpage-field-759">Chức danh hiển thị</label>
                  <input id="usermanagementpage-field-759"
                    type="text"
                    value={userFormData.job_title}
                    onChange={(e) => setUserFormData({ ...userFormData, job_title: e.target.value })}
                    placeholder="Ví dụ: Kỹ sư phần mềm"
                    className="input-text"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="usermanagementpage-field-770">Chức vụ (Vai trò RBAC) *</label>
                  <select id="usermanagementpage-field-770"
                    required
                    value={userFormData.role_id}
                    onChange={(e) => setUserFormData({ ...userFormData, role_id: e.target.value })}
                    className="input-select"
                  >
                    <option value="">— Chọn vai trò —</option>
                    {(rolesRes.data?.items || []).map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} ({r.code})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group" style={{ marginTop: "0.75rem" }}>
                <label htmlFor="usermanagementpage-field-788">Phòng ban trực thuộc *</label>
                <select id="usermanagementpage-field-788"
                  required
                  value={userFormData.department_id}
                  onChange={(e) => setUserFormData({ ...userFormData, department_id: e.target.value })}
                  className="input-select"
                >
                  <option value="">— Chọn phòng ban —</option>
                  {(deptsRes.data?.items || []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="modal-actions" style={{ marginTop: "1.5rem", display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  disabled={userSubmitting}
                  onClick={() => setEditUserModal(null)}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="primary"
                  disabled={userSubmitting}
                >
                  {userSubmitting ? "Đang lưu..." : isNewUser ? "Tạo người dùng" : "Lưu thay đổi"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


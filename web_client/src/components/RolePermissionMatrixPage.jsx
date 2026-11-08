import { useState, useEffect } from "react";
import { errorText } from "../domain.js";
import { api } from "../api.js";
import { useResource } from "./ui.jsx";
import { notifyPermissionsChanged } from "../sessionRefresh.js";

const SYSTEM_LOCKED_MODULES = new Set([
  "permissions",
  "ai_engine",
  "api_management",
  "system_versions",
]);

export default function RolePermissionMatrixPage() {
  const [activeTab, setActiveTab] = useState("role"); // "role" | "user"
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [matrixData, setMatrixData] = useState(null);
  const [savingKey, setSavingKey] = useState(null); // module_code + action

  // User override state
  const [selectedUserId, setSelectedUserId] = useState("");
  const [userMatrixData, setUserMatrixData] = useState(null);

  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg, type = "success") => {
    setToastMessage({ msg, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Fetch roles and users list
  const rolesRes = useResource("/api/v1/admin/rbac/roles");
  const usersRes = useResource("/api/v1/admin/users-management?limit=200");

  // First role is the default selection; loading flags derive from the fetched data.
  const roleId = selectedRoleId || rolesRes.data?.items?.[0]?.id || "";
  const loadingMatrix = Boolean(roleId) && matrixData?.role_id !== roleId;
  const loadingUserMatrix = Boolean(selectedUserId) && userMatrixData?.user?.id !== selectedUserId;

  // Fetch role matrix whenever the role changes
  useEffect(() => {
    if (!roleId) return;
    api(`/api/v1/admin/rbac/matrix?role_id=${roleId}`)
      .then(setMatrixData)
      .catch((err) => {
        showToast("Không thể tải ma trận phân quyền: " + errorText(err), "error");
      });
  }, [roleId]);

  // Fetch user override matrix whenever selectedUserId changes
  useEffect(() => {
    if (!selectedUserId) return;
    api(`/api/v1/admin/rbac/user-permissions/${selectedUserId}`)
      .then(setUserMatrixData)
      .catch((err) => {
        showToast("Không thể tải quyền riêng người dùng: " + errorText(err), "error");
      });
  }, [selectedUserId]);

  // Toggle permission for a role
  const handleToggleRolePermission = async (moduleCode, action, currentValue) => {
    if (SYSTEM_LOCKED_MODULES.has(moduleCode)) {
      showToast("Chức năng hệ thống/cấu hình này bị khóa cứng, không thể phân quyền!", "error");
      return;
    }
    const newValue = !currentValue;
    const saveKey = `${moduleCode}_${action}`;
    setSavingKey(saveKey);

    // Optimistic UI update
    setMatrixData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        modules: prev.modules.map((m) => {
          if (m.code === moduleCode) {
            return { ...m, [action]: newValue };
          }
          return m;
        }),
      };
    });

    try {
      await api("/api/v1/admin/rbac/role-permission", {
        method: "POST",
        body: JSON.stringify({
          role_id: roleId,
          module_code: moduleCode,
          field: action,
          value: newValue,
        }),
      });
      showToast(`Đã lưu quyền "${moduleCode} - ${action}" cho chức vụ!`, "success");
      notifyPermissionsChanged();
    } catch (err) {
      showToast("Lỗi cập nhật quyền: " + errorText(err), "error");
      // Revert optimistic update
      setMatrixData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          modules: prev.modules.map((m) => {
            if (m.code === moduleCode) {
              return { ...m, [action]: currentValue };
            }
            return m;
          }),
        };
      });
    } finally {
      setSavingKey(null);
    }
  };

  // Toggle user override permission
  const handleToggleUserPermission = async (moduleCode, action, currentValue) => {
    if (SYSTEM_LOCKED_MODULES.has(moduleCode)) {
      showToast("Chức năng hệ thống/cấu hình này bị khóa cứng, không thể phân quyền!", "error");
      return;
    }
    const newValue = !currentValue;
    const saveKey = `user_${moduleCode}_${action}`;
    setSavingKey(saveKey);

    // Optimistic UI update
    setUserMatrixData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        modules: prev.modules.map((m) => {
          if (m.code === moduleCode) {
            return { ...m, [action]: newValue, is_user_override: true };
          }
          return m;
        }),
      };
    });

    try {
      await api("/api/v1/admin/rbac/user-permission", {
        method: "POST",
        body: JSON.stringify({
          user_id: selectedUserId,
          module_code: moduleCode,
          field: action,
          value: newValue,
        }),
      });
      showToast(`Đã cập nhật quyền riêng "${moduleCode} - ${action}" cho nhân viên!`, "success");
      notifyPermissionsChanged();
    } catch (err) {
      showToast("Lỗi cập nhật quyền riêng: " + errorText(err), "error");
      // Revert
      setUserMatrixData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          modules: prev.modules.map((m) => {
            if (m.code === moduleCode) {
              return { ...m, [action]: currentValue };
            }
            return m;
          }),
        };
      });
    } finally {
      setSavingKey(null);
    }
  };

  // Reset user permissions to role defaults
  const handleResetUserPermissions = async () => {
    if (!window.confirm("Bạn có chắc chắn muốn khôi phục quyền mặc định theo chức vụ cho nhân viên này?")) {
      return;
    }
    try {
      await api(`/api/v1/admin/rbac/user-permission/${selectedUserId}/reset`, {
        method: "POST",
      });
      showToast("Đã khôi phục quyền mặc định thành công!", "success");
      // Refetch user matrix
      const res = await api(`/api/v1/admin/rbac/user-permissions/${selectedUserId}`);
      setUserMatrixData(res);
      notifyPermissionsChanged();
    } catch (err) {
      showToast("Lỗi khôi phục quyền: " + errorText(err), "error");
    }
  };

  const filteredUsers = usersRes.data?.items || [];

  return (
    <div className="rbac-matrix-page">
      {/* Toast Notification */}
      {toastMessage && (
        <div className={`notification-toast ${toastMessage.type}`} role="alert">
          {toastMessage.msg}
        </div>
      )}

      {/* Page Heading */}
      <div className="page-heading">
        <div>
          <p className="eyebrow">TỔ CHỨC & NHÂN SỰ</p>
          <h1>Ma trận Phân quyền (RBAC Matrix)</h1>
          <p className="muted">
            Quản trị quyền Xem (can_view), Thêm (can_create), Sửa (can_update) và Xóa (can_delete) cho 9 chức năng hệ thống theo Chức vụ hoặc cấp quyền riêng cho từng nhân viên.
          </p>
        </div>
        <div className="page-heading-actions">
          <div className="tab-group-pills">
            <button
              type="button"
              className={`pill-tab ${activeTab === "role" ? "active" : ""}`}
              onClick={() => setActiveTab("role")}
            >
              Ma trận theo Chức vụ
            </button>
            <button
              type="button"
              className={`pill-tab ${activeTab === "user" ? "active" : ""}`}
              onClick={() => setActiveTab("user")}
            >
              Cấp quyền riêng Nhân viên
            </button>
          </div>
        </div>
      </div>

      {/* TAB 1: ROLE RBAC MATRIX */}
      {activeTab === "role" && (
        <div className="rbac-role-section">
          {/* Role Selector Tabs */}
          <div className="role-selector-bar">
            <span className="role-selector-label">Chọn Chức vụ / Vai trò:</span>
            <div className="role-pill-list">
              {(rolesRes.data?.items || []).map((r) => {
                const isActive = r.id === roleId;
                return (
                  <button
                    key={r.id}
                    type="button"
                    className={`role-pill-btn ${isActive ? "active" : ""}`}
                    onClick={() => setSelectedRoleId(r.id)}
                  >
                    <strong>{r.name}</strong>
                    <span className="role-code-tag">{r.code}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* RBAC Info Notice */}
          <div className="rbac-info-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <div>
              <strong>Quy tắc áp dụng phân quyền trực tiếp:</strong>
              <p>
                - Nếu <strong>Xem (can_view) = TẮT</strong>: Chức năng sẽ bị <strong>ẨN HOÀN TOÀN</strong> khỏi thanh điều hướng Sidebar và chặn truy cập URL.
                <br />
                - Nếu <strong>Xem = BẬT</strong> nhưng <strong>Thêm / Sửa / Xóa = TẮT</strong>: Người dùng xem được dữ liệu nhưng các nút Thêm mới, Sửa hoặc Khóa/Xóa sẽ tự động ẩn khỏi giao diện.
              </p>
            </div>
          </div>

          {/* Matrix Table */}
          {loadingMatrix ? (
            <div style={{ textAlign: "center", padding: "4rem", color: "#64748b" }}>
              Đang tải dữ liệu ma trận phân quyền...
            </div>
          ) : (
            <div className="table-wrap" style={{ marginTop: "1rem" }}>
              <table className="rbac-matrix-table">
                <thead>
                  <tr>
                    <th style={{ width: "35%" }}>Chức năng hệ thống (Module)</th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>XEM</span>
                        <small className="muted">can_view</small>
                      </div>
                    </th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>THÊM</span>
                        <small className="muted">can_create</small>
                      </div>
                    </th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>SỬA</span>
                        <small className="muted">can_update</small>
                      </div>
                    </th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>XÓA / KHÓA</span>
                        <small className="muted">can_delete</small>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(!matrixData?.modules || matrixData.modules.length === 0) ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: "3rem" }}>
                        Chưa có dữ liệu phân quyền cho vai trò này.
                      </td>
                    </tr>
                  ) : (
                    matrixData.modules.map((m, idx) => {
                      // Admin-only modules can never be granted to employee roles (server enforces it too).
                      const isLocked = SYSTEM_LOCKED_MODULES.has(m.code);
                      const isSavingView = savingKey === `${m.code}_can_view`;
                      const isSavingCreate = savingKey === `${m.code}_can_create`;
                      const isSavingUpdate = savingKey === `${m.code}_can_update`;
                      const isSavingDelete = savingKey === `${m.code}_can_delete`;

                      return (
                        <tr key={m.code} className={isLocked ? "row-locked-module" : !m.can_view ? "row-view-disabled" : ""}>
                          <td>
                            <div className="module-title-cell">
                              <span className="module-order-num">{idx + 1}</span>
                              <div>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                  <strong className="module-display-name">{m.name}</strong>
                                  {isLocked && (
                                    <span className="badge badge-locked" style={{ backgroundColor: "#fee2e2", color: "#991b1b", fontSize: "0.75rem", padding: "2px 6px", borderRadius: "4px" }} title="4 chức năng hệ thống bị khóa cứng, chỉ Super Admin mới có quyền truy cập">
                                      🔒 Khóa cứng hệ thống
                                    </span>
                                  )}
                                </div>
                                <div className="module-code-hint">
                                  <code>{m.code}</code> • {m.description || "Chức năng hệ thống"}
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Toggle: can_view */}
                          <td style={{ textAlign: "center" }}>
                            <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Xem module này"} aria-label="Bật/Tắt quyền Xem module này">
                              <input
                                type="checkbox"
                                checked={isLocked ? false : Boolean(m.can_view)}
                                disabled={isLocked || isSavingView}
                                onChange={() => handleToggleRolePermission(m.code, "can_view", m.can_view)}
                              />
                              <span className="slider round"></span>
                            </label>
                          </td>

                          {/* Toggle: can_create */}
                          <td style={{ textAlign: "center" }}>
                            <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Thêm mới trong module này"} aria-label="Bật/Tắt quyền Thêm mới trong module này">
                              <input
                                type="checkbox"
                                checked={isLocked ? false : Boolean(m.can_create)}
                                disabled={isLocked || !m.can_view || isSavingCreate}
                                onChange={() => handleToggleRolePermission(m.code, "can_create", m.can_create)}
                              />
                              <span className="slider round"></span>
                            </label>
                          </td>

                          {/* Toggle: can_update */}
                          <td style={{ textAlign: "center" }}>
                            <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Sửa trong module này"} aria-label="Bật/Tắt quyền Sửa trong module này">
                              <input
                                type="checkbox"
                                checked={isLocked ? false : Boolean(m.can_update)}
                                disabled={isLocked || !m.can_view || isSavingUpdate}
                                onChange={() => handleToggleRolePermission(m.code, "can_update", m.can_update)}
                              />
                              <span className="slider round"></span>
                            </label>
                          </td>

                          {/* Toggle: can_delete */}
                          <td style={{ textAlign: "center" }}>
                            <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Xóa / Khóa trong module này"} aria-label="Bật/Tắt quyền Xóa / Khóa trong module này">
                              <input
                                type="checkbox"
                                checked={isLocked ? false : Boolean(m.can_delete)}
                                disabled={isLocked || !m.can_view || isSavingDelete}
                                onChange={() => handleToggleRolePermission(m.code, "can_delete", m.can_delete)}
                              />
                              <span className="slider round"></span>
                            </label>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: USER-SPECIFIC OVERRIDE */}
      {activeTab === "user" && (
        <div className="rbac-user-section">
          {/* User Search & Selector Bar */}
          <div className="user-override-header-bar">
            <div style={{ flex: 1, maxWidth: "420px" }}>
              <label htmlFor="rolepermissionmatrixpage-field-418" style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "0.35rem" }}>
                Chọn nhân viên cần cấp quyền riêng:
              </label>
              <select id="rolepermissionmatrixpage-field-418"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="input-select"
                style={{ width: "100%" }}
              >
                <option value="">— Vui lòng chọn nhân viên —</option>
                {filteredUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.employee_code || "—"}) — {u.role_name || u.role_code} ({u.department_name})
                  </option>
                ))}
              </select>
            </div>

            {selectedUserId && userMatrixData && (
              <div style={{ display: "flex", alignItems: "flex-end", gap: "0.75rem" }}>
                <button
                  type="button"
                  className="secondary danger-text-btn"
                  onClick={handleResetUserPermissions}
                  title="Xóa toàn bộ các cấu hình quyền riêng và khôi phục về mặc định theo chức vụ"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                    <path d="M21 3v5h-5" />
                    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                    <path d="M3 21v-5h5" />
                  </svg>
                  <span>Khôi phục quyền mặc định theo chức vụ</span>
                </button>
              </div>
            )}
          </div>

          {!selectedUserId ? (
            <div className="empty-user-select-box">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
                <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <h3>Chưa chọn nhân viên</h3>
              <p className="muted">
                Hãy chọn một nhân viên từ danh sách trên để xem và cấu hình quyền riêng (ghi đè lên quyền chức vụ).
              </p>
            </div>
          ) : loadingUserMatrix ? (
            <div style={{ textAlign: "center", padding: "4rem", color: "#64748b" }}>
              Đang tải quyền riêng của nhân viên...
            </div>
          ) : (
            <div className="table-wrap" style={{ marginTop: "1.5rem" }}>
              <div className="user-override-summary-badge">
                <span>Nhân viên: <strong>{userMatrixData?.user?.full_name}</strong></span>
                <span>Chức vụ gốc: <strong>{userMatrixData?.user?.role_name}</strong></span>
                <span>Phòng ban: <strong>{userMatrixData?.user?.department_name}</strong></span>
              </div>

              <table className="rbac-matrix-table">
                <thead>
                  <tr>
                    <th style={{ width: "35%" }}>Chức năng hệ thống (Module)</th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>XEM</span>
                        <small className="muted">can_view</small>
                      </div>
                    </th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>THÊM</span>
                        <small className="muted">can_create</small>
                      </div>
                    </th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>SỬA</span>
                        <small className="muted">can_update</small>
                      </div>
                    </th>
                    <th style={{ width: "16%", textAlign: "center" }}>
                      <div className="th-toggle-header">
                        <span>XÓA / KHÓA</span>
                        <small className="muted">can_delete</small>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(userMatrixData?.modules || []).map((m, idx) => {
                    const isLocked = SYSTEM_LOCKED_MODULES.has(m.code);
                    const isOverride = m.is_user_override;
                    const isSavingView = savingKey === `user_${m.code}_can_view`;
                    const isSavingCreate = savingKey === `user_${m.code}_can_create`;
                    const isSavingUpdate = savingKey === `user_${m.code}_can_update`;
                    const isSavingDelete = savingKey === `user_${m.code}_can_delete`;

                    return (
                      <tr key={m.code} className={isLocked ? "row-locked-module" : !m.can_view ? "row-view-disabled" : ""}>
                        <td>
                          <div className="module-title-cell">
                            <span className="module-order-num">{idx + 1}</span>
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <strong className="module-display-name">{m.name}</strong>
                                {isLocked ? (
                                  <span className="badge badge-locked" style={{ backgroundColor: "#fee2e2", color: "#991b1b", fontSize: "0.75rem", padding: "2px 6px", borderRadius: "4px" }} title="4 chức năng hệ thống bị khóa cứng, chỉ Super Admin mới có quyền truy cập">
                                    🔒 Khóa cứng hệ thống
                                  </span>
                                ) : isOverride ? (
                                  <span className="badge badge-override" title="Quyền này được ghi đè riêng cho nhân viên">
                                    Quyền riêng
                                  </span>
                                ) : null}
                              </div>
                              <div className="module-code-hint">
                                <code>{m.code}</code> • {m.description || "Chức năng"}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Toggle: can_view */}
                        <td style={{ textAlign: "center" }}>
                          <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Xem riêng"} aria-label="Bật/Tắt quyền Xem riêng">
                            <input
                              type="checkbox"
                              checked={isLocked ? false : Boolean(m.can_view)}
                              disabled={isLocked || isSavingView}
                              onChange={() => handleToggleUserPermission(m.code, "can_view", m.can_view)}
                            />
                            <span className="slider round"></span>
                          </label>
                        </td>

                        {/* Toggle: can_create */}
                        <td style={{ textAlign: "center" }}>
                          <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Thêm riêng"} aria-label="Bật/Tắt quyền Thêm riêng">
                            <input
                              type="checkbox"
                              checked={isLocked ? false : Boolean(m.can_create)}
                              disabled={isLocked || !m.can_view || isSavingCreate}
                              onChange={() => handleToggleUserPermission(m.code, "can_create", m.can_create)}
                            />
                            <span className="slider round"></span>
                          </label>
                        </td>

                        {/* Toggle: can_update */}
                        <td style={{ textAlign: "center" }}>
                          <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Sửa riêng"} aria-label="Bật/Tắt quyền Sửa riêng">
                            <input
                              type="checkbox"
                              checked={isLocked ? false : Boolean(m.can_update)}
                              disabled={isLocked || !m.can_view || isSavingUpdate}
                              onChange={() => handleToggleUserPermission(m.code, "can_update", m.can_update)}
                            />
                            <span className="slider round"></span>
                          </label>
                        </td>

                        {/* Toggle: can_delete */}
                        <td style={{ textAlign: "center" }}>
                          <label className={`switch-toggle ${isLocked ? "switch-disabled" : ""}`} title={isLocked ? "Khóa cứng hệ thống (không thể chỉnh sửa)" : "Bật/Tắt quyền Xóa riêng"} aria-label="Bật/Tắt quyền Xóa riêng">
                            <input
                              type="checkbox"
                              checked={isLocked ? false : Boolean(m.can_delete)}
                              disabled={isLocked || !m.can_view || isSavingDelete}
                              onChange={() => handleToggleUserPermission(m.code, "can_delete", m.can_delete)}
                            />
                            <span className="slider round"></span>
                          </label>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

with open(r'web_client/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update ADMIN_NAV
old_nav = """const ADMIN_NAV = [
  ["GIÁM SÁT", ["home", "ops"]],
  ["LUỒNG CÔNG VIỆC", ["request-catalog"]],
  ["TỔ CHỨC & NHÂN SỰ", ["org-chart", "users", "departments", "permissions"]],
  ["TRI THỨC & AI", ["policy", "ai-process"]],
  ["HỆ THỐNG", ["api-admin", "system", "sla", "audit"]],
];"""

new_nav = """const ADMIN_NAV = [
  ["GIÁM SÁT", ["home"]],
  ["LUỒNG CÔNG VIỆC", ["request-catalog"]],
  ["TỔ CHỨC & NHÂN SỰ", ["org-chart", "users", "permissions"]],
  ["TRI THỨC & AI", ["policy", "ai-process"]],
  ["HỆ THỐNG", ["api-admin", "system"]],
];"""

if old_nav in content:
    content = content.replace(old_nav, new_nav)
else:
    content = content.replace(old_nav.replace('\n', '\r\n'), new_nav.replace('\n', '\r\n'))

# 2. Update ADMIN_PAGES to still include ops, sla, audit, identity, departments
old_admin_pages = """const ADMIN_PAGES = new Set([...navKeys(ADMIN_NAV), "notifications"]);"""
new_admin_pages = """const ADMIN_PAGES = new Set([...navKeys(ADMIN_NAV), "ops", "sla", "audit", "identity", "departments", "notifications"]);"""

if old_admin_pages in content:
    content = content.replace(old_admin_pages, new_admin_pages)
else:
    content = content.replace(old_admin_pages.replace('\n', '\r\n'), new_admin_pages.replace('\n', '\r\n'))

# 3. Update route rendering in renderWorkspaceContent
old_routes = """    case "identity":
    case "users":
      return <AdminScreen name="IdentityAdmin" key="users" initialKind="users" onNavigateOrgChart={() => navigate("org-chart")} />;
    case "departments":
      return <AdminScreen name="IdentityAdmin" key="departments" initialKind="departments" onNavigateOrgChart={() => navigate("org-chart")} />;
    case "permissions":
      return <AdminScreen name="IdentityAdmin" key="memberships" initialKind="memberships" onNavigateOrgChart={() => navigate("org-chart")} />;"""

new_routes = """    case "identity":
    case "users":
      return <AdminScreen name="UserManagementPage" onNavigateOrgChart={() => navigate("org-chart")} />;
    case "departments":
      return <AdminScreen name="OrgChart" navigate={navigate} portal={portal} user={user} />;
    case "permissions":
      return <AdminScreen name="RolePermissionMatrixPage" />;"""

if old_routes in content:
    content = content.replace(old_routes, new_routes)
else:
    content = content.replace(old_routes.replace('\n', '\r\n'), new_routes.replace('\n', '\r\n'))

# 4. Add Access Denied guard in renderWorkspaceContent
old_start = """  const canOpenAsAdmin = user.roles.includes("AUDITOR");
  if (editor) {"""

new_start = """  const canOpenAsAdmin = user.roles.includes("AUDITOR");
  const mod = pageToModuleCode(page);
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
  if (editor) {"""

if old_start in content:
    content = content.replace(old_start, new_start)
else:
    content = content.replace(old_start.replace('\n', '\r\n'), new_start.replace('\n', '\r\n'))

with open(r'web_client/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated App.jsx successfully!")


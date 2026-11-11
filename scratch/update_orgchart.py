with open(r'web_client/src/components/OrgChart.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update resources
content = content.replace(
    'const usersRes = useResource("/api/v1/admin/users?limit=300");',
    'const treeRes = useResource("/api/v1/admin/org-chart-tree");\n  const usersRes = useResource("/api/v1/admin/users-management?limit=300");'
)

# 2. Update stats bar
old_stats = """        <div className="org-chart-stats">
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
        </div>"""

new_stats = """        <div className="org-chart-stats">
          <span className="stat-pill stat-total">
            Tổng nhân sự: <strong>{treeRes.data?.summary?.total_employees ?? chartData.totalEmployees}</strong>
          </span>
          <span className="stat-pill stat-depts">
            Phòng ban: <strong>{treeRes.data?.summary?.total_departments ?? Object.keys(chartData.departments).length}</strong>
          </span>
          <span className="stat-pill stat-working" style={{ background: "#e8f8ed", color: "#0f5132", borderColor: "#42b86c" }}>
            🟢 Đang làm: <strong>{treeRes.data?.summary?.working_count ?? "—"}</strong>
          </span>
          <span className="stat-pill stat-leave" style={{ background: "#fff6eb", color: "#8f4400", borderColor: "#f0932b" }}>
            🟡 Nghỉ làm: <strong>{treeRes.data?.summary?.leave_count ?? "—"}</strong>
          </span>
          <span className="stat-pill stat-trip" style={{ background: "#eaf3ff", color: "#084298", borderColor: "#4b8fe2" }}>
            🔵 Công tác: <strong>{treeRes.data?.summary?.trip_count ?? "—"}</strong>
          </span>
        </div>"""

# Try both CRLF and LF
if old_stats in content:
    content = content.replace(old_stats, new_stats)
else:
    content = content.replace(old_stats.replace('\n', '\r\n'), new_stats.replace('\n', '\r\n'))

# 3. Update navigation button in header
content = content.replace(
    'onClick={() => navigate("identity")}',
    'onClick={() => navigate("users")}'
)
content = content.replace(
    '+ Cấp tài khoản mới',
    '+ Quản lý người dùng'
)
content = content.replace(
    'Quản lý trong Danh tính & phân quyền →',
    'Quản lý Người dùng & Trạng thái làm việc →'
)

# 4. Update roster item rendering with status badge
old_roster = """                      <div className="org-roster-status">
                        <span className="status-tag active">Hoạt động</span>
                      </div>"""

new_roster = """                      <div className="org-roster-status">
                        {u.working_status_code === "CONG_TAC" ? (
                          <span className="status-tag trip" style={{ background: "#cfe2ff", color: "#084298", borderColor: "#b6d4fe" }}>Công tác</span>
                        ) : u.working_status_code === "NGHI_LAM" ? (
                          <span className="status-tag leave" style={{ background: "#ffe5d0", color: "#8f4400", borderColor: "#fcd4b4" }}>Nghỉ làm</span>
                        ) : (
                          <span className="status-tag active">Đang làm</span>
                        )}
                      </div>"""

if old_roster in content:
    content = content.replace(old_roster, new_roster)
else:
    content = content.replace(old_roster.replace('\n', '\r\n'), new_roster.replace('\n', '\r\n'))

with open(r'web_client/src/components/OrgChart.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated OrgChart.jsx successfully!")


import { useMemo, useState } from "react";
import { useResource, ResourceState } from "./ui.jsx";
import { ClientPageHeader } from "./clientDesign.jsx";

const fold = (value) => String(value || "").toLocaleLowerCase("vi-VN");

function PersonNode({ person, childrenOf, selfId, needle, depth = 0 }) {
  const reports = childrenOf.get(person.id) || [];
  const [open, setOpen] = useState(depth < 1);
  const matches = !needle || fold(person.display_name).includes(needle);
  return <li className="client-org-node">
    <div className={`client-org-person ${person.id === selfId ? "client-org-self" : ""} ${needle && matches ? "client-org-match" : ""}`}>
      <span className="client-avatar" aria-hidden="true">{(person.display_name || "?").trim().slice(0, 1).toLocaleUpperCase("vi-VN")}</span>
      <div><strong>{person.display_name}{person.id === selfId && <span className="client-org-you"> (Bạn)</span>}</strong>
        <small>{reports.length ? `Quản lý ${reports.length} người` : "Nhân viên"}</small></div>
      {reports.length > 0 && <button type="button" className="link client-org-toggle" aria-expanded={open || Boolean(needle)} onClick={() => setOpen((v) => !v)}>{open || needle ? "Thu gọn" : "Mở rộng"}</button>}
    </div>
    {reports.length > 0 && (open || needle) && <ul className="client-org-children">
      {reports.map((child) => <PersonNode key={child.id} person={child} childrenOf={childrenOf} selfId={selfId} needle={needle} depth={depth + 1} />)}
    </ul>}
  </li>;
}

/** Organization → Department → Manager → Employees, built only from /api/v1/meta/org-chart.
 * The API decides which people are visible; this view never infers hierarchy. */
export default function ClientOrgChart({ user }) {
  const chart = useResource("/api/v1/meta/org-chart");
  const [search, setSearch] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [collapsed, setCollapsed] = useState(() => new Set());
  const needle = fold(search.trim());
  const departments = useMemo(() => chart.data?.departments || [], [chart.data]);
  const people = useMemo(() => chart.data?.users || [], [chart.data]);

  const tree = useMemo(() => {
    const byId = new Map(people.map((p) => [p.id, p]));
    const childrenOf = new Map();
    const rootsByDept = new Map();
    for (const person of people) {
      const manager = person.manager_id && byId.get(person.manager_id);
      // A manager in another department leads their own unit; show the person as a root here.
      if (manager && manager.department_id === person.department_id) {
        if (!childrenOf.has(manager.id)) childrenOf.set(manager.id, []);
        childrenOf.get(manager.id).push(person);
      } else {
        if (!rootsByDept.has(person.department_id)) rootsByDept.set(person.department_id, []);
        rootsByDept.get(person.department_id).push(person);
      }
    }
    const sortByName = (a, b) => a.display_name.localeCompare(b.display_name, "vi");
    childrenOf.forEach((list) => list.sort(sortByName));
    rootsByDept.forEach((list) => list.sort((a, b) => (childrenOf.get(b.id)?.length || 0) - (childrenOf.get(a.id)?.length || 0) || sortByName(a, b)));
    return { childrenOf, rootsByDept };
  }, [people]);

  const visibleDepartments = departments.filter((d) => {
    if (departmentFilter && d.id !== departmentFilter) return false;
    if (!needle) return true;
    return fold(d.name).includes(needle) || people.some((p) => p.department_id === d.id && fold(p.display_name).includes(needle));
  });
  const scopeLabel = chart.data?.scope === "organization" ? "Toàn tổ chức" : "Phòng ban của bạn và cấp quản lý trực tiếp";
  function toggle(id) { setCollapsed((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }

  return <section className="client-section">
    <ClientPageHeader eyebrow="TỔ CHỨC" title="Sơ đồ tổ chức" description="Cơ cấu phòng ban và quan hệ quản lý trực tiếp theo dữ liệu nhân sự của hệ thống." />
    <ResourceState resource={chart}>
      <section className="panel client-org-workspace">
        <div className="section-head"><div><p className="eyebrow">{scopeLabel}</p><h2>{departments.length} phòng ban · {people.length} nhân sự hiển thị</h2></div>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setCollapsed(new Set())}>Mở tất cả</button>
            <button type="button" className="secondary" onClick={() => setCollapsed(new Set(departments.map((d) => d.id)))}>Thu gọn tất cả</button>
            <button type="button" className="secondary" onClick={chart.reload}>Cập nhật</button>
          </div></div>
        <div className="client-org-filters">
          <label className="client-org-search">Tìm nhân sự hoặc phòng ban
            <input value={search} onChange={(e) => setSearch(e.target.value)} type="search" placeholder="Nhập tên…" /></label>
          <label>Phòng ban
            <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)}>
              <option value="">Tất cả phòng ban</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select></label>
        </div>
        <div className="client-org-tree" aria-label="Cây tổ chức">
          {visibleDepartments.map((dept) => {
            const roots = tree.rootsByDept.get(dept.id) || [];
            const isOpen = !collapsed.has(dept.id) || Boolean(needle);
            return <section key={dept.id} className="client-org-group">
              <button type="button" className="client-org-dept-head" aria-expanded={isOpen} onClick={() => toggle(dept.id)}>
                <span aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                <strong>{dept.name}</strong>
                <small>{dept.member_count} thành viên{dept.id === user.department_id ? " · Phòng của bạn" : ""}</small>
              </button>
              {isOpen && (roots.length
                ? <ul className="client-org-children client-org-roots">{roots.map((p) => <PersonNode key={p.id} person={p} childrenOf={tree.childrenOf} selfId={user.id} needle={needle} />)}</ul>
                : <p className="muted client-org-hidden">Danh sách nhân sự phòng này nằm ngoài phạm vi bạn được xem.</p>)}
            </section>;
          })}
          {!visibleDepartments.length && <p className="muted">Không tìm thấy phòng ban hoặc nhân sự phù hợp.</p>}
        </div>
        <p className="muted client-org-footnote">Sơ đồ chỉ dùng họ tên, phòng ban và quan hệ quản lý trực tiếp; không công bố email hay quyền hệ thống. Là quản lý trực tiếp không đồng nghĩa có quyền phê duyệt mọi loại yêu cầu.</p>
      </section>
    </ResourceState>
  </section>;
}

import { useMemo, useState } from "react";
import { useResource, ResourceState } from "./ui.jsx";
import { ClientPageHeader } from "./clientDesign.jsx";

function Person({ person, isSelf, isManager = false }) {
  return <div className={`client-org-person ${isSelf ? "client-org-self" : ""}`}>
    <span className="client-avatar" aria-hidden="true">{(person.display_name || "?").trim().slice(0,1).toLocaleUpperCase("vi-VN")}</span>
    <div><strong>{person.display_name || "Chưa có tên"}{isSelf && <span className="client-org-you"> (Bạn)</span>}</strong>
      <small>{isManager ? "Quản lý trực tiếp" : person.manager_name ? `Quản lý: ${person.manager_name}` : "Chưa cập nhật quản lý trực tiếp"}</small></div>
  </div>;
}

/** Read-only, department-scoped organization structure. All relationships are read from API. */
export default function ClientOrgChart({ user }) {
  const colleagues = useResource("/api/v1/meta/colleagues");
  const [search, setSearch] = useState("");
  const people = useMemo(() => colleagues.data?.organization || [], [colleagues.data]);
  const groups = useMemo(() => {
    const byId = new Map(people.map(p => [p.id, p]));
    const buckets = new Map();
    people.forEach(person => {
      const manager = person.manager_id && byId.get(person.manager_id);
      const key = manager ? manager.id : "unassigned";
      if (!buckets.has(key)) buckets.set(key, { manager: manager || null, members: [] });
      if (manager?.id !== person.id) buckets.get(key).members.push(person);
    });
    // Root managers are already displayed as group leaders, not unassigned employees.
    const knownLeaders = new Set([...buckets.values()].filter(b => b.manager).map(b => b.manager.id));
    const unassigned = buckets.get("unassigned");
    if (unassigned) unassigned.members = unassigned.members.filter(p => !knownLeaders.has(p.id));
    return [...buckets.values()].filter(b => b.manager || b.members.length).sort((a,b) => (a.manager?.display_name || "~~~").localeCompare(b.manager?.display_name || "~~~", "vi"));
  }, [people]);
  const needle = search.trim().toLocaleLowerCase("vi-VN");
  const visible = groups.filter(g => !needle || [g.manager?.display_name, ...g.members.map(m=>m.display_name)].some(t => String(t||"").toLocaleLowerCase("vi-VN").includes(needle)));
  const department = people[0]?.department_name || "Phòng ban của bạn";
  return <section className="client-section">
    <ClientPageHeader eyebrow="TỔ CHỨC" title="Sơ đồ phòng ban" description="Trưởng nhóm và thành viên được sắp xếp theo quan hệ quản lý đã khai báo trong hệ thống."/>
    {!user.roles?.some(role => ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR"].includes(role)) ? <section className="panel empty"><h2>Không có quyền tra cứu</h2><p>Thông tin nhân sự chỉ hiển thị trong phạm vi được phân quyền.</p></section> :
      <ResourceState resource={colleagues}>
        <section className="panel client-org-workspace">
          <div className="section-head"><div><p className="eyebrow">PHÒNG BAN</p><h2>{department}</h2><p className="muted">{people.length} thành viên đang hoạt động · Phân cấp theo quản lý trực tiếp.</p></div>
            <button type="button" className="secondary" onClick={colleagues.reload}>Cập nhật</button></div>
          <label className="client-org-search">Tìm thành viên
            <input value={search} onChange={e=>setSearch(e.target.value)} type="search" placeholder="Nhập tên đồng nghiệp hoặc trưởng nhóm…"/>
          </label>
          {people.length === 0 ? <p className="muted">Chưa có dữ liệu nhân sự trong phòng ban được phép xem.</p> :
            <div className="client-org-tree" aria-label="Cây tổ chức theo quản lý trực tiếp">
              {visible.map((group,i) => <section key={group.manager?.id || `unassigned-${i}`} className="client-org-group">
                <div className="client-org-leader">{group.manager ? <Person person={group.manager} isManager isSelf={group.manager.id === user.id}/> : <div className="client-org-unassigned"><strong>Chưa được gán quản lý trong phòng ban</strong><small>Kiểm tra quan hệ quản lý với bộ phận nhân sự.</small></div>}</div>
                {group.members.length > 0 && <div className="client-org-members">{group.members.filter(p=>!needle||[p.display_name,group.manager?.display_name].some(s=>String(s||"").toLocaleLowerCase("vi-VN").includes(needle))).map(p => <Person key={p.id} person={p} isSelf={p.id === user.id}/>)}</div>}
              </section>)}
              {visible.length===0 && <p className="muted">Không tìm thấy thành viên phù hợp.</p>}
            </div>}
          <p className="muted client-org-footnote">Sơ đồ chỉ sử dụng tên và quan hệ quản lý trong phòng ban được phép xem; không công bố tài khoản đăng nhập hay thông tin cá nhân khác. Người được gán là quản lý trực tiếp không đồng nghĩa tự động có quyền phê duyệt mọi hồ sơ.</p>
        </section>
      </ResourceState>}
  </section>;
}

import { useEffect, useState } from "react";
import { PasswordField, PageControls } from "./ux.jsx";
import { roles, date } from "../domain.js";
import { ActionForm, Data, Modal, Reason, ResourceState, command, useResource } from "./ui.jsx";

const entities = {
  users: "Người dùng",
  departments: "Phòng ban",
  memberships: "Phân quyền",
  "request-types": "Loại yêu cầu",
};

function LookupSelect({ kind, label, name, value, optional = false, excludeId = null }) {
  const [query, setQuery] = useState("");
  const [current, setCurrent] = useState(value || "");
  const [searched, setSearched] = useState("");
  useEffect(() => { const t = setTimeout(() => setSearched(query.trim()), 280); return () => clearTimeout(t); }, [query]);
  const params = new URLSearchParams({ limit: "100", offset: "0" });
  if (searched) params.set("q", searched);
  const res = useResource(`/api/v1/admin/${kind}?${params}`);
  const items = (res.data?.items || []).filter((x) => x.id !== excludeId);
  const hasCurrent = items.some((x) => x.id === current);
  function title(item) {
    if (kind === "users") return `${item.display_name} (${item.username})`;
    return `${item.code || item.name} ${item.name && item.code ? "· " + item.name : ""}`;
  }
  return <div className="lookup-select">
    <label>{label}<small> Chọn trong danh sách (có tìm kiếm)</small>
      <input type="search" aria-label={`Tìm ${label.toLowerCase()}`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm theo tên hoặc mã…" />
    </label>
    <select name={name} aria-label={label} value={current} onChange={(e) => setCurrent(e.target.value)} required={!optional}>
      <option value="">{optional ? "Không chọn" : "— Chọn mục bắt buộc —"}</option>
      {current && !hasCurrent && <option value={current}>Đang chọn: {current}</option>}
      {items.map((item) => <option key={item.id} value={item.id}>{title(item)}</option>)}
    </select>
    {res.error && <small className="error" role="alert">Không thể tải danh mục: {res.error}</small>}
    {!res.error && res.data?.next_offset != null && <small>Danh sách có nhiều kết quả. Hãy tìm tên để chọn chính xác.</small>}
  </div>;
}

function Active({ value }) {
  return <label>Trạng thái<select name="is_active" defaultValue={String(value)}>
    <option value="true">Hoạt động</option><option value="false">Ngừng hoạt động</option>
  </select></label>;
}

function MembershipEditor({ record }) {
  const [scope, setScope] = useState(record?.scope_kind || "DEPARTMENT");
  const [typeScope, setTypeScope] = useState(record?.type_scope || "ALL");
  return <>
    <div className="identity-editor-help">Phân quyền theo đúng hai chiều: <strong>phòng ban</strong> và <strong>loại yêu cầu</strong>. GLOBAL/ALL phải được chọn rõ, không suy ra từ việc bỏ trống UUID.</div>
    {record ? <p className="muted">Người nhận quyền: <code>{record.user_id}</code> (không thay đổi sau khi cấp)</p> :
      <LookupSelect kind="users" name="user_id" label="Người dùng được cấp quyền" />}
    <label>Vai trò
      <select name="role" defaultValue={record?.role || "REQUESTER"}>
        {Object.entries(roles).map(([k, v]) => <option key={k} value={k}>{v} ({k})</option>)}
      </select>
    </label>
    <div className="form-grid">
      <label>Phạm vi phòng ban<select name="scope_kind" value={scope} onChange={(e) => setScope(e.target.value)}>
        <option value="DEPARTMENT">DEPARTMENT — Một phòng ban</option>
        <option value="GLOBAL">GLOBAL — Toàn tổ chức</option>
      </select></label>
      <label>Phạm vi loại yêu cầu<select name="type_scope" value={typeScope} onChange={(e) => setTypeScope(e.target.value)}>
        <option value="ALL">ALL — Tất cả loại</option><option value="ONE">ONE — Một loại cụ thể</option>
      </select></label>
    </div>
    <div className="form-grid">
      {scope === "DEPARTMENT" ? <LookupSelect key={`department-${scope}`} kind="departments" name="department_id" label="Phòng ban áp dụng" value={record?.department_id} /> : <input name="department_id" type="hidden" value="" />}
      {typeScope === "ONE" ? <LookupSelect key={`type-${typeScope}`} kind="request-types" name="type_id" label="Loại yêu cầu áp dụng" value={record?.type_id} /> : <input name="type_id" type="hidden" value="" />}
    </div>
    <div className="form-grid">
      <label>Hiệu lực từ (ISO 8601 có múi giờ)<input name="valid_from" defaultValue={record?.valid_from || new Date().toISOString()} required /></label>
      <label>Hiệu lực đến (có thể để trống)<input name="valid_to" defaultValue={record?.valid_to || ""} placeholder="2027-01-01T00:00:00+07:00" /></label>
    </div>
    <p className="muted">Khi thu hồi hoặc đổi quyền, session cũ được vô hiệu hóa theo auth_version và security_epoch. Không xóa lịch sử quyết định.</p>
  </>;
}

function Editor({ kind, record }) {
  if (kind === "memberships") return <MembershipEditor record={record} />;
  if (kind === "users") return <>
    <div className="form-grid">
      <label>Tên đăng nhập<input name="username" autoComplete="off" defaultValue={record?.username || ""} required maxLength={150} /></label>
      <label>Họ tên<input name="display_name" defaultValue={record?.display_name || ""} required maxLength={150} /></label>
      <LookupSelect kind="departments" name="department_id" label="Phòng ban" value={record?.department_id} />
      <LookupSelect kind="users" name="manager_id" label="Người quản lý trực tiếp" value={record?.manager_id} optional excludeId={record?.id} />
    </div>
    <PasswordField label={record ? "Mật khẩu tạm mới (để trống nếu không đổi)" : "Mật khẩu tạm"}
      name="password" autoComplete="new-password" required={!record} minLength={15} maxLength={128} />
    <p className="muted">Mật khẩu từ 15–128 ký tự, chữ hoa + chữ thường + số + ký tự đặc biệt. Sau khi cấp lại, người dùng phải đổi mật khẩu khi đăng nhập.</p>
    <Active value={record?.is_active ?? true}/>
  </>;
  if (kind === "departments") return <>
    <div className="form-grid">
      <label>Mã phòng ban<input name="code" defaultValue={record?.code || ""} required maxLength={50}/></label>
      <label>Tên phòng ban<input name="name" defaultValue={record?.name || ""} required maxLength={150}/></label>
      <LookupSelect kind="departments" name="parent_id" label="Phòng ban cha" value={record?.parent_id} optional excludeId={record?.id}/>
      <Active value={record?.is_active ?? true}/>
    </div>
    <small>Hệ thống ngăn chu kỳ phòng ban. Không vô hiệu phòng đang có user hoặc phòng con hoạt động.</small>
  </>;
  return <>
    {record ? <p>Loại yêu cầu <strong>{record.code}</strong> · Mẫu {record.lifecycle}; mã và vòng đời không được đổi sau khi tạo.</p> : <>
      <label>Mã loại yêu cầu<input name="code" placeholder="TRAVEL_EXPENSE" maxLength={30} pattern="[A-Z][A-Z0-9_]{1,29}" required /></label>
      <label>Mẫu vòng đời<select name="lifecycle" defaultValue="B"><option value="A">A — Phê duyệt</option><option value="B">B — Phê duyệt + Thực hiện</option><option value="C">C — Phê duyệt + Thực hiện + Nghiệm thu</option></select></label>
    </>}
    <Active value={record?.is_active ?? true}/>
    <p className="muted">Việc tạo thêm loại chỉ khả dụng khi quản trị CSDL đã áp dụng migration mở rộng và bật EAS_ALLOW_REPORT_CATALOG_EXPANSION. Loại mới phải được Policy Admin công bố bản cấu hình và cấp quyền REQUESTER trước khi sử dụng.</p>
  </>;
}

function UserDetail({ kind, item }) {
  const resource = useResource(`/api/v1/admin/${kind}/${item.id}`);
  return <ResourceState resource={resource}>
    <div className="identity-detail-card"><Data value={resource.data?.item || item}/></div>
    {kind === "users" && <><h3>Các quyền đã cấp (kể cả đã thu hồi)</h3>
      <div className="identity-scope-list">{(resource.data?.item?.memberships || []).map((m) => <article key={m.id} className="identity-scope-card"><strong>{roles[m.role] || m.role}</strong><span>{m.scope_kind}{m.department_id ? ` / ${m.department_id}` : ""} · {m.type_scope}{m.type_id ? ` / ${m.type_id}` : ""}</span><small>{m.revoked_at ? "Đã thu hồi" : m.valid_to && new Date(m.valid_to) < new Date() ? "Hết hạn" : "Chưa thu hồi"}</small></article>)}
        {!resource.data?.item?.memberships?.length && <p className="muted">Chưa có role membership.</p>}
      </div></>}
  </ResourceState>;
}

export default function IdentityAdmin() {
  const [kind, setKind] = useState("users");
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [modal, setModal] = useState(null);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [role, setRole] = useState("");
  useEffect(() => { const timer = setTimeout(() => { setDebounced(search.trim()); setOffset(0); }, 300); return () => clearTimeout(timer); }, [search]);
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (debounced) params.set("q", debounced);
  if (status) params.set(kind === "memberships" ? "state" : "active", status);
  if (role && ["users", "memberships"].includes(kind)) params.set("role", role);
  const r = useResource(`/api/v1/admin/${kind}?${params}`);
  const total = r.data?.total ?? 0;
  async function save(v) {
    const body = { ...v };
    if ("is_active" in body) body.is_active = body.is_active === "true";
    if (!body.password) delete body.password;
    if (modal.record) body.expected_revision = modal.record.revision;
    await command(`admin/${kind}${modal.record ? "/" + modal.record.id : ""}`, body, modal.record ? "PATCH" : "POST");
    setModal(null);
    setNotice("Đã lưu thay đổi. Quản trị được ghi vào audit và cập nhật security_epoch.");
    setOffset(0);
    r.reload();
  }
  function switchKind(k) {
    setKind(k); setOffset(0); setSearch(""); setDebounced(""); setStatus(""); setRole(""); setModal(null); setNotice("");
  }
  return <>
    <div className="page-heading"><div><p className="eyebrow">QUẢN TRỊ DANH TÍNH / UC17</p><h1>Người dùng & ma trận phân quyền</h1><p className="muted">Quản trị tài khoản, quan hệ quản lý, phòng ban, vai trò có thời hạn và phạm vi áp dụng; không xóa user có dữ liệu lịch sử.</p></div>
      <button type="button" onClick={() => setModal({mode: "edit", record: null})}>+ {kind === "users" ? "Tạo người dùng" : kind === "memberships" ? "Cấp quyền" : kind === "request-types" ? "Tạo loại yêu cầu" : "Thêm phòng ban"}</button>
    </div>
    {kind === "request-types" && <p className="muted" role="status">Báo cáo v1.0 đặt mục tiêu 16 loại yêu cầu. Hệ thống hiện có {total} loại theo bộ lọc đang chọn; loại mới cần được cấp quyền, cấu hình và công bố trước khi tạo hồ sơ.</p>}
    <div className="identity-explain" role="note"><strong>Bảo mật UC17:</strong> chỉ OPS_ADMIN với role membership <code>GLOBAL + ALL</code> mới được gọi API quản lý. Không suy quyền từ chức danh; mọi hành động cần lý do, idempotency và audit; không tự cấp/sửa role của chính mình.</div>
    <div className="tabs" aria-label="Mục quản trị danh tính">{Object.entries(entities).map(([k, v]) => <button type="button" className={kind === k ? "active" : "secondary"} key={k} onClick={() => switchKind(k)}>{v}</button>)}</div>
    {notice && <p className="success" role="status">{notice}</p>}
    <section className="panel identity-filter-panel" aria-label="Lọc dữ liệu">
      <div className="identity-filter-grid">
        <label>Tìm kiếm {entities[kind].toLowerCase()}
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={kind === "users" ? "Tên đăng nhập hoặc họ tên" : kind === "memberships" ? "Tên role hoặc UUID user" : "Mã hoặc tên"} maxLength={100}/>
        </label>
        <label>Trạng thái<select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
          <option value="">Tất cả trạng thái</option>
          {kind === "memberships" ? <><option value="ACTIVE">Đang hiệu lực</option><option value="FUTURE">Chưa hiệu lực</option><option value="EXPIRED">Hết hạn</option><option value="REVOKED">Đã thu hồi</option></> : <><option value="true">Đang hoạt động</option><option value="false">Ngừng hoạt động</option></>}
        </select></label>
        {["users", "memberships"].includes(kind) && <label>Vai trò<select value={role} onChange={(e) => { setRole(e.target.value); setOffset(0); }}>
          <option value="">Mọi vai trò</option>{Object.entries(roles).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select></label>}
        <div className="identity-filter-reset"><button className="secondary" type="button" onClick={() => { setSearch(""); setStatus(""); setRole(""); setOffset(0); }}>Đặt lại bộ lọc</button></div>
      </div>
    </section>
    <section className="panel" id="identity-results"><div className="section-head identity-result-head"><div><h2>Danh sách {entities[kind].toLowerCase()}</h2><p className="muted">{total} bản ghi theo bộ lọc hiện tại · Phân trang trực tiếp trên PostgreSQL.</p></div></div>
      <ResourceState resource={r}>
        <div className="table-wrap"><table className="responsive-records identity-table"><thead><tr><th>Thông tin</th><th>Phòng ban / scope</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>
          {r.data?.items?.map((item) => <tr key={item.id}>
            <td data-label="Thông tin"><div className="identity-primary"><span className="identity-avatar" aria-hidden="true">{(item.display_name || item.name || item.role || item.code || "E").slice(0, 1).toLocaleUpperCase("vi")}</span><span><strong>{item.display_name || item.name || roles[item.role] || item.code || "—"}</strong><small>{item.username || item.code || item.user_id || item.role || ""}</small><small className="identity-id">ID {item.id}</small></span></div></td>
            <td data-label="Phạm vi"><small>{item.scope_kind ? `${item.scope_kind} · ${item.type_scope}` : item.department_id ? `Phòng: ${item.department_id}` : "—"}</small></td>
            <td data-label="Trạng thái"><span className={`identity-status ${kind === "memberships" ? (item.revoked_at ? "off" : item.valid_to && new Date(item.valid_to) <= new Date() ? "off" : new Date(item.valid_from) > new Date() ? "future" : "on") : item.is_active ? "on" : "off"}`}>{kind === "memberships" ? item.revoked_at ? "Đã thu hồi" : item.valid_to && new Date(item.valid_to) <= new Date() ? "Hết hiệu lực" : new Date(item.valid_from) > new Date() ? "Chưa hiệu lực" : "Đang hiệu lực" : item.is_active ? "Hoạt động" : "Ngừng hoạt động"}</span></td>
            <td data-label="Thao tác"><div className="actions"><button type="button" className="secondary" onClick={() => setModal({mode:"view",record:item})}>Chi tiết</button><button type="button" className="secondary" disabled={!!item.revoked_at} onClick={() => setModal({mode:"edit",record:item})}>Sửa</button><button type="button" className="danger" disabled={kind === "memberships" ? !!item.revoked_at : !item.is_active} onClick={() => setModal({mode:"delete",record:item})}>{kind === "memberships" ? "Thu hồi" : "Vô hiệu hóa"}</button></div></td>
          </tr>)}
        </tbody></table></div>
        {!r.data?.items?.length && <p className="empty">Không có dữ liệu phù hợp. Bạn có thể đổi bộ lọc hoặc thêm mới.</p>}
        <PageControls offset={offset} limit={limit} nextOffset={r.data?.next_offset} count={r.data?.items?.length || 0} title="bản ghi" targetId="identity-results" onPage={setOffset} onLimit={(v) => { setLimit(v); setOffset(0); }}/>
      </ResourceState>
    </section>
    {modal && <Modal title={`${entities[kind]} · ${modal.mode === "view" ? "Thông tin chi tiết" : modal.mode === "delete" ? "Xác nhận thay đổi trạng thái" : modal.record ? "Cập nhật" : "Thêm mới"}`} onClose={() => setModal(null)}>
      {modal.mode === "view" ? <><UserDetail kind={kind} item={modal.record}/>{modal.record.valid_to && <p>Hiệu lực đến: {date(modal.record.valid_to)}</p>}</> :
        <ActionForm onSubmit={modal.mode === "delete" ? async (v) => {
          await command(`admin/${kind}/${modal.record.id}`, {reason:v.reason, expected_revision:modal.record.revision}, "DELETE");
          setModal(null); setNotice("Đã vô hiệu hóa hoặc thu hồi. Lịch sử vẫn được giữ lại."); r.reload();
        } : save} danger={modal.mode === "delete"}>
          {modal.mode === "delete" ? <p>Không xóa dữ liệu nghiệp vụ. Khi vô hiệu user hoặc thu hồi role, các phiên đăng nhập cũ sẽ không còn hợp lệ.</p> : <Editor kind={kind} record={modal.record}/>}
          <Reason />
        </ActionForm>}
    </Modal>}
  </>;
}

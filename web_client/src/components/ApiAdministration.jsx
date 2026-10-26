import { useEffect, useMemo, useState } from "react";
import { PageControls } from "./ux.jsx";
import { ResourceState, useResource } from "./ui.jsx";
import { roles } from "../domain.js";

const methodOrder = ["GET", "POST", "PATCH", "DELETE"];

function Method({ name }) {
  return <span className={`api-method api-${name.toLowerCase()}`}>{name}</span>;
}

function Info({ name, value }) {
  return <article className="api-overview-stat"><span>{name}</span><strong>{value}</strong></article>;
}

function Matrix({ data }) {
  return <>
    <div className="api-inline-note" role="note">
      Quyền cuối cùng = tài khoản hoạt động + role còn hiệu lực + phạm vi phòng ban/loại yêu cầu + actor được giao + trạng thái + phân tách nhiệm vụ (SoD). Một người có nhiều role vẫn không vượt các ràng buộc này.
    </div>
    <div className="role-matrix-cards">
      {data.items.map((item) => <article className="role-matrix-card" key={item.role}>
        <div className="section-head"><div><small>{item.uc}</small><h3>{item.name}</h3></div><span className="role-pill">{item.role}</span></div>
        <dl><dt>Quyền xem</dt><dd>{item.read}</dd><dt>Hành động được phép</dt><dd>{item.write}</dd><dt>Giới hạn bắt buộc</dt><dd>{item.constraints}</dd></dl>
      </article>)}
    </div>
    <section className="panel api-policy-footnotes">
      <h2>Phạm vi được áp dụng</h2>
      <p><strong>{data.scope_model}</strong> · Phạm vi DEPARTMENT không tự bao gồm phòng ban con. GLOBAL và ALL phải khai báo rõ.</p>
      <p>{data.note}</p>
    </section>
  </>;
}

export default function ApiAdministration() {
  const [tab, setTab] = useState("endpoints");
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("");
  const [method, setMethod] = useState("");
  const [role, setRole] = useState("");
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const catalog = useResource("/api/v1/admin/api-catalog");
  const matrix = useResource("/api/v1/admin/access-matrix");
  const ready = useResource("/health/ready");
  const items = useMemo(() => catalog.data?.items || [], [catalog.data]);
  const domains = useMemo(() => [...new Set(items.map((i) => i.domain))].sort(), [items]);
  const filtered = useMemo(() => items.filter((item) => {
    const needle = query.trim().toLocaleLowerCase("vi");
    return (!needle || [item.path, item.purpose, item.uc, item.protection].some((part) => part.toLocaleLowerCase("vi").includes(needle)))
      && (!domain || item.domain === domain) && (!method || item.method === method)
      && (!role || item.roles.includes(role));
  }), [items, query, domain, method, role]);
  useEffect(() => { setOffset(0); }, [query, domain, method, role]);
  const visible = filtered.slice(offset, offset + limit);
  const total = filtered.length;
  const verbs = methodOrder.map((name) => [name, items.filter((x) => x.method === name).length]);
  return <>
    <header className="page-heading api-title"><div><p className="eyebrow">QUẢN TRỊ HỆ THỐNG / UC17</p><h1>Quản lý API & ma trận quyền</h1>
      <p className="muted">Danh mục endpoint theo hợp đồng SRS v2, chức năng theo 7 vai trò và chẩn đoán trạng thái dịch vụ. Quyền thực tế luôn được bảo vệ tại Backend.</p></div>
      <span className="api-readonly">CHỈ ĐỌC CẤU HÌNH API</span>
    </header>
    <section className="api-overview-grid" aria-label="Thông tin API">
      <Info name="Endpoint được mô tả" value={items.length || "—"}/>
      <Info name="Nhóm nghiệp vụ" value={domains.length || "—"}/>
      <Info name="Vai trò trong đặc tả" value={matrix.data?.items?.length || 7}/>
      <article className="api-overview-stat"><span>Backend readiness</span>
        <strong className={ready.data?.status === "ready" ? "api-ok" : "api-alert"}>{ready.loading ? "Đang kiểm tra" : ready.data?.status === "ready" ? "READY" : "Chưa xác nhận"}</strong>
        {ready.error && <small>{ready.error}</small>}
      </article>
    </section>
    <div className="tabs" role="tablist" aria-label="Quản lý API">
      <button type="button" role="tab" aria-selected={tab === "endpoints"} className={tab === "endpoints" ? "active" : "secondary"} onClick={() => setTab("endpoints")}>Danh mục API</button>
      <button type="button" role="tab" aria-selected={tab === "matrix"} className={tab === "matrix" ? "active" : "secondary"} onClick={() => setTab("matrix")}>Ma trận phân quyền</button>
      <button type="button" role="tab" aria-selected={tab === "health"} className={tab === "health" ? "active" : "secondary"} onClick={() => setTab("health")}>Giám sát API</button>
    </div>
    {tab === "endpoints" && <section className="panel" id="api-results">
      <div className="section-head"><div><h2>Hợp đồng API phiên bản 1</h2><p className="muted">{catalog.data?.contract}. Đây là danh mục dùng để quản trị và truy vết, không phải công cụ cấp token hoặc thay đổi route đang chạy.</p></div></div>
      <ResourceState resource={catalog}>
        <div className="api-filter-grid">
          <label>Tìm API / Use Case<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nhập đường dẫn, UC hoặc chức năng" aria-label="Tìm kiếm endpoint" /></label>
          <label>Nhóm nghiệp vụ<select value={domain} onChange={(e) => setDomain(e.target.value)}><option value="">Tất cả nhóm</option>{domains.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label>Phương thức<select value={method} onChange={(e) => setMethod(e.target.value)}><option value="">Mọi phương thức</option>{verbs.map(([name, n]) => <option key={name} value={name}>{name} ({n})</option>)}</select></label>
          <label>Vai trò<select value={role} onChange={(e) => setRole(e.target.value)}><option value="">Mọi vai trò</option>{matrix.data?.items?.map((item) => <option key={item.role} value={item.role}>{roles[item.role] || item.role}</option>)}</select></label>
        </div>
        <div className="api-result-summary"><strong>{total} endpoint</strong> phù hợp bộ lọc · Phương thức và scope chỉ mang tính tài liệu; server vẫn quyết định có được gọi hay không.</div>
        <div className="table-wrap"><table className="responsive-records api-table"><thead><tr><th>Phương thức</th><th>API / Mục đích</th><th>Vai trò</th><th>Quy tắc bảo vệ</th><th>UC</th></tr></thead><tbody>
          {visible.map((item) => <tr key={`${item.method}-${item.path}`}>
            <td data-label="Phương thức"><Method name={item.method}/></td>
            <td data-label="Endpoint"><div className="api-endpoint"><code>{item.path}</code><strong>{item.purpose}</strong><small>{item.domain}</small></div></td>
            <td data-label="Vai trò"><div className="api-role-list">{item.roles.map((r) => <span key={r} className="api-role-chip">{r}</span>)}</div></td>
            <td data-label="Bảo vệ"><span className="muted">{item.protection}</span></td>
            <td data-label="Use Case">{item.uc}</td>
          </tr>)}
        </tbody></table></div>
        {total === 0 && <p className="empty">Không tìm thấy API nào phù hợp với bộ lọc hiện tại.</p>}
        <PageControls offset={offset} limit={limit} count={visible.length} nextOffset={offset + limit < total ? offset + limit : null} onPage={setOffset} onLimit={(v) => { setLimit(v); setOffset(0); }} title="API" targetId="api-results"/>
      </ResourceState>
    </section>}
    {tab === "matrix" && <ResourceState resource={matrix}><Matrix data={matrix.data}/></ResourceState>}
    {tab === "health" && <section className="panel api-health-panel"><div className="section-head"><div><h2>Kiểm tra trạng thái Backend</h2><p className="muted">Đọc trực tiếp /health/ready; mỗi dấu kiểm lấy từ Backend đang chạy, không sử dụng dữ liệu minh họa.</p></div><button className="secondary" type="button" onClick={ready.reload}>Kiểm tra lại</button></div>
      <ResourceState resource={ready}>
        <div className="api-health-summary"><span className={ready.data?.status === "ready" ? "api-health-light success" : "api-health-light"}/><strong>{ready.data?.status === "ready" ? "Dịch vụ sẵn sàng" : "Dịch vụ chưa sẵn sàng"}</strong></div>
        <div className="api-check-grid">{Object.entries(ready.data?.checks || {}).map(([key, value]) => <div className="api-check" key={key}><span aria-hidden="true">{value ? "✓" : "!"}</span><code>{key}</code><strong>{value ? "PASS" : "FAIL"}</strong></div>)}</div>
      </ResourceState>
    </section>}
    <div className="api-inline-note" role="note"><strong>Giới hạn theo P0:</strong> tài liệu mô tả quản lý danh tính qua công cụ vận hành được kiểm soát; giao diện này bổ sung danh mục API và ma trận quyền để vận hành/kiểm chứng. Không có API-key CRUD, proxy gọi API tùy ý hoặc chuyển quyền của người dùng bằng việc sửa catalogue.</div>
  </>;
}

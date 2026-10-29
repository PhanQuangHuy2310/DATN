import { useEffect, useMemo, useState } from "react";
import { PageControls } from "./ux.jsx";
import { ResourceState, useResource } from "./ui.jsx";
import { roles } from "../domain.js";
import { buildAccessMatrix } from "../accessMatrix.js";

const methodOrder = ["GET", "POST", "PATCH", "DELETE"];

function Method({ name }) {
  return <span className={`api-method api-${name.toLowerCase()}`}>{name}</span>;
}

function Info({ name, value }) {
  return <article className="api-overview-stat"><span>{name}</span><strong>{value}</strong></article>;
}

function Matrix({ data, endpoints = [], catalogLoading = false, catalogError = "" }) {
  const [focusRole, setFocusRole] = useState("");
  const [focusDomain, setFocusDomain] = useState("");
  const [selection, setSelection] = useState(null);
  const matrix = useMemo(() => buildAccessMatrix(data?.items || [], endpoints), [data, endpoints]);
  const columns = focusDomain ? matrix.domains.filter((name) => name === focusDomain) : matrix.domains;
  const rows = focusRole ? matrix.rows.filter((item) => item.role === focusRole) : matrix.rows;
  const selectedRole = (data?.items || []).find((item) => item.role === (selection?.role || focusRole)) || (data?.items || [])[0];
  const selectedCell = selection && matrix.rows.find((row) => row.role === selection.role)?.cells.find((cell) => cell.domain === selection.domain);
  return <section className="access-matrix-layout" aria-label="Biểu đồ ma trận phân quyền">
    <div className="access-matrix-heading">
      <div><p className="eyebrow">BẢN ĐỒ PHÂN QUYỀN</p><h2>Vai trò × nhóm nghiệp vụ</h2>
        <p className="muted">Mỗi ô thể hiện số endpoint có khai báo vai trò trực tiếp trong danh mục API. Chọn một ô để xem chi tiết.</p></div>
      <div className="access-matrix-legend" aria-label="Chú giải biểu đồ">
        <span><i className="access-key access-none"/>Chưa khai báo</span><span><i className="access-key access-read"/>Chỉ đọc</span>
        <span><i className="access-key access-write"/>Thao tác</span><span><i className="access-key access-both"/>Cả hai</span>
      </div>
    </div>
    <div className="access-matrix-filters">
      <label>Vai trò
        <select value={focusRole} onChange={(e) => { setFocusRole(e.target.value); setSelection(null); }}><option value="">Cả 7 vai trò</option>
          {(data?.items || []).map((item) => <option value={item.role} key={item.role}>{item.name}</option>)}
        </select>
      </label>
      <label>Nhóm nghiệp vụ
        <select value={focusDomain} onChange={(e) => {setFocusDomain(e.target.value);setSelection(null);}}><option value="">Tất cả nhóm</option>
          {matrix.domains.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
        </select>
      </label>
      {(focusRole || focusDomain) && <button className="secondary" type="button" onClick={() => {setFocusRole("");setFocusDomain("");setSelection(null);}}>Đặt lại bộ lọc</button>}
    </div>
    {catalogLoading ? <p role="status">Đang tải danh mục API để lập biểu đồ…</p> : catalogError ?
      <p className="error" role="alert">Không tải được danh mục endpoint để lập biểu đồ: {catalogError}</p> : matrix.domains.length ? <>
      <div className="access-matrix-scroll" tabIndex={0} aria-label="Bảng ma trận phân quyền, cuộn ngang để xem đủ cột">
        <table className="access-matrix-heatmap" style={{minWidth: `${155 + columns.length * 116}px`}}>
          <thead><tr><th scope="col">Vai trò</th>{columns.map((domain) => <th scope="col" key={domain}>{domain}</th>)}</tr></thead>
          <tbody>{rows.map((row) => <tr key={row.role}>
            <th scope="row"><strong>{row.name}</strong><small>{row.role}</small></th>
            {row.cells.filter((cell) => columns.includes(cell.domain)).map((cell) =>
              <td key={cell.domain}><button type="button" className={`access-matrix-cell access-${cell.kind} ${selection?.role === row.role && selection?.domain === cell.domain ? "is-focused" : ""}`}
                aria-pressed={selection?.role === row.role && selection?.domain === cell.domain}
                title={`${row.name} · ${cell.domain}: ${cell.reads} GET, ${cell.writes} thao tác`}
                aria-label={`${row.name} / ${cell.domain}: ${cell.reads} endpoint đọc, ${cell.writes} endpoint thao tác`}
                onClick={() => setSelection({role: row.role, domain: cell.domain})}>
                <strong>{cell.count || "—"}</strong>{cell.count > 0 && <small>{cell.reads ? `${cell.reads} đọc` : ""}{cell.reads && cell.writes ? " · " : ""}{cell.writes ? `${cell.writes} ghi` : ""}</small>}
              </button></td>)}
          </tr>)}</tbody>
        </table>
      </div>
      <p className="access-matrix-disclaimer">Chỉ phản ánh hợp đồng API; <strong>không phải quyền hiệu lực của từng tài khoản</strong>. Vai trò tổng quát như PARTICIPANT/AUTHENTICATED chưa được quy thành quyền trực tiếp. Ô trống không đồng nghĩa bị cấm tuyệt đối. Backend vẫn kiểm tra phiên, scope, actor, trạng thái và SoD.</p>
    </> : <p role="status">Chưa có endpoint gán trực tiếp cho các vai trò trong danh mục API.</p>}
    {selectedCell && <div className="access-matrix-drilldown" role="region" aria-label="Chi tiết nhóm quyền đã chọn">
      <div className="section-head"><div><p className="eyebrow">CHI TIẾT Ô MA TRẬN</p><h3>{roles[selectedCell.role] || selectedCell.role} · {selectedCell.domain}</h3><p className="muted">{selectedCell.reads} endpoint GET · {selectedCell.writes} endpoint thao tác</p></div>
        <button className="secondary" type="button" onClick={() => setSelection(null)}>Đóng chi tiết</button></div>
      {selectedCell.endpoints.length ? <div className="access-matrix-endpoints">{selectedCell.endpoints.map((endpoint) => <div className="access-matrix-endpoint" key={`${endpoint.method}:${endpoint.path}`}><Method name={endpoint.method}/><div><code>{endpoint.path}</code><span>{endpoint.purpose}</span><small>{endpoint.protection}</small></div></div>)}</div> : <p className="muted">Danh mục API chưa khai báo endpoint trực tiếp cho cặp vai trò và nhóm này.</p>}
    </div>}
    {selectedRole && <div className="access-matrix-role-detail"><div className="section-head"><h3>Quy tắc nghiệp vụ · {selectedRole.name}</h3><small>{selectedRole.uc}</small></div>
      <dl><div><dt>Phạm vi xem</dt><dd>{selectedRole.read}</dd></div><div><dt>Thao tác nghiệp vụ</dt><dd>{selectedRole.write}</dd></div><div><dt>Giới hạn bắt buộc</dt><dd>{selectedRole.constraints}</dd></div></dl>
    </div>}
    <div className="access-matrix-scope"><strong>Phạm vi cấp quyền: </strong>{data.scope_model}. {data.note}</div>
  </section>;
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
    {tab === "matrix" && <ResourceState resource={matrix}><Matrix data={matrix.data} endpoints={items} catalogLoading={catalog.loading} catalogError={catalog.error}/></ResourceState>}
    {tab === "health" && <section className="panel api-health-panel"><div className="section-head"><div><h2>Kiểm tra trạng thái Backend</h2><p className="muted">Đọc trực tiếp /health/ready; mỗi dấu kiểm lấy từ Backend đang chạy, không sử dụng dữ liệu minh họa.</p></div><button className="secondary" type="button" onClick={ready.reload}>Kiểm tra lại</button></div>
      <ResourceState resource={ready}>
        <div className="api-health-summary"><span className={ready.data?.status === "ready" ? "api-health-light success" : "api-health-light"}/><strong>{ready.data?.status === "ready" ? "Dịch vụ sẵn sàng" : "Dịch vụ chưa sẵn sàng"}</strong></div>
        <div className="api-check-grid">{Object.entries(ready.data?.checks || {}).map(([key, value]) => <div className="api-check" key={key}><span aria-hidden="true">{value ? "✓" : "!"}</span><code>{key}</code><strong>{value ? "PASS" : "FAIL"}</strong></div>)}</div>
        {ready.data?.catalog && <div className="api-inline-note" role="status">
          <strong>Danh mục yêu cầu:</strong> {ready.data.catalog.active_type_count} loại đang bật; <strong>{ready.data.catalog.unconfigured_active_type_count} loại thiếu quy chế PUBLISHED</strong>.
          {ready.data.catalog.unconfigured_active_type_count > 0
            ? " Các loại này sẽ chưa được phép tạo/gửi đơn cho đến khi Policy Admin công bố release hợp lệ; các loại P0 có cấu hình vẫn hoạt động."
            : " Tất cả loại đang bật đều có release hợp lệ."}
        </div>}
      </ResourceState>
    </section>}
    <div className="api-inline-note" role="note"><strong>Giới hạn theo P0:</strong> tài liệu mô tả quản lý danh tính qua công cụ vận hành được kiểm soát; giao diện này bổ sung danh mục API và ma trận quyền để vận hành/kiểm chứng. Không có API-key CRUD, proxy gọi API tùy ý hoặc chuyển quyền của người dùng bằng việc sửa catalogue.</div>
  </>;
}

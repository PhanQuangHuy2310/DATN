import { useState } from "react";
import { date, types } from "../domain.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";
import { PeriodChooser } from "./DashboardOverview.jsx";
import { ClientPageHeader } from "./clientDesign.jsx";

function localDay(value) { return new Date(value).toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }); }

export function formatHours(hours) {
  if (hours === null || hours === undefined) return "—";
  if (hours >= 48) return `${(hours / 24).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} ngày`;
  return `${hours.toLocaleString("vi-VN", { maximumFractionDigits: 1 })} giờ`;
}

function rate(done, total) { return total ? `${Math.round((100 * done) / total)}%` : "—"; }

function EmployeeRequests({ employee, from, to, onOpen }) {
  const [offset, setOffset] = useState(0), [limit, setLimit] = useState(20);
  const params = new URLSearchParams({ requester_id: employee.requester_id, limit: String(limit), offset: String(offset),
    created_from: `${from}T00:00:00+07:00`, created_to: `${to}T23:59:59+07:00` });
  const list = useResource(`/api/v1/requests?${params}`);
  const items = (list.data?.items || []).filter((item) => item.status !== "DRAFT");
  return <section className="panel table-panel" id="team-employee-requests">
    <div className="section-head"><div><h2>Hồ sơ của {employee.requester_name}</h2><p className="muted">Chỉ gồm hồ sơ bạn được phép xem.</p></div></div>
    <ResourceState resource={list}>
      <div className="table-wrap"><table className="responsive-records"><thead><tr><th>Mã hồ sơ</th><th>Loại yêu cầu</th><th>Trạng thái</th><th>Người đang xử lý</th><th>Hạn xử lý</th><th></th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.id}>
          <td data-label="Mã hồ sơ" className="request-code">{item.code}</td>
          <td data-label="Loại yêu cầu">{item.type_name || types[item.type_code] || "Yêu cầu"}</td>
          <td data-label="Trạng thái"><Badge value={item.status} /></td>
          <td data-label="Người đang xử lý">{item.current_assignee_name || "—"}</td>
          <td data-label="Hạn xử lý" className={item.overdue ? "overdue" : ""}>{item.due_at ? date(item.due_at) : "—"}</td>
          <td data-label="Thao tác">{onOpen ? <button type="button" className="link" onClick={() => onOpen(item.id)}>Xem chi tiết →</button> : null}</td>
        </tr>)}</tbody></table></div>
      {!items.length && <p className="muted">Không có hồ sơ trong khoảng thời gian đã chọn.</p>}
      <PageControls offset={offset} limit={limit} nextOffset={list.data?.next_offset} count={items.length} title="hồ sơ" targetId="team-employee-requests" onPage={setOffset} onLimit={setLimit} />
    </ResourceState>
  </section>;
}

const SEGMENTS = [
  ["completed", "Hoàn thành", "done"],
  ["in_progress", "Đang thực hiện", "work"],
  ["pending", "Chờ duyệt / bổ sung", "wait"],
  ["rejected", "Bị từ chối", "stop"],
];

/** Share of each status in one row of report counts, as a stacked bar. */
function StatusBar({ row, legend = false }) {
  const total = SEGMENTS.reduce((sum, [key]) => sum + (row[key] || 0), 0);
  const label = SEGMENTS.map(([key, name]) => `${name}: ${row[key] || 0}`).join(", ");
  return <div className="team-status">
    <div className="team-status-bar" role="img" aria-label={label}>
      {total
        ? SEGMENTS.map(([key, , tone]) => (row[key] ? <span key={key} className={`seg-${tone}`} style={{ width: `${(100 * row[key]) / total}%` }} /> : null))
        : <span className="seg-empty" style={{ width: "100%" }} />}
    </div>
    {legend && <ul className="team-status-legend">{SEGMENTS.map(([key, name, tone]) => (
      <li key={key}><i className={`seg-${tone}`} aria-hidden="true" />{name} <strong>{row[key] || 0}</strong></li>
    ))}</ul>}
  </div>;
}

function initials(name = "") {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function Kpis({ totals }) {
  return <div className="team-kpis">
    <article className={`team-kpi ${totals.awaiting_me ? "is-action" : ""}`}>
      <span>Chờ tôi phê duyệt</span><strong>{totals.awaiting_me ?? 0}</strong><small>Đang đến lượt bạn xử lý</small>
    </article>
    <article className="team-kpi">
      <span>Đang xử lý</span><strong>{(totals.pending || 0) + (totals.in_progress || 0)}</strong>
      <small>{totals.pending || 0} chờ duyệt · {totals.in_progress || 0} đang thực hiện</small>
    </article>
    <article className={`team-kpi ${totals.overdue ? "is-danger" : ""}`}>
      <span>Quá hạn</span><strong>{totals.overdue ?? 0}</strong><small>Bước hiện tại đã quá hạn</small>
    </article>
    <article className="team-kpi">
      <span>Hoàn thành</span><strong>{rate(totals.completed, totals.total)}</strong>
      <small>{totals.completed || 0}/{totals.total || 0} hồ sơ · {totals.rejected || 0} bị từ chối</small>
    </article>
  </div>;
}

function DepartmentCards({ departments, onPick }) {
  if (!departments.length) return <p className="muted">Chưa có hồ sơ nào trong phạm vi của bạn trong khoảng thời gian này.</p>;
  return <div className="team-dept-grid">{departments.map((row) => <article key={row.department_id} className="team-dept-card">
    <header>
      <h3>{row.department_name}</h3>
      {row.overdue > 0 && <span className="team-pill danger">{row.overdue} quá hạn</span>}
    </header>
    <p className="team-dept-meta">{row.employees} nhân viên · {row.total} hồ sơ · hoàn thành {rate(row.completed, row.total)}</p>
    <StatusBar row={row} />
    <dl className="team-dept-stats">
      <div><dt>Chờ duyệt</dt><dd>{row.pending}</dd></div>
      <div><dt>Đang làm</dt><dd>{row.in_progress}</dd></div>
      <div><dt>Hoàn thành</dt><dd>{row.completed}</dd></div>
    </dl>
    <button type="button" className="secondary team-dept-open" onClick={() => onPick(row)}>Xem nhân viên →</button>
  </article>)}</div>;
}

function EmployeeList({ employees, showDepartment, onPick }) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLocaleLowerCase("vi-VN");
  const rows = employees
    .filter((row) => !needle || row.requester_name.toLocaleLowerCase("vi-VN").includes(needle))
    .sort((a, b) => (b.overdue || 0) - (a.overdue || 0) || b.total - a.total);
  return <>
    <input className="team-search" type="search" aria-label="Tìm nhân viên theo tên" placeholder="Tìm nhân viên theo tên…" value={query} onChange={(e) => setQuery(e.target.value)} />
    {rows.length ? <ul className="team-member-list">{rows.map((row) => <li key={row.requester_id} className="team-member">
      <span className="team-avatar" aria-hidden="true">{initials(row.requester_name)}</span>
      <div className="team-member-id">
        <strong>{row.requester_name}</strong>
        <small>{showDepartment ? `${row.department_name} · ` : ""}{row.total} hồ sơ{row.avg_completion_hours == null ? "" : ` · TB ${formatHours(row.avg_completion_hours)}`}</small>
      </div>
      <div className="team-member-chips">
        <span className="team-pill">Chờ duyệt <b>{row.pending}</b></span>
        <span className="team-pill">Đang làm <b>{row.in_progress}</b></span>
        <span className="team-pill">Từ chối <b>{row.rejected}</b></span>
        {row.overdue > 0 && <span className="team-pill danger">Quá hạn <b>{row.overdue}</b></span>}
      </div>
      <div className="team-member-rate">
        <span>Hoàn thành {rate(row.completed, row.total)}</span>
        <StatusBar row={row} />
      </div>
      <button type="button" className="secondary team-member-open" onClick={() => onPick(row)}>Xem hồ sơ →</button>
    </li>)}</ul> : <p className="muted">{needle ? "Không có nhân viên phù hợp." : "Chưa có hồ sơ nào trong phạm vi của bạn trong khoảng thời gian này."}</p>}
  </>;
}

/** Department / organization dashboard. All figures come from /api/v1/reports/team,
 * which applies the documented participant/auditor read scope on the server. */
export default function TeamDashboard({ onOpen, mode = "departments" }) {
  const employeeMode = mode === "employees";
  const [from, setFrom] = useState(() => localDay(Date.now() - 29 * 86400000));
  const [to, setTo] = useState(() => localDay(Date.now()));
  const [department, setDepartment] = useState(null);
  const [employee, setEmployee] = useState(null);
  const valid = Boolean(from && to && from <= to && Date.parse(to) - Date.parse(from) <= 366 * 86400000);
  const params = new URLSearchParams({ created_from: `${from}T00:00:00+07:00`, created_to: `${to}T23:59:59+07:00` });
  const report = useResource(valid ? `/api/v1/reports/team?${params}` : "");
  const data = report.data?.report;
  const totals = data?.totals || {};
  const employees = (data?.employees || []).filter((row) => !department || row.department_id === department.department_id);
  const drilled = Boolean(department || employee);

  return <div className="client-dashboard team-dashboard">
    <ClientPageHeader eyebrow="QUẢN LÝ PHÒNG BAN" title={employeeMode ? "Nhân viên phòng ban" : "Tổng quan phòng ban"}
      description={employeeMode ? "Hiệu suất xử lý hồ sơ theo từng nhân viên trong phạm vi bạn tham gia phê duyệt hoặc kiểm toán." : "Theo dõi hồ sơ của nhân viên mà bạn tham gia phê duyệt hoặc được cấp quyền kiểm toán."} />
    <PeriodChooser start={from} end={to} setStart={setFrom} setEnd={setTo} reload={report.reload} />
    {!valid && <p role="alert" className="error">Khoảng thời gian không hợp lệ hoặc dài hơn 12 tháng.</p>}
    {valid && <ResourceState resource={report}>{data && <>
      <Kpis totals={totals} />
      {!employeeMode && !drilled && <section className="panel team-status-panel">
        <h2>Tình trạng hồ sơ trong kỳ</h2>
        <StatusBar row={totals} legend />
      </section>}

      {drilled && <nav className="team-breadcrumb" aria-label="Phạm vi đang xem">
        <button type="button" className="link" onClick={() => { setDepartment(null); setEmployee(null); }}>{employeeMode ? "Tất cả nhân viên" : "Tất cả phòng ban"}</button>
        {department && <><span aria-hidden="true">›</span><button type="button" className="link" onClick={() => setEmployee(null)} aria-current={employee ? undefined : "page"}>{department.department_name}</button></>}
        {employee && <><span aria-hidden="true">›</span><span aria-current="page">{employee.requester_name}</span></>}
      </nav>}

      {!department && !employeeMode && <section className="panel">
        <h2>Phòng ban ({data.departments.length})</h2>
        <DepartmentCards departments={data.departments} onPick={setDepartment} />
      </section>}

      {(department || employeeMode) && !employee && <section className="panel">
        <h2>Nhân viên{department ? ` · ${department.department_name}` : ""} ({employees.length})</h2>
        <EmployeeList employees={employees} showDepartment={!department} onPick={setEmployee} />
      </section>}

      {employee && <EmployeeRequests key={employee.requester_id} employee={employee} from={from} to={to} onOpen={onOpen} />}
      <p className="muted client-org-footnote">Số liệu không gồm hồ sơ của chính bạn và chỉ tính hồ sơ bạn tham gia xử lý hoặc thuộc phạm vi kiểm toán được cấp. Thời gian hoàn thành tính từ lần gửi đầu tiên đến khi hoàn tất.</p>
    </>}</ResourceState>}
  </div>;
}

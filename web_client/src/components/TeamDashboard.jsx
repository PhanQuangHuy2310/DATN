import { useState } from "react";
import { date, types } from "../domain.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";
import { PeriodChooser } from "./DashboardOverview.jsx";
import { ClientPageHeader, ClientStatCard } from "./clientDesign.jsx";

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
  const departments = data?.departments || [];
  const employees = (data?.employees || []).filter((row) => !department || row.department_id === department.department_id);

  return <div className="client-dashboard team-dashboard">
    <ClientPageHeader eyebrow="QUẢN LÝ PHÒNG BAN" title={employeeMode ? "Nhân viên phòng ban" : "Tổng quan phòng ban"}
      description={employeeMode ? "Hiệu suất xử lý hồ sơ theo từng nhân viên trong phạm vi bạn tham gia phê duyệt hoặc kiểm toán." : "Theo dõi hồ sơ của nhân viên mà bạn tham gia phê duyệt hoặc được cấp quyền kiểm toán."} />
    <PeriodChooser start={from} end={to} setStart={setFrom} setEnd={setTo} reload={report.reload} />
    {!valid && <p role="alert" className="error">Khoảng thời gian không hợp lệ hoặc dài hơn 12 tháng.</p>}
    {valid && <ResourceState resource={report}>{data && <>
      <div className="client-metric-grid">
        <ClientStatCard title="Tổng hồ sơ" value={totals.total} detail="Trong phạm vi được xem" />
        <ClientStatCard title="Chờ tôi phê duyệt" value={totals.awaiting_me} detail="Đang đến lượt bạn" />
        <ClientStatCard title="Chờ duyệt / bổ sung" value={totals.pending} detail="Chưa có quyết định cuối" />
        <ClientStatCard title="Đang thực hiện" value={totals.in_progress} detail="Thực hiện và nghiệm thu" />
        <ClientStatCard title="Quá hạn" value={totals.overdue} detail="Bước hiện tại đã quá hạn" />
        <ClientStatCard title="Hoàn thành" value={totals.completed} detail={`Tỉ lệ ${rate(totals.completed, totals.total)}`} />
        <ClientStatCard title="Bị từ chối" value={totals.rejected} detail="Có lý do từ chối" />
      </div>

      <nav className="team-breadcrumb" aria-label="Phạm vi đang xem">
        <button type="button" className="link" onClick={() => { setDepartment(null); setEmployee(null); }} aria-current={!department ? "page" : undefined}>Tổ chức</button>
        {department && <><span aria-hidden="true">›</span><button type="button" className="link" onClick={() => setEmployee(null)} aria-current={!employee ? "page" : undefined}>{department.department_name}</button></>}
        {employee && <><span aria-hidden="true">›</span><span aria-current="page">{employee.requester_name}</span></>}
      </nav>

      {!department && !employeeMode && <section className="panel table-panel">
        <h2>Phòng ban</h2>
        <div className="table-wrap"><table className="responsive-records"><thead><tr><th>Phòng ban</th><th>Nhân viên</th><th>Tổng</th><th>Chờ duyệt</th><th>Đang thực hiện</th><th>Quá hạn</th><th>Hoàn thành</th><th></th></tr></thead>
          <tbody>{departments.map((row) => <tr key={row.department_id}>
            <td data-label="Phòng ban"><strong>{row.department_name}</strong></td>
            <td data-label="Nhân viên">{row.employees}</td><td data-label="Tổng">{row.total}</td>
            <td data-label="Chờ duyệt">{row.pending}</td><td data-label="Đang thực hiện">{row.in_progress}</td>
            <td data-label="Quá hạn">{row.overdue ? <span className="badge REJECTED">{row.overdue}</span> : 0}</td>
            <td data-label="Hoàn thành">{row.completed} ({rate(row.completed, row.total)})</td>
            <td data-label="Thao tác"><button type="button" className="link" onClick={() => setDepartment(row)}>Xem nhân viên →</button></td>
          </tr>)}</tbody></table></div>
        {!departments.length && <p className="muted">Chưa có hồ sơ nào trong phạm vi của bạn trong khoảng thời gian này.</p>}
      </section>}

      {(department || employeeMode) && !employee && <section className="panel table-panel">
        <h2>Hiệu suất nhân viên{department ? ` · ${department.department_name}` : ""}</h2>
        <div className="table-wrap"><table className="responsive-records"><thead><tr><th>Nhân viên</th><th>Tổng</th><th>Chờ duyệt</th><th>Đang thực hiện</th><th>Hoàn thành</th><th>Từ chối</th><th>Quá hạn</th><th>TG hoàn thành TB</th><th></th></tr></thead>
          <tbody>{employees.map((row) => <tr key={row.requester_id}>
            <td data-label="Nhân viên"><strong>{row.requester_name}</strong>{!department && <span className="ds-cell-sub">{row.department_name}</span>}</td>
            <td data-label="Tổng">{row.total}</td><td data-label="Chờ duyệt">{row.pending}</td>
            <td data-label="Đang thực hiện">{row.in_progress}</td><td data-label="Hoàn thành">{row.completed}</td>
            <td data-label="Từ chối">{row.rejected}</td>
            <td data-label="Quá hạn">{row.overdue ? <span className="badge REJECTED">{row.overdue}</span> : 0}</td>
            <td data-label="TG hoàn thành TB">{formatHours(row.avg_completion_hours)}</td>
            <td data-label="Thao tác"><button type="button" className="link" onClick={() => setEmployee(row)}>Xem hồ sơ →</button></td>
          </tr>)}</tbody></table></div>
      </section>}

      {employee && <EmployeeRequests key={employee.requester_id} employee={employee} from={from} to={to} onOpen={onOpen} />}
      <p className="muted client-org-footnote">Số liệu không gồm hồ sơ của chính bạn và chỉ tính hồ sơ bạn tham gia xử lý hoặc thuộc phạm vi kiểm toán được cấp. Thời gian hoàn thành tính từ lần gửi đầu tiên đến khi hoàn tất.</p>
    </>}</ResourceState>}
  </div>;
}

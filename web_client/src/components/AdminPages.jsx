import { useState } from "react";
import { api } from "../api.js";
import { date, statuses, types } from "../domain.js";
import { ActionForm, Badge, Modal, Reason, ResourceState, command, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";
import { PeriodChooser } from "./DashboardOverview.jsx";
import { EmptyState, PageHeader, PageTabs, StatCard, useDebounced } from "./design.jsx";
import { Policy, AdminEvents } from "./Admin.jsx";
import PlanCatalog from "./PlanCatalog.jsx";
import WorkflowDiagrams from "./WorkflowDiagrams.jsx";
import AuditorWorkspace from "./AuditorWorkspace.jsx";
import ApiAdministration from "./ApiAdministration.jsx";

const localDay = (value) => new Date(value).toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });
const STAGE = { APPROVAL: "Phê duyệt", EXECUTION: "Thực hiện", ACCEPTANCE: "Nghiệm thu" };
const EVENT_TYPES = { APPROVAL_REQUESTED: "Yêu cầu phê duyệt", EXECUTION_READY: "Sẵn sàng thực hiện", SLA_REMINDER: "Nhắc hạn xử lý", SLA_BREACH: "Quá hạn xử lý", REQUEST_UPDATED: "Cập nhật hồ sơ" };
const OUTBOX_STATES = { PENDING: "Đang chờ gửi", PROCESSING: "Đang gửi", SENT: "Đã gửi", DEAD: "Gửi thất bại" };

const shortDate = (value) => new Date(value).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" });
function rate(part, total) { return total ? `${Math.round((100 * part) / total)}%` : "—"; }

function DepartmentSelect({ value, onChange, label = "Phòng ban" }) {
  const list = useResource("/api/v1/admin/departments?limit=100&active=true");
  return <label>{label}<select value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Tất cả phòng ban</option>
    {(list.data?.items || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
  </select></label>;
}
function TypeSelect({ value, onChange }) {
  const list = useResource("/api/v1/request-types");
  return <label>Loại yêu cầu<select value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Tất cả loại</option>
    {(list.data?.items || []).map((t) => <option key={t.code} value={t.code}>{t.name || types[t.code] || "Loại yêu cầu"}</option>)}
  </select></label>;
}
function StatusSelect({ value, onChange }) {
  return <label>Trạng thái<select value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Tất cả trạng thái</option>
    {Object.entries(statuses).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
  </select></label>;
}

function HealthList({ diagnostics, ready }) {
  const checks = ready.data?.checks || {};
  const rows = [
    ["Máy chủ ứng dụng (API)", ready.error ? "bad" : ready.data?.status === "ready" ? "ok" : "warn", ready.error ? "Không kết nối được" : ready.data?.status === "ready" ? "Sẵn sàng" : "Cần kiểm tra"],
    ["Cơ sở dữ liệu", checks.database ? "ok" : "bad", checks.database ? "Kết nối bình thường" : "Không sẵn sàng"],
    ["Bộ nhớ đệm bảo mật", checks.shared_security_cache ? "ok" : "warn", checks.shared_security_cache ? "Bình thường" : "Không khả dụng"],
    ["Dịch vụ AI", diagnostics.data ? (diagnostics.data.ai_service.healthy ? "ok" : "warn") : "", diagnostics.data ? (diagnostics.data.ai_service.healthy ? "Đang phản hồi" : "Không phản hồi — AI dùng chế độ dự phòng") : "Đang kiểm tra…"],
    ["Hàng đợi thông báo (worker)", diagnostics.data ? (diagnostics.data.worker.backlog_ok ? "ok" : "bad") : "", diagnostics.data ? (diagnostics.data.worker.backlog_ok ? "Không có tồn đọng quá hạn" : `Tồn đọng ${Math.round(diagnostics.data.outbox.oldest_pending_seconds / 60)} phút — kiểm tra worker`) : "Đang kiểm tra…"],
  ];
  return <ul className="ds-health-list">{rows.map(([name, tone, text]) => <li key={name}><span>{name}</span><span><i className={`ds-dot ${tone}`} aria-hidden="true" />{text}</span></li>)}</ul>;
}

/** System-wide dashboard; every figure comes from /api/v1/admin/overview and diagnostics. */
export function AdminDashboard({ navigate }) {
  const [start, setStart] = useState(() => localDay(Date.now() - 29 * 86400000));
  const [end, setEnd] = useState(() => localDay(Date.now()));
  const [department, setDepartment] = useState(""), [type, setType] = useState(""), [status, setStatus] = useState("");
  const valid = Boolean(start && end && start <= end && Date.parse(end) - Date.parse(start) <= 366 * 86400000);
  const params = new URLSearchParams({ created_from: `${start}T00:00:00+07:00`, created_to: `${end}T23:59:59+07:00` });
  if (department) params.set("department_id", department);
  if (type) params.set("type_code", type);
  if (status) params.set("status", status);
  const overview = useResource(valid ? `/api/v1/admin/overview?${params}` : "");
  const diagnostics = useResource("/api/v1/admin/diagnostics");
  const ready = useResource("/health/ready");
  const data = overview.data;
  const by = data?.by_status || {};
  const pending = (by.PENDING_APPROVAL || 0) + (by.NEEDS_INFO || 0);
  const running = (by.READY_FOR_EXECUTION || 0) + (by.IN_PROGRESS || 0) + (by.WAITING_FOR_ACCEPTANCE || 0);
  const maxType = Math.max(1, ...(data?.top_types || []).map((t) => t.count));
  return <>
    <PageHeader eyebrow="TRUNG TÂM QUẢN TRỊ" title="Tổng quan hệ thống" description="Khối lượng hồ sơ, hạn xử lý và tình trạng dịch vụ trong phạm vi quản trị được cấp."
      action={<button type="button" onClick={() => navigate("ops")}>Theo dõi vận hành →</button>} />
    <PeriodChooser start={start} end={end} setStart={setStart} setEnd={setEnd} reload={() => { overview.reload(); diagnostics.reload(); }} />
    <section className="panel ds-filter"><div className="client-filter-fields">
      <DepartmentSelect value={department} onChange={setDepartment} /><TypeSelect value={type} onChange={setType} /><StatusSelect value={status} onChange={setStatus} />
    </div></section>
    {!valid && <p role="alert" className="error">Khoảng thời gian không hợp lệ hoặc dài hơn 12 tháng.</p>}
    {valid && <ResourceState resource={overview}>{data && <>
      <div className="ds-stat-grid" style={{ margin: "16px 0" }}>
        <StatCard title="Tổng hồ sơ" value={data.total} detail="Trong kỳ đã chọn" />
        <StatCard title="Chờ phê duyệt" value={pending} detail="Gồm hồ sơ cần bổ sung" tone="warning" />
        <StatCard title="Đang thực hiện" value={running} detail="Thực hiện và nghiệm thu" />
        <StatCard title="Hoàn thành" value={by.COMPLETED || 0} detail={`Tỉ lệ ${rate(by.COMPLETED || 0, data.total)}`} tone="success" />
        <StatCard title="Từ chối / Đã hủy" value={`${by.REJECTED || 0} / ${by.CANCELLED || 0}`} detail="Kết thúc không hoàn thành" />
        <StatCard title="Quá hạn" value={data.overdue} detail="Bước hiện tại đã quá hạn" tone={data.overdue ? "danger" : undefined} />
        <StatCard title="Người dùng hoạt động" value={data.users?.active} detail={`Trên tổng ${data.users?.total ?? "—"} tài khoản`} />
      </div>
      <div className="ds-grid-2">
        <section className="panel"><h2>So sánh phòng ban</h2>
          {data.by_department?.length ? <div className="table-wrap"><table><thead><tr><th>Phòng ban</th><th>Tổng</th><th>Chờ duyệt</th><th>Quá hạn</th><th>Hoàn thành</th></tr></thead>
            <tbody>{data.by_department.map((d) => <tr key={d.department_id} className={d.overdue ? "is-overdue" : ""}><td>{d.department_name || "—"}</td><td>{d.total}</td><td>{d.pending}</td><td className={d.overdue ? "overdue" : ""}>{d.overdue}</td><td>{d.completed} ({rate(d.completed, d.total)})</td></tr>)}</tbody></table></div>
            : <EmptyState title="Chưa có hồ sơ" description="Không có dữ liệu trong bộ lọc hiện tại." />}
        </section>
        <section className="panel"><h2>Loại yêu cầu phát sinh nhiều</h2>
          {data.top_types?.length ? <div className="client-chart-list">{data.top_types.map((t) => <div key={t.code} className="client-chart-row"><span>{t.name || types[t.code] || "Loại yêu cầu"}</span><div className="ds-bar"><span style={{ width: `${(100 * t.count) / maxType}%` }} /></div><strong>{t.count}</strong></div>)}</div>
            : <EmptyState title="Chưa có dữ liệu" />}
        </section>
      </div>
    </>}</ResourceState>}
    <section className="panel" style={{ marginTop: 16 }}><div className="section-head"><h2>Tình trạng dịch vụ</h2><button type="button" className="secondary" onClick={() => { ready.reload(); diagnostics.reload(); }}>Kiểm tra lại</button></div>
      <HealthList diagnostics={diagnostics} ready={ready} />
    </section>
  </>;
}

const ROLE_FOR_TARGET = { APPROVAL_STEP: "APPROVER", EXECUTOR: "EXECUTOR", PLANNED_EXECUTOR: "EXECUTOR", ACCEPTOR: "ACCEPTOR" };
function ReassignDialog({ item, onClose, onDone }) {
  const initial = item.active_step ? "APPROVAL_STEP" : item.current_attempt ? "EXECUTOR" : item.acceptor_id ? "ACCEPTOR" : "PLANNED_EXECUTOR";
  const [target, setTarget] = useState(initial);
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim(), 300);
  const users = useResource(`/api/v1/admin/users?limit=50&active=true&role=${ROLE_FOR_TARGET[target]}${q ? `&q=${encodeURIComponent(q)}` : ""}`);
  const targetId = target === "APPROVAL_STEP" ? item.active_step?.id : target === "EXECUTOR" ? item.current_attempt?.id : item.id;
  return <Modal title={`Điều chuyển ${item.code}`} onClose={onClose}>
    <ActionForm submitLabel="Xác nhận điều chuyển" onSubmit={async (values) => {
      if (!values.new_user_id) throw new Error("Vui lòng chọn người nhận mới.");
      await command(`requests/${item.id}/reassign`, { target_kind: target, target_id: targetId, new_user_id: values.new_user_id, reason: values.reason, expected_version: item.lock_version });
      onDone();
    }}>
      <p className="muted">Hiện tại: <strong>{item.responsible?.name || "Chưa phân công"}</strong>{item.responsible?.stage ? ` · ${STAGE[item.responsible.stage]}` : ""}</p>
      <label>Vị trí xử lý<select value={target} onChange={(e) => setTarget(e.target.value)}>
        {item.active_step && <option value="APPROVAL_STEP">Người phê duyệt (bước đang chờ)</option>}
        {item.current_attempt && <option value="EXECUTOR">Người thực hiện</option>}
        {item.acceptor_id && <option value="ACCEPTOR">Người nghiệm thu</option>}
        {item.planned_executor_id && <option value="PLANNED_EXECUTOR">Người thực hiện dự kiến</option>}
      </select></label>
      <label>Tìm người nhận<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Họ tên hoặc email" /></label>
      <label>Người nhận mới<select name="new_user_id" required defaultValue="" key={target + q}>
        <option value="" disabled>{users.loading ? "Đang tải…" : "Chọn người có vai trò phù hợp"}</option>
        {(users.data?.items || []).map((u) => <option key={u.id} value={u.id}>{u.display_name}{u.email ? ` · ${u.email}` : ""}</option>)}
      </select></label>
      <small className="muted">Chỉ hiển thị tài khoản đang hoạt động có vai trò phù hợp; hệ thống kiểm tra lại phạm vi và quy tắc tách biệt trách nhiệm khi xác nhận.</small>
      <Reason />
    </ActionForm>
  </Modal>;
}

/** Request | Creator | Current handler | Department | Stage | Deadline | Overdue | Status | Actions */
export function OperationsPage({ onOpen, initialQuery = "" }) {
  const [search, setSearch] = useState(initialQuery), [status, setStatus] = useState(""), [department, setDepartment] = useState(""), [type, setType] = useState("");
  const [offset, setOffset] = useState(0), [limit, setLimit] = useState(20), [selected, setSelected] = useState(null);
  const q = useDebounced(search.trim(), 300);
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (department) params.set("department_id", department);
  if (type) params.set("type_code", type);
  const list = useResource(`/api/v1/ops/requests?${params}`);
  const items = list.data?.items || [];
  const reset = (setter) => (value) => { setter(value); setOffset(0); };
  return <>
    <PageHeader eyebrow="VẬN HÀNH" title="Theo dõi vận hành" description="Người đang xử lý, giai đoạn và hạn của từng hồ sơ; điều chuyển khi người phụ trách không thể tiếp tục." />
    <section className="panel ds-filter"><div className="client-filter-fields">
      <label>Tìm hồ sơ<input type="search" value={search} onChange={(e) => reset(setSearch)(e.target.value)} placeholder="Mã hoặc tiêu đề" /></label>
      <StatusSelect value={status} onChange={reset(setStatus)} /><DepartmentSelect value={department} onChange={reset(setDepartment)} /><TypeSelect value={type} onChange={reset(setType)} />
    </div></section>
    <ResourceState resource={list}><section className="panel table-panel" id="ops-results">
      {items.length ? <div className="table-wrap"><table className="responsive-records ds-compact-table"><thead><tr>
        <th>Hồ sơ</th><th>Người tạo</th><th>Người đang xử lý</th><th>Phòng ban</th><th>Giai đoạn</th><th>Hạn xử lý</th><th>Quá hạn</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
        <tbody>{items.map((r) => <tr key={r.id} className={r.overdue ? "is-overdue" : ""}>
          <td data-label="Hồ sơ"><strong>{r.code}</strong><span className="ds-cell-sub">{r.type_name || types[r.type_code] || "Yêu cầu"}</span></td>
          <td data-label="Người tạo">{r.requester_name || "—"}</td>
          <td data-label="Người đang xử lý">{r.responsible?.name || <span className="muted">Chưa phân công</span>}</td>
          <td data-label="Phòng ban">{r.department_name || "—"}</td>
          <td data-label="Giai đoạn">{STAGE[r.responsible?.stage] || "—"}</td>
          <td data-label="Hạn xử lý">{r.sla?.due_at ? shortDate(r.sla.due_at) : "—"}</td>
          <td data-label="Quá hạn">{r.overdue ? <span className="badge REJECTED">Quá hạn</span> : <span className="muted">Không</span>}</td>
          <td data-label="Trạng thái"><Badge value={r.status} /></td>
          <td data-label="Thao tác"><div className="actions">
            {onOpen && <button type="button" className="link" onClick={() => onOpen(r.id)}>Xem</button>}
            <button type="button" className="secondary" disabled={["COMPLETED", "CANCELLED", "REJECTED", "DRAFT"].includes(r.status) || !(r.active_step || r.current_attempt || r.acceptor_id || r.planned_executor_id)} onClick={() => setSelected(r)}>Điều chuyển</button>
          </div></td>
        </tr>)}</tbody></table></div> : <EmptyState title="Không có hồ sơ phù hợp" description="Thử thay đổi bộ lọc." />}
      <PageControls offset={offset} limit={limit} nextOffset={list.data?.next_offset} count={items.length} title="hồ sơ" targetId="ops-results" onPage={setOffset} onLimit={setLimit} />
    </section></ResourceState>
    {selected && <ReassignDialog item={selected} onClose={() => setSelected(null)} onDone={() => { setSelected(null); list.reload(); }} />}
  </>;
}

/** Outbox / worker / SLA diagnostics with replay of failed deliveries. */
export function SlaNotificationsPage({ navigate }) {
  const diag = useResource("/api/v1/admin/diagnostics");
  const [replay, setReplay] = useState(null);
  const d = diag.data;
  const counts = d?.outbox?.counts || {};
  return <>
    <PageHeader eyebrow="VẬN HÀNH" title="SLA & thông báo" description="Hạn xử lý đang mở, nhắc hạn đã phát và tình trạng gửi thông báo của worker."
      action={<button type="button" className="secondary" onClick={diag.reload}>Làm mới</button>} />
    <ResourceState resource={diag}>{d && <>
      <div className="ds-stat-grid" style={{ marginBottom: 16 }}>
        <StatCard title="Bước đang tính hạn" value={d.sla.open_stages} detail="Phê duyệt, thực hiện, nghiệm thu" />
        <StatCard title="Đã quá hạn" value={d.sla.overdue_stages} tone={d.sla.overdue_stages ? "danger" : undefined} detail="Cần xử lý hoặc điều chuyển" />
        <StatCard title="Nhắc hạn 24 giờ qua" value={d.sla.alerts_24h.REMINDER || 0} detail={`Báo quá hạn: ${d.sla.alerts_24h.BREACH || 0}`} />
        <StatCard title="Thông báo gửi lỗi" value={counts.DEAD || 0} tone={counts.DEAD ? "danger" : undefined} detail="Cần gửi lại thủ công" />
      </div>
      <div className="ds-grid-2">
        <section className="panel"><h2>Hàng đợi thông báo</h2>
          <ul className="ds-health-list">{Object.entries(OUTBOX_STATES).map(([k, v]) => <li key={k}><span>{v}</span><strong>{counts[k] || 0}</strong></li>)}</ul>
          <p className="muted">Lần gửi gần nhất: {d.outbox.last_sent_at ? date(d.outbox.last_sent_at) : "chưa có"}. {d.worker.backlog_ok ? "Không có thông báo tồn đọng quá 5 phút." : `Có thông báo chờ quá ${Math.round(d.outbox.oldest_pending_seconds / 60)} phút — kiểm tra worker (start_worker_local.cmd).`}</p>
        </section>
        <section className="panel"><h2>Quá hạn cần xử lý</h2>
          <p className="muted">Danh sách chi tiết người đang xử lý và hạn nằm ở trang vận hành.</p>
          <button type="button" onClick={() => navigate("ops")}>Mở theo dõi vận hành →</button>
        </section>
      </div>
      <section className="panel" style={{ marginTop: 16 }}><h2>Thông báo gửi thất bại</h2>
        {d.outbox.dead_events.length ? <div className="table-wrap"><table><thead><tr><th>Loại thông báo</th><th>Hồ sơ</th><th>Số lần thử</th><th>Mã lỗi</th><th>Thời điểm</th><th></th></tr></thead>
          <tbody>{d.outbox.dead_events.map((e) => <tr key={e.id}><td>{EVENT_TYPES[e.event_type] || "Thông báo hệ thống"}</td><td>{e.request_code || "—"}</td><td>{e.attempts}{e.replay_count ? ` (đã gửi lại ${e.replay_count})` : ""}</td><td>{e.last_error_code || "—"}</td><td>{date(e.created_at)}</td>
            <td><button type="button" className="secondary" onClick={() => setReplay(e)}>Gửi lại</button></td></tr>)}</tbody></table></div>
          : <EmptyState title="Không có thông báo gửi lỗi" description="Mọi thông báo đã được worker xử lý." />}
      </section>
    </>}</ResourceState>
    {replay && <Modal title="Gửi lại thông báo" onClose={() => setReplay(null)}>
      <ActionForm submitLabel="Gửi lại" onSubmit={async (values) => { await command(`ops/outbox/${replay.id}/replay`, { reason: values.reason }); setReplay(null); diag.reload(); }}>
        <p>{EVENT_TYPES[replay.event_type] || "Thông báo hệ thống"} · {replay.request_code || "—"}</p><Reason />
      </ActionForm>
    </Modal>}
  </>;
}

function Maintenance() {
  const info = useResource("/api/v1/system/maintenance");
  const m = info.data?.maintenance || info.data || {};
  const [confirm, setConfirm] = useState(null);
  return <section className="panel"><h2>Chế độ bảo trì</h2>
    <ResourceState resource={info}>
      <p><i className={`ds-dot ${m.active ? "warn" : "ok"}`} aria-hidden="true" />{m.active ? "Đang bảo trì" : "Hoạt động bình thường"}{m.started_at ? ` · bắt đầu ${date(m.started_at)}` : ""}</p>
      {m.message && <p className="muted">Thông điệp cho người dùng: {m.message}</p>}
      {m.active ? <button type="button" onClick={() => setConfirm("complete")}>Kết thúc bảo trì</button>
        : <button type="button" className="danger" onClick={() => setConfirm("start")}>Bật chế độ bảo trì</button>}
    </ResourceState>
    {confirm && <Modal title={confirm === "start" ? "Bật chế độ bảo trì" : "Kết thúc bảo trì"} onClose={() => setConfirm(null)}>
      <ActionForm danger={confirm === "start"} submitLabel="Xác nhận" onSubmit={async (values) => {
        await api(`/api/v1/system/maintenance/${confirm}`, { method: "POST", body: JSON.stringify(values) });
        setConfirm(null); info.reload();
      }}>
        {confirm === "start" && <><p>Người dùng nghiệp vụ sẽ thấy thông báo bảo trì cho đến khi kết thúc.</p>
          <label>Thông điệp hiển thị cho người dùng<textarea name="message" maxLength={500} rows={3} placeholder="Ví dụ: Hệ thống đang cập nhật quy chế, vui lòng quay lại sau." /></label></>}
        <label>Ghi chú quản trị<textarea name="admin_message" maxLength={500} rows={2} /></label>
      </ActionForm>
    </Modal>}
  </section>;
}

export function SystemConfigPage() {
  const [tab, setTab] = useState("maintenance");
  return <>
    <PageHeader eyebrow="HỆ THỐNG" title="Cấu hình hệ thống" description="Bảo trì, danh mục API và trạng thái tích hợp." />
    <PageTabs label="Mục cấu hình" value={tab} onChange={setTab} tabs={[["maintenance", "Bảo trì"], ["api", "API & tích hợp"]]} />
    {tab === "maintenance" ? <Maintenance /> : <ApiAdministration />}
  </>;
}

export function PolicyWorkspace({ canManageAccess, onManageAccess }) {
  const [tab, setTab] = useState("releases");
  return <>
    <PageTabs label="Quy chế & quy trình" value={tab} onChange={setTab} tabs={[["releases", "Phiên bản quy chế"], ["catalog", "Danh mục 18 mẫu"], ["diagrams", "Sơ đồ luồng"]]} />
    {tab === "releases" && <Policy canManageAccess={canManageAccess} onManageAccess={onManageAccess} />}
    {tab === "catalog" && <PlanCatalog />}
    {tab === "diagrams" && <WorkflowDiagrams />}
  </>;
}

export function AuditLogPage({ onOpen }) {
  const [tab, setTab] = useState("requests");
  return <>
    <PageHeader eyebrow="KIỂM TOÁN" title="Nhật ký kiểm toán" description="Xác minh chuỗi nhật ký của hồ sơ và tra cứu thay đổi quản trị." />
    <PageTabs label="Loại nhật ký" value={tab} onChange={setTab} tabs={[["requests", "Kiểm toán hồ sơ"], ["admin", "Nhật ký quản trị"]]} />
    {tab === "requests" ? <AuditorWorkspace onOpen={onOpen} /> : <AdminEvents />}
  </>;
}

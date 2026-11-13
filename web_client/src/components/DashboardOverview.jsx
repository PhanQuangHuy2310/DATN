import { InfoHint, PageInfo } from "./design.jsx";
import { useState } from "react";
import { useResource, ResourceState, Badge } from "./ui.jsx";
import { statuses, types } from "../domain.js";

function dateInput(value) { return new Date(value).toLocaleDateString("en-CA", {timeZone:"Asia/Ho_Chi_Minh"}); }
const initialEnd = () => dateInput(new Date());
const initialStart = () => dateInput(new Date(Date.now()-29*86400000));

export function PeriodChooser({start, end, setStart, setEnd, reload}) {
  function quick(days) {
    setEnd(initialEnd());setStart(dateInput(new Date(Date.now()-(days-1)*86400000)));
  }
  return <div className="panel overview-filter" aria-label="Bộ lọc thời gian báo cáo">
    <div className="overview-quick-group"><span className="overview-field-title">Chọn nhanh</span>
      <div className="overview-quick-dates">
        <button type="button" className="secondary" onClick={() => quick(1)}>Hôm nay</button>
        <button type="button" className="secondary" onClick={() => quick(7)}>7 ngày</button>
        <button type="button" className="secondary" onClick={() => quick(30)}>30 ngày</button>
        <button type="button" className="secondary" onClick={() => quick(365)}>12 tháng</button>
      </div>
    </div>
    <label className="overview-date-field"><span>Từ ngày</span><input type="date" value={start} max={end} onChange={e => setStart(e.target.value)}/></label>
    <label className="overview-date-field"><span>Đến ngày</span><input type="date" value={end} min={start} onChange={e => setEnd(e.target.value)}/></label>
    <div className="overview-apply-group"><span className="overview-field-title" aria-hidden="true">&nbsp;</span><button type="button" className="secondary" onClick={reload}>Cập nhật</button></div>
  </div>;
}
function Trend({rows}) {
  const max = Math.max(1, ...rows.map(row => row.count));
  return <div className="overview-ranked-list">{rows.length ? rows.map((row, idx) =>
    <div className="overview-ranked-row" key={row.code}>
      <span className="overview-ranked-position">{idx+1}</span>
      <div><strong>{row.name || types[row.code] || "Loại yêu cầu"}</strong>
        <div className="overview-ranked-track"><span style={{width:`${100*row.count/max}%`}}/></div>
      </div>
      <b>{row.count}</b>
    </div>) : <p className="muted">Chưa có yêu cầu trong khoảng thời gian này.</p>}</div>;
}
export function DashboardStats({byStatus={}, total=0, overdue=null, topTypes=[]}) {
  const pending = (byStatus.PENDING_APPROVAL || 0) + (byStatus.NEEDS_INFO || 0);
  const running = (byStatus.READY_FOR_EXECUTION || 0) + (byStatus.IN_PROGRESS || 0) + (byStatus.WAITING_FOR_ACCEPTANCE || 0);
  return <>
    <div className="stats-grid overview-cards" aria-label="Tình hình xử lý">
      {[["Tổng yêu cầu",total],["Cần xử lý",pending],["Đang thực hiện",running],["Đã hoàn thành",byStatus.COMPLETED||0], ...(overdue === null ? [] : [["Quá hạn",overdue]])].map(([title,n]) =>
        <article className="stat" key={title}><span>{title}</span><strong>{n}</strong><small>Trong thời gian đã chọn</small></article>)}
    </div>
    <div className="overview-grid">
      <section className="panel"><h2>Trạng thái hồ sơ<InfoHint>Đếm theo hồ sơ, trong phạm vi quyền truy cập của bạn.</InfoHint></h2>
        <div className="overview-status-grid">{Object.entries(statuses).map(([key])=><div key={key}><Badge value={key}/><strong>{byStatus[key]||0}</strong></div>)}</div>
      </section>
      <section className="panel"><h2>Loại yêu cầu được xử lý nhiều<InfoHint>Xếp theo số hồ sơ trong khoảng thời gian đã chọn.</InfoHint></h2><Trend rows={topTypes}/></section>
    </div>
  </>;
}
export function SystemOverview({navigate}) {
  const [start,setStart] = useState(initialStart), [end,setEnd] = useState(initialEnd);
  const valid = Boolean(start && end && start<=end && (new Date(end)-new Date(start))<=366*86400000);
  const params = new URLSearchParams({created_from:`${start}T00:00:00+07:00`,created_to:`${end}T23:59:59+07:00`});
  const r = useResource(`/api/v1/admin/overview?${params}`);
  const health = useResource("/health/ready");
  return <>
    <div className="page-heading"><div><p className="eyebrow">TRUNG TÂM ĐIỀU HÀNH</p><h1>Tình hình toàn hệ thống<PageInfo>Theo dõi khối lượng công việc, hạn xử lý và các loại yêu cầu thường phát sinh theo quyền quản trị được cấp.</PageInfo></h1></div></div>
    <PeriodChooser start={start} end={end} setStart={setStart} setEnd={setEnd} reload={r.reload}/>
    {!valid && <p role="alert" className="error">Vui lòng chọn khoảng thời gian hợp lệ (không quá 12 tháng).</p>}
    {valid && <ResourceState resource={r}>
      {r.data && <DashboardStats byStatus={r.data.by_status} total={r.data.total} overdue={r.data.overdue} topTypes={r.data.top_types}/>}
    </ResourceState>}
    <div className="overview-grid">
      <section className="panel"><h2>Sức khỏe dịch vụ<InfoHint>Đọc trạng thái từ Backend, không tự suy đoán tình trạng Supabase hoặc dịch vụ AI.</InfoHint></h2>
        <span className={`health-indicator ${health.data?.status === "ready" ? "healthy" : "warning"}`} role="status">{health.loading ? "Đang kiểm tra…" : health.error ? "Chưa kết nối được Backend" : health.data?.status === "ready" ? "Dịch vụ sẵn sàng" : "Cần kiểm tra dịch vụ"}</span>
        <div className="dashboard-quick"><button className="secondary" type="button" onClick={health.reload}>Kiểm tra lại</button><button type="button" onClick={()=>navigate("ops")}>Đi đến vận hành →</button></div>
      </section>
      <section className="panel"><h2>Quản lý nhanh</h2><div className="dashboard-quick"><button type="button" onClick={()=>navigate("ops")}>Theo dõi người xử lý & hạn →</button><button className="secondary" type="button" onClick={()=>navigate("request-catalog")}>Danh mục yêu cầu →</button><button className="secondary" type="button" onClick={()=>navigate("users")}>Quản lý nhân viên →</button></div></section>
    </div>
    <p className="muted">Lưu ý: số liệu phản ánh các hồ sơ trong phạm vi OPS được cấp, không bao gồm các phòng ban ngoài quyền truy cập.</p>
  </>;
}
export function PersonalOverviewStats({report}) {
 return <DashboardStats byStatus={report?.by_status||{}} total={report?.submitted||0} topTypes={report?.top_types||[]}/>;
}

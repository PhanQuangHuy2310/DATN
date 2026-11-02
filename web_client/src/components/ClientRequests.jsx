import { useEffect, useMemo, useState } from "react";
import { date, statuses, types } from "../domain.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";
import { ClientPageHeader, ClientFilterSection } from "./clientDesign.jsx";

import { WORKFLOW_COLUMNS, allowedStages, requestStage, STATUS_STAGES } from "../clientWorkflow.js";
const STAGE_TITLES = { ...Object.fromEntries(WORKFLOW_COLUMNS.map(stage => [stage.key, stage.title])), rejected: "Từ chối", cancelled: "Đã hủy" };
function dayBoundary(day, end=false) { return day ? `${day}T${end ? "23:59:59" : "00:00:00"}+07:00` : ""; }
function RequestEntry({item, onOpen, names}) {
  return <article className="client-request-entry">
    <div className="client-request-entry-head"><strong>{names[item.type_code] || types[item.type_code] || "Yêu cầu"}</strong><Badge value={item.status}/></div>
    <p className="muted">{item.code || "Mã đang cập nhật"}</p>
    {item.current_assignee_name && <p className="client-request-assignee">Đang xử lý: <strong>{item.current_assignee_name}</strong></p>}
    {item.due_at && <p className={item.overdue ? "client-request-due overdue" : "client-request-due"}>Hạn: {date(item.due_at)}</p>}
    <div className="client-request-entry-foot"><small>Cập nhật {date(item.updated_at)}</small><button type="button" className="link" onClick={() => onOpen(item.id)}>Xem chi tiết →</button></div>
  </article>;
}
export default function ClientRequests({ user, onOpen, onNew, revision, initialQuery = "", initialStage = "mine" }) {
  const stages = allowedStages(user);
  const [stage, setStage] = useState(() => stages.some(x => x.key===initialStage) ? initialStage : stages[0]?.key || "mine");
  const [mode, setMode] = useState("kanban");
  const [search, setSearch] = useState(initialQuery);
  const [debounced, setDebounced] = useState(initialQuery);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState("newest");
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [prevQuery, setPrevQuery] = useState(initialQuery);
  if (prevQuery !== initialQuery) {
    setPrevQuery(initialQuery);
    setSearch(initialQuery);
    setDebounced(initialQuery.trim());
    setOffset(0);
  }
  useEffect(() => { const timer=setTimeout(()=>{setDebounced(search.trim());setOffset(0);},320);return()=>clearTimeout(timer);},[search]);
  const active = stages.find(x=>x.key===stage) || stages[0];
  const params = new URLSearchParams({limit: String(limit), offset: String(offset), tab: active?.filter || "mine"});
  if (debounced) params.set("q",debounced);
  if (type) params.set("type_code",type);
  if (status || active?.status) params.set("status",active?.status || status);
  if (from) params.set("created_from",dayBoundary(from));
  if (to) params.set("created_to",dayBoundary(to,true));
  const result = useResource(`/api/v1/requests?${params.toString()}&_revision=${revision}`);
  const catalog = useResource("/api/v1/request-types");
  const names=Object.fromEntries((catalog.data?.items || []).map(item=>[item.code,item.name]));
  const rows=useMemo(()=>{
    const items=[...(result.data?.items || [])];
    items.sort((a,b)=>{
      const da=Date.parse(sort==="oldest" ? a.created_at || a.updated_at : a.updated_at || a.created_at)||0;
      const db=Date.parse(sort==="oldest" ? b.created_at || b.updated_at : b.updated_at || b.created_at)||0;
      return sort==="oldest" ? da-db : db-da;
    });
    return items;
  },[result.data,sort]);
  const columns=stage==="mine" ? STATUS_STAGES : [stage];
  function reset() {setSearch("");setDebounced("");setType("");setStatus("");setFrom("");setTo("");setSort("newest");setOffset(0);}
  return <div className="client-requests">
    <ClientPageHeader eyebrow="KHÔNG GIAN LÀM VIỆC" title="Yêu cầu của tôi" description="Tra cứu hồ sơ và công việc theo quyền được cấp, theo dõi từ nháp đến hoàn thành." action={user.roles.includes("REQUESTER") ? <button type="button" onClick={onNew}>＋ Tạo yêu cầu mới</button> : null}/>
    <nav className="client-stage-tabs" aria-label="Các bước xử lý yêu cầu">{stages.map(s=><button type="button" key={s.key} aria-current={stage===s.key?"page":undefined} aria-pressed={stage===s.key} className={stage===s.key?"is-active":""} onClick={()=>{setStage(s.key);setOffset(0);setStatus("");}}>{s.title}</button>)}</nav>
    <ClientFilterSection footer={<><small className="muted">{active?.help}. Số lượng chỉ tính trên trang dữ liệu đã tải.</small><div className="actions"><button className="secondary" type="button" onClick={reset}>Xóa lọc</button><button className="secondary" type="button" onClick={result.reload}>Làm mới</button><div className="client-view-toggle" role="group" aria-label="Kiểu hiển thị"><button type="button" className={mode==="kanban"?"is-active":""} aria-pressed={mode==="kanban"} onClick={()=>setMode("kanban")}>Cột</button><button type="button" className={mode==="table"?"is-active":""} aria-pressed={mode==="table"} onClick={()=>setMode("table")}>Bảng</button></div></div></>}><label>Tìm mã yêu cầu<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Tìm mã hồ sơ…"/></label>
      <label>Loại yêu cầu<select value={type} onChange={e=>{setType(e.target.value);setOffset(0);}}><option value="">Tất cả</option>{(catalog.data?.items||[]).map(t=><option key={t.code} value={t.code}>{t.name||types[t.code]||"Loại yêu cầu"}</option>)}</select></label>
      <label>Trạng thái<select value={active?.status || status} disabled={Boolean(active?.status)} onChange={e=>{setStatus(e.target.value);setOffset(0);}}><option value="">Tất cả</option>{Object.entries(statuses).map(([k,label])=><option key={k} value={k}>{label}</option>)}</select></label>
      <label>Từ ngày<input type="date" value={from} max={to||undefined} onChange={e=>{setFrom(e.target.value);setOffset(0);}}/></label><label>Đến ngày<input type="date" value={to} min={from||undefined} onChange={e=>{setTo(e.target.value);setOffset(0);}}/></label>
      <label>Sắp xếp<select value={sort} onChange={e=>setSort(e.target.value)}><option value="newest">Mới cập nhật</option><option value="oldest">Cũ trước</option></select></label>
    </ClientFilterSection>
    <ResourceState resource={result}><div id="client-request-results">
      {mode==="kanban" ? <div className="client-kanban" aria-label="Bảng tiến trình xử lý">{columns.map(column=><section key={column} className="client-kanban-column"><h2>{STAGE_TITLES[column]} <span>{rows.filter(r=>requestStage(r.status)===column).length}</span></h2><div className="client-kanban-cards">{rows.filter(r=>requestStage(r.status)===column).map(item=><RequestEntry key={item.id} item={item} onOpen={onOpen} names={names}/>)}{!rows.some(r=>requestStage(r.status)===column)&&<p className="muted client-empty-column">Không có hồ sơ trên trang hiện tại.</p>}</div></section>)}</div> : <section className="panel table-panel"><div className="table-wrap"><table className="responsive-records"><thead><tr><th>Mã hồ sơ</th><th>Loại yêu cầu</th><th>Trạng thái</th><th>Người đang xử lý</th><th>Hạn xử lý</th><th>Ngày cập nhật</th><th>Thao tác</th></tr></thead><tbody>{rows.map(item=><tr key={item.id}><td data-label="Mã hồ sơ">{item.code}</td><td data-label="Loại yêu cầu">{names[item.type_code]||types[item.type_code]||"Yêu cầu"}</td><td data-label="Trạng thái"><Badge value={item.status}/></td><td data-label="Người đang xử lý">{item.current_assignee_name||"—"}</td><td data-label="Hạn xử lý" className={item.overdue?"overdue":""}>{item.due_at?date(item.due_at):"—"}</td><td data-label="Ngày cập nhật">{date(item.updated_at)}</td><td data-label="Thao tác"><button type="button" className="link" onClick={()=>onOpen(item.id)}>Xem chi tiết →</button></td></tr>)}</tbody></table></div></section>}
      {rows.length===0&&<div className="panel empty"><h3>Chưa có hồ sơ phù hợp</h3><p>Thử xóa bộ lọc hoặc chọn giai đoạn khác.</p></div>}
      <PageControls offset={offset} limit={limit} nextOffset={result.data?.next_offset} count={rows.length} title="hồ sơ" targetId="client-request-results" onPage={setOffset} onLimit={setLimit}/>
    </div></ResourceState>
  </div>;
}

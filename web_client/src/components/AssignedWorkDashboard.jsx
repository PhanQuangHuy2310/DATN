import { date, types } from "../domain.js";
import { useResource, ResourceState, Badge } from "./ui.jsx";
import { ClientPageHeader } from "./clientDesign.jsx";
const TASKS=[
 {role:"APPROVER", tab:"approval", name:"Chờ tôi phê duyệt"},
 {role:"EXECUTOR", tab:"execution", name:"Công việc thực hiện"},
 {role:"ACCEPTOR", tab:"acceptance", name:"Chờ tôi nghiệm thu"},
];
/** No organization-wide metrics unless the API grants scoped management analytics. */
export default function AssignedWorkDashboard({ user, onOpen, navigate }) {
 const queues=TASKS.filter(t=>user.roles.includes(t.role));
 const selected=queues[0];
 const list=useResource(`/api/v1/requests?tab=${selected?.tab||"mine"}&limit=20&offset=0`);
 const items=list.data?.items||[];
 return <div className="client-dashboard">
  <ClientPageHeader eyebrow="CÔNG VIỆC CỦA TÔI" title={`Xin chào, ${user.display_name||"bạn"}`} description="Các hồ sơ đang chờ bạn xử lý theo quyền được cấp, không hiển thị dữ liệu phòng ban ngoài phạm vi quyền." action={selected?<button type="button" onClick={()=>navigate(selected.tab)}>Mở công việc →</button>:null}/>
  <section className="panel"><div className="section-head"><h2>{selected?.name||"Công việc được giao"}</h2><button type="button" className="secondary" onClick={list.reload}>Cập nhật</button></div>
   <ResourceState resource={list}>{items.length?<div className="client-recent-list">{items.map(item=><button type="button" key={item.id} className="client-recent-row" onClick={()=>onOpen(item.id)}><span><strong>{types[item.type_code]||"Yêu cầu"}</strong><small>{item.code} · {date(item.updated_at)}</small></span><Badge value={item.status}/><span aria-hidden="true">→</span></button>)}</div>:<p className="muted">Hiện không có hồ sơ trong trang công việc đầu tiên.</p>}</ResourceState>
   {list.data?.next_offset!==null&&list.data?.next_offset!==undefined&&<small className="muted">Còn hồ sơ khác. Vào danh sách công việc để xem tiếp.</small>}
  </section>
  <div className="role-task-grid">{queues.map(task=><button type="button" key={task.tab} className="panel role-task" onClick={()=>navigate(task.tab)}><strong>{task.name}</strong><span aria-hidden="true">→</span></button>)}</div>
  <section className="panel client-scope-note"><h2>Báo cáo cấp quản lý</h2><p>Để xem toàn bộ phòng ban hoặc đơn vị, Backend cần cung cấp endpoint thống kê và quyền truy cập theo từng cấp quản lý. Hiện tại cổng này chỉ hiển thị các công việc được phân công thực sự.</p></section>
 </div>;
}

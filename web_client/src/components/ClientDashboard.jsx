import { useState } from "react";
import { date, types } from "../domain.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";
import { PeriodChooser } from "./DashboardOverview.jsx";
import { ClientPageHeader, ClientStatCard } from "./clientDesign.jsx";
import { formatHours } from "./TeamDashboard.jsx";

function localDay(value) { return new Date(value).toLocaleDateString("en-CA",{timeZone:"Asia/Ho_Chi_Minh"}); }
function initialFrom(){return localDay(Date.now()-29*86400000);}
function initialTo(){return localDay(Date.now());}
function formatPercent(n){return n===null||n===undefined?"—":`${Math.round(n*100)}%`;}
const closeStatuses=new Set(["COMPLETED","REJECTED","CANCELLED"]);
export default function ClientDashboard({ user, onOpen, navigate }) {
 const [from,setFrom]=useState(initialFrom), [to,setTo]=useState(initialTo);
 const valid=Boolean(from&&to&&from<=to&&(Date.parse(to)-Date.parse(from))<=366*86400000);
 const params=new URLSearchParams({created_from:`${from}T00:00:00+07:00`,created_to:`${to}T23:59:59+07:00`,scope:"mine"});
 const report=useResource(`/api/v1/reports/requests?${params}`);
 const recent=useResource("/api/v1/requests?tab=mine&limit=10&offset=0");
 const mine=recent.data?.items||[];
 const data=report.data?.report;
 const by=data?.by_status||{};
 const total=data?.submitted||0;
 const inProgress=Object.entries(by).filter(([key])=>!closeStatuses.has(key)).reduce((s,[,n])=>s+n,0);
 const rejected=by.REJECTED||0;
 const top=data?.top_types||[];
 const maxTop=Math.max(1,...top.map(x=>x.count));
 const days=Math.max(1,Math.ceil((Date.parse(to)-Date.parse(from))/86400000)+1||1);
 const cards=[
  ["Yêu cầu đã gửi",total,"Trong khoảng thời gian"],
  ["Tần suất yêu cầu",`${(total/days*30).toLocaleString("vi-VN",{maximumFractionDigits:1})}/30 ngày`,"Ước tính theo khoảng đã chọn"],
  ["Đang xử lý",inProgress,"Chưa kết thúc xử lý"],
  ["Chờ phê duyệt",(by.PENDING_APPROVAL||0)+(by.NEEDS_INFO||0),"Gồm hồ sơ cần bổ sung"],
  ["Bị từ chối",rejected,"Yêu cầu bị từ chối"],
  ["Hoàn thành",by.COMPLETED||0,"Yêu cầu đã kết thúc"],
  ["Tỉ lệ hoàn thành",formatPercent(data?.completed_rate),"Số hoàn thành / đã gửi"],
  ["Thời gian hoàn thành TB",formatHours(data?.avg_completion_hours),"Từ lúc gửi đến khi hoàn tất"],
  ["Thời gian phê duyệt TB",formatHours(data?.avg_approval_hours),"Từ lúc gửi đến khi duyệt xong"],
 ];
 return <div className="client-dashboard"><ClientPageHeader eyebrow="TỔNG QUAN CÁ NHÂN" title={`Xin chào, ${user.display_name||"bạn"}`} description="Thống kê yêu cầu bạn đã tạo; không tính bản nháp." action={<button type="button" onClick={()=>navigate("mine")}>Xem yêu cầu của tôi →</button>}/>
  <PeriodChooser start={from} end={to} setStart={setFrom} setEnd={setTo} reload={report.reload}/>
  {!valid?<p role="alert" className="error">Khoảng thời gian không hợp lệ hoặc dài hơn 12 tháng.</p>:<ResourceState resource={report}>
   {data&&<><div className="client-metric-grid">{cards.map(([title,value,detail])=><ClientStatCard key={title} title={title} value={value} detail={detail}/>)}</div>
   <div className="client-dashboard-charts"><section className="panel"><h2>Phân bố trạng thái</h2><div className="client-chart-list">{Object.entries(by).map(([status,count])=><div key={status} className="client-chart-row"><Badge value={status}/><div className="client-chart-track"><span style={{width:`${100*count/Math.max(1,total)}%`}}/></div><strong>{count}</strong></div>)}{!Object.keys(by).length&&<p className="muted">Chưa có hồ sơ được gửi trong kỳ.</p>}</div></section>
   <section className="panel"><h2>Loại yêu cầu thường gặp</h2><div className="client-chart-list">{top.map(item=><div className="client-chart-row" key={item.code}><span>{item.name||types[item.code]||"Loại yêu cầu"}</span><div className="client-chart-track"><span style={{width:`${100*item.count/maxTop}%`}}/></div><strong>{item.count}</strong></div>)}{!top.length&&<p className="muted">Không có dữ liệu cho kỳ này.</p>}</div></section></div></>}
  </ResourceState>}
  <section className="panel"><div className="section-head"><h2>Hồ sơ gần đây</h2><button type="button" className="secondary" onClick={()=>navigate("mine")}>Xem tất cả</button></div><ResourceState resource={recent}><div className="client-recent-list">{mine.map(item=><button key={item.id} type="button" className="client-recent-row" onClick={()=>onOpen(item.id)}><span><strong>{types[item.type_code]||"Yêu cầu"}</strong><small>{item.code} · {date(item.updated_at)}</small></span><Badge value={item.status}/><span aria-hidden="true">→</span></button>)}{!mine.length&&<p className="muted">Chưa có hồ sơ gần đây.</p>}</div></ResourceState></section>
  {(user.roles.includes("APPROVER")||user.roles.includes("AUDITOR"))&&<section className="panel client-scope-note"><h2>Theo dõi phòng ban</h2><p>Xem hồ sơ của nhân viên mà bạn tham gia phê duyệt: số đang chờ, quá hạn và hiệu suất theo từng người.</p><button type="button" className="secondary" onClick={()=>navigate("team")}>Mở bảng điều khiển phòng ban →</button></section>}
 </div>;
}

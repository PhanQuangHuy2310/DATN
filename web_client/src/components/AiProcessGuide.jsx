import { useState } from "react";
import { types, resolverLabels } from "../domain.js";
import { resolveLifecycle } from "../flowDiagrams.js";
import { useResource, ResourceState, Badge } from "./ui.jsx";
import { ClientPageHeader } from "./clientDesign.jsx";
import { AiAssessmentPanel } from "./RequestProgress.jsx";

const FLOW = [
  ["Tạo hồ sơ", "Nhân viên nhập biểu mẫu; AI có thể gợi ý loại yêu cầu và đánh giá rủi ro."],
  ["Gửi yêu cầu", "Hệ thống kiểm tra biểu mẫu, quy chế và xác định đúng người duyệt."],
  ["Phê duyệt", "Người phụ trách đọc kết quả AI (nếu có) và tự quyết định duyệt, từ chối hoặc yêu cầu bổ sung."],
  ["Thực hiện & nghiệm thu", "Sau khi được duyệt, công việc chuyển sang xử lý và nghiệm thu nếu quy trình yêu cầu."],
];
const statusStage = { DRAFT: 0, NEEDS_INFO: 1, PENDING_APPROVAL: 2, READY_FOR_EXECUTION: 3, IN_PROGRESS: 3, WAITING_FOR_ACCEPTANCE: 3, COMPLETED: 4, REJECTED: 2, CANCELLED: 1 };

/** Read-only actual workflow data + on-demand AI inference. Never makes approval decisions. */
export default function AiProcessGuide({ user, onOpen, navigate, portal = "client" }) {
  const isAdmin = portal === "admin";
  const canApprove = Boolean(user?.roles?.includes("APPROVER"));
  const canCreate = Boolean(user?.roles?.includes("REQUESTER"));
  const [queue, setQueue] = useState(canCreate ? "mine" : "approval");
  // Admins have no business queues: list by their own read scope (auditors see their audit scope).
  const list = useResource(isAdmin ? "/api/v1/requests?limit=20&offset=0" : `/api/v1/requests?tab=${queue}&limit=20&offset=0`);
  const [picked, setPicked] = useState("");
  const currentId = (list.data?.items || []).some(r=>r.id===picked) ? picked : (list.data?.items?.[0]?.id || "");
  const detail = useResource(currentId ? `/api/v1/requests/${currentId}` : "");
  const request = detail.data?.request;
  const selectedStage=request ? (statusStage[request.status] ?? 0) : null;
  const current=request?.progress?.current_assignee;
  const isApprovalOnly = resolveLifecycle(request) === "A";
  return <div className="client-section ai-workflow-page">
    <ClientPageHeader eyebrow="HỖ TRỢ NGHIỆP VỤ" title="AI trong quy trình xử lý yêu cầu" description="Theo dõi luồng tạo, đánh giá, phê duyệt và thực hiện hồ sơ. AI chỉ cung cấp gợi ý; người có quyền quyết định duyệt hoặc từ chối." action={isAdmin ? null : <button type="button" className="secondary" onClick={()=>navigate?.(canCreate?"mine":"approval")}>Mở không gian xử lý →</button>}/>
    <section className="panel"><div className="section-head"><h2>Quy trình trong hệ thống</h2><span className="muted">Dữ liệu cập nhật theo thời gian thực</span></div>
      <ol className="ai-workflow-track">{FLOW.map(([title,desc],i)=><li key={title}><span className="ai-workflow-number">{i+1}</span><strong>{title}</strong><p>{desc}</p></li>)}</ol>
    </section>
    <section className="panel"><div className="section-head"><div><h2>Theo dõi hồ sơ và kiểm tra AI</h2><p className="muted">Chọn một hồ sơ thực tế để xem tuyến duyệt và chạy phân tích khi cần.</p></div><button type="button" className="secondary" onClick={()=>{list.reload();if(currentId) detail.reload();}}>Làm mới</button></div>
      <div className="ai-workflow-chooser">
        {!isAdmin&&canCreate&&canApprove&&<label>Nguồn hồ sơ<select value={queue} onChange={e=>{setQueue(e.target.value);setPicked("");}}><option value="mine">Yêu cầu của tôi</option><option value="approval">Đang chờ tôi duyệt</option></select></label>}
        <ResourceState resource={list}><label>Hồ sơ<select value={currentId} onChange={e=>setPicked(e.target.value)} disabled={!list.data?.items?.length}><option value="">{list.data?.items?.length?"Chọn hồ sơ":"Chưa có hồ sơ"}</option>{(list.data?.items||[]).map(item=><option value={item.id} key={item.id}>{item.code} · {types[item.type_code]||"Yêu cầu"}</option>)}</select></label></ResourceState>
      </div>
      {currentId && <ResourceState resource={detail}>{request&&<>
        <div className="ai-workflow-summary"><div><strong>{request.payload?.title||types[request.type_code]||"Yêu cầu"}</strong><p className="muted">Trạng thái hiện tại</p><Badge value={request.status}/></div><div><strong>Người đang phụ trách</strong><p>{current?.name||"Không có bước đang chờ"}</p><p className="muted">{current?(resolverLabels[current.resolver_code]||({APPROVER:"Người phê duyệt",EXECUTOR:"Người thực hiện",ACCEPTOR:"Người nghiệm thu",REQUESTER:"Người yêu cầu"})[current.role]):"Cập nhật theo hồ sơ thực tế"}</p></div></div>
        <div className="ai-workflow-progress" aria-label="Trạng thái xử lý hồ sơ">{FLOW.map(([title],i)=><div key={title} className={isApprovalOnly && i===3 ? "is-skipped" : selectedStage>i?"is-done":selectedStage===i?"is-current":"is-upcoming"}><span aria-hidden="true">{isApprovalOnly && i===3 ? "—" : selectedStage>i?"":i+1}</span><strong>{isApprovalOnly && i===3 ? "Không cần thực hiện / nghiệm thu" : title}</strong></div>)}</div>
        {["REJECTED", "CANCELLED", "NEEDS_INFO"].includes(request.status) && <p className="muted">Hồ sơ đang ở trạng thái cần xử lý riêng; không được tính là đã hoàn thành toàn bộ các công đoạn.</p>}
        <div className="ai-workflow-controls"><button type="button" className="secondary" onClick={()=>onOpen?.(request.id)}>Mở hồ sơ để xử lý →</button></div>
        {request.status === "DRAFT" ? <p className="muted">Bản nháp chưa được gửi nên chưa thể đánh giá AI.</p> : <AiAssessmentPanel key={request.id} requestId={request.id} canRun={!isAdmin && request.progress?.stage !== "CLOSED"} />}
      </>}</ResourceState>}
      {!currentId&&!list.loading&&<p className="muted">{isAdmin ? "Không có hồ sơ trong phạm vi bạn được xem. Theo quy định, quản trị vận hành chỉ xem thông tin điều phối; đánh giá AI theo hồ sơ dành cho người tham gia xử lý và kiểm toán viên." : "Chưa có hồ sơ phù hợp để theo dõi. Bạn có thể tạo yêu cầu mới hoặc mở danh sách cần phê duyệt."}</p>}
    </section>
  </div>;
}

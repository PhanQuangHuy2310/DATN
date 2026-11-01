import { useState } from "react";
import { api } from "../api.js";
import { types, errorText } from "../domain.js";
import { resolveLifecycle } from "../flowDiagrams.js";
import { useResource, ResourceState, Badge } from "./ui.jsx";
import { ClientPageHeader } from "./clientDesign.jsx";

const FLOW = [
  ["Tạo hồ sơ", "Nhân viên nhập biểu mẫu; AI có thể gợi ý loại yêu cầu và đánh giá rủi ro."],
  ["Gửi yêu cầu", "Backend kiểm tra biểu mẫu, quy chế và xác định đúng người duyệt."],
  ["Phê duyệt", "Người phụ trách đọc kết quả AI (nếu có) và tự quyết định duyệt, từ chối hoặc yêu cầu bổ sung."],
  ["Thực hiện & nghiệm thu", "Sau khi được duyệt, công việc chuyển sang xử lý và nghiệm thu nếu quy trình yêu cầu."],
];
const statusStage = { DRAFT: 0, NEEDS_INFO: 1, PENDING_APPROVAL: 2, READY_FOR_EXECUTION: 3, IN_PROGRESS: 3, WAITING_FOR_ACCEPTANCE: 3, COMPLETED: 4, REJECTED: 2, CANCELLED: 1 };
function phaseText(value) { return value === "running" ? "Đang phân tích…" : value === "done" ? "Đã hoàn thành" : value === "fallback" ? "Kết quả dự phòng" : value === "error" ? "Không thành công" : "Chưa chạy"; }

/** Read-only actual workflow data + on-demand AI inference. Never makes approval decisions. */
export default function AiProcessGuide({ user, onOpen, navigate }) {
  const canApprove = Boolean(user?.roles?.includes("APPROVER"));
  const canCreate = Boolean(user?.roles?.includes("REQUESTER"));
  const [queue, setQueue] = useState(canCreate ? "mine" : "approval");
  const list = useResource(`/api/v1/requests?tab=${queue}&limit=20&offset=0`);
  const [picked, setPicked] = useState("");
  const currentId = (list.data?.items || []).some(r=>r.id===picked) ? picked : (list.data?.items?.[0]?.id || "");
  const detail = useResource(currentId ? `/api/v1/requests/${currentId}` : "");
  const request = detail.data?.request;
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState({});
  const [result, setResult] = useState({});
  const [error, setError] = useState("");
  const [analyzedId, setAnalyzedId] = useState("");
  const analysis = analyzedId === currentId ? result : {};
  const stages = analyzedId === currentId ? phase : {};

  async function runAssessment() {
    if (!request || busy) return;
    setBusy(true); setError(""); setAnalyzedId(request.id); setResult({});
    setPhase({classify:"running",risk:"running"});
    const p = request.payload || {};
    const tasks = await Promise.allSettled([
      api("/api/v1/ai/classify", {method:"POST",body:JSON.stringify({title:String(p.title||types[request.type_code]||"Yêu cầu"),description:String(p.reason||p.description||"")})})
        .then(r=>{setResult(prev=>({...prev,classify:r.data}));setPhase(prev=>({...prev,classify:r.data?.fallback_used?"fallback":"done"}));})
        .catch(e=>{setPhase(prev=>({...prev,classify:"error"}));throw e;}),
      api("/api/v1/ai/risk-score", {method:"POST",body:JSON.stringify({request_type:String(request.type_code||"general").toLowerCase(),lifecycle_template:resolveLifecycle(request)||"A",risk_weight:Number(request.risk_weight)||2})})
        .then(r=>{setResult(prev=>({...prev,risk:r.data}));setPhase(prev=>({...prev,risk:r.data?.fallback_used?"fallback":"done"}));})
        .catch(e=>{setPhase(prev=>({...prev,risk:"error"}));throw e;}),
    ]);
    const fail=tasks.find(t=>t.status==="rejected");
    if (fail) setError(`Không thể hoàn tất toàn bộ phân tích: ${errorText(fail.reason)}`);
    setBusy(false);
  }
  const selectedStage=request ? (statusStage[request.status] ?? 0) : null;
  const activeApprover=request?.approval_steps?.find(s=>s.state==="ACTIVE");
  const isApprovalOnly = resolveLifecycle(request) === "A";
  return <div className="client-section ai-workflow-page">
    <ClientPageHeader eyebrow="HỖ TRỢ NGHIỆP VỤ" title="AI trong quy trình xử lý yêu cầu" description="Theo dõi luồng tạo, đánh giá, phê duyệt và thực hiện hồ sơ. AI chỉ cung cấp gợi ý; người có quyền quyết định duyệt hoặc từ chối." action={<button type="button" className="secondary" onClick={()=>navigate?.(canCreate?"mine":"approval")}>Mở không gian xử lý →</button>}/>
    <section className="panel"><div className="section-head"><h2>Quy trình trong hệ thống</h2><span className="muted">Dữ liệu hồ sơ được đọc trực tiếp từ Backend</span></div>
      <ol className="ai-workflow-track">{FLOW.map(([title,desc],i)=><li key={title}><span className="ai-workflow-number">{i+1}</span><strong>{title}</strong><p>{desc}</p></li>)}</ol>
    </section>
    <section className="panel"><div className="section-head"><div><h2>Theo dõi hồ sơ và kiểm tra AI</h2><p className="muted">Chọn một hồ sơ thực tế để xem tuyến duyệt và chạy phân tích khi cần.</p></div><button type="button" className="secondary" onClick={()=>{list.reload();if(currentId) detail.reload();}}>Làm mới</button></div>
      <div className="ai-workflow-chooser">
        {canCreate&&canApprove&&<label>Nguồn hồ sơ<select value={queue} onChange={e=>{setQueue(e.target.value);setPicked("");}}><option value="mine">Yêu cầu của tôi</option><option value="approval">Đang chờ tôi duyệt</option></select></label>}
        <ResourceState resource={list}><label>Hồ sơ<select value={currentId} onChange={e=>setPicked(e.target.value)} disabled={!list.data?.items?.length}><option value="">{list.data?.items?.length?"Chọn hồ sơ":"Chưa có hồ sơ"}</option>{(list.data?.items||[]).map(item=><option value={item.id} key={item.id}>{item.code} · {types[item.type_code]||"Yêu cầu"}</option>)}</select></label></ResourceState>
      </div>
      {currentId && <ResourceState resource={detail}>{request&&<>
        <div className="ai-workflow-summary"><div><strong>{request.payload?.title||types[request.type_code]||"Yêu cầu"}</strong><p className="muted">Trạng thái hiện tại</p><Badge value={request.status}/></div><div><strong>Người đang phụ trách</strong><p>{activeApprover?.assignee_name|| (request.status==="PENDING_APPROVAL"?"Chưa có tên người duyệt":"Không ở bước chờ phê duyệt")}</p><p className="muted">{activeApprover?`Cấp duyệt ${activeApprover.tier_level||activeApprover.step_no}`:"Cập nhật theo hồ sơ thực tế"}</p></div></div>
        <div className="ai-workflow-progress" aria-label="Trạng thái xử lý hồ sơ">{FLOW.map(([title],i)=><div key={title} className={isApprovalOnly && i===3 ? "is-skipped" : selectedStage>i?"is-done":selectedStage===i?"is-current":"is-upcoming"}><span aria-hidden="true">{isApprovalOnly && i===3 ? "—" : selectedStage>i?"✓":i+1}</span><strong>{isApprovalOnly && i===3 ? "Không cần thực hiện / nghiệm thu" : title}</strong></div>)}</div>
        {["REJECTED", "CANCELLED", "NEEDS_INFO"].includes(request.status) && <p className="muted">Hồ sơ đang ở trạng thái cần xử lý riêng; không được tính là đã hoàn thành toàn bộ các công đoạn.</p>}
        <div className="ai-workflow-controls"><button type="button" disabled={busy} onClick={runAssessment}>{busy?"AI đang phân tích…":"Chạy đánh giá AI cho hồ sơ"}</button><button type="button" className="secondary" onClick={()=>onOpen?.(request.id)}>Mở hồ sơ để xử lý →</button></div>
        <div className="ai-workflow-ai-steps" aria-live="polite">{[["classify","Phân loại yêu cầu"],["risk","Đánh giá rủi ro"]].map(([key,title])=><div key={key} className={`ai-workflow-ai-step ${stages[key]||"idle"}`}><strong>{title}</strong><span>{phaseText(stages[key])}</span></div>)}</div>
        {analysis.classify&&<p className="ai-workflow-result">Loại AI đề xuất: <strong>{types[analysis.classify.predicted_request_type]||"Chưa có nhãn tương ứng"}</strong> · Độ tin cậy: {Math.round((Number(analysis.classify.confidence_request_type)||0)*100)}%</p>}
        {analysis.risk&&<p className="ai-workflow-result">Điểm đánh giá rủi ro: <strong>{analysis.risk.risk_score??"Chưa có kết quả"}/5</strong>{analysis.risk.auto_approve_eligible ? " · AI gợi ý đủ điều kiện xem xét nhanh, không tự phê duyệt." : " · Cần người có thẩm quyền xem xét."}</p>}
        {(analysis.classify?.fallback_used||analysis.risk?.fallback_used)&&<p className="muted">Một phần kết quả là dữ liệu dự phòng, không phải dự đoán từ mô hình AI.</p>}
        {error&&<p className="error" role="alert">{error}</p>}
        <p className="muted ai-workflow-footnote">Trạng thái phê duyệt do Backend cung cấp. Các bước AI ở trên chỉ phản ánh lần phân tích vừa gọi trong phiên này; hệ thống chưa có API lịch sử tác vụ AI theo hồ sơ nên không tự nhận đã chạy ở các phiên trước.</p>
      </>}</ResourceState>}
      {!currentId&&!list.loading&&<p className="muted">Chưa có hồ sơ phù hợp để theo dõi. Bạn có thể tạo yêu cầu mới hoặc mở danh sách cần phê duyệt.</p>}
    </section>
  </div>;
}

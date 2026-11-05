import FullHistory from "./FullHistory.jsx";
import WorkflowDiagrams from "./WorkflowDiagrams.jsx";
import { AiSummary } from "./AiAssist.jsx";
import { AiAssessmentPanel, ProgressSummary } from "./RequestProgress.jsx";
import { EmptyState, PageTabs, WorkflowTimeline } from "./design.jsx";
import { requestActionPayload } from "../actionPayload.js";
import { useState } from "react";
import { api, API_BASE } from "../api.js";
import { date, fields, fieldLabels, permissions, types, riskLevels, approvalLevels, resolverLabels, typeLevels } from "../domain.js";
import {
  ActionForm,
  Badge,
  Modal,
  Reason,
  ResourceState,
  command,
  useResource,
} from "./ui.jsx";
const ACTION_LABELS = {
  DRAFT_CREATED: "Tạo bản nháp", DRAFT_UPDATED: "Cập nhật bản nháp", REQUEST_SUBMITTED: "Gửi yêu cầu",
  ATTACHMENT_ADDED: "Thêm tệp đính kèm", DRAFT_ATTACHMENT_REMOVED: "Gỡ tệp khỏi bản nháp", ATTACHMENT_DOWNLOADED: "Tải tệp đính kèm",
  APPROVAL_APPROVE: "Phê duyệt", APPROVAL_REJECT: "Từ chối", APPROVAL_NEEDS_INFO: "Yêu cầu bổ sung",
  EXECUTION_STARTED: "Nhận công việc thực hiện", EXECUTION_EVIDENCE_ADDED: "Thêm minh chứng thực hiện", EXECUTION_RESULT_SUBMITTED: "Nộp kết quả thực hiện",
  EXECUTION_ISSUE_BLOCKED: "Báo vướng mắc", EXECUTION_ISSUE_UNABLE_TO_CLAIM: "Báo không thể nhận việc",
  ACCEPTANCE_ACCEPT: "Nghiệm thu đạt", ACCEPTANCE_REWORK: "Yêu cầu làm lại",
  REQUEST_CANCELLED: "Hủy yêu cầu", ACTOR_REASSIGNED: "Điều chuyển người xử lý",
  SLA_REMINDER: "Nhắc hạn xử lý", SLA_BREACH: "Quá hạn xử lý", AI_ASSESSMENT_RECORDED: "Đánh giá AI",
  NOTIFICATION_SKIPPED_INACTIVE_OR_REVOKED: "Bỏ qua thông báo cho tài khoản ngừng hoạt động",
};
const STEP_STATES = { WAITING: "Chờ đến lượt", ACTIVE: "Đang xử lý", APPROVED: "Đã phê duyệt", REJECTED: "Đã từ chối", NEEDS_INFO: "Yêu cầu bổ sung", SKIPPED: "Bỏ qua" };

function fieldLabel(typeCode, name) {
  return fields[typeCode]?.find(([field]) => field === name)?.[1] || fieldLabels[name] || name.replaceAll("_", " ");
}
function PayloadList({ typeCode, payload }) {
  const entries = Object.entries(payload || {});
  if (!entries.length) return <p className="muted">Chưa có nội dung.</p>;
  return <dl className="data-list">{entries.map(([name, value]) => <div key={name}>
    <dt>{fieldLabel(typeCode, name)}</dt>
    <dd>{typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "—")}</dd>
  </div>)}</dl>;
}
function Attachments({ id, typeCode }) {
  const r = useResource(`/api/v1/requests/${id}/revisions`);
  const revisions = r.data?.revisions || [];
  return <ResourceState resource={r}>
    {revisions.length ? revisions.map((v, index) => <details key={v.id} className="record" open={index === revisions.length - 1}>
      <summary>Lần gửi {v.revision_no} · {date(v.submitted_at)} · {v.attachments?.length || 0} tệp</summary>
      {v.attachments?.length ? <ul className="ds-health-list">{v.attachments.map((a) => <li key={a.id}>
        <span>{a.original_name}</span>
        <span><Badge value={a.scan_state} /> {a.scan_state === "CLEAN" && <a href={`${API_BASE}/api/v1/attachments/${a.id}/download`} target="_blank" rel="noreferrer">Tải xuống</a>}</span>
      </li>)}</ul> : <p className="muted">Không có tệp đính kèm.</p>}
      <details><summary>Nội dung đã gửi</summary><PayloadList typeCode={typeCode} payload={v.payload} /></details>
    </details>) : <EmptyState title="Chưa có tệp đính kèm" description="Tệp được lưu theo từng lần gửi yêu cầu." />}
  </ResourceState>;
}
/** Human-readable activity log built from the request audit chain (no hashes or identifiers). */
function ActivityLog({ id, userId }) {
  const r = useResource(`/api/v1/requests/${id}/audit`);
  const items = [...(r.data?.items || [])].reverse();
  return <ResourceState resource={r}>
    {items.length ? <ol className="ds-timeline">{items.map((event) => <li key={event.id} className="ds-timeline-item is-done">
      <span className="ds-timeline-dot" aria-hidden="true" />
      <div className="ds-timeline-body">
        <strong>{ACTION_LABELS[event.action] || "Cập nhật hồ sơ"}</strong>
        <small className="muted">{date(event.occurred_at)} · {event.actor_kind === "SYSTEM" ? "Hệ thống" : event.actor_id === userId ? "Bạn" : "Người dùng"}</small>
        {event.details?.reason && <blockquote>{event.details.reason}</blockquote>}
      </div>
    </li>)}</ol> : <EmptyState title="Chưa có hoạt động" />}
  </ResourceState>;
}
function ApproversTable({ request }) {
  const steps = request.approval_steps || [];
  const decisions = request.progress?.decisions || [];
  if (!steps.length) return <EmptyState title="Chưa có tuyến phê duyệt" description="Tuyến duyệt được xác định khi yêu cầu được gửi." />;
  return <div className="table-wrap"><table><thead><tr><th>Cấp</th><th>Vai trò</th><th>Người phê duyệt</th><th>Trạng thái</th><th>Thời điểm</th><th>Nhận xét</th></tr></thead>
    <tbody>{steps.map((s) => {
      const decision = decisions.filter((d) => d.kind === "APPROVAL" && d.step_no === s.step_no && d.revision_no === request.revision_no).pop();
      return <tr key={s.step_no} className={s.state === "ACTIVE" && request.progress?.deadline?.overdue ? "is-overdue" : ""}>
        <td>{s.tier_level || s.step_no}</td>
        <td>{resolverLabels[s.resolver_code] || "Người phê duyệt"}</td>
        <td><strong>{s.assignee_name || "Đang phân công"}</strong></td>
        <td><Badge value={s.state} /> <span className="sr-only">{STEP_STATES[s.state]}</span></td>
        <td>{date(s.closed_at || s.activated_at) || "—"}</td>
        <td>{decision?.reason || <span className="muted">—</span>}</td>
      </tr>;
    })}</tbody></table></div>;
}
function timelineItems(request) {
  const status = request.status;
  const lifecycle = request.workflow?.lifecycle;
  const steps = request.approval_steps || [];
  const closedBad = status === "REJECTED" || status === "CANCELLED";
  const submitted = status !== "DRAFT";
  const approved = ["READY_FOR_EXECUTION", "IN_PROGRESS", "WAITING_FOR_ACCEPTANCE", "COMPLETED"].includes(status);
  const items = [{ key: "submit", title: "Gửi yêu cầu", state: submitted ? "done" : "current", meta: submitted ? `Lần gửi ${request.revision_no || 1}` : "Đang là bản nháp" }];
  steps.forEach((s) => items.push({
    key: `step-${s.step_no}`,
    title: `Phê duyệt cấp ${s.tier_level || s.step_no} · ${resolverLabels[s.resolver_code] || "Người phê duyệt"}`,
    meta: `${s.assignee_name || "Đang phân công"} · ${STEP_STATES[s.state] || ""}${s.closed_at ? ` · ${date(s.closed_at)}` : ""}`,
    state: s.state === "APPROVED" ? "done" : s.state === "ACTIVE" ? "current" : ["REJECTED", "NEEDS_INFO"].includes(s.state) ? "failed" : s.state === "SKIPPED" ? "skipped" : "upcoming",
  }));
  if (lifecycle === "B" || lifecycle === "C") items.push({
    key: "execution", title: "Thực hiện",
    meta: request.progress?.executor?.name || undefined,
    state: ["WAITING_FOR_ACCEPTANCE", "COMPLETED"].includes(status) || (lifecycle === "B" && status === "COMPLETED") ? "done" : ["READY_FOR_EXECUTION", "IN_PROGRESS"].includes(status) ? "current" : closedBad ? "skipped" : "upcoming",
  });
  if (lifecycle === "C") items.push({
    key: "acceptance", title: "Nghiệm thu", meta: request.progress?.acceptor?.name || undefined,
    state: status === "COMPLETED" ? "done" : status === "WAITING_FOR_ACCEPTANCE" ? "current" : closedBad ? "skipped" : "upcoming",
  });
  items.push({
    key: "end",
    title: status === "REJECTED" ? "Bị từ chối" : status === "CANCELLED" ? "Đã hủy" : "Hoàn thành",
    state: status === "COMPLETED" ? "done" : closedBad ? "failed" : "upcoming",
    meta: !approved && !closedBad && status !== "COMPLETED" ? "Chưa kết thúc" : undefined,
  });
  return items;
}
function AssignDownSelect({ requestId }) {
  const resource = useResource(`/api/v1/requests/${requestId}/assignable-executors`);
  const items = resource.data?.items || [];
  if (!items.length) return null;
  return (
    <label>
      Giao việc cho cấp dưới (tùy chọn)
      <select name="executor_id" defaultValue="">
        <option value="">Người thực hiện theo cấu hình</option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>{item.display_name}</option>
        ))}
      </select>
    </label>
  );
}

function DetailTabContent({ tab, r, id, user, verify, setVerify }) {
  if (tab === "info") return <><h2>Nội dung đề nghị</h2><PayloadList typeCode={r.type_code} payload={r.payload} /></>;
  if (tab === "progress") return (
    <>
      <h2>Tiến trình xử lý</h2>
      <WorkflowTimeline items={timelineItems(r)} />
      {r.workflow?.attempt && (
        <div className="record">
          <strong>Lần thực hiện {r.workflow.attempt.attempt_no}</strong> <Badge value={r.workflow.attempt.state} />
          <p>{r.workflow.attempt.result_note || "Chưa nộp kết quả."}</p>
          {r.workflow.attempt.external_reference && <p className="muted">Mã tham chiếu: {r.workflow.attempt.external_reference}</p>}
        </div>
      )}
      <FullHistory id={id} />
    </>
  );
  if (tab === "approvers") return <><h2>Người phê duyệt</h2><ApproversTable request={r} /></>;
  if (tab === "files") return <><h2>Tệp đính kèm</h2><Attachments id={id} typeCode={r.type_code} /></>;
  if (tab === "ai" && r.status !== "DRAFT") return (
    <>
      <AiAssessmentPanel requestId={id} canRun={r.progress?.stage !== "CLOSED" && !user.roles.some((role) => ["OPS_ADMIN", "POLICY_ADMIN", "AUDITOR"].includes(role))} />
      <AiSummary request={r} />
    </>
  );
  if (tab === "activity") return (
    <>
      <h2>Lịch sử hoạt động</h2>
      {user.roles.includes("AUDITOR") && (
        <div className="record">
          <ActionForm onSubmit={async () => setVerify(await api(`/api/v1/requests/${id}/audit/verify`))} submitLabel="Xác minh tính toàn vẹn nhật ký" />
          {verify && <p role="status"><Badge value={verify.status === "PASS" ? "COMPLETED" : "REJECTED"} /> {verify.status === "PASS" ? "Chuỗi nhật ký toàn vẹn." : verify.status === "FAIL" ? "Phát hiện sai lệch trong chuỗi nhật ký." : "Chưa đủ dữ liệu để kết luận."}</p>}
        </div>
      )}
      <ActivityLog id={id} userId={user.id} />
    </>
  );
  if (tab === "diagrams") return <WorkflowDiagrams request={r} embedded />;
  return null;
}

export default function RequestDetail({ id, user, onBack, onEdit, onChanged, initialTab = "info" }) {
  const resource = useResource(`/api/v1/requests/${id}`),
    [tab, setTab] = useState(initialTab),
    [action, setAction] = useState(null),
    [verify, setVerify] = useState(null);
  const r = resource.data?.request,
    p = r ? permissions(user, r) : {};
  async function done() {
    setAction(null);
    resource.reload();
    onChanged();
  }
  const actions = {
    approve: ["Phê duyệt", "approval-decisions", "APPROVE"],
    reject: ["Từ chối yêu cầu", "approval-decisions", "REJECT"],
    info: ["Yêu cầu bổ sung", "approval-decisions", "NEEDS_INFO"],
    cancel: ["Hủy yêu cầu", "cancel"],
    revokeAi: ["Thu hồi duyệt tự động của AI", "ai-approval/revoke"],
    claim: ["Nhận công việc", "execution/start"],
    accept: ["Chấp nhận nghiệm thu", "acceptance-decisions", "ACCEPT"],
    rework: ["Yêu cầu làm lại", "acceptance-decisions", "REWORK"],
    issue: ["Báo vướng mắc", "issues"],
  };
  async function decide(values) {
    const [, path] = actions[action];
    await command(`requests/${id}/${path}`,
      requestActionPayload(action, r.lock_version, values));
    await done();
  }
  async function execute(values) {
    const file = values.evidence;
    if (file?.size) {
      const body = new FormData();
      body.append("file", file);
      await api(`/api/v1/requests/${id}/execution/attachments`, {
        method: "POST",
        body,
      });
    }
    await command(`requests/${id}/execution/submit`, {
      expected_version: r.lock_version,
      result_note: values.result_note,
      external_reference: values.external_reference,
    });
    await done();
  }
  return (
    <section>
      <div className="section-head">
        <button type="button" className="secondary" onClick={onBack}>
          ← Danh sách
        </button>
        <button type="button" className="secondary" onClick={resource.reload}>
          Tải lại hồ sơ
        </button>
      </div>
      <ResourceState resource={resource}>
        {r && (
          <>
            <div className="page-heading">
              <div>
                <p className="eyebrow">
                  {r.code} / {r.progress?.type_name || types[r.type_code] || "Yêu cầu"}
                </p>
                <h1>{r.payload?.title || r.code}</h1>
                <p className="muted">
                  Tạo lúc {date(r.created_at)} · Cập nhật {date(r.updated_at)} · {riskLevels[r.risk_weight || typeLevels[r.type_code]?.risk_weight || 3]} · {approvalLevels[r.approval_level || r.approval_steps?.length || typeLevels[r.type_code]?.approval_level || 1]}
                </p>
              </div>
              <Badge value={r.status} />
            </div>
            <ProgressSummary progress={r.progress} />
            <PageTabs label="Nội dung hồ sơ" value={tab} onChange={(key) => {
              setTab(key);
              window.requestAnimationFrame(() => document.getElementById("request-detail-content")?.scrollIntoView({ behavior: "smooth", block: "start" }));
            }} tabs={[
              ["info", "Thông tin"],
              ["progress", "Tiến trình xử lý"],
              ["approvers", "Người phê duyệt", r.approval_steps?.length || null],
              ["files", "Tệp đính kèm"],
              ...(r.status !== "DRAFT" ? [["ai", "Đánh giá AI"]] : []),
              ["activity", "Lịch sử hoạt động"],
              ["diagrams", "Sơ đồ luồng"],
            ]} />
            <div className={tab === "diagrams" ? "detail-grid flow-detail-grid" : "detail-grid"} id="request-detail-content">
              <div className="panel">
                <DetailTabContent tab={tab} r={r} id={id} user={user} verify={verify} setVerify={setVerify} />
              </div>
              <aside className="panel">
                <p className="eyebrow">XỬ LÝ HỒ SƠ</p>
                <h2>Thao tác của bạn</h2>
                <div className="stack">
                  {p.edit && <button type="button" onClick={() => onEdit(r)}>Chỉnh sửa / bổ sung</button>}
                  {p.approve && <>
                    <button type="button" onClick={() => setAction("approve")}>Phê duyệt</button>
                    <button type="button" className="secondary" onClick={() => setAction("info")}>Yêu cầu bổ sung</button>
                    <button type="button" className="danger" onClick={() => setAction("reject")}>Từ chối</button>
                  </>}
                  {p.claim && <button type="button" onClick={() => setAction("claim")}>Nhận công việc</button>}
                  {p.execute && <button type="button" onClick={() => setAction("execution")}>Nộp kết quả thực hiện</button>}
                  {(p.claim || p.execute) && <button type="button" className="secondary" onClick={() => setAction("issue")}>Báo vướng mắc</button>}
                  {p.accept && <>
                    <button type="button" onClick={() => setAction("accept")}>Chấp nhận nghiệm thu</button>
                    <button type="button" className="danger" onClick={() => setAction("rework")}>Yêu cầu làm lại</button>
                  </>}
                  {p.cancel && <button type="button" className="danger" onClick={() => setAction("cancel")}>Hủy yêu cầu</button>}
                  {p.revokeAi && <button type="button" className="danger" onClick={() => setAction("revokeAi")}>Thu hồi duyệt tự động của AI</button>}
                  {!Object.values(p).some(Boolean) && <p className="muted">Không có thao tác nào dành cho bạn ở trạng thái hiện tại.</p>}
                  {r.status !== "DRAFT" && <button type="button" className="secondary" onClick={() => setTab("ai")}>Xem đánh giá AI</button>}
                </div>
                <hr />
                <small className="muted">Mọi quyết định được lưu trong lịch sử hoạt động của hồ sơ.</small>
              </aside>
            </div>
            {action && (
              <Modal
                title={
                  action === "execution"
                    ? "Nộp kết quả thực hiện"
                    : actions[action][0]
                }
                onClose={() => setAction(null)}
              >
                <ActionForm
                  onSubmit={action === "execution" ? execute : decide}
                  danger={["cancel", "reject", "rework", "revokeAi"].includes(action)}
                >
                  <p>
                    {r.code} · {r.payload?.title}
                  </p>
                  {action === "execution" ? (
                    <>
                      <label>
                        Mô tả kết quả
                        <textarea
                          name="result_note"
                          minLength={10}
                          maxLength={4000}
                          required
                        />
                      </label>
                      <label>
                        Mã tham chiếu
                        <input
                          name="external_reference"
                          maxLength={200}
                          required
                        />
                      </label>
                      <label>
                        Minh chứng
                        <input
                          name="evidence"
                          type="file"
                          accept="application/pdf,image/jpeg,image/png"
                        />
                      </label>
                      <p className="muted">
                        Cần có minh chứng hợp lệ trước khi nộp. Nếu tệp đang
                        kiểm tra, chờ rồi nộp lại.
                      </p>
                    </>
                  ) : ["reject", "info", "cancel", "rework", "issue", "revokeAi"].includes(
                      action,
                    ) ? (
                    <>
                      <Reason />
                      {action === "issue" && (
                        <input
                          type="hidden"
                          name="kind"
                          value={p.claim ? "UNABLE_TO_CLAIM" : "BLOCKED"}
                        />
                      )}
                    </>
                  ) : (
                    <>
                      <p>Xác nhận thực hiện thao tác trên hồ sơ này?</p>
                      {action === "approve" && <AssignDownSelect requestId={id} />}
                    </>
                  )}
                </ActionForm>
              </Modal>
            )}
          </>
        )}
      </ResourceState>
    </section>
  );
}

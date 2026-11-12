import { useState } from "react";
import { api, notify } from "../api.js";
import { date, errorText, resolverLabels } from "../domain.js";
import { ResourceState, useResource } from "./ui.jsx";

const STAGES = { DRAFT: "Bản nháp", REVISION: "Chờ người yêu cầu bổ sung", APPROVAL: "Đang phê duyệt", EXECUTION: "Đang thực hiện", ACCEPTANCE: "Đang nghiệm thu", CLOSED: "Đã kết thúc" };
const ROLES = { APPROVER: "Người phê duyệt", EXECUTOR: "Người thực hiện", ACCEPTOR: "Người nghiệm thu", REQUESTER: "Người yêu cầu" };
const OUTCOMES = { APPROVE: "Phê duyệt", REJECT: "Từ chối", NEEDS_INFO: "Yêu cầu bổ sung", ACCEPT: "Nghiệm thu đạt", REWORK: "Yêu cầu làm lại" };
const SLA_KINDS = { APPROVAL: "phê duyệt", EXECUTION: "thực hiện", ACCEPTANCE: "nghiệm thu" };

function duration(seconds) {
  const abs = Math.abs(seconds);
  if (abs >= 172800) return `${Math.round(abs / 86400)} ngày`;
  if (abs >= 3600) return `${Math.round(abs / 3600)} giờ`;
  return `${Math.max(1, Math.round(abs / 60))} phút`;
}

function Person({ person, empty }) {
  if (!person) return <span className="muted">{empty}</span>;
  const role = person.resolver_code ? resolverLabels[person.resolver_code] || ROLES[person.role] : ROLES[person.role];
  return <span><strong>{person.name || "Đang cập nhật"}</strong><small className="muted"> · {role || "Người xử lý"}</small></span>;
}

/** Current handler, next handler, deadline and every recorded decision reason. */
export function ProgressSummary({ progress }) {
  if (!progress) return null;
  const deadline = progress.deadline;
  return <section className="panel progress-summary" aria-label="Tình trạng xử lý hiện tại">
    <div className="progress-summary-grid">
      <div><span className="progress-label">Giai đoạn</span><strong>{STAGES[progress.stage] || "—"}</strong></div>
      <div><span className="progress-label">Đang xử lý</span><Person person={progress.current_assignee} empty="Không có bước đang chờ" /></div>
      <div><span className="progress-label">Bước tiếp theo</span><Person person={progress.next_assignee} empty="Không còn bước tiếp theo" /></div>
      <div><span className="progress-label">Hạn {deadline ? SLA_KINDS[deadline.kind] || "" : "xử lý"}</span>
        {deadline ? <span><strong>{date(deadline.due_at)}</strong>
          <small className={deadline.overdue ? "progress-overdue" : "muted"}> · {deadline.overdue ? `Quá hạn ${duration(deadline.remaining_seconds)}` : `Còn ${duration(deadline.remaining_seconds)}`}</small></span>
          : <span className="muted">Không áp dụng</span>}</div>
    </div>
    <p className="muted progress-meta">Người yêu cầu: {progress.requester_name || "—"} · {progress.department_name || "—"}</p>
    {progress.decisions?.length > 0 && <div className="progress-decisions">
      <h3>Quyết định đã ghi nhận</h3>
      <ol className="timeline">{progress.decisions.map((d, i) => <li key={i}>
        <strong>{OUTCOMES[d.outcome] || d.outcome}</strong>
        {d.kind === "APPROVAL" ? ` · Cấp ${d.step_no}${d.revision_no > 1 ? ` (lần gửi ${d.revision_no})` : ""}` : ` · Lần thực hiện ${d.attempt_no}`}
        <p className="muted">{d.actor_name || "—"} · {date(d.decided_at)}</p>
        {d.reason && <blockquote className="progress-reason">{d.reason}</blockquote>}
      </li>)}</ol>
    </div>}
  </section>;
}

const AI_STAGES = { RECEIVED: "Tiếp nhận", VALIDATING: "Kiểm tra dữ liệu", OCR: "Nhận dạng tài liệu (OCR)", CLASSIFICATION: "Phân loại", RISK_ANALYSIS: "Phân tích rủi ro", ROUTING: "Định tuyến phê duyệt", RECOMMENDATION: "Đề xuất", HUMAN_REVIEW: "Người có thẩm quyền xem xét", DECISION: "Quyết định" };
const AI_STATUS = { DONE: ["Hoàn thành", "done"], WARNING: ["Cần lưu ý", "fallback"], FALLBACK: ["Dự phòng — không phải kết quả mô hình", "fallback"], NOT_APPLICABLE: ["Không áp dụng", "skipped"], NOT_RUN: ["Chưa chạy", "skipped"], NOT_AVAILABLE: ["Chưa có dữ liệu", "skipped"], PENDING: ["Đang chờ", "running"] };
const DECISIONS = { auto_approve: "Đủ điều kiện ưu tiên phê duyệt", escalate_to_human: "Cần người duyệt xem xét kỹ" };

function stageDetail(stage) {
  if (stage.key === "VALIDATING" && stage.missing_fields?.length) return `Thiếu: ${stage.missing_fields.join(", ")}`;
  if (stage.key === "RISK_ANALYSIS" && stage.risk_score != null) return `Điểm rủi ro ${stage.risk_score}/5`;
  if (stage.key === "ROUTING" && stage.route?.length) return stage.route.map((r) => `Cấp ${r.level}: ${r.assignee_name}`).join(" → ");
  if (stage.key === "RECOMMENDATION") return `${DECISIONS[stage.decision] || stage.decision}${stage.method === "rule_based" ? " (theo quy tắc nghiệp vụ)" : ""}`;
  return stage.detail || "";
}

/** Company regulation clauses the AI advice was checked against (applied or not). */
export function Citations({ items = [], version }) {
  if (!items.length) {
    return <p className="muted ai-citations-empty">Không có điều khoản quy chế nào{version ? ` trong bộ quy định ${version}` : ""} liên quan tới loại yêu cầu này; khuyến nghị dựa trên mức rủi ro và luồng duyệt.</p>;
  }
  return <section className="ai-citations" aria-label="Căn cứ đối chiếu theo quy chế công ty">
    <h4>Căn cứ đối chiếu theo quy chế công ty{version ? ` · bộ quy định ${version}` : ""}</h4>
    <ol>{items.map((c) => <li key={c.rule_id} className={c.applies ? "applies" : "not-applies"}>
      <div className="ai-citation-head">
        <span className={`ai-citation-badge ${c.applies ? "applies" : ""}`}>{c.applies ? "Áp dụng" : "Không áp dụng"}</span>
        <strong>{c.regulation_title || c.regulation_code || c.rule_id}</strong>
        <small className="muted">
          {[c.regulation_code, c.regulation_version && `phiên bản ${c.regulation_version}`, c.clause_no && `câu ${c.clause_no}`].filter(Boolean).join(" · ")}
        </small>
      </div>
      {c.text && <blockquote className="ai-citation-quote">“{c.text}”</blockquote>}
      {c.checks?.length > 0 && <ul className="ai-citation-checks">{c.checks.map((x) => <li key={x}>{x}</li>)}</ul>}
      {c.applies && c.effect && <p className="ai-citation-effect">Hệ quả: {c.effect}</p>}
    </li>)}</ol>
  </section>;
}

function Assessment({ item }) {
  const recommendation = item.stages?.find((s) => s.key === "RECOMMENDATION");
  return <div className="ai-assessment">
    <ol className="ai-stage-list">{(item.stages || []).map((stage) => {
      const [label, tone] = AI_STATUS[stage.status] || [stage.status, "skipped"];
      return <li key={stage.key} className={`ai-progress-step ${tone}`}>
        <span aria-hidden="true">{tone === "done" ? "✓" : tone === "fallback" ? "!" : "◌"}</span>
        <span>{AI_STAGES[stage.key] || stage.key}</span><small>{label}</small>
        {stageDetail(stage) && <p className="muted ai-stage-detail">{stageDetail(stage)}</p>}
      </li>;
    })}</ol>
    {recommendation?.reasons?.length > 0 && <ul className="ai-reasons">{recommendation.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
    {recommendation && <Citations items={recommendation.citations} version={recommendation.policy_version} />}
    {item.fallback_used && <p className="error" role="note">Một phần đánh giá dùng dữ liệu dự phòng vì dịch vụ AI chưa phản hồi; không coi đó là kết quả mô hình.</p>}
  </div>;
}

/** Persisted, per-request AI assessment. Advisory only: the assigned human decides. */
export function AiAssessmentPanel({ requestId, canRun }) {
  const history = useResource(`/api/v1/requests/${requestId}/ai-assessments`);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const items = history.data?.items || [];
  async function run() {
    setBusy(true); setError("");
    try {
      const result = await api(`/api/v1/requests/${requestId}/ai-assessments`, { method: "POST", body: "{}", silent: true, timeoutMs: 90000 });
      notify(result.assessment?.fallback_used ? "Đã lưu đánh giá; một phần dùng dữ liệu dự phòng" : "Đã lưu đánh giá AI cho hồ sơ", result.assessment?.fallback_used ? "error" : "success");
      history.reload();
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  return <div className="ai-panel">
    <div className="section-head"><h3>Đánh giá AI</h3>
      {canRun && <button type="button" className="ai-btn" onClick={run} disabled={busy}>{busy ? "Đang phân tích…" : "Chạy đánh giá"}</button>}</div>
    {busy && <p className="ai-progress-step running" role="status"><span aria-hidden="true">◌</span> Đang gửi hồ sơ tới dịch vụ AI và chờ kết quả…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    <p className="muted">AI chỉ đưa ra khuyến nghị; người có thẩm quyền vẫn quyết định phê duyệt hoặc từ chối.</p>
    <ResourceState resource={history}>
      {items.length ? <>
        <p className="muted">Lần gần nhất: {date(items[0].occurred_at)} · {items[0].requested_by_name || "—"}</p>
        <Assessment item={items[0]} />
        {items.length > 1 && <details><summary>Lịch sử đánh giá ({items.length - 1} lần trước)</summary>
          {items.slice(1).map((item) => <div key={item.id} className="record"><p className="muted">{date(item.occurred_at)} · {item.requested_by_name || "—"}</p><Assessment item={item} /></div>)}
        </details>}
      </> : <p className="muted">Chưa có đánh giá AI cho hồ sơ này.</p>}
    </ResourceState>
  </div>;
}

/** Compact AI advice for the approver, shown next to the request content. */
export function AiAdviceCard({ requestId, canRun, onOpenDetails }) {
  const history = useResource(`/api/v1/requests/${requestId}/ai-assessments`);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const latest = history.data?.items?.[0];
  const recommendation = latest?.stages?.find((s) => s.key === "RECOMMENDATION");
  const risk = latest?.stages?.find((s) => s.key === "RISK_ANALYSIS");
  async function run() {
    setBusy(true); setError("");
    try {
      await api(`/api/v1/requests/${requestId}/ai-assessments`, { method: "POST", body: "{}", silent: true, timeoutMs: 90000 });
      history.reload();
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  return <section className="ai-advice-card" aria-label="Khuyến nghị AI">
    <div className="section-head">
      <h3>Khuyến nghị AI &amp; căn cứ quy chế</h3>
      <span className="ai-advice-actions">
        {canRun && <button type="button" className="secondary" onClick={run} disabled={busy}>{busy ? "Đang phân tích…" : latest ? "Đánh giá lại" : "Chạy đánh giá AI"}</button>}
        {latest && onOpenDetails && <button type="button" className="link" onClick={onOpenDetails}>Xem chi tiết các bước →</button>}
      </span>
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    <ResourceState resource={history}>
      {recommendation ? <>
        <p className="ai-advice-verdict">
          <strong>{DECISIONS[recommendation.decision] || recommendation.decision}</strong>
          {risk?.risk_score != null && <span className="muted"> · Điểm rủi ro {risk.risk_score}/5</span>}
          <span className="muted"> · {date(latest.occurred_at)}</span>
        </p>
        <Citations items={recommendation.citations} version={recommendation.policy_version} />
        {latest.fallback_used && <p className="error" role="note">Một phần đánh giá dùng dữ liệu dự phòng; không coi đó là kết quả mô hình.</p>}
      </> : <p className="muted">Chưa có đánh giá AI cho hồ sơ này{canRun ? ". Bấm “Chạy đánh giá AI” để AI đối chiếu với quy chế công ty." : "."}</p>}
    </ResourceState>
    <p className="muted ai-advice-note">AI chỉ khuyến nghị; người có thẩm quyền quyết định phê duyệt hoặc từ chối.</p>
  </section>;
}

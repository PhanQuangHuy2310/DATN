import FullHistory from "./FullHistory.jsx";
import WorkflowDiagrams from "./WorkflowDiagrams.jsx";
import { AiSummary } from "./AiAssist.jsx";
import { AiAssessmentPanel, ProgressSummary } from "./RequestProgress.jsx";
import { DetailSkeleton, EmptyState, PageTabs, WorkflowTimeline } from "./design.jsx";
import { requestActionPayload } from "../actionPayload.js";
import { useRef, useState } from "react";
import { api, API_BASE } from "../api.js";
import {
  date,
  fields,
  fieldLabels,
  resolveFieldLabel,
  permissions,
  types,
  riskLevels,
  approvalLevels,
  resolverLabels,
  typeLevels,
} from "../domain.js";
import { formatVnd, vndToVietnameseWords } from "../formatters.js";
import {
  ActionForm,
  Badge,
  Data,
  Modal,
  Reason,
  ResourceState,
  command,
  useResource,
} from "./ui.jsx";

const ACTION_LABELS = {
  DRAFT_CREATED: "Tạo bản nháp yêu cầu",
  DRAFT_UPDATED: "Cập nhật nội dung bản nháp",
  REQUEST_SUBMITTED: "Gửi yêu cầu phê duyệt",
  ATTACHMENT_ADDED: "Đính kèm tệp tài liệu",
  DRAFT_ATTACHMENT_REMOVED: "Gỡ tệp khỏi bản nháp",
  ATTACHMENT_DOWNLOADED: "Tải xuống tệp đính kèm",
  APPROVAL_APPROVE: "Phê duyệt đồng ý",
  APPROVAL_REJECT: "Từ chối phê duyệt",
  APPROVAL_NEEDS_INFO: "Yêu cầu bổ sung thông tin",
  AI_AUTO_APPROVED: "AI phê duyệt tự động theo quy chế",
  AI_AUTO_APPROVAL_REVOKED: "Thu hồi phê duyệt tự động của AI",
  DELEGATION_APPLIED: "Áp dụng ủy quyền người phê duyệt",
  EXECUTION_STARTED: "Tiếp nhận công việc thực hiện",
  EXECUTION_EVIDENCE_ADDED: "Tải lên minh chứng thực hiện",
  EXECUTION_RESULT_SUBMITTED: "Hoàn tất và nộp kết quả thực hiện",
  EXECUTION_ISSUE_BLOCKED: "Báo cáo vướng mắc khi thực hiện",
  EXECUTION_ISSUE_UNABLE_TO_CLAIM: "Báo cáo không thể tiếp nhận công việc",
  ACCEPTANCE_ACCEPT: "Nghiệm thu đạt yêu cầu",
  ACCEPTANCE_REWORK: "Yêu cầu thực hiện lại",
  REQUEST_CANCELLED: "Hủy yêu cầu",
  ACTOR_REASSIGNED: "Điều chuyển người phụ trách xử lý",
  SLA_REMINDER: "Hệ thống nhắc hạn xử lý",
  SLA_BREACH: "Cảnh báo quá hạn xử lý (SLA)",
  AI_ASSESSMENT_RECORDED: "Ghi nhận kết quả phân tích AI",
  NOTIFICATION_SKIPPED_INACTIVE_OR_REVOKED: "Bỏ qua thông báo đối với tài khoản ngừng hoạt động",
};

const STEP_STATES = {
  WAITING: "Chờ đến lượt",
  ACTIVE: "Đang xử lý",
  APPROVED: "Đã phê duyệt",
  REJECTED: "Đã từ chối",
  NEEDS_INFO: "Yêu cầu bổ sung",
  SKIPPED: "Bỏ qua",
};

const DANGER_WARNINGS = {
  reject:
    "Cảnh báo: Quyết định từ chối sẽ kết thúc quy trình phê duyệt của hồ sơ này và không thể hoàn tác.",
  cancel:
    "Cảnh báo: Hồ sơ sau khi hủy sẽ đóng vĩnh viễn và không thể khôi phục hay gửi lại.",
  rework:
    "Lưu ý: Yêu cầu làm lại sẽ trả công việc về cho người thực hiện để xử lý bổ sung.",
  revokeAi:
    "Lưu ý: Thu hồi duyệt tự động của AI sẽ đưa hồ sơ quay lại trạng thái chờ người có thẩm quyền xét duyệt thủ công.",
};

function fieldLabel(typeCode, name) {
  return (
    fields[typeCode]?.find(([field]) => field === name)?.[1] ||
    fieldLabels[name] ||
    resolveFieldLabel(name)
  );
}

function PayloadList({ typeCode, payload, resolvedUsers = {} }) {
  const entries = Object.entries(payload || {}).filter(
    ([name, val]) =>
      name !== "department_id" && val !== null && val !== undefined && val !== "",
  );
  if (!entries.length) return <p className="muted">Chưa có nội dung nghiệp vụ.</p>;
  return (
    <dl className="data-list ds-business-payload">
      {entries.map(([name, value]) => (
        <div key={name} className={typeof value === "string" && value.length > 90 ? "is-wide" : undefined}>
          <dt>{fieldLabel(typeCode, name)}</dt>
          <dd>
            <Data value={value} fieldName={name} resolvedUsers={resolvedUsers} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Attachments({ id, typeCode, resolvedUsers }) {
  const r = useResource(`/api/v1/requests/${id}/revisions`);
  const revisions = r.data?.revisions || [];
  return (
    <ResourceState resource={r}>
      {revisions.length ? (
        revisions.map((v, index) => (
          <details key={v.id} className="record" open={index === revisions.length - 1}>
            <summary>
              Lần gửi thứ {v.revision_no} · {date(v.submitted_at)} ·{" "}
              {v.attachments?.length || 0} tệp đính kèm
            </summary>
            {v.attachments?.length ? (
              <ul className="ds-health-list">
                {v.attachments.map((a) => (
                  <li key={a.id}>
                    <span>
                      <strong>{a.original_name}</strong>
                    </span>
                    <span>
                      <Badge value={a.scan_state} />{" "}
                      {a.scan_state === "CLEAN" && (
                        <a
                          href={`${API_BASE}/api/v1/attachments/${a.id}/download`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Tải xuống
                        </a>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Không có tệp đính kèm ở lần gửi này.</p>
            )}
            <details>
              <summary>Xem lại nội dung biểu mẫu đã gửi</summary>
              <PayloadList
                typeCode={typeCode}
                payload={v.payload}
                resolvedUsers={resolvedUsers}
              />
            </details>
          </details>
        ))
      ) : (
        <EmptyState
          title="Chưa có tệp đính kèm"
          description="Tệp chứng từ và tài liệu minh chứng được lưu theo từng lần gửi yêu cầu."
        />
      )}
    </ResourceState>
  );
}

/** Human-readable activity log built from the request audit chain (no hashes or internal IDs). */
function ActivityLog({ id, userId }) {
  const r = useResource(`/api/v1/requests/${id}/audit`);
  const items = [...(r.data?.items || [])].reverse();
  return (
    <ResourceState resource={r}>
      {items.length ? (
        <ol className="ds-timeline">
          {items.map((event) => {
            const actorLabel =
              event.actor_kind === "SYSTEM"
                ? "Hệ thống tự động"
                : event.actor_id && event.actor_id === userId
                  ? `${event.actor_name || "Bạn"} (Bạn)`
                  : event.actor_name || "Nhân sự tham gia quy trình";
            return (
              <li key={event.id} className="ds-timeline-item is-done">
                <span className="ds-timeline-dot" aria-hidden="true">
                  ✓
                </span>
                <div className="ds-timeline-body">
                  <strong>{ACTION_LABELS[event.action] || "Cập nhật trạng thái hồ sơ"}</strong>
                  <small className="muted">
                    {date(event.occurred_at)} · Thực hiện bởi: <strong>{actorLabel}</strong>
                  </small>
                  {event.details?.reason && <blockquote>{event.details.reason}</blockquote>}
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <EmptyState
          title="Chưa có hoạt động nào"
          description="Nhật ký hoạt động sẽ được ghi nhận ngay khi hồ sơ có thao tác đầu tiên."
        />
      )}
    </ResourceState>
  );
}

function ApproversTable({ request }) {
  const steps = request.approval_steps || [];
  const decisions = request.progress?.decisions || [];
  if (!steps.length) {
    return (
      <EmptyState
        title="Chưa xác định tuyến phê duyệt"
        description="Tuyến người phê duyệt các cấp sẽ được hệ thống gán tự động ngay khi hồ sơ được gửi đi."
      />
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Cấp duyệt</th>
            <th>Chức danh / Vai trò</th>
            <th>Người phê duyệt</th>
            <th>Trạng thái</th>
            <th>Thời điểm ghi nhận</th>
            <th>Ý kiến / Nhận xét</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s) => {
            const decision = decisions
              .filter(
                (d) =>
                  d.kind === "APPROVAL" &&
                  d.step_no === s.step_no &&
                  d.revision_no === request.revision_no,
              )
              .pop();
            const roleTitle = resolverLabels[s.resolver_code] || "Người phê duyệt";
            return (
              <tr
                key={s.step_no}
                className={
                  s.state === "ACTIVE" && request.progress?.deadline?.overdue
                    ? "is-overdue"
                    : ""
                }
              >
                <td>Cấp {s.tier_level || s.step_no}</td>
                <td>{roleTitle}</td>
                <td>
                  <strong>
                    {s.assignee_name || `Chờ phân công (${roleTitle})`}
                  </strong>
                </td>
                <td>
                  <Badge value={s.state} />{" "}
                  <span className="sr-only">{STEP_STATES[s.state]}</span>
                </td>
                <td>{date(s.closed_at || s.activated_at)}</td>
                <td>{decision?.reason || <span className="muted">—</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function timelineItems(request) {
  const status = request.status;
  const lifecycle = request.workflow?.lifecycle;
  const steps = request.approval_steps || [];
  const closedBad = status === "REJECTED" || status === "CANCELLED";
  const submitted = status !== "DRAFT";
  const approved = [
    "READY_FOR_EXECUTION",
    "IN_PROGRESS",
    "WAITING_FOR_ACCEPTANCE",
    "COMPLETED",
  ].includes(status);
  const items = [
    {
      key: "submit",
      title: "Khởi tạo & Gửi yêu cầu",
      state: submitted ? "done" : "current",
      meta: submitted
        ? `${request.requester_name || request.progress?.requester_name || "Người gửi"} · Lần gửi ${request.revision_no || 1}`
        : "Đang soạn bản nháp",
    },
  ];
  steps.forEach((s) => {
    const roleTitle = resolverLabels[s.resolver_code] || "Người phê duyệt";
    items.push({
      key: `step-${s.step_no}`,
      title: `Phê duyệt cấp ${s.tier_level || s.step_no} · ${roleTitle}`,
      meta: `${s.assignee_name || `Chờ phân công (${roleTitle})`} · ${STEP_STATES[s.state] || ""}${s.closed_at ? ` · ${date(s.closed_at)}` : ""}`,
      state:
        s.state === "APPROVED"
          ? "done"
          : s.state === "ACTIVE"
            ? "current"
            : ["REJECTED", "NEEDS_INFO"].includes(s.state)
              ? "failed"
              : s.state === "SKIPPED"
                ? "skipped"
                : "upcoming",
    });
  });
  if (lifecycle === "B" || lifecycle === "C") {
    items.push({
      key: "execution",
      title: "Triển khai thực hiện",
      meta: request.progress?.executor?.name || "Bộ phận chuyên môn thực hiện",
      state:
        ["WAITING_FOR_ACCEPTANCE", "COMPLETED"].includes(status) ||
        (lifecycle === "B" && status === "COMPLETED")
          ? "done"
          : ["READY_FOR_EXECUTION", "IN_PROGRESS"].includes(status)
            ? "current"
            : closedBad
              ? "skipped"
              : "upcoming",
    });
  }
  if (lifecycle === "C") {
    items.push({
      key: "acceptance",
      title: "Kiểm tra & Nghiệm thu",
      meta: request.progress?.acceptor?.name || "Người nghiệm thu kết quả",
      state:
        status === "COMPLETED"
          ? "done"
          : status === "WAITING_FOR_ACCEPTANCE"
            ? "current"
            : closedBad
              ? "skipped"
              : "upcoming",
    });
  }
  items.push({
    key: "end",
    title:
      status === "REJECTED"
        ? "Hồ sơ bị từ chối"
        : status === "CANCELLED"
          ? "Hồ sơ đã hủy"
          : "Hoàn thành quy trình",
    state: status === "COMPLETED" ? "done" : closedBad ? "failed" : "upcoming",
    meta: !approved && !closedBad && status !== "COMPLETED" ? "Đang trong quy trình xử lý" : undefined,
  });
  return items;
}

function AssignDownSelect({ requestId }) {
  const resource = useResource(`/api/v1/requests/${requestId}/assignable-executors`);
  const items = resource.data?.items || [];
  if (!items.length) return null;
  return (
    <label>
      Phân công nhân sự thực hiện (tùy chọn)
      <select name="executor_id" defaultValue="">
        <option value="">— Giữ người thực hiện mặc định theo quy chế —</option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.display_name}
          </option>
        ))}
      </select>
    </label>
  );
}

function DetailTabContent({ tab, r, id, user, verify, setVerify }) {
  if (tab === "info") {
    return (
      <>
        <div className="section-head">
          <h2>Nội dung đề nghị</h2>
          {r.amount_vnd > 0 && (
            <div className="ds-amount-highlight">
              <span>Giá trị đề nghị:</span>
              <strong>{formatVnd(r.amount_vnd)}</strong>
              <small>({vndToVietnameseWords(r.amount_vnd)})</small>
            </div>
          )}
        </div>
        <PayloadList
          typeCode={r.type_code}
          payload={r.payload}
          resolvedUsers={r.resolved_users}
        />
      </>
    );
  }
  if (tab === "progress") {
    return (
      <>
        <h2>Tiến trình xử lý</h2>
        <WorkflowTimeline items={timelineItems(r)} />
        {r.workflow?.attempt && (
          <div className="record">
            <strong>Lần thực hiện thứ {r.workflow.attempt.attempt_no}</strong>{" "}
            <Badge value={r.workflow.attempt.state} />
            <p>{r.workflow.attempt.result_note || "Chưa nộp kết quả thực hiện."}</p>
            {r.workflow.attempt.external_reference && (
              <p className="muted">
                Mã tham chiếu kết quả: {r.workflow.attempt.external_reference}
              </p>
            )}
          </div>
        )}
        <FullHistory id={id} />
      </>
    );
  }
  if (tab === "approvers") {
    return (
      <>
        <h2>Danh sách người phê duyệt các cấp</h2>
        <ApproversTable request={r} />
      </>
    );
  }
  if (tab === "files") {
    return (
      <>
        <h2>Tệp tài liệu & Chứng từ đính kèm</h2>
        <Attachments id={id} typeCode={r.type_code} resolvedUsers={r.resolved_users} />
      </>
    );
  }
  if (tab === "ai" && r.status !== "DRAFT") {
    return (
      <>
        <AiAssessmentPanel
          requestId={id}
          canRun={
            r.progress?.stage !== "CLOSED" &&
            !user.roles.some((role) =>
              ["OPS_ADMIN", "POLICY_ADMIN", "AUDITOR"].includes(role),
            )
          }
        />
        <AiSummary request={r} />
      </>
    );
  }
  if (tab === "activity") {
    return (
      <>
        <h2>Lịch sử hoạt động</h2>
        {user.roles.includes("AUDITOR") && (
          <div className="record">
            <ActionForm
              onSubmit={async () =>
                setVerify(await api(`/api/v1/requests/${id}/audit/verify`))
              }
              submitLabel="Xác minh tính toàn vẹn nhật ký"
            />
            {verify && (
              <p role="status">
                <Badge value={verify.status === "PASS" ? "COMPLETED" : "REJECTED"} />{" "}
                {verify.status === "PASS"
                  ? "Chuỗi nhật ký kiểm toán toàn vẹn."
                  : verify.status === "FAIL"
                    ? "Cảnh báo: Phát hiện sai lệch trong chuỗi nhật ký."
                    : "Chưa đủ dữ liệu để kết luận."}
              </p>
            )}
          </div>
        )}
        <ActivityLog id={id} userId={user.id} />
      </>
    );
  }
  if (tab === "diagrams") return <WorkflowDiagrams request={r} embedded />;
  return null;
}

export default function RequestDetail({
  id,
  user,
  onBack,
  onEdit,
  onChanged,
  initialTab = "info",
}) {
  const resource = useResource(`/api/v1/requests/${id}`),
    [tab, setTab] = useState(initialTab),
    [action, setAction] = useState(null),
    [verify, setVerify] = useState(null);
  const uploadedEvidence = useRef("");
  const r = resource.data?.request,
    p = r ? permissions(user, r) : {};

  async function done() {
    setAction(null);
    resource.reload();
    onChanged();
  }

  const actions = {
    approve: ["Phê duyệt yêu cầu", "approval-decisions", "APPROVE"],
    reject: ["Từ chối yêu cầu", "approval-decisions", "REJECT"],
    info: ["Yêu cầu bổ sung thông tin", "approval-decisions", "NEEDS_INFO"],
    cancel: ["Hủy yêu cầu", "cancel"],
    revokeAi: ["Thu hồi duyệt tự động của AI", "ai-approval/revoke"],
    claim: ["Nhận công việc thực hiện", "execution/start"],
    accept: ["Chấp nhận nghiệm thu", "acceptance-decisions", "ACCEPT"],
    rework: ["Yêu cầu làm lại", "acceptance-decisions", "REWORK"],
    issue: ["Báo cáo vướng mắc", "issues"],
  };

  async function decide(values) {
    const [, path] = actions[action];
    await command(
      `requests/${id}/${path}`,
      requestActionPayload(action, r.lock_version, values),
    );
    await done();
  }

  async function execute(values) {
    const file = values.evidence;
    const fileKey = file?.size ? `${file.name}:${file.size}:${file.lastModified}` : "";
    // A failed submit keeps the evidence already stored; retrying must not
    // upload the same file again (the attempt allows only 5 files).
    if (fileKey && uploadedEvidence.current !== fileKey) {
      const body = new FormData();
      body.append("file", file);
      await api(`/api/v1/requests/${id}/execution/attachments`, {
        method: "POST",
        body,
      });
      uploadedEvidence.current = fileKey;
    }
    await command(`requests/${id}/execution/submit`, {
      expected_version: r.lock_version,
      result_note: values.result_note,
      external_reference: values.external_reference,
    });
    await done();
  }

  const requesterDisplay = r?.requester_name || r?.progress?.requester_name;
  const deptDisplay = r?.department_name || r?.progress?.department_name;

  return (
    <section>
      <div className="section-head">
        <button type="button" className="secondary" onClick={onBack}>
          ← Quay lại danh sách
        </button>
        <button type="button" className="secondary" onClick={resource.reload}>
          Làm mới hồ sơ
        </button>
      </div>
      <ResourceState resource={resource} skeleton={<DetailSkeleton />}>
        {r && (
          <>
            <div className="page-heading ds-detail-header">
              <div>
                <p className="eyebrow">
                  {r.code} · {r.type_name || r.progress?.type_name || types[r.type_code] || "Yêu cầu"}
                </p>
                <h1>{r.payload?.title || r.type_name || types[r.type_code] || r.code}</h1>
                <p className="muted">
                  {requesterDisplay && (
                    <>
                      Người đề nghị: <strong>{requesterDisplay}</strong>
                      {deptDisplay ? ` (${deptDisplay})` : ""} ·{" "}
                    </>
                  )}
                  Tạo lúc {date(r.created_at)} · Cập nhật {date(r.updated_at)} ·{" "}
                  {riskLevels[r.risk_weight || typeLevels[r.type_code]?.risk_weight || 3]} ·{" "}
                  {approvalLevels[
                    r.approval_level ||
                      r.approval_steps?.length ||
                      typeLevels[r.type_code]?.approval_level ||
                      1
                  ]}
                </p>
              </div>
              <Badge value={r.status} />
            </div>
            <ProgressSummary progress={r.progress} />
            <PageTabs
              label="Nội dung hồ sơ"
              value={tab}
              onChange={(key) => {
                setTab(key);
                window.requestAnimationFrame(() =>
                  document
                    .getElementById("request-detail-content")
                    ?.scrollIntoView({ behavior: "smooth", block: "start" }),
                );
              }}
              tabs={[
                ["info", "Thông tin"],
                ["progress", "Tiến trình xử lý"],
                ["approvers", "Người phê duyệt", r.approval_steps?.length || null],
                ["files", "Tệp đính kèm"],
                ...(r.status !== "DRAFT" ? [["ai", "Đánh giá AI"]] : []),
                ["activity", "Lịch sử hoạt động"],
                ["diagrams", "Sơ đồ luồng"],
              ]}
            />
            <div
              className={
                tab === "diagrams" ? "detail-grid flow-detail-grid" : "detail-grid"
              }
              id="request-detail-content"
            >
              <div className="panel">
                <DetailTabContent
                  tab={tab}
                  r={r}
                  id={id}
                  user={user}
                  verify={verify}
                  setVerify={setVerify}
                />
              </div>
              <aside className="panel">
                <p className="eyebrow">XỬ LÝ HỒ SƠ</p>
                <h2>Thao tác của bạn</h2>
                <div className="stack">
                  {p.edit && (
                    <button type="button" onClick={() => onEdit(r)}>
                      Chỉnh sửa / bổ sung
                    </button>
                  )}
                  {p.approve && (
                    <>
                      <button type="button" onClick={() => setAction("approve")}>
                        Phê duyệt
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setAction("info")}
                      >
                        Yêu cầu bổ sung
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => setAction("reject")}
                      >
                        Từ chối
                      </button>
                    </>
                  )}
                  {p.claim && (
                    <button type="button" onClick={() => setAction("claim")}>
                      Nhận công việc
                    </button>
                  )}
                  {p.execute && (
                    <button type="button" onClick={() => setAction("execution")}>
                      Nộp kết quả thực hiện
                    </button>
                  )}
                  {(p.claim || p.execute) && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setAction("issue")}
                    >
                      Báo vướng mắc
                    </button>
                  )}
                  {p.accept && (
                    <>
                      <button type="button" onClick={() => setAction("accept")}>
                        Chấp nhận nghiệm thu
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => setAction("rework")}
                      >
                        Yêu cầu làm lại
                      </button>
                    </>
                  )}
                  {p.cancel && (
                    <button
                      type="button"
                      className="danger"
                      onClick={() => setAction("cancel")}
                    >
                      Hủy yêu cầu
                    </button>
                  )}
                  {p.revokeAi && (
                    <button
                      type="button"
                      className="danger"
                      onClick={() => setAction("revokeAi")}
                    >
                      Thu hồi duyệt tự động của AI
                    </button>
                  )}
                  {!Object.values(p).some(Boolean) && (
                    <p className="muted">
                      Hiện không có thao tác xử lý nào cần bạn thực hiện ở bước này.
                    </p>
                  )}
                  {r.status !== "DRAFT" && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setTab("ai")}
                    >
                      Xem đánh giá AI
                    </button>
                  )}
                </div>
                <hr />
                <small className="muted">
                  Mọi quyết định phê duyệt, thực hiện và nghiệm thu đều được ghi nhận
                  minh bạch trong lịch sử hoạt động.
                </small>
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
                  warningNote={DANGER_WARNINGS[action] || ""}
                >
                  <p className="ds-modal-subject">
                    <strong>{r.code}</strong> · {r.payload?.title || types[r.type_code] || "Yêu cầu"}
                  </p>
                  {action === "execution" ? (
                    <>
                      <label>
                        Mô tả kết quả thực hiện
                        <textarea
                          name="result_note"
                          minLength={10}
                          maxLength={4000}
                          required
                          placeholder="Mô tả chi tiết công việc đã hoàn thành (tối thiểu 10 ký tự)…"
                        />
                      </label>
                      <label>
                        Mã tham chiếu / Số biên bản bàn giao
                        <input
                          name="external_reference"
                          maxLength={200}
                          required
                          placeholder="Ví dụ: BB-2026-015 hoặc mã phiếu trên hệ thống liên quan"
                        />
                      </label>
                      <label>
                        Tệp minh chứng kết quả (PDF, JPG, PNG)
                        <input
                          name="evidence"
                          type="file"
                          accept="application/pdf,image/jpeg,image/png"
                        />
                      </label>
                      <p className="muted">
                        Cần đính kèm minh chứng hợp lệ trước khi hoàn tất. Nếu tệp đang
                        được kiểm tra an toàn, vui lòng đợi vài giây rồi nộp lại.
                      </p>
                    </>
                  ) : ["reject", "info", "cancel", "rework", "issue", "revokeAi"].includes(
                      action,
                    ) ? (
                    <>
                      <Reason
                        placeholder={
                          action === "reject"
                            ? "Nhập lý do từ chối phê duyệt (từ 10 đến 2.000 ký tự)…"
                            : action === "info"
                              ? "Nhập nội dung yêu cầu người gửi bổ sung (từ 10 đến 2.000 ký tự)…"
                              : action === "cancel"
                                ? "Nhập lý do hủy yêu cầu (từ 10 đến 2.000 ký tự)…"
                                : "Nhập lý do hoặc nhận xét chi tiết (từ 10 đến 2.000 ký tự)…"
                        }
                      />
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
                      <p>
                        Bạn xác nhận thực hiện thao tác{" "}
                        <strong>{actions[action][0].toLowerCase()}</strong> đối với hồ sơ
                        này?
                      </p>
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

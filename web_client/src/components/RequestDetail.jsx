import FullHistory from "./FullHistory.jsx";
import ActivityTimeline from "./ActivityTimeline.jsx";
import { requestActionPayload } from "../actionPayload.js";
import { useState } from "react";
import { api, API_BASE } from "../api.js";
import { date, fields, permissions, types } from "../domain.js";
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
function History({ id }) {
  const r = useResource(`/api/v1/requests/${id}/revisions`);
  return (
    <ResourceState resource={r}>
      {r.data?.revisions?.map((v) => (
        <details key={v.id} className="record">
          <summary>
            Phiên bản {v.revision_no} · {date(v.submitted_at)}
          </summary>
          <Data value={v.payload} />
          {v.attachments?.map((a) => (
            <p key={a.id}>
              {a.original_name} <Badge value={a.scan_state} />{" "}
              {a.scan_state === "CLEAN" && (
                <a
                  href={`${API_BASE}/api/v1/attachments/${a.id}/download`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Tải xuống
                </a>
              )}
            </p>
          ))}
        </details>
      ))}
    </ResourceState>
  );
}
function Audit({ id }) {
  const r = useResource(`/api/v1/requests/${id}/audit`);
  return (
    <ResourceState resource={r}>
      <Data value={r.data?.items || r.data} />
    </ResourceState>
  );
}
export default function RequestDetail({ id, user, onBack, onEdit, onChanged, initialTab = "info" }) {
  const resource = useResource(`/api/v1/requests/${id}`),
    [tab, setTab] = useState(initialTab),
    [action, setAction] = useState(null),
    [verify, setVerify] = useState(null),
    [expandProgress, setExpandProgress] = useState(false);
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
        <button className="secondary" onClick={onBack}>
          ← Danh sách
        </button>
        <button className="secondary" onClick={resource.reload}>
          Tải lại hồ sơ
        </button>
      </div>
      <ResourceState resource={resource}>
        {r && (
          <>
            <div className="page-heading">
              <div>
                <p className="eyebrow">
                  {r.code} / {types[r.type_code]}
                </p>
                <h1>{r.payload?.title || r.code}</h1>
                <p className="muted">
                  Tạo lúc {date(r.created_at)} · Cập nhật {date(r.updated_at)}
                </p>
              </div>
              <Badge value={r.status} />
            </div>
            <div className="tabs" aria-label="Nội dung hồ sơ">
              {[
                ["info", "Thông tin yêu cầu"],
                ["progress", "Tiến trình"],
                ["history", "Phiên bản & tài liệu"],
                ["audit", "Nhật ký"],
              ].map(([key, title]) => (
                <button
                  key={key}
                  className={tab === key ? "active" : "secondary"}
                  onClick={() => {
                    setTab(key);
                    window.requestAnimationFrame(() => document.getElementById("request-detail-content")?.scrollIntoView({ behavior: "smooth", block: "start" }));
                  }}
                >
                  {title}
                </button>
              ))}
            </div>
            <div className="detail-grid" id="request-detail-content">
              <div className="panel">
                {tab === "info" && (
                  <>
                    <h2>Nội dung đề nghị</h2>
                    <dl className="data-list">
                      {Object.entries(r.payload || {}).map(([name, value]) => (
                        <div key={name}>
                          <dt>{fields[r.type_code]?.find(([field]) => field === name)?.[1] || name.replaceAll("_", " ")}</dt>
                          <dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</dd>
                        </div>
                      ))}
                    </dl>
                  </>
                )}
                {tab === "progress" && (
                  <>
                    <ActivityTimeline id={id} />
                    <details className="progress-extra"
                      onToggle={(event) => setExpandProgress(event.currentTarget.open)}>
                    <summary>Chi tiết các bước phê duyệt & nghiệm thu</summary>
                    <h2>Tiến trình phê duyệt</h2>
                    <ol className="timeline">
                      {r.approval_steps?.map((s, i) => (
                        <li key={i}>
                          <strong>Cấp {s.step_no}</strong>{" "}
                          <Badge value={s.state} />
                          <p className="muted">Người xử lý: {s.assignee_id}</p>
                          <small>{date(s.closed_at || s.activated_at)}</small>
                        </li>
                      ))}
                    </ol>
                    <h2>Thực hiện & nghiệm thu</h2>
                    {r.workflow?.attempt ? (
                      <>
                        <Badge value={r.workflow.attempt.state} />
                        <p>Lần thực hiện {r.workflow.attempt.attempt_no}</p>
                        <p>
                          {r.workflow.attempt.result_note ||
                            "Chưa nộp kết quả."}
                        </p>
                        <p>
                          Mã tham chiếu:{" "}
                          {r.workflow.attempt.external_reference || "—"}
                        </p>
                      </>
                    ) : (
                      <p className="muted">
                        Không có lần thực hiện đang hoạt động. Xem nhật ký để
                        tra cứu các lần đã kết thúc.
                      </p>
                    )}
                    {expandProgress && <FullHistory id={id} />}
                    </details>
                  </>
                )}
                {tab === "history" && <History id={id} />}
                {tab === "audit" && <Audit id={id} />}
              </div>
              <aside className="panel">
                <p className="eyebrow">XỬ LÝ HỒ SƠ</p>
                <h2>Thao tác của bạn</h2>
                <div className="stack">
                  {p.edit && (
                    <button onClick={() => onEdit(r)}>
                      Chỉnh sửa / bổ sung
                    </button>
                  )}
                  {p.approve && (
                    <>
                      <button onClick={() => setAction("approve")}>
                        Phê duyệt
                      </button>
                      <button
                        className="secondary"
                        onClick={() => setAction("info")}
                      >
                        Yêu cầu bổ sung
                      </button>
                      <button
                        className="danger"
                        onClick={() => setAction("reject")}
                      >
                        Từ chối
                      </button>
                    </>
                  )}
                  {p.claim && (
                    <button onClick={() => setAction("claim")}>
                      Nhận công việc
                    </button>
                  )}
                  {p.execute && (
                    <button onClick={() => setAction("execution")}>
                      Nộp kết quả thực hiện
                    </button>
                  )}
                  {(p.claim || p.execute) && (
                    <button
                      className="secondary"
                      onClick={() => setAction("issue")}
                    >
                      Báo vướng mắc
                    </button>
                  )}
                  {p.accept && (
                    <>
                      <button onClick={() => setAction("accept")}>
                        Chấp nhận nghiệm thu
                      </button>
                      <button
                        className="danger"
                        onClick={() => setAction("rework")}
                      >
                        Yêu cầu làm lại
                      </button>
                    </>
                  )}
                  {p.cancel && (
                    <button
                      className="danger"
                      onClick={() => setAction("cancel")}
                    >
                      Hủy yêu cầu
                    </button>
                  )}
                  {!Object.values(p).some(Boolean) && (
                    <p className="muted">
                      Hồ sơ ở chế độ xem theo quyền và trạng thái hiện tại.
                    </p>
                  )}
                  {user.roles.includes("AUDITOR") && (
                    <ActionForm
                      onSubmit={async () =>
                        setVerify(
                          await api(`/api/v1/requests/${id}/audit/verify`),
                        )
                      }
                      submitLabel="Xác minh nhật ký"
                    />
                  )}
                  {verify && <Data value={verify} />}
                </div>
                <hr />
                <small className="muted">
                  Quyết định và thay đổi được lưu trong lịch sử hồ sơ.
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
                  danger={["cancel", "reject", "rework"].includes(action)}
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
                  ) : ["reject", "info", "cancel", "rework", "issue"].includes(
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
                    <p>Xác nhận thực hiện thao tác trên hồ sơ này?</p>
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

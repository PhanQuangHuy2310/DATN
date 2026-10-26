import { API_BASE } from "../api.js";
import { date } from "../domain.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";
const outcomes = {
  APPROVE: "Đã phê duyệt",
  REJECT: "Từ chối",
  NEEDS_INFO: "Yêu cầu bổ sung",
  ACCEPT: "Nghiệm thu đạt",
  REWORK: "Yêu cầu làm lại",
  REASSIGNED: "Điều chuyển",
  SUCCESS: "Thành công",
  ACCEPTED: "Nghiệm thu đạt",
};
export default function FullHistory({ id }) {
  const r = useResource(`/api/v1/requests/${id}/history`);
  return (
    <ResourceState resource={r}>
      <h2>Lịch sử quyết định</h2>
      {r.data?.decisions?.map((d, i) => (
        <article className="record" key={i}>
          <strong>
            Cấp {d.step_no} · {outcomes[d.outcome]}
          </strong>
          <p>
            {d.actor_name} · {date(d.decided_at)}
          </p>
          <p>{d.reason || "Không có nhận xét bổ sung."}</p>
        </article>
      ))}
      <h2>Các lần thực hiện</h2>
      {r.data?.attempts?.map((a) => (
        <article className="record" key={a.id}>
          <div className="section-head">
            <strong>
              Lần {a.attempt_no} · {a.executor_name}
            </strong>
            <Badge value={a.state} />
          </div>
          <p>{a.result_note || "Chưa nộp kết quả."}</p>
          <p className="muted">
            {a.external_reference || "—"} ·{" "}
            {outcomes[a.closure_kind] || "Đang xử lý"}
          </p>
          {a.attachments?.map((f) => (
            <p key={f.id}>
              {f.original_name} <Badge value={f.scan_state} />
              {f.scan_state === "CLEAN" && (
                <a
                  href={`${API_BASE}/api/v1/attachments/${f.id}/download`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {" "}
                  Tải minh chứng
                </a>
              )}
            </p>
          ))}
          {a.decisions?.map((d, i) => (
            <div className="record" key={i}>
              <strong>{outcomes[d.outcome]}</strong>
              <p>
                {d.actor_name} · {date(d.decided_at)}
              </p>
              <p>{d.reason}</p>
            </div>
          ))}
        </article>
      ))}
      {!r.data?.attempts?.length && (
        <p className="muted">Chưa có lần thực hiện.</p>
      )}
    </ResourceState>
  );
}

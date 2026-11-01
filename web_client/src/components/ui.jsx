import { useEffect, useRef, useState } from "react";
import { api, getResource, peekResource, invalidateResource, onDataChanged, idempotencyKey } from "../api.js";
import { labels, fieldLabels, errorText } from "../domain.js";
export function Badge({ value }) {
  return (
    <span className={"badge " + value}>{labels[value] || value || "—"}</span>
  );
}
const commonLabels = {
  actor_kind:"Nguồn thao tác", action:"Hành động", created_at:"Ngày tạo", updated_at:"Cập nhật",
  occurred_at:"Thời điểm", reason:"Lý do", state:"Trạng thái", status:"Trạng thái",
  display_name:"Họ tên", department:"Phòng ban", role:"Vai trò", request_type:"Loại yêu cầu",
  result:"Kết quả", notes:"Ghi chú", details:"Chi tiết", score:"Điểm đánh giá",
  revision_no:"Phiên bản", submitted_at:"Ngày gửi", verified:"Đã xác minh",
};
export function Data({ value, technical = false }) {
  if (value === null || value === undefined)
    return <span className="muted">—</span>;
  if (Array.isArray(value))
    return value.length ? (
      <div className="stack">
        {value.map((v, i) => (
          <div className="record" key={i}>
            <Data value={v} technical={technical} />
          </div>
        ))}
      </div>
    ) : (
      <p className="muted">Chưa có dữ liệu.</p>
    );
  if (typeof value === "object")
    return (
      <dl className="data-list">
        {Object.entries(value).filter(([k]) => technical || !(["id", "actor_id", "request_id", "user_id", "department_id", "type_id", "assignee_id", "instance_id", "event_id", "step_id", "attempt_id", "correlation_id", "target_id", "revision_id", "workflow_id", "attachment_id", "prev_hash", "hash", "hash_version"].includes(k))).map(([k, v]) => (
          <div key={k}>
            <dt>{fieldLabels[k] || commonLabels[k] || (technical ? k : k.replace(/_/g," "))}</dt>
            <dd>
              <Data value={v} technical={technical} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span>{String(value)}</span>;
}
export function useResource(url) {
  const [state, setState] = useState(() => ({
    url,
    data: peekResource(url),
    error: "",
    loading: !peekResource(url),
    refreshing: false,
  }));
  const [version, setVersion] = useState(0);
  const [mutationVersion, setMutationVersion] = useState(0);

  const syncKey = `${url}:${version}:${mutationVersion}`;
  const [prevSyncKey, setPrevSyncKey] = useState(syncKey);
  if (prevSyncKey !== syncKey) {
    setPrevSyncKey(syncKey);
    const stale = peekResource(url);
    setState((s) => ({
      data: stale ?? (s.data && s.url === url ? s.data : null),
      url,
      error: "",
      loading: !stale && s.url !== url,
      refreshing: Boolean(stale) || (s.url === url && Boolean(s.data)),
    }));
  }

  useEffect(() => onDataChanged(() => setMutationVersion((v) => v + 1)), []);
  useEffect(() => {
    if (!url) {
      setState({ url, data: null, error: "", loading: false, refreshing: false });
      return;
    }
    let active = true;
    getResource(url).then((data) => {
      if (active) setState({ url, data, error: "", loading: false, refreshing: false });
    }).catch((e) => {
      if (active) setState((s) => ({ ...s, loading: false, refreshing: false, error: errorText(e) }));
    });
    return () => { active = false; };
  }, [url, version, mutationVersion]);
  return {
    ...state,
    reload: () => {
      invalidateResource(url);
      setState((s) => ({ ...s, refreshing: true, error: "" }));
      setVersion((v) => v + 1);
    },
  };
}
export function ResourceState({ resource, children }) {
  if (resource.loading && !resource.data) return <output className="empty" aria-live="polite"><span className="loading-spinner" /> Đang tải dữ liệu…</output>;
  if (resource.error && !resource.data) return <div role="alert" className="error">
    {resource.error} <button type="button" className="secondary" onClick={resource.reload}>Thử lại</button>
  </div>;
  return <>{resource.refreshing && <div className="resource-refresh" role="status">Đang đồng bộ dữ liệu mới…</div>}{children}{resource.error && <div role="status" className="muted">Dữ liệu đang hiển thị có thể chưa mới nhất. <button className="link" type="button" onClick={resource.reload}>Thử lại</button></div>}</>;
}
export function Modal({ title, onClose, children }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <dialog ref={ref} onCancel={onClose} aria-label={title}>
      <div className="section-head">
        <h2>{title}</h2>
        <button
          type="button"
          className="secondary"
          onClick={onClose}
          aria-label="Đóng hộp thoại"
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}
export async function command(
  path,
  body = {},
  method = "POST",
  key = idempotencyKey(),
) {
  return api("/api/v1/" + path, {
    method,
    headers: { "Idempotency-Key": key },
    body: JSON.stringify(body),
  });
}
export function ActionForm({
  title,
  onSubmit,
  children,
  submitLabel = "Xác nhận",
  danger = false,
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      await onSubmit(values);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        {children}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button type="submit" className={danger ? "danger" : ""} disabled={busy}>
            {busy ? "Đang xử lý…" : submitLabel || title}
          </button>
        </div>
      </fieldset>
    </form>
  );
}
export function Reason() {
  return (
    <label>
      Lý do / nhận xét
      <textarea
        name="reason"
        minLength={10}
        maxLength={2000}
        required
        rows={4}
        placeholder="Nhập từ 10 đến 2.000 ký tự"
      />
    </label>
  );
}

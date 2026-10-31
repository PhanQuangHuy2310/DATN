import { useEffect, useRef, useState } from "react";
import { api, getResource, peekResource, invalidateResource, onDataChanged, idempotencyKey } from "../api.js";
import { labels, errorText } from "../domain.js";
export function Badge({ value }) {
  return (
    <span className={"badge " + value}>{labels[value] || value || "—"}</span>
  );
}
export function Data({ value }) {
  if (value === null || value === undefined)
    return <span className="muted">—</span>;
  if (Array.isArray(value))
    return value.length ? (
      <div className="stack">
        {value.map((v, i) => (
          <div className="record" key={i}>
            <Data value={v} />
          </div>
        ))}
      </div>
    ) : (
      <p className="muted">Chưa có dữ liệu.</p>
    );
  if (typeof value === "object")
    return (
      <dl className="data-list">
        {Object.entries(value).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>
              <Data value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span>{String(value)}</span>;
}
export function useResource(url) {
  const [state, setState] = useState(() => ({ data: peekResource(url), error: "", loading: !peekResource(url), refreshing: false }));
  const [version, setVersion] = useState(0);
  const [mutationVersion, setMutationVersion] = useState(0);
  useEffect(() => onDataChanged(() => setMutationVersion((v) => v + 1)), []);
  useEffect(() => {
    let active = true;
    const stale = peekResource(url);
    setState((s) => ({
      data: stale ?? (s.data && s.url === url ? s.data : null),
      url, error: "", loading: !stale && s.url !== url,
      refreshing: !!stale || (s.url === url && !!s.data),
    }));
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

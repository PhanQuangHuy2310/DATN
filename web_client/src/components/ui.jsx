import { useEffect, useRef, useState } from "react";
import { api, idempotencyKey } from "../api.js";
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
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    api(url, { signal: controller.signal })
      .then((data) => {
        if (active) setState({ data, error: "", loading: false });
      })
      .catch((e) => {
        if (active)
          setState({ data: null, error: errorText(e), loading: false });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [url, version]);
  return {
    ...state,
    reload: () => {
      setState((s) => ({ ...s, loading: true, error: "" }));
      setVersion((v) => v + 1);
    },
  };
}
export function ResourceState({ resource, children }) {
  if (resource.loading)
    return (
      <p role="status" className="empty">
        Đang tải dữ liệu…
      </p>
    );
  if (resource.error)
    return (
      <div role="alert" className="error">
        {resource.error}{" "}
        <button className="secondary" onClick={resource.reload}>
          Thử lại
        </button>
      </div>
    );
  return children;
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
          <button className={danger ? "danger" : ""} disabled={busy}>
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

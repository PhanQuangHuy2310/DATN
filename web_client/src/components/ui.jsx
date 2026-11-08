import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import {
  api,
  getResource,
  peekResource,
  invalidateResource,
  onDataChanged,
  idempotencyKey,
} from "../api.js";
import {
  labels,
  enumLabels,
  types,
  roles,
  resolverLabels,
  fieldLabels,
  resolveFieldLabel,
  errorText,
} from "../domain.js";
import { formatScalarDisplay, isCurrencyField, vndToVietnameseWords } from "../formatters.js";

export function Badge({ value }) {
  const display = labels[value] || enumLabels[value] || value || "—";
  return <span className={"badge " + (value || "")}>{display}</span>;
}

const commonLabels = {
  actor_kind: "Nguồn thao tác",
  actor_name: "Người thực hiện",
  action: "Hành động",
  created_at: "Thời điểm tạo",
  updated_at: "Cập nhật gần nhất",
  occurred_at: "Thời điểm ghi nhận",
  reason: "Lý do / Diễn giải",
  state: "Trạng thái",
  status: "Trạng thái",
  display_name: "Họ và tên",
  department: "Phòng ban",
  department_name: "Phòng ban",
  role: "Vai trò",
  request_type: "Loại yêu cầu",
  type_code: "Loại yêu cầu",
  result: "Kết quả",
  notes: "Ghi chú",
  details: "Chi tiết nghiệp vụ",
  score: "Điểm đánh giá",
  revision_no: "Phiên bản hồ sơ",
  submitted_at: "Thời điểm gửi",
  verified: "Trạng thái xác minh",
  from_status: "Trạng thái trước",
  to_status: "Trạng thái mới",
  step_no: "Bước phê duyệt",
  tier_level: "Cấp phê duyệt",
  decision: "Quyết định",
  filename: "Tên tệp",
  original_name: "Tên tệp gốc",
  size_bytes: "Dung lượng (byte)",
};

const HIDDEN_KEYS = new Set([
  "id",
  "actor_id",
  "request_id",
  "user_id",
  "department_id",
  "type_id",
  "assignee_id",
  "instance_id",
  "event_id",
  "step_id",
  "attempt_id",
  "correlation_id",
  "target_id",
  "revision_id",
  "workflow_id",
  "attachment_id",
  "prev_hash",
  "hash",
  "hash_version",
  "client_ip",
  "ip",
  "user_agent",
  "session_id",
]);

const COMBINED_ENUM_MAP = {
  ...labels,
  ...enumLabels,
  ...types,
  ...roles,
  ...resolverLabels,
};

export function Data({ value, technical = false, fieldName = "", resolvedUsers = {} }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted">—</span>;
  }
  if (Array.isArray(value)) {
    if (!value.length) return <span className="muted">Chưa có dữ liệu.</span>;
    const allPrimitive = value.every((item) => item === null || typeof item !== "object");
    if (allPrimitive) {
      return (
        <ul className="ds-inline-value-list">
          {value.map((item, idx) => (
            <li key={idx}>
              {formatScalarDisplay(fieldName, item, {
                enumMap: COMBINED_ENUM_MAP,
                resolvedUsers,
                technical,
              })}
            </li>
          ))}
        </ul>
      );
    }
    return (
      <div className="stack">
        {value.map((v, i) => (
          <div className="record" key={i}>
            <Data value={v} technical={technical} resolvedUsers={resolvedUsers} />
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value).filter(
      ([k, v]) =>
        v !== null &&
        v !== undefined &&
        v !== "" &&
        (technical || (!HIDDEN_KEYS.has(k) && !k.endsWith("_id")))
    );
    if (!entries.length) {
      return <span className="muted">Không có chi tiết bổ sung.</span>;
    }
    return (
      <dl className="data-list">
        {entries.map(([k, v]) => (
          <div key={k}>
            <dt>{fieldLabels[k] || commonLabels[k] || resolveFieldLabel(k, { technical })}</dt>
            <dd>
              <Data
                value={v}
                technical={technical}
                fieldName={k}
                resolvedUsers={resolvedUsers}
              />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  const formatted = formatScalarDisplay(fieldName, value, {
    enumMap: COMBINED_ENUM_MAP,
    resolvedUsers,
    technical,
  });
  const words = isCurrencyField(fieldName) ? vndToVietnameseWords(value) : "";

  return (
    <span className={isCurrencyField(fieldName) ? "ds-currency-value" : undefined}>
      {formatted}
      {words && <small className="ds-currency-words">({words})</small>}
    </span>
  );
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
    if (!url) return;
    let active = true;
    let fetching = false;
    let failed = false;
    let retryCount = 0;
    let timer = null;

    const retryable = (e) => e?.status === 0
      || [408, 429, 500, 502, 503, 504].includes(e?.status)
      || ["NETWORK_UNAVAILABLE", "REQUEST_TIMED_OUT"].includes(e?.message);

    const refresh = async () => {
      if (!active || fetching) return;
      fetching = true;
      try {
        const data = await getResource(url);
        failed = false;
        retryCount = 0;
        if (active) setState({ url, data, error: "", errorStatus: null, loading: false, refreshing: false });
      } catch (e) {
        failed = true;
        if (active) {
          setState((old) => ({ ...old, loading: false, refreshing: false, error: errorText(e), errorStatus: e?.status ?? null }));
          // Only safe GETs are retried here; write actions are never repeated.
          // Back off and stop after a few attempts rather than filling Console.
          if (retryable(e) && retryCount < 4 && document.visibilityState !== "hidden") {
            const delay = e?.status === 429
              ? Math.max(15000, e?.retryAfterMs || 0)
              : Math.min(12000, 1500 * 2 ** retryCount);
            retryCount += 1;
            timer = window.setTimeout(() => {
              timer = null;
              invalidateResource(url);
              void refresh();
            }, delay);
          }
        }
      } finally {
        fetching = false;
      }
    };
    const onReconnect = () => {
      if (!active || !failed || fetching || document.visibilityState !== "visible") return;
      window.clearTimeout(timer);
      timer = null;
      retryCount = 0;
      invalidateResource(url);
      void refresh();
    };
    void refresh();
    window.addEventListener("online", onReconnect);
    document.addEventListener("visibilitychange", onReconnect);
    return () => {
      active = false;
      window.clearTimeout(timer);
      window.removeEventListener("online", onReconnect);
      document.removeEventListener("visibilitychange", onReconnect);
    };
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

export function ResourceState({ resource, skeleton = null, children }) {
  if (resource.loading && !resource.data) {
    return (
      <output className="ds-loading" aria-live="polite" aria-busy="true">
        <span className="sr-only">Đang tải dữ liệu…</span>
        {skeleton || (
          <span className="ds-skeleton" aria-hidden="true">
            {[92, 78, 64].map((w) => (
              <span key={w} className="ds-skeleton-line" style={{ width: `${w}%` }} />
            ))}
          </span>
        )}
      </output>
    );
  }
  if (resource.error && !resource.data && resource.errorStatus === 403) {
    // Permission is decided by the server; retrying cannot help.
    return (
      <div role="status" className="ds-permission-denied">
        <strong>Bạn không có quyền xem nội dung này</strong>
        <p className="muted">Quyền truy cập do quản trị viên cấp theo vai trò và phạm vi phòng ban. Liên hệ quản trị viên nếu bạn cần sử dụng chức năng này.</p>
      </div>
    );
  }
  if (resource.error && !resource.data) {
    return (
      <div role="alert" className="error">
        <span>{resource.error}</span>{" "}
        <button type="button" className="secondary" onClick={resource.reload}>
          Thử lại
        </button>
      </div>
    );
  }
  return (
    <>
      {resource.refreshing && (
        <div className="resource-refresh" role="status">
          Đang đồng bộ dữ liệu mới…
        </div>
      )}
      {children}
      {resource.error && (
        <div role="status" className="muted">
          Dữ liệu đang hiển thị có thể chưa mới nhất.{" "}
          <button className="link" type="button" onClick={resource.reload}>
            Thử lại
          </button>
        </div>
      )}
    </>
  );
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
  warningNote = "",
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
        {danger && warningNote && (
          <div className="ds-danger-callout" role="note">
            <strong aria-hidden="true"><Icon name="alert" size={14} /></strong>
            <span>{warningNote}</span>
          </div>
        )}
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

export function Reason({ label = "Lý do / nhận xét", placeholder = "Nhập từ 10 đến 2.000 ký tự" } = {}) {
  return (
    <label>
      {label}
      <textarea
        name="reason"
        minLength={10}
        maxLength={2000}
        required
        rows={4}
        placeholder={placeholder}
      />
    </label>
  );
}

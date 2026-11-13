import { useCallback, useEffect, useState } from "react";
import { InfoHint } from "./design.jsx";
import { api } from "../api.js";
import { errorText, resolverLabels } from "../domain.js";

const ROLE_LABELS = { APPROVER: "Phê duyệt", EXECUTOR: "Thực hiện", ACCEPTOR: "Nghiệm thu" };
const PROBLEMS = {
  ROUTE_CONFIGURATION_INVALID: "Chưa xác định được người duyệt cho phòng ban của bạn (ví dụ chưa có quản lý trực tiếp). Hãy liên hệ quản trị trước khi gửi.",
  ROUTE_ACTOR_INACTIVE: "Một người trong tuyến chưa được cấp quyền hoặc đã ngừng hoạt động; yêu cầu sẽ không gửi được cho đến khi quản trị cập nhật.",
  ROUTE_SOD_ESCALATION_UNRESOLVED: "Không tìm thấy người quản lý cấp trên đủ quyền thay thế để tránh tự duyệt. Hãy liên hệ quản trị để cập nhật sơ đồ tổ chức và quyền phê duyệt.",
};

function previewPayload(values) {
  const payload = {};
  for (const [key, value] of Object.entries(values)) {
    if (value instanceof File || value === "") continue;
    payload[key] = /^\d+$/.test(String(value)) ? Number(value) : value;
  }
  return payload;
}

function fetchPreview(type, values) {
  return api("/api/v1/requests/route-preview", {
    method: "POST", silent: true,
    body: JSON.stringify({ type_code: type, payload: previewPayload(values) }),
  }).then((result) => result.preview);
}

/** Shows who will approve/execute/accept before submission. Read-only: the
 * backend runs the same resolver as submit and persists nothing. */
export default function RoutePreview({ type, getValues }) {
  const [state, setState] = useState({ type: null, error: "", preview: null });
  const [refreshing, setRefreshing] = useState(false);
  // Initial preview when the type changes; amounts/dates are applied on demand.
  useEffect(() => {
    if (!type) return undefined;
    let active = true;
    fetchPreview(type, getValues())
      .then((preview) => { if (active) setState({ type, error: "", preview }); })
      .catch((error) => { if (active) setState({ type, error: errorText(error), preview: null }); });
    return () => { active = false; };
    // getValues reads the live form; re-running on its identity would refetch every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try { setState({ type, error: "", preview: await fetchPreview(type, getValues()) }); }
    catch (error) { setState({ type, error: errorText(error), preview: null }); }
    finally { setRefreshing(false); }
  }, [type, getValues]);
  const loading = refreshing || (Boolean(type) && state.type !== type);
  const preview = state.preview;
  return <section className="route-preview" aria-label="Tuyến phê duyệt dự kiến" aria-busy={loading}>
    <div className="section-head">
      <div><h3>Tuyến xử lý dự kiến<InfoHint>Tính theo quy chế đang công bố, phòng ban và quản lý trực tiếp của bạn.</InfoHint></h3></div>
      <button type="button" className="secondary" onClick={refresh} disabled={loading}>{loading ? "Đang tính…" : "Cập nhật theo nội dung"}</button>
    </div>
    {state.error && <p className="error" role="alert">Không xem trước được tuyến duyệt: {state.error}</p>}
    {preview && <>
      {preview.problem && <p className="error" role="alert">{PROBLEMS[preview.problem] || preview.problem}</p>}
      {preview.steps.length > 0 && <ol className="route-preview-steps">
        {preview.steps.map((step, index) => <li key={`${step.role}-${index}`} className={step.authorized ? "" : "route-step-invalid"}>
          <span className="route-step-tag">{step.level ? `Cấp ${step.level}` : ROLE_LABELS[step.role]}</span>
          <strong>{step.assignee_name || "Chưa xác định"}</strong>
          <small className="muted">{resolverLabels[step.resolver_code] || ROLE_LABELS[step.role]}{step.sod_escalated ? " · Đã chuyển cấp để tránh tự duyệt" : ""}{!step.authorized ? " · chưa đủ quyền" : ""}</small>
        </li>)}
      </ol>}
      {preview.sla_hours?.approval && <p className="muted">Thời hạn phê duyệt mỗi cấp: {preview.sla_hours.approval} giờ{preview.sla_hours.execution ? ` · thực hiện ${preview.sla_hours.execution} giờ` : ""}{preview.sla_hours.acceptance ? ` · nghiệm thu ${preview.sla_hours.acceptance} giờ` : ""}.</p>}
    </>}
  </section>;
}

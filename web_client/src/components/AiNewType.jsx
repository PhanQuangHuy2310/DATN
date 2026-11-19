import { useEffect, useState } from "react";
import { api, notify } from "../api.js";
import { errorText } from "../domain.js";
import { isNewNeed, MIN_CLASSIFY_CHARS, suggestTypes } from "../aiTypeSwitch.js";
import { Modal } from "./ui.jsx";

const LIFECYCLE_TEXT = {
  B: "Mẫu B · phê duyệt rồi bộ phận thực hiện",
  C: "Mẫu C · phê duyệt, thực hiện và nghiệm thu",
};

// Loại yêu cầu người dùng được tạo (mã + tên), dùng chung cho các ô tìm kiếm trong một phút.
let creatable = { at: 0, promise: null };

export function loadCreatableTypes() {
  if (!creatable.promise || Date.now() - creatable.at > 60_000) {
    const promise = api("/api/v1/meta/request-type-forms", { silent: true })
      .then((result) => (result.items || []).map(({ code, name }) => ({ code, name: name || code })))
      .catch(() => {
        creatable = { at: 0, promise: null };
        return [];
      });
    creatable = { at: Date.now(), promise };
  }
  return creatable.promise;
}

export function forgetCreatableTypes() {
  creatable = { at: 0, promise: null };
}

/**
 * "Có phải ý bạn là…": AI so nội dung tìm kiếm với các loại yêu cầu (kể cả loại mới tạo sau khi huấn luyện).
 * `newNeed` = AI đánh giá nhu cầu chưa có trong danh mục.
 */
export function useAiTypeSuggestions(query, { enabled = true } = {}) {
  const text = String(query || "").trim();
  const active = enabled && text.length >= MIN_CLASSIFY_CHARS;
  const [state, setState] = useState({ text: "", items: [], newNeed: false, failed: false });

  useEffect(() => {
    if (!active) return undefined;
    let alive = true;
    Promise.all([
      api("/api/v1/ai/classify", { method: "POST", silent: true, body: JSON.stringify({ title: text }) }),
      loadCreatableTypes(),
    ])
      .then(([response, types]) => {
        if (!alive) return;
        const result = response.data || {};
        setState({
          text,
          items: suggestTypes(result, types),
          newNeed: isNewNeed(result),
          failed: Boolean(result.fallback_used),
        });
      })
      .catch(() => {
        if (alive) setState({ text, items: [], newNeed: false, failed: true });
      });
    return () => {
      alive = false;
    };
  }, [active, text]);

  const ready = active && state.text === text;
  return {
    active,
    loading: active && !ready,
    items: ready ? state.items : [],
    newNeed: ready && state.newNeed,
    failed: ready && state.failed,
  };
}

/**
 * Nhu cầu chưa có loại yêu cầu: AI xem đã có loại phù hợp chưa; chưa có thì cho xem loại sẽ tạo (tên, nhóm,
 * tuyến duyệt) và tạo ngay khi người dùng đồng ý. Loại tạo xong ai cũng tìm thấy, người sau không phải tạo lại.
 */
export function NewTypeDialog({ text, onStart, onClose }) {
  const [state, setState] = useState({ text: "", step: "loading" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api("/api/v1/ai/request-types/proposal", { method: "POST", silent: true, body: JSON.stringify({ text }) })
      .then((response) => {
        if (!alive) return;
        const data = response.data || {};
        setState(data.existing ? { text, step: "existing", type: data.existing } : { text, step: "proposal", proposal: data.proposal });
      })
      .catch((err) => {
        if (alive) setState({ text, step: "error", message: errorText(err) });
      });
    return () => {
      alive = false;
    };
  }, [text]);

  const phase = state.text === text ? state : { step: "loading" };

  async function create() {
    setBusy(true);
    setError("");
    try {
      const response = await api("/api/v1/ai/request-types", { method: "POST", body: JSON.stringify({ text }) });
      const created = response.data || {};
      forgetCreatableTypes();
      notify(created.created ? `Đã tạo loại yêu cầu «${created.type.name}»` : `Hệ thống đã có loại «${created.type.name}»`);
      onStart({ type: created.type.code, label: created.type.name, title: text });
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Tạo yêu cầu mới với AI" onClose={onClose}>
      <div className="ai-new-type">
        <p className="muted">
          Nhu cầu: <strong>«{text}»</strong>
        </p>
        {phase.step === "loading" && <p role="status">AI đang xem nhu cầu này đã có loại yêu cầu nào chưa…</p>}
        {phase.step === "error" && (
          <p className="error" role="alert">
            {phase.message}
          </p>
        )}
        {phase.step === "existing" && (
          <>
            <p>
              Hệ thống đã có loại phù hợp: <strong>{phase.type.name}</strong> (độ tin cậy{" "}
              {Math.round((phase.type.confidence || 0) * 100)}%). Không cần tạo loại mới.
            </p>
            <div className="modal-actions">
              <button type="button" onClick={() => onStart({ type: phase.type.code, label: phase.type.name, title: text })}>
                Tạo yêu cầu «{phase.type.name}»
              </button>
              <button type="button" className="secondary" onClick={onClose}>
                Đóng
              </button>
            </div>
          </>
        )}
        {phase.step === "proposal" && (
          <>
            <p>AI chưa thấy loại yêu cầu nào phù hợp nên đề xuất tạo loại mới:</p>
            <dl className="ai-new-type-facts">
              <dt>Tên loại</dt>
              <dd>
                <strong>{phase.proposal.name}</strong>
              </dd>
              <dt>Nhóm nghiệp vụ</dt>
              <dd>{phase.proposal.group_name}</dd>
              <dt>Quy trình</dt>
              <dd>{LIFECYCLE_TEXT[phase.proposal.lifecycle] || phase.proposal.lifecycle}</dd>
              <dt>Tuyến duyệt</dt>
              <dd>{phase.proposal.route_summary}</dd>
              <dt>Rủi ro</dt>
              <dd>Cấp {phase.proposal.risk_weight}/5</dd>
            </dl>
            <p className="muted">
              Loại mới không bao giờ được tự duyệt: luôn có người phê duyệt. Quản trị được thông báo để rà soát; người
              sau tìm nhu cầu tương tự sẽ thấy ngay loại này.
            </p>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <div className="modal-actions">
              <button type="button" onClick={create} disabled={busy}>
                {busy ? "Đang tạo…" : "Tạo loại và lập yêu cầu"}
              </button>
              <button type="button" className="secondary" onClick={onClose} disabled={busy}>
                Hủy
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

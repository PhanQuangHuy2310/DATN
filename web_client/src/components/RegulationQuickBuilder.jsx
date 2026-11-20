import { useState } from "react";
import { ACTIONS, APPROVERS, buildClause, CONDITIONS, nextArticle, OPERATORS } from "../regulationTemplate.js";

/** Mẫu nạp nhanh: chọn loại, điều kiện, ngưỡng, cách duyệt -> thêm một điều khoản vào nội dung (sửa tay được). */
export default function RegulationQuickBuilder({ types = [], content, onAppend }) {
  const [state, setState] = useState({ type: "", cond: "amount", op: "gt", value: "", act: "manual", approver: "Trưởng bộ phận" });
  const set = (patch) => setState((prev) => ({ ...prev, ...patch }));
  const typeName = types.find((t) => t.code === state.type)?.name || "";
  const unit = CONDITIONS.find((c) => c.id === state.cond)?.unit;
  const clause = buildClause({ ...state, typeName }, nextArticle(content));

  return (
    <fieldset className="reg-quick">
      <legend>Mẫu nạp nhanh — chọn vài ô, hệ thống tự viết điều khoản đúng chuẩn AI hiểu</legend>
      <div className="reg-quick-grid">
        <label>
          Loại yêu cầu
          <select className="eas-select" value={state.type} onChange={(e) => set({ type: e.target.value })}>
            <option value="">— Chọn loại —</option>
            {types.map((t) => (
              <option key={t.code} value={t.code}>{t.name}</option>
            ))}
          </select>
        </label>
        <label>
          Điều kiện
          <select className="eas-select" value={state.cond} onChange={(e) => set({ cond: e.target.value })}>
            {CONDITIONS.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        </label>
        {state.cond !== "all" && state.cond !== "repeat" && (
          <label>
            So sánh
            <select className="eas-select" value={state.op} onChange={(e) => set({ op: e.target.value })}>
              {OPERATORS.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </label>
        )}
        {state.cond !== "all" && (
          <label>
            Ngưỡng ({unit})
            <input className="eas-input" inputMode="decimal" value={state.value} placeholder="Ví dụ: 5"
              onChange={(e) => set({ value: e.target.value })} />
          </label>
        )}
        <label>
          Cách duyệt
          <select className="eas-select" value={state.act} onChange={(e) => set({ act: e.target.value })}>
            {ACTIONS.map((a) => (
              <option key={a.id} value={a.id}>{a.label}</option>
            ))}
          </select>
        </label>
        {state.act !== "auto" && (
          <label>
            Người duyệt
            <select className="eas-select" value={state.approver} onChange={(e) => set({ approver: e.target.value })}>
              {APPROVERS.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <p className="reg-quick-preview">
        {clause || (state.act === "auto" && state.cond === "repeat"
          ? "AI không được tự duyệt theo số lần lặp lại; chọn cách duyệt khác."
          : "Chọn loại yêu cầu và nhập ngưỡng để xem trước điều khoản.")}
      </p>
      <button type="button" className="btn-secondary" disabled={!clause}
        onClick={() => onAppend(clause, typeName)}>
        + Thêm điều khoản này
      </button>
    </fieldset>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api.js";
import { date } from "../domain.js";

const KIND_TEXT = {
  GARBLED: "Lỗi ký tự",
  CONTRADICTION: "Mâu thuẫn",
  EMPTY: "Trống",
  UNPARSED: "AI chưa hiểu",
  DUPLICATE: "Trùng lặp",
  NO_CONTROL: "Không đổi cách duyệt",
  VALIDATION: "Văn bản lỗi",
  TECHNICAL: "Lỗi kỹ thuật",
};
const ACTION_TEXT = { CREATE: "Thêm mới", UPDATE: "Sửa", DELETE: "Bãi bỏ" };

function Issue({ item }) {
  return (
    <li className={`reg-check-item ${item.severity === "ERROR" ? "error" : "warning"}`}>
      <span className="reg-check-badge">{KIND_TEXT[item.kind] || item.kind}</span>
      {item.article && <strong> {item.article}: </strong>} {item.message}
      {item.sentence && <blockquote className="ai-citation-quote">{item.sentence}</blockquote>}
      {item.related?.sentence && (
        <p className="muted">
          Chồng với {item.related.article || "một điều"}
          {item.related.code ? ` của ${item.related.code}` : ""}: “{item.related.sentence}”
        </p>
      )}
    </li>
  );
}

/** Kết quả AI đọc văn bản quy định: lỗi chặn (đỏ) và cảnh báo (vàng), chỉ rõ từng câu. */
export function RegulationCheckList({ check }) {
  if (!check) return null;
  const errors = check.errors || [];
  const warnings = check.warnings || [];
  return (
    <section className="reg-check" aria-label="AI kiểm tra văn bản quy định" role="status">
      <p className={errors.length ? "reg-check-head error" : "reg-check-head ok"}>
        {errors.length
          ? `AI phát hiện ${errors.length} lỗi, cần sửa trước khi ban hành.`
          : `AI không thấy lỗi chặn${check.rules != null ? ` · hiểu được ${check.rules} luật duyệt` : ""}.`}
        {warnings.length ? ` ${warnings.length} lưu ý.` : ""}
      </p>
      {(errors.length > 0 || warnings.length > 0) && (
        <ul className="reg-check-list">
          {errors.map((e, i) => (
            <Issue key={`e${i}`} item={e} />
          ))}
          {warnings.map((w, i) => (
            <Issue key={`w${i}`} item={w} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** Quy định bị trả lại: hiệu lực đã quay về bản đã áp dụng; admin sửa theo danh sách lỗi rồi nạp lại. */
export function RejectedRegulations({ apiBase, onRevise, version }) {
  const [data, setData] = useState(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    api(`${apiBase}/regulations/rejections?state=OPEN`, { silent: true })
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null));
    return () => {
      alive = false;
    };
  }, [apiBase, reload, version]);

  if (!data?.installed || !data.items?.length) return null;

  async function dismiss(item) {
    const note = window.prompt("Vì sao bỏ qua bản bị trả lại này (không nạp lại)?");
    if (!note || note.trim().length < 5) return;
    await api(`${apiBase}/regulations/rejections/${item.id}/dismiss`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
    setReload((v) => v + 1);
  }

  return (
    <section className="reg-rejected" aria-label="Quy định bị trả lại">
      <h2>Quy định bị trả lại ({data.items.length})</h2>
      <p className="muted">
        Các văn bản dưới đây KHÔNG được áp dụng: hiệu lực (văn bản hiển thị và bộ luật AI) đã quay về bản đã áp dụng
        trước đó. Sửa đúng các chỗ AI chỉ ra rồi nạp lại.
      </p>
      <ol className="reg-rejected-list">
        {data.items.map((item) => (
          <li key={item.id} className="reg-rejected-card">
            <div className="ai-remedy-item-head">
              <strong>
                {item.regulation_code} · {item.rejected_title || "(không tiêu đề)"}
              </strong>
              <span className="muted">
                {ACTION_TEXT[item.action] || item.action} · bản {item.rejected_version || "?"} bị trả lại
                {item.restored_version ? ` · hiệu lực hiện tại: bản ${item.restored_version}` : ""} ·{" "}
                {date(item.created_at)}
              </span>
            </div>
            <p>
              <span className="reg-check-badge">{KIND_TEXT[item.cause] || item.cause}</span> {item.message}
            </p>
            <RegulationCheckList check={{ errors: item.errors, warnings: item.warnings }} />
            {item.rejected_content && (
              <details>
                <summary>Nội dung bản bị trả lại</summary>
                <pre className="reg-rejected-content">{item.rejected_content}</pre>
              </details>
            )}
            <div className="ai-remedy-actions">
              {item.action !== "DELETE" && (
                <button type="button" onClick={() => onRevise(item)}>
                  Sửa và nạp lại
                </button>
              )}
              <button type="button" className="secondary" onClick={() => dismiss(item)}>
                Bỏ qua
              </button>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

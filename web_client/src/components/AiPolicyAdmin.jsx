import { PageInfo } from "./design.jsx";
import { useState } from "react";
import { date, errorText } from "../domain.js";
import { ResourceState, command, useResource } from "./ui.jsx";
import { parsePolicyFile } from "../actionPayload.js";

/** POLICY_ADMIN: upload AI policy rules, list stored versions, activate/restore. */
export default function AiPolicyAdmin() {
  const resource = useResource("/api/v1/policies/ai-rules");
  const [draft, setDraft] = useState(null);
  const [versionOverride, setVersionOverride] = useState("");
  const [activate, setActivate] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ kind: "", text: "" });

  async function onFile(event) {
    setMessage({ kind: "", text: "" });
    const file = event.target.files?.[0];
    if (!file) return setDraft(null);
    try {
      setDraft(parsePolicyFile(await file.text()));
    } catch (error) {
      setDraft(null);
      setMessage({ kind: "error", text: error.message });
    }
  }

  async function run(action, success) {
    setBusy(true);
    setMessage({ kind: "", text: "" });
    try {
      const result = await action();
      setMessage({
        kind: "success",
        text: success + (result?.ai_cache_refreshed === false ? " AI sẽ tự đồng bộ khi kết nối lại." : ""),
      });
      resource.reload();
    } catch (error) {
      setMessage({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  function upload(event) {
    event.preventDefault();
    if (!draft) return;
    const body = { ...draft, version: versionOverride.trim() || draft.version, activate };
    return run(
      () => command("policies/ai-rules", body),
      `Đã lưu bộ luật ${body.version}${activate ? " và kích hoạt" : ""}.`,
    );
  }

  const items = resource.data?.items || [];
  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">EAS / QUY ĐỊNH AI</p>
          <h1>Bộ luật quy định AI<PageInfo>Bộ luật lưu trong cơ sở dữ liệu; phiên bản đang kích hoạt được AI áp dụng ngay ở yêu cầu kế tiếp.</PageInfo></h1>
        </div>
      </div>
      <form className="panel" onSubmit={upload} aria-label="Tải bộ luật mới">
        <h2>Tải bộ luật mới</h2>
        <label>
          Tệp JSON
          <input type="file" accept="application/json,.json" onChange={onFile} disabled={busy} />
        </label>
        <p className="muted">Định dạng: {"{"}"version": "QD-2026-11", "rules": [{"{"}"id": "...", "min_risk": 4 | "auto_approve": false, "request_type"?, "amount_gt"?, "days_gt"?{"}"}]{"}"}</p>
        <label>
          Mã phiên bản (để trống để dùng giá trị trong tệp)
          <input value={versionOverride} maxLength={50} onChange={(e) => setVersionOverride(e.target.value)} placeholder={draft?.version || "QD-2026-11"} />
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={activate} onChange={(e) => setActivate(e.target.checked)} /> Kích hoạt ngay sau khi lưu
        </label>
        {draft && <p role="status">Đã đọc {draft.rules.length} luật từ tệp.</p>}
        {message.text && <p role={message.kind === "error" ? "alert" : "status"} className={message.kind}>{message.text}</p>}
        <button type="submit" disabled={!draft || busy}>{busy ? "Đang lưu…" : "Lưu bộ luật"}</button>
      </form>
      <section className="panel" aria-label="Các phiên bản bộ luật">
        <div className="section-head">
          <h2>Các phiên bản</h2>
          <button type="button" className="secondary" onClick={resource.reload}>Làm mới</button>
        </div>
        <ResourceState resource={resource}>
          {items.length ? (
            <div className="table-wrap"><table className="responsive-records">
              <thead><tr><th>Phiên bản</th><th>Trạng thái</th><th>Số luật</th><th>Người tạo</th><th>Tạo lúc</th><th>Kích hoạt lúc</th><th>Thao tác</th></tr></thead>
              <tbody>{items.map((item) => (
                <tr key={item.id}>
                  <td data-label="Phiên bản"><strong>{item.version}</strong></td>
                  <td data-label="Trạng thái">{item.state === "ACTIVE" ? "Đang áp dụng" : "Không hoạt động"}</td>
                  <td data-label="Số luật">{item.rules.length}</td>
                  <td data-label="Người tạo">{item.created_by || "—"}</td>
                  <td data-label="Tạo lúc">{date(item.created_at)}</td>
                  <td data-label="Kích hoạt lúc">{date(item.activated_at)}</td>
                  <td data-label="Thao tác">
                    {item.state !== "ACTIVE" && (
                      <button type="button" disabled={busy} onClick={() => run(
                        () => command(`policies/ai-rules/${item.id}/activate`, {}),
                        `Đã ${item.activated_at ? "khôi phục" : "kích hoạt"} bộ luật ${item.version}.`,
                      )}>{item.activated_at ? "Khôi phục" : "Kích hoạt"}</button>
                    )}
                  </td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <p className="empty">Chưa có bộ luật nào được lưu.</p>}
        </ResourceState>
      </section>
    </section>
  );
}

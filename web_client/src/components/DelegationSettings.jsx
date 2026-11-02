import { useState } from "react";
import { date, errorText } from "../domain.js";
import { delegationActive, delegationBody } from "../actionPayload.js";
import { ResourceState, command, useResource } from "./ui.jsx";

/** Approver hands approval steps to a colleague for a time window. */
export default function DelegationSettings() {
  const list = useResource("/api/v1/delegations");
  const candidates = useResource("/api/v1/delegations/candidates");
  const [message, setMessage] = useState({ kind: "", text: "" });
  const [busy, setBusy] = useState(false);

  async function run(action, success) {
    setBusy(true);
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "success", text: success });
      list.reload();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error && !error.code ? error.message : errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    return run(async () => {
      await command("delegations", delegationBody(values));
      form.reset();
    }, "Đã tạo ủy quyền duyệt.");
  }

  const row = (item, given) => (
    <tr key={item.id}>
      <td data-label={given ? "Người nhận" : "Người ủy quyền"}>{given ? item.delegate_name : item.delegator_name}</td>
      <td data-label="Từ">{date(item.starts_at)}</td>
      <td data-label="Đến">{date(item.ends_at)}</td>
      <td data-label="Trạng thái">{item.revoked_at ? "Đã thu hồi" : delegationActive(item) ? "Đang hiệu lực" : "Chưa/hết hiệu lực"}</td>
      <td data-label="Lý do">{item.reason}</td>
      <td data-label="Thao tác">{given && !item.revoked_at && (
        <button type="button" className="danger" disabled={busy}
          onClick={() => run(() => command(`delegations/${item.id}/revoke`, {}), "Đã thu hồi ủy quyền.")}>Thu hồi</button>
      )}</td>
    </tr>
  );

  return (
    <section className="panel" aria-label="Ủy quyền duyệt">
      <h2>Ủy quyền duyệt</h2>
      <p className="muted">Trong khoảng thời gian ủy quyền, các bước duyệt mới giao cho bạn sẽ chuyển sang người được ủy quyền. Nếu bạn vắng mặt (theo chấm công) mà không ủy quyền, bước duyệt chuyển lên quản lý trực tiếp.</p>
      <form onSubmit={submit} className="form-grid">
        <label>Người nhận ủy quyền
          <select name="delegate_id" required defaultValue="">
            <option value="" disabled>Chọn người duyệt</option>
            {(candidates.data?.items || []).map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
          </select>
        </label>
        <label>Từ<input type="datetime-local" name="starts_at" required /></label>
        <label>Đến<input type="datetime-local" name="ends_at" required /></label>
        <label>Lý do<input name="reason" minLength={5} maxLength={500} required placeholder="Ví dụ: Nghỉ phép năm" /></label>
        <button type="submit" disabled={busy}>Tạo ủy quyền</button>
      </form>
      {message.text && <p role={message.kind === "error" ? "alert" : "status"} className={message.kind}>{message.text}</p>}
      <ResourceState resource={list}>
        {["given", "received"].map((key) => (list.data?.[key] || []).length > 0 && (
          <div className="table-wrap" key={key}>
            <h3>{key === "given" ? "Tôi đã ủy quyền" : "Tôi được ủy quyền"}</h3>
            <table className="responsive-records">
              <thead><tr><th>{key === "given" ? "Người nhận" : "Người ủy quyền"}</th><th>Từ</th><th>Đến</th><th>Trạng thái</th><th>Lý do</th><th></th></tr></thead>
              <tbody>{list.data[key].map((item) => row(item, key === "given"))}</tbody>
            </table>
          </div>
        ))}
      </ResourceState>
    </section>
  );
}

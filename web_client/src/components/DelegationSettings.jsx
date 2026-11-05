import { useState } from "react";
import { date, errorText } from "../domain.js";
import { delegationActive, delegationBody } from "../actionPayload.js";
import { ConfirmDialog, EmptyState } from "./design.jsx";
import { Badge, ResourceState, command, useResource } from "./ui.jsx";

/** Approver hands approval steps to a colleague for a time window. */
export default function DelegationSettings() {
  const list = useResource("/api/v1/delegations");
  const candidates = useResource("/api/v1/delegations/candidates");
  const [message, setMessage] = useState({ kind: "", text: "" });
  const [busy, setBusy] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState(null);

  async function run(action, success) {
    setBusy(true);
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "success", text: success });
      list.reload();
    } catch (error) {
      setMessage({
        kind: "error",
        text:
          error instanceof Error && !error.code ? error.message : errorText(error),
      });
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
    }, "Đã thiết lập ủy quyền phê duyệt thành công.");
  }

  const row = (item, given) => {
    const isActive = !item.revoked_at && delegationActive(item);
    return (
      <tr key={item.id}>
        <td data-label={given ? "Người nhận ủy quyền" : "Người ủy quyền"}>
          <strong>{given ? item.delegate_name : item.delegator_name}</strong>
        </td>
        <td data-label="Hiệu lực từ">{date(item.starts_at)}</td>
        <td data-label="Đến hết">{date(item.ends_at)}</td>
        <td data-label="Trạng thái">
          <Badge
            value={
              item.revoked_at ? "CANCELLED" : isActive ? "ACTIVE" : "WAITING"
            }
          />{" "}
          <small className="muted">
            {item.revoked_at
              ? "Đã thu hồi"
              : isActive
                ? "Đang hiệu lực"
                : "Chưa / hết hiệu lực"}
          </small>
        </td>
        <td data-label="Lý do">{item.reason}</td>
        <td data-label="Thao tác">
          {given && !item.revoked_at && (
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={() => setRevokeTarget(item)}
            >
              Thu hồi
            </button>
          )}
        </td>
      </tr>
    );
  };

  const hasGiven = (list.data?.given || []).length > 0;
  const hasReceived = (list.data?.received || []).length > 0;

  return (
    <section className="panel" aria-label="Ủy quyền duyệt">
      <h2>Ủy quyền phê duyệt khi vắng mặt</h2>
      <p className="muted">
        Trong thời gian ủy quyền có hiệu lực, các hồ sơ mới chuyển đến bước duyệt của bạn sẽ
        được giao cho đồng nghiệp nhận ủy quyền. Nếu bạn đang nghỉ phép hoặc đi công tác đã
        được phê duyệt mà chưa thiết lập ủy quyền, hệ thống tự động chuyển bước duyệt lên cấp
        quản lý trực tiếp.
      </p>
      <form onSubmit={submit} className="form-grid">
        <label>
          Người nhận ủy quyền
          <select name="delegate_id" required defaultValue="">
            <option value="" disabled>
              — Chọn người phê duyệt thay thế —
            </option>
            {(candidates.data?.items || []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Bắt đầu từ
          <input type="datetime-local" name="starts_at" required />
        </label>
        <label>
          Kết thúc lúc
          <input type="datetime-local" name="ends_at" required />
        </label>
        <label>
          Lý do ủy quyền
          <input
            name="reason"
            minLength={5}
            maxLength={500}
            required
            placeholder="Ví dụ: Đi công tác chi nhánh miền Nam / Nghỉ phép năm"
          />
        </label>
        <div className="form-actions" style={{ alignSelf: "end" }}>
          <button type="submit" disabled={busy}>
            Thiết lập ủy quyền
          </button>
        </div>
      </form>
      {message.text && (
        <p role={message.kind === "error" ? "alert" : "status"} className={message.kind}>
          {message.text}
        </p>
      )}
      <ResourceState resource={list}>
        {!hasGiven && !hasReceived && (
          <EmptyState
            title="Chưa có lịch ủy quyền nào"
            description="Bạn có thể tạo lịch ủy quyền trước các chuyến công tác hoặc kỳ nghỉ dài ngày để tránh tồn đọng hồ sơ."
          />
        )}
        {["given", "received"].map(
          (key) =>
            (list.data?.[key] || []).length > 0 && (
              <div className="table-wrap" key={key} style={{ marginTop: "16px" }}>
                <h3>
                  {key === "given"
                    ? "Danh sách tôi đã ủy quyền"
                    : "Danh sách tôi được ủy quyền"}
                </h3>
                <table className="responsive-records">
                  <thead>
                    <tr>
                      <th>{key === "given" ? "Người nhận" : "Người ủy quyền"}</th>
                      <th>Hiệu lực từ</th>
                      <th>Đến hết</th>
                      <th>Trạng thái</th>
                      <th>Lý do</th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data[key].map((item) => row(item, key === "given"))}
                  </tbody>
                </table>
              </div>
            ),
        )}
      </ResourceState>
      {revokeTarget && (
        <ConfirmDialog
          title="Thu hồi ủy quyền phê duyệt?"
          message={`Ủy quyền dành cho ${revokeTarget.delegate_name} sẽ chấm dứt hiệu lực ngay lập tức và các bước duyệt mới sẽ quay trở lại hộp việc của bạn.`}
          warningNote="Lưu ý: Ủy quyền đã thu hồi không thể kích hoạt lại; bạn sẽ cần tạo lượt ủy quyền mới nếu muốn tiếp tục chuyển giao."
          confirmLabel="Xác nhận thu hồi"
          danger
          onClose={() => setRevokeTarget(null)}
          onConfirm={async () => {
            const targetId = revokeTarget.id;
            setRevokeTarget(null);
            await run(
              () => command(`delegations/${targetId}/revoke`, {}),
              "Đã thu hồi ủy quyền phê duyệt.",
            );
          }}
        />
      )}
    </section>
  );
}

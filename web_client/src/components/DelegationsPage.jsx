import { useState } from "react";
import { date, errorText, types } from "../domain.js";

const DISABLED_TEXT = errorText({ message: "DELEGATION_NOT_ENABLED" });
import { ActionForm, Modal, Reason, ResourceState, command, useResource } from "./ui.jsx";
import { EmptyState, PageHeader, PageTabs, useDebounced } from "./design.jsx";

const STATUS_LABELS = { ACTIVE: "Đang hiệu lực", SCHEDULED: "Chưa bắt đầu", EXPIRED: "Đã hết hạn", REVOKED: "Đã thu hồi" };

/** <input type="datetime-local"> value (browser-local) -> ISO with offset. */
export function localInputToIso(value) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString();
}

function toLocalInput(when) {
  const shifted = new Date(when.getTime() - when.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}

function PersonPicker({ name, label }) {
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim(), 300);
  const people = useResource(`/api/v1/delegations/candidates${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  return <>
    <label>Tìm {label.toLowerCase()}<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Họ tên" /></label>
    <label>{label}<select name={name} required defaultValue="" key={q}>
      <option value="" disabled>{people.loading ? "Đang tải…" : "Chọn người có quyền phê duyệt"}</option>
      {(people.data?.items || []).map((p) => <option key={p.id} value={p.id}>{p.display_name}{p.department_name ? ` · ${p.department_name}` : ""}</option>)}
    </select></label>
  </>;
}

function ScopeFields() {
  const org = useResource("/api/v1/meta/org-chart");
  const typeList = useResource("/api/v1/request-types");
  return <div className="form-grid">
    <label>Phạm vi phòng ban<select name="department_id" defaultValue="">
      <option value="">Mọi phòng ban tôi được duyệt</option>
      {(org.data?.departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
    </select></label>
    <label>Phạm vi loại yêu cầu<select name="type_code" defaultValue="">
      <option value="">Mọi loại tôi được duyệt</option>
      {(typeList.data?.items || []).map((t) => <option key={t.code} value={t.code}>{t.name || types[t.code] || t.code}</option>)}
    </select></label>
  </div>;
}

function CreateDelegation({ ops, onClose, onDone }) {
  const now = new Date();
  return <Modal title="Tạo ủy quyền phê duyệt tạm thời" onClose={onClose}>
    <ActionForm submitLabel="Tạo ủy quyền" onSubmit={async (values) => {
      const body = {
        delegate_id: values.delegate_id,
        department_id: values.department_id || null,
        type_code: values.type_code || null,
        valid_from: localInputToIso(values.valid_from),
        valid_to: localInputToIso(values.valid_to),
        reason: values.reason,
      };
      if (ops) body.delegator_id = values.delegator_id;
      if (!body.valid_from || !body.valid_to) throw new Error("Vui lòng nhập đủ thời gian bắt đầu và kết thúc.");
      await command(ops ? "ops/delegations" : "delegations", body);
      onDone();
    }}>
      {ops && <PersonPicker name="delegator_id" label="Người ủy quyền (vắng mặt)" />}
      <PersonPicker name="delegate_id" label="Người được ủy quyền" />
      <div className="form-grid">
        <label>Bắt đầu<input type="datetime-local" name="valid_from" required defaultValue={toLocalInput(now)} /></label>
        <label>Kết thúc<input type="datetime-local" name="valid_to" required defaultValue={toLocalInput(new Date(now.getTime() + 7 * 86400000))} /></label>
      </div>
      <ScopeFields />
      <small className="muted">Người được ủy quyền phải có quyền phê duyệt trong phạm vi đã chọn suốt thời gian ủy quyền. Không được ủy quyền tiếp (không bắc cầu). Ủy quyền áp dụng cho các yêu cầu được gửi trong thời gian hiệu lực; hệ thống vẫn kiểm tra quyền và nguyên tắc không tự duyệt cho từng hồ sơ.</small>
      <Reason />
    </ActionForm>
  </Modal>;
}

function RevokeDelegation({ item, ops, onClose, onDone }) {
  return <Modal title="Thu hồi ủy quyền" onClose={onClose}>
    <ActionForm danger submitLabel="Thu hồi" onSubmit={async (values) => {
      await command(`${ops ? "ops/" : ""}delegations/${item.id}/revoke`, { reason: values.reason });
      onDone();
    }}>
      <p>Thu hồi ủy quyền của <strong>{item.delegator_name}</strong> cho <strong>{item.delegate_name}</strong>. Yêu cầu gửi sau thời điểm này sẽ không chuyển cho người được ủy quyền nữa.</p>
      <Reason />
    </ActionForm>
  </Modal>;
}

/** Time-limited approval delegation. Approvers manage their own; OPS_ADMIN acts for an absent approver. */
export default function DelegationsPage({ ops = false, user }) {
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [revoking, setRevoking] = useState(null);
  const list = useResource(`/api/v1/${ops ? "ops/" : ""}delegations${status ? `?status=${status}` : ""}`);
  const disabled = String(list.error || "").startsWith(DISABLED_TEXT);
  const items = list.data?.items || [];
  const done = () => { setCreating(false); setRevoking(null); list.reload?.(); };
  return <>
    <PageHeader eyebrow={ops ? "VẬN HÀNH" : "CÔNG VIỆC ĐƯỢC GIAO"} title="Ủy quyền phê duyệt"
      description={ops ? "Thiết lập ủy quyền thay cho người phê duyệt vắng mặt; mọi thao tác được ghi nhật ký quản trị." : "Ủy quyền tạm thời cho người khác phê duyệt thay khi bạn vắng mặt."}
      action={!disabled && <button type="button" onClick={() => setCreating(true)}>Tạo ủy quyền</button>} />
    {disabled ? <EmptyState title="Chức năng ủy quyền chưa được bật" description="Cần quản trị cơ sở dữ liệu áp dụng migration 08 và bật EAS_APPROVAL_DELEGATION sau khi được phê duyệt." /> : <>
      <PageTabs label="Lọc trạng thái" value={status} onChange={setStatus}
        tabs={[["", "Tất cả"], ...Object.entries(STATUS_LABELS)]} />
      <ResourceState resource={list}>
        {items.length ? <section className="panel table-panel"><div className="table-wrap"><table className="responsive-records ds-compact-table">
          <thead><tr><th>Người ủy quyền</th><th>Người được ủy quyền</th><th>Phạm vi</th><th>Hiệu lực</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
          <tbody>{items.map((d) => {
            const canRevoke = ["ACTIVE", "SCHEDULED"].includes(d.status) && (ops || d.delegator_id === user?.id);
            return <tr key={d.id}>
              <td data-label="Người ủy quyền">{d.delegator_name}</td>
              <td data-label="Người được ủy quyền">{d.delegate_name}</td>
              <td data-label="Phạm vi">{d.department_name || "Mọi phòng ban"} · {d.type_name || "Mọi loại"}</td>
              <td data-label="Hiệu lực">{date(d.valid_from)} → {date(d.valid_to)}</td>
              <td data-label="Trạng thái"><span className={`badge delegation-${d.status.toLowerCase()}`}>{STATUS_LABELS[d.status]}</span></td>
              <td data-label="Thao tác">{canRevoke ? <button type="button" className="secondary" onClick={() => setRevoking(d)}>Thu hồi</button> : <span className="muted">—</span>}</td>
            </tr>;
          })}</tbody>
        </table></div></section> : <EmptyState title="Chưa có ủy quyền" description="Các ủy quyền bạn tạo hoặc được nhận sẽ hiển thị tại đây." />}
      </ResourceState>
    </>}
    {creating && <CreateDelegation ops={ops} onClose={() => setCreating(false)} onDone={done} />}
    {revoking && <RevokeDelegation item={revoking} ops={ops} onClose={() => setRevoking(null)} onDone={done} />}
  </>;
}

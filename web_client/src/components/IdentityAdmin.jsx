import { useState } from "react";
import { PasswordField, PageControls } from "./ux.jsx";
import { roles, date } from "../domain.js";
import {
  ActionForm,
  Data,
  Modal,
  Reason,
  ResourceState,
  command,
  useResource,
} from "./ui.jsx";
const entities = {
  users: "Người dùng",
  departments: "Phòng ban",
  memberships: "Phân quyền",
  "request-types": "Loại yêu cầu",
};
function UuidInput({ name, label, value, nullable = false }) {
  return (
    <label>
      {label}
      <input
        name={name}
        defaultValue={value || ""}
        required={!nullable}
        pattern="[0-9a-fA-F-]{36}"
        placeholder={nullable ? "Không bắt buộc" : "UUID"}
      />
    </label>
  );
}
function Editor({ kind, record }) {
  if (kind === "users")
    return (
      <>
        <div className="form-grid">
          <label>
            Tên đăng nhập
            <input
              name="username"
              defaultValue={record?.username || ""}
              required
              maxLength={150}
            />
          </label>
          <label>
            Họ tên
            <input
              name="display_name"
              defaultValue={record?.display_name || ""}
              required
              maxLength={150}
            />
          </label>
          <UuidInput
            name="department_id"
            label="ID phòng ban"
            value={record?.department_id}
          />
          <UuidInput
            name="manager_id"
            label="ID quản lý trực tiếp"
            value={record?.manager_id}
            nullable
          />
        </div>
        <PasswordField label={record ? "Mật khẩu tạm mới (bỏ trống nếu không đổi)" : "Mật khẩu tạm"}
          name="password" autoComplete="new-password" required={!record} minLength={12} maxLength={128} />
        <p className="muted">
          12–128 ký tự; gồm chữ hoa, chữ thường, số và ký tự đặc biệt; không
          chứa tên đăng nhập. Người dùng phải đổi mật khẩu khi đăng nhập.
        </p>
        <Active value={record?.is_active ?? true} />
      </>
    );
  if (kind === "departments")
    return (
      <>
        <label>
          Mã phòng ban
          <input
            name="code"
            defaultValue={record?.code || ""}
            required
            maxLength={50}
          />
        </label>
        <label>
          Tên phòng ban
          <input
            name="name"
            defaultValue={record?.name || ""}
            required
            maxLength={150}
          />
        </label>
        <UuidInput
          name="parent_id"
          label="ID phòng ban cha"
          value={record?.parent_id}
          nullable
        />
        <Active value={record?.is_active ?? true} />
      </>
    );
  if (kind === "memberships")
    return (
      <>
        <UuidInput
          name="user_id"
          label="ID người được cấp quyền"
          value={record?.user_id}
        />
        <label>
          Vai trò
          <select name="role" defaultValue={record?.role || "REQUESTER"}>
            {Object.entries(roles).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Phạm vi tổ chức
          <select
            name="scope_kind"
            defaultValue={record?.scope_kind || "DEPARTMENT"}
          >
            <option value="DEPARTMENT">Theo phòng ban</option>
            <option value="GLOBAL">Toàn hệ thống</option>
          </select>
        </label>
        <UuidInput
          name="department_id"
          label="ID phòng ban (bỏ trống khi toàn hệ thống)"
          value={record?.department_id}
          nullable
        />
        <label>
          Phạm vi loại yêu cầu
          <select name="type_scope" defaultValue={record?.type_scope || "ALL"}>
            <option value="ALL">Tất cả loại</option>
            <option value="ONE">Một loại</option>
          </select>
        </label>
        <UuidInput
          name="type_id"
          label="ID loại yêu cầu (bỏ trống khi tất cả)"
          value={record?.type_id}
          nullable
        />
        <label>
          Hiệu lực từ (ISO 8601, có múi giờ)
          <input
            name="valid_from"
            defaultValue={record?.valid_from || new Date().toISOString()}
            required
          />
        </label>
        <label>
          Hiệu lực đến (không bắt buộc)
          <input
            name="valid_to"
            defaultValue={record?.valid_to || ""}
            placeholder="2027-01-01T00:00:00+07:00"
          />
        </label>
      </>
    );
  return (
    <>
      <p>
        {record?.code} · Luồng {record?.lifecycle}
      </p>
      <Active value={record?.is_active ?? true} />
      <p className="muted">
        Ba loại LEAVE, ACCESS, EQUIPMENT có hợp đồng dữ liệu riêng. Cấu hình quy
        trình được quản lý tại menu Cấu hình quy trình.
      </p>
    </>
  );
}
function Active({ value }) {
  return (
    <label>
      Trạng thái
      <select name="is_active" defaultValue={String(value)}>
        <option value="true">Hoạt động</option>
        <option value="false">Ngừng hoạt động</option>
      </select>
    </label>
  );
}
export default function IdentityAdmin() {
  const [kind, setKind] = useState("users"),
    [offset, setOffset] = useState(0),
    [limit, setLimit] = useState(20),
    [modal, setModal] = useState(null),
    [notice, setNotice] = useState("");
  const r = useResource(`/api/v1/admin/${kind}?limit=${limit}&offset=${offset}`);
  async function save(v) {
    const body = { ...v };
    if ("is_active" in body) body.is_active = body.is_active === "true";
    if (!body.password) delete body.password;
    if (modal.record) body.expected_revision = modal.record.revision;
    await command(
      `admin/${kind}${modal.record ? "/" + modal.record.id : ""}`,
      body,
      modal.record ? "PATCH" : "POST",
    );
    setModal(null);
    setNotice("Đã lưu thay đổi và ghi nhật ký.");
    r.reload();
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">QUẢN TRỊ TỔ CHỨC</p>
          <h1>Danh tính & phân quyền</h1>
          <p className="muted">
            Dành cho Ops Admin toàn hệ thống, phạm vi tất cả loại yêu cầu.
          </p>
        </div>
        {kind !== "request-types" && (
          <button onClick={() => setModal({ mode: "edit", record: null })}>
            + Thêm mới
          </button>
        )}
      </div>
      <div className="tabs">
        {Object.entries(entities).map(([k, v]) => (
          <button
            className={kind === k ? "active" : "secondary"}
            key={k}
            onClick={() => {
              setKind(k);
              setOffset(0);
              setModal(null);
              setNotice("");
            }}
          >
            {v}
          </button>
        ))}
      </div>
      {notice && (
        <p className="success" role="status">
          {notice}
        </p>
      )}
      <section className="panel" id="identity-results">
        <ResourceState resource={r}>
          <div className="table-wrap">
            <table className="responsive-records">
              <thead>
                <tr>
                  <th>Thông tin</th>
                  <th>ID tham chiếu</th>
                  <th>Trạng thái</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {r.data?.items?.map((item) => (
                  <tr key={item.id}>
                    <td data-label="Thông tin">
                      <strong>
                        {item.display_name ||
                          item.name ||
                          item.code ||
                          roles[item.role]}
                      </strong>
                      <small className="block">
                        {item.username || item.user_id || ""}
                      </small>
                    </td>
                    <td data-label="ID tham chiếu">
                      <code>{item.id}</code>
                    </td>
                    <td data-label="Trạng thái">
                      {kind === "memberships"
                        ? item.revoked_at
                          ? "Đã thu hồi"
                          : item.valid_to &&
                              new Date(item.valid_to) <= new Date()
                            ? "Hết hiệu lực"
                            : new Date(item.valid_from) > new Date()
                              ? "Chưa hiệu lực"
                              : "Đang hiệu lực"
                        : item.is_active
                          ? "Hoạt động"
                          : "Ngừng hoạt động"}
                    </td>
                    <td data-label="Thao tác">
                      <div className="actions">
                        <button
                          className="secondary"
                          onClick={() =>
                            setModal({ mode: "view", record: item })
                          }
                        >
                          Xem
                        </button>
                        <button
                          className="secondary"
                          disabled={!!item.revoked_at}
                          onClick={() =>
                            setModal({ mode: "edit", record: item })
                          }
                        >
                          Sửa
                        </button>
                        <button
                          className="danger"
                          disabled={
                            kind === "memberships"
                              ? !!item.revoked_at
                              : !item.is_active
                          }
                          onClick={() =>
                            setModal({ mode: "delete", record: item })
                          }
                        >
                          {kind === "memberships" ? "Thu hồi" : "Vô hiệu hóa"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!r.data?.items?.length && <p className="empty">Chưa có dữ liệu.</p>}
          <PageControls offset={offset} limit={limit} nextOffset={r.data?.next_offset}
            count={r.data?.items?.length || 0} title="bản ghi"
            targetId="identity-results" onPage={setOffset} onLimit={setLimit} />
        </ResourceState>
      </section>
      {modal && (
        <Modal
          title={`${entities[kind]} · ${modal.mode === "view" ? "Chi tiết" : modal.mode === "delete" ? "Xác nhận ngừng sử dụng" : modal.record ? "Cập nhật" : "Thêm mới"}`}
          onClose={() => setModal(null)}
        >
          {modal.mode === "view" ? (
            <>
              <Data value={modal.record} />
              {modal.record.valid_to && (
                <p>Hết hạn: {date(modal.record.valid_to)}</p>
              )}
            </>
          ) : (
            <ActionForm
              onSubmit={
                modal.mode === "delete"
                  ? async (v) => {
                      await command(
                        `admin/${kind}/${modal.record.id}`,
                        {
                          reason: v.reason,
                          expected_revision: modal.record.revision,
                        },
                        "DELETE",
                      );
                      setModal(null);
                      setNotice(
                        "Đã ngừng sử dụng. Dữ liệu lịch sử được giữ lại.",
                      );
                      r.reload();
                    }
                  : save
              }
              danger={modal.mode === "delete"}
            >
              {modal.mode === "delete" ? (
                <p>
                  Thao tác này giữ lịch sử. Thay đổi tài khoản hoặc quyền sẽ làm
                  phiên đăng nhập cũ của người liên quan hết hiệu lực.
                </p>
              ) : (
                <Editor kind={kind} record={modal.record} />
              )}
              <Reason />
            </ActionForm>
          )}
        </Modal>
      )}
    </>
  );
}

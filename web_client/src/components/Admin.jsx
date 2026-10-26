import { useEffect, useState } from "react";
import { PasswordField, PageControls, useLocalPagination } from "./ux.jsx";
import { api } from "../api.js";
import { date, types } from "../domain.js";
import {
  ActionForm,
  Badge,
  Data,
  Modal,
  Reason,
  ResourceState,
  command,
  useResource,
} from "./ui.jsx";
export function Policy() {
  const resource = useResource("/api/v1/config-releases"),
    [selected, setSelected] = useState(null),
    [validation, setValidation] = useState(null),
    [modal, setModal] = useState(null);
  async function open(id) {
    setSelected((await api(`/api/v1/config-releases/${id}`)).release);
    setValidation(null);
  }
  const policies = useLocalPagination(10);
  useEffect(() => {
    if (selected) document.getElementById("policy-editor")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selected]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">POLICY ADMIN</p>
          <h1>Phiên bản cấu hình</h1>
          <p className="muted">
            Soạn thảo, kiểm tra và công bố quy trình nghiệp vụ.
          </p>
        </div>
        <button onClick={() => setModal("create")}>＋ Tạo bản nháp</button>
      </div>
      <section className="panel">
        <ResourceState resource={resource}>
          <div className="table-wrap">
            <table className="responsive-records">
              <thead>
                <tr>
                  <th>Loại yêu cầu</th>
                  <th>Phiên bản</th>
                  <th>Trạng thái</th>
                  <th>Công bố</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {policies.slice(resource.data?.items || []).map((r) => (
                  <tr key={r.id}>
                    <td data-label="Loại yêu cầu">{types[r.type_code]}</td>
                    <td data-label="Phiên bản">v{r.version}</td>
                    <td data-label="Trạng thái"><Badge value={r.state} /></td>
                    <td data-label="Công bố">{date(r.published_at)}</td>
                    <td data-label="Thao tác">
                      <ActionForm
                        onSubmit={() => open(r.id)}
                        submitLabel="Mở cấu hình"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!resource.data?.items?.length && (
            <p className="empty">Chưa có phiên bản cấu hình.</p>
          )}
          <PageControls offset={policies.offset} limit={policies.pageSize}
            count={policies.slice(resource.data?.items || []).length} title="phiên bản"
            nextOffset={policies.nextOffset(resource.data?.items || [])}
            onPage={policies.setOffset} onLimit={policies.setPageSize} />
        </ResourceState>
      </section>
      {selected && (
        <section
          id="policy-editor"
          className="panel"
          key={selected.id + ":" + selected.lock_version}
        >
          <div className="section-head">
            <h2>
              {types[selected.type_code]} · v{selected.version}
            </h2>
            <Badge value={selected.state} />
          </div>
          <ActionForm
            submitLabel={
              selected.state === "DRAFT"
                ? "Lưu bản nháp"
                : "Sao chép thành bản nháp"
            }
            onSubmit={async (values) => {
              if (selected.state === "PUBLISHED") {
                await command("config-releases", {
                  type_code: selected.type_code,
                  clone_from_release_id: selected.id,
                });
                setSelected(null);
              } else {
                const body = { expected_version: selected.lock_version };
                for (const key of [
                  "form_schema",
                  "route_rules",
                  "actor_bindings",
                  "sla_profile",
                ])
                  body[key] = JSON.parse(values[key]);
                await command(`config-releases/${selected.id}`, body, "PATCH");
                await open(selected.id);
              }
              resource.reload();
            }}
          >
            {[
              "form_schema",
              "route_rules",
              "actor_bindings",
              "sla_profile",
            ].map((key, i) => (
              <label key={key}>
                {
                  [
                    "Biểu mẫu",
                    "Quy tắc định tuyến",
                    "Phân công vai trò",
                    "Thời hạn SLA",
                  ][i]
                }
                <textarea
                  className="code"
                  name={key}
                  rows={7}
                  readOnly={selected.state !== "DRAFT"}
                  defaultValue={JSON.stringify(selected[key], null, 2)}
                />
              </label>
            ))}
          </ActionForm>
          {selected.state === "DRAFT" && (
            <div className="actions">
              <ActionForm
                submitLabel="Kiểm tra cấu hình"
                onSubmit={async () =>
                  setValidation(
                    await command(`config-releases/${selected.id}/validate`),
                  )
                }
              />
              <button
                disabled={!validation?.valid}
                onClick={() => setModal("publish")}
              >
                Công bố phiên bản
              </button>
            </div>
          )}
          {validation && (
            <p className="success">
              Cấu hình hợp lệ. Phiên bản đã sẵn sàng để công bố.
            </p>
          )}
        </section>
      )}
      {modal && (
        <Modal
          title={
            modal === "create" ? "Tạo phiên bản nháp" : "Công bố phiên bản"
          }
          onClose={() => setModal(null)}
        >
          <ActionForm
            onSubmit={async (values) => {
              if (modal === "create") await command("config-releases", values);
              else
                await command(`config-releases/${selected.id}/publish`, {
                  expected_version: selected.lock_version,
                  validation_hash: validation.validation_hash,
                  reason: values.reason,
                });
              setModal(null);
              setSelected(null);
              setValidation(null);
              resource.reload();
            }}
          >
            {modal === "create" ? (
              <label>
                Loại yêu cầu
                <select name="type_code">
                  {Object.entries(types).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <>
                <p>
                  Bản đã công bố được giữ nguyên. Các chỉnh sửa tiếp theo cần
                  phiên bản mới.
                </p>
                <Reason />
              </>
            )}
          </ActionForm>
        </Modal>
      )}
    </>
  );
}
export function Operations({ items, onRefresh }) {
  const [selected, setSelected] = useState(null),
    [target, setTarget] = useState("EXECUTOR");
  return (
    <>
      <div className="panel">
        <h2>Điều phối công việc</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mã yêu cầu</th>
                <th>Trạng thái</th>
                <th>Hạn xử lý</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td data-label="Mã yêu cầu">{r.code}</td>
                  <td data-label="Trạng thái">
                    <Badge value={r.status} />
                  </td>
                  <td data-label="Hạn xử lý">
                    {date(r.sla?.due_at)}{" "}
                    {r.sla?.breached_at && (
                      <span className="badge REJECTED">Quá hạn</span>
                    )}
                  </td>
                  <td data-label="Thao tác">
                    <button
                      className="secondary"
                      disabled={[
                        "COMPLETED",
                        "CANCELLED",
                        "REJECTED",
                        "DRAFT",
                      ].includes(r.status)}
                      onClick={() => {
                        setSelected(r);
                        setTarget(
                          r.active_step
                            ? "APPROVAL_STEP"
                            : r.current_attempt
                              ? "EXECUTOR"
                              : "ACCEPTOR",
                        );
                      }}
                    >
                      Điều chuyển
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <section className="panel">
        <h2>Thử lại sự kiện gửi thông báo</h2>
        <p className="muted">
          Chỉ áp dụng sự kiện DEAD đã được xác định trong vận hành.
        </p>
        <ActionForm
          submitLabel="Gửi xử lý lại"
          onSubmit={async (values) => {
            await command(`ops/outbox/${values.event_id}/replay`, {
              reason: values.reason,
            });
            onRefresh();
          }}
        >
          <label>
            ID sự kiện
            <input name="event_id" required pattern="[0-9a-fA-F-]{36}" />
          </label>
          <Reason />
        </ActionForm>
      </section>
      {selected && (
        <Modal
          title={"Điều chuyển " + selected.code}
          onClose={() => setSelected(null)}
        >
          <ActionForm
            onSubmit={async (values) => {
              await command(`requests/${selected.id}/reassign`, {
                target_kind: target,
                target_id: values.target_id,
                new_user_id: values.new_user_id,
                reason: values.reason,
                expected_version: selected.lock_version,
              });
              setSelected(null);
              onRefresh();
            }}
          >
            <label>
              Vị trí xử lý
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="APPROVAL_STEP">Người phê duyệt</option>
                <option value="EXECUTOR">Người thực hiện</option>
                <option value="ACCEPTOR">Người nghiệm thu</option>
                <option value="PLANNED_EXECUTOR">
                  Người thực hiện dự kiến
                </option>
              </select>
            </label>
            <label>
              ID đối tượng được điều chuyển
              <input
                key={target}
                name="target_id"
                defaultValue={
                  target === "APPROVAL_STEP"
                    ? selected.active_step?.id
                    : target === "EXECUTOR"
                      ? selected.current_attempt?.id
                      : selected.id
                }
                required
                pattern="[0-9a-fA-F-]{36}"
              />
            </label>
            <label>
              ID người nhận mới
              <input name="new_user_id" required pattern="[0-9a-fA-F-]{36}" />
            </label>
            <Reason />
          </ActionForm>
        </Modal>
      )}
    </>
  );
}
export function Notifications({ onOpen }) {
  const [offset, setOffset] = useState(0),
    [limit, setLimit] = useState(20),
    [unread, setUnread] = useState(false);
  const r = useResource(
    `/api/v1/notifications?limit=${limit}&offset=${offset}&unread=${unread}`,
  );
  return (
    <section className="panel">
      <div className="section-head">
        <h2>Trung tâm thông báo</h2>
        <label className="inline">
          <input
            type="checkbox"
            checked={unread}
            onChange={(e) => {
              setUnread(e.target.checked);
              setOffset(0);
            }}
          />{" "}
          Chỉ chưa đọc
        </label>
      </div>
      <ResourceState resource={r}>
        {r.data?.items?.map((n) => (
          <article className="notification" key={n.id}>
            <div>
              <strong>{n.label}</strong>
              <p className="muted">
                {date(n.created_at)} · {n.read_at ? "Đã đọc" : "Chưa đọc"}
              </p>
            </div>
            <div className="actions">
              {n.request_id && (
                <button
                  className="secondary"
                  onClick={() => onOpen(n.request_id)}
                >
                  Mở hồ sơ
                </button>
              )}
              {!n.read_at && (
                <ActionForm
                  submitLabel="Đánh dấu đã đọc"
                  onSubmit={async () => {
                    await api(`/api/v1/notifications/${n.id}/read`, {
                      method: "POST",
                    });
                    r.reload();
                  }}
                />
              )}
            </div>
          </article>
        ))}
        {!r.data?.items?.length && <p className="empty">Không có thông báo.</p>}
        <PageControls offset={offset} limit={limit} nextOffset={r.data?.next_offset}
          count={r.data?.items?.length || 0} title="thông báo"
          onPage={setOffset} onLimit={setLimit} />
      </ResourceState>
    </section>
  );
}
export function AdminEvents() {
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const r = useResource(`/api/v1/admin-events?limit=${limit}&offset=${offset}`);
  return (
    <section className="panel">
      <h2>Nhật ký quản trị</h2>
      <ResourceState resource={r}>
        <Data value={r.data?.items} />
        <PageControls offset={offset} limit={limit} nextOffset={r.data?.next_offset}
          count={r.data?.items?.length || 0} title="sự kiện" onPage={setOffset} onLimit={setLimit} />
      </ResourceState>
    </section>
  );
}
export function Profile({ user, onChanged }) {
  const [done, setDone] = useState(false);
  return (
    <section className="panel">
      <h2>Hồ sơ cá nhân</h2>
      <p>{user.display_name}</p>
      <p className="muted">
        {user.username} · {user.department_id}
      </p>
      <h2>Đổi mật khẩu</h2>
      <ActionForm
        submitLabel="Đổi mật khẩu"
        onSubmit={async (v) => {
          if (v.new_password !== v.confirm_password)
            throw new Error("Mật khẩu xác nhận không khớp.");
          const pwd = v.new_password;
          if (pwd.length < 12 || pwd.length > 128 || !/[a-z]/.test(pwd) ||
            !/[A-Z]/.test(pwd) || !/[0-9]/.test(pwd) || !/[^\p{L}\p{N}]/u.test(pwd) ||
            (user.username && pwd.toLowerCase().includes(user.username.toLowerCase())))
            throw new Error("Mật khẩu chưa đạt chính sách: 12–128 ký tự, có chữ hoa, thường, số, ký tự đặc biệt và không chứa username.");
          await api("/api/v1/auth/password", {
            method: "POST",
            body: JSON.stringify({
              current_password: v.current_password,
              new_password: v.new_password,
            }),
          });
          setDone(true);
          if (onChanged) await onChanged();
        }}
      >
        <PasswordField label="Mật khẩu hiện tại" name="current_password" autoComplete="current-password" required />
        <PasswordField label="Mật khẩu mới" name="new_password" autoComplete="new-password" minLength={12} maxLength={128} required
          help="12–128 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt; không chứa tên đăng nhập." />
        <PasswordField label="Xác nhận mật khẩu" name="confirm_password" autoComplete="new-password" required />
      </ActionForm>
      {done && <p className="success">Đã đổi mật khẩu.</p>}
    </section>
  );
}

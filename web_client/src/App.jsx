import { useEffect, useRef, useState } from "react";
import { api, idempotencyKey, initializeCsrf } from "./api.js";

const fields = {
  LEAVE: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["start_date", "Ngày bắt đầu", "date"],
    ["end_date", "Ngày kết thúc", "date"],
    ["handover_user_id", "ID người bàn giao", "text"],
  ],
  ACCESS: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["app_code", "Mã ứng dụng", "text"],
    ["requested_role", "Quyền yêu cầu", "text"],
    ["duration_days", "Số ngày", "number"],
    ["purpose", "Mục đích", "textarea"],
  ],
  EQUIPMENT: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["item_name", "Thiết bị", "text"],
    ["quantity", "Số lượng", "number"],
    ["amount_vnd", "Giá trị VND", "number"],
    ["specs", "Cấu hình", "textarea"],
    ["location", "Nơi sử dụng", "text"],
  ],
};

function Login({ onLogin }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await initializeCsrf();
      await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(form)),
      });
      onLogin();
    } catch (reason) {
      setError(reason.message === "INVALID_CREDENTIALS" ? "Thông tin đăng nhập không hợp lệ." : "Không thể đăng nhập lúc này.");
    } finally {
      setBusy(false);
    }
  }
  return <main id="main" className="auth-shell">
    <form className="panel auth-card" onSubmit={submit}>
      <p className="eyebrow">Enterprise Approval System</p>
      <h1>Đăng nhập</h1>
      <label htmlFor="username">Tên đăng nhập</label>
      <input id="username" name="username" autoComplete="username" required />
      <label htmlFor="password">Mật khẩu</label>
      <input id="password" name="password" type="password" autoComplete="current-password" required />
      {error && <p className="error" role="alert">{error}</p>}
      <button disabled={busy}>{busy ? "Đang xác thực…" : "Đăng nhập"}</button>
    </form>
  </main>;
}

function RequestForm({ onCreated }) {
  const [type, setType] = useState("LEAVE");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const errorRef = useRef(null);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const values = Object.fromEntries(new FormData(event.currentTarget));
    delete values.type_code;
    for (const [name, , kind] of fields[type]) {
      if (kind === "number") {
        values[name] = Number(values[name]);
      }
    }
    try {
      const draft = await api("/api/v1/request-drafts", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ type_code: type }),
      });
      const request = draft.request;
      const file = event.currentTarget.elements.attachment?.files?.[0];
      const attachmentIds = [];
      if (file) {
        const upload = new FormData();
        upload.append("file", file);
        const uploaded = await api(`/api/v1/request-drafts/${request.id}/attachments`, { method: "POST", body: upload });
        attachmentIds.push(uploaded.attachment.id);
      }
      if (type === "EQUIPMENT" && attachmentIds.length === 0) throw new Error("EQUIPMENT_QUOTE_REQUIRED");
      await api("/api/v1/requests/submit", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ request_id: request.id, expected_version: 0, type_code: type, payload: values, attachment_ids: attachmentIds }),
      });
      event.currentTarget.reset();
      setMessage("Đã gửi yêu cầu thành công.");
      onCreated();
    } catch (reason) {
      setMessage(reason.message === "EQUIPMENT_QUOTE_REQUIRED" ? "Yêu cầu thiết bị bắt buộc có báo giá PDF/JPG/PNG sạch." : `Không thể gửi: ${reason.message}`);
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel" aria-labelledby="new-request-title">
    <h2 id="new-request-title">Tạo yêu cầu</h2>
    <form onSubmit={submit}>
      <label htmlFor="type_code">Loại yêu cầu</label>
      <select id="type_code" name="type_code" value={type} onChange={(event) => setType(event.target.value)}>
        <option value="LEAVE">Nghỉ phép</option>
        <option value="ACCESS">Cấp quyền</option>
        <option value="EQUIPMENT">Thiết bị</option>
      </select>
      <div className="form-grid">
        {fields[type].map(([name, label, kind]) => <div key={name} className={kind === "textarea" ? "wide" : ""}>
          <label htmlFor={name}>{label}</label>
          {kind === "textarea" ? <textarea id={name} name={name} required rows="3" /> : <input id={name} name={name} type={kind} required />}
        </div>)}
      </div>
      {type === "EQUIPMENT" && <><label htmlFor="attachment">Báo giá</label><input id="attachment" name="attachment" type="file" accept="application/pdf,image/jpeg,image/png" required /></>}
      {message && <p ref={errorRef} tabIndex="-1" aria-live="assertive">{message}</p>}
      <button disabled={busy}>{busy ? "Đang xử lý…" : "Gửi phê duyệt"}</button>
    </form>
  </section>;
}

function Dashboard({ user, onLogout }) {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState("");
  async function refresh() {
    setStatus("Đang tải danh sách…");
    try {
      const result = await api("/api/v1/requests?limit=50");
      setItems(result.items);
      setStatus(result.items.length ? "" : "Chưa có yêu cầu nào.");
    } catch (reason) { setStatus(`Không thể tải danh sách: ${reason.message}`); }
  }
  useEffect(() => {
    let active = true;
    api("/api/v1/requests?limit=50")
      .then((result) => {
        if (!active) return;
        setItems(result.items);
        setStatus(result.items.length ? "" : "Chưa có yêu cầu nào.");
      })
      .catch((reason) => {
        if (active) setStatus(`Không thể tải danh sách: ${reason.message}`);
      });
    return () => { active = false; };
  }, []);
  async function open(id) {
    try { setSelected((await api(`/api/v1/requests/${id}`)).request); }
    catch (reason) { setStatus(`Không thể mở yêu cầu: ${reason.message}`); }
  }
  async function decide(outcome) {
    const reason = outcome === "APPROVE" ? null : window.prompt("Nhập lý do (10–2000 ký tự):");
    if (outcome !== "APPROVE" && (!reason || reason.trim().length < 10)) return;
    try {
      await api(`/api/v1/requests/${selected.id}/approval-decisions`, {
        method: "POST", headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ outcome, reason, expected_version: selected.lock_version }),
      });
      setSelected(null); await refresh();
    } catch (error) { setStatus(`Không thể quyết định: ${error.message}`); }
  }
  async function startExecution() {
    try {
      await api(`/api/v1/requests/${selected.id}/execution/start`, {
        method: "POST", headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ expected_version: selected.lock_version }),
      });
      await open(selected.id); await refresh();
    } catch (error) { setStatus(`Không thể bắt đầu thực hiện: ${error.message}`); }
  }
  async function submitExecution(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("evidence");
    try {
      const upload = new FormData(); upload.append("file", file);
      await api(`/api/v1/requests/${selected.id}/execution/attachments`, { method: "POST", body: upload });
      await api(`/api/v1/requests/${selected.id}/execution/submit`, {
        method: "POST", headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ expected_version: selected.lock_version, result_note: form.get("result_note"), external_reference: form.get("external_reference") }),
      });
      await open(selected.id); await refresh();
    } catch (error) { setStatus(`Không thể nộp kết quả: ${error.message}`); }
  }
  async function decideAcceptance(outcome) {
    const reason = outcome === "ACCEPT" ? null : window.prompt("Nêu lý do yêu cầu làm lại (10–2000 ký tự):");
    if (outcome === "REWORK" && (!reason || reason.trim().length < 10)) return;
    try {
      await api(`/api/v1/requests/${selected.id}/acceptance-decisions`, {
        method: "POST", headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ outcome, reason, expected_version: selected.lock_version }),
      });
      await open(selected.id); await refresh();
    } catch (error) { setStatus(`Không thể nghiệm thu: ${error.message}`); }
  }
  async function cancelRequest() {
    const reason = window.prompt("Nêu lý do hủy yêu cầu (10–2000 ký tự):");
    if (!reason || reason.trim().length < 10) return;
    try {
      await api(`/api/v1/requests/${selected.id}/cancel`, {
        method: "POST", headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ reason, expected_version: selected.lock_version }),
      });
      setSelected(null); await refresh();
    } catch (error) { setStatus(`Không thể hủy yêu cầu: ${error.message}`); }
  }
  return <>
    <header><div><p className="eyebrow">Enterprise Approval System</p><strong>{user.display_name}</strong></div><button className="secondary" onClick={onLogout}>Đăng xuất</button></header>
    <main id="main" className="layout">
      {user.roles.includes("REQUESTER") && <RequestForm onCreated={refresh} />}
      <section className="panel" aria-labelledby="request-list-title">
        <div className="section-head"><h2 id="request-list-title">Yêu cầu của tôi</h2><button className="secondary" onClick={refresh}>Làm mới</button></div>
        <p aria-live="polite">{status}</p>
        <div className="table-wrap"><table><thead><tr><th>Mã</th><th>Loại</th><th>Trạng thái</th><th></th></tr></thead><tbody>
          {items.map((item) => <tr key={item.id}><td>{item.code}</td><td>{item.type_code}</td><td><span className="status">{item.status}</span></td><td><button className="link" onClick={() => open(item.id)}>Chi tiết</button></td></tr>)}
        </tbody></table></div>
      </section>
      {selected && <section className="panel wide-panel" aria-labelledby="detail-title"><div className="section-head"><h2 id="detail-title">{selected.code}</h2><button className="secondary" onClick={() => setSelected(null)}>Đóng</button></div>
        <pre>{JSON.stringify(selected.payload, null, 2)}</pre>
        <ol>{selected.approval_steps.map((step) => <li key={step.step_no}>Cấp {step.step_no}: {step.state}</li>)}</ol>
        {user.roles.includes("APPROVER") && selected.status === "PENDING_APPROVAL" && selected.approval_steps.some((step) => step.state === "ACTIVE" && step.assignee_id === user.id) && <div className="actions"><button onClick={() => decide("APPROVE")}>Duyệt</button><button className="danger" onClick={() => decide("REJECT")}>Từ chối</button><button className="secondary" onClick={() => decide("NEEDS_INFO")}>Yêu cầu bổ sung</button></div>}
        {user.roles.includes("EXECUTOR") && selected.status === "READY_FOR_EXECUTION" && selected.workflow?.attempt?.executor_id === user.id && <button onClick={startExecution}>Bắt đầu thực hiện</button>}
        {user.roles.includes("EXECUTOR") && selected.status === "IN_PROGRESS" && selected.workflow?.attempt?.executor_id === user.id && <form onSubmit={submitExecution} className="execution-form"><h3>Nộp kết quả thực hiện</h3><label htmlFor="result_note">Mô tả kết quả</label><textarea id="result_note" name="result_note" minLength="10" maxLength="4000" required /><label htmlFor="external_reference">Mã tham chiếu</label><input id="external_reference" name="external_reference" maxLength="200" required /><label htmlFor="evidence">Bằng chứng</label><input id="evidence" name="evidence" type="file" accept="application/pdf,image/jpeg,image/png" required /><button>Nộp kết quả</button></form>}
        {user.roles.includes("ACCEPTOR") && selected.status === "WAITING_FOR_ACCEPTANCE" && selected.workflow?.acceptor_id === user.id && <div className="actions"><button onClick={() => decideAcceptance("ACCEPT")}>Nghiệm thu</button><button className="danger" onClick={() => decideAcceptance("REWORK")}>Yêu cầu làm lại</button></div>}
        {selected.requester_id === user.id && ["DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"].includes(selected.status) && <button className="danger" onClick={cancelRequest}>Hủy yêu cầu</button>}
      </section>}
    </main>
  </>;
}

export default function App() {
  const [user, setUser] = useState(undefined);
  async function load() {
    try { setUser((await api("/api/v1/auth/me")).user); }
    catch { setUser(null); }
  }
  useEffect(() => { initializeCsrf().then(load).catch(() => setUser(null)); }, []);
  async function logout() { await api("/api/v1/auth/logout", { method: "POST", body: JSON.stringify({}) }); setUser(null); }
  if (user === undefined) return <main id="main" className="loading" aria-live="polite">Đang khởi tạo…</main>;
  return user ? <Dashboard user={user} onLogout={logout} /> : <Login onLogin={load} />;
}

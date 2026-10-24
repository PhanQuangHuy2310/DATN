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
      setError(
        reason.message === "INVALID_CREDENTIALS"
          ? "Thông tin đăng nhập không hợp lệ."
          : "Không thể đăng nhập lúc này."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="auth-shell">
      <form className="panel auth-card" onSubmit={submit}>
        <p className="eyebrow">Enterprise Approval System</p>
        <h1>Đăng nhập</h1>
        <label htmlFor="username">Tên đăng nhập</label>
        <input id="username" name="username" autoComplete="username" required />
        <label htmlFor="password">Mật khẩu</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button disabled={busy}>
          {busy ? "Đang xác thực…" : "Đăng nhập"}
        </button>
      </form>
    </main>
  );
}

function RequestForm({ onCreated }) {
  const [type, setType] = useState("LEAVE");
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [aiClassifyResult, setAiClassifyResult] = useState(null);
  const [aiRiskResult, setAiRiskResult] = useState(null);
  const errorRef = useRef(null);

  async function handleAiClassify() {
    const titleInput = document.getElementById("title")?.value || "";
    const reasonInput = document.getElementById("reason")?.value || "";
    if (!titleInput.trim()) {
      setMessage("Vui lòng nhập tiêu đề trước khi yêu cầu AI gợi ý.");
      return;
    }
    setAiBusy(true);
    try {
      const res = await api("/api/v1/ai/classify", {
        method: "POST",
        body: JSON.stringify({ title: titleInput, description: reasonInput }),
      });
      setAiClassifyResult(res.data);
      if (res.data?.predicted_request_type) {
        const pred = res.data.predicted_request_type.toUpperCase();
        if (pred.includes("LEAVE")) setType("LEAVE");
        else if (
          pred.includes("ACCESS") ||
          pred.includes("VPN") ||
          pred.includes("PERMISSION")
        )
          setType("ACCESS");
        else if (pred.includes("EQUIPMENT") || pred.includes("DEVICE"))
          setType("EQUIPMENT");
      }
    } catch (err) {
      setMessage(`AI phân loại tạm thời không khả dụng: ${err.message}`);
    } finally {
      setAiBusy(false);
    }
  }

  async function handleAiRisk() {
    setAiBusy(true);
    try {
      const amountInput = Number(
        document.getElementById("amount_vnd")?.value || 0
      );
      const res = await api("/api/v1/ai/risk-score", {
        method: "POST",
        body: JSON.stringify({
          request_type: type.toLowerCase(),
          lifecycle_template:
            type === "LEAVE" ? "A" : type === "EQUIPMENT" ? "B" : "A",
          risk_weight: type === "EQUIPMENT" ? 3 : 2,
          amount_vnd: amountInput,
        }),
      });
      setAiRiskResult(res.data);
    } catch (err) {
      setMessage(`AI đánh giá rủi ro không phản hồi: ${err.message}`);
    } finally {
      setAiBusy(false);
    }
  }

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
        const uploaded = await api(
          `/api/v1/request-drafts/${request.id}/attachments`,
          { method: "POST", body: upload }
        );
        attachmentIds.push(uploaded.attachment.id);
      }
      if (type === "EQUIPMENT" && attachmentIds.length === 0)
        throw new Error("EQUIPMENT_QUOTE_REQUIRED");
      await api("/api/v1/requests/submit", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          request_id: request.id,
          expected_version: 0,
          type_code: type,
          payload: values,
          attachment_ids: attachmentIds,
        }),
      });
      event.currentTarget.reset();
      setAiClassifyResult(null);
      setAiRiskResult(null);
      setMessage("Đã gửi yêu cầu thành công.");
      onCreated();
    } catch (reason) {
      setMessage(
        reason.message === "EQUIPMENT_QUOTE_REQUIRED"
          ? "Yêu cầu thiết bị bắt buộc có báo giá PDF/JPG/PNG sạch."
          : `Không thể gửi: ${reason.message}`
      );
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="new-request-title">
      <h2 id="new-request-title">Tạo yêu cầu</h2>
      <form onSubmit={submit}>
        <label htmlFor="type_code">Loại yêu cầu</label>
        <select
          id="type_code"
          name="type_code"
          value={type}
          onChange={(event) => setType(event.target.value)}
        >
          <option value="LEAVE">Nghỉ phép</option>
          <option value="ACCESS">Cấp quyền</option>
          <option value="EQUIPMENT">Thiết bị</option>
        </select>
        <div className="form-grid">
          {fields[type].map(([name, label, kind]) => (
            <div key={name} className={kind === "textarea" ? "wide" : ""}>
              <label htmlFor={name}>{label}</label>
              {kind === "textarea" ? (
                <textarea id={name} name={name} required rows="3" />
              ) : (
                <input id={name} name={name} type={kind} required />
              )}
            </div>
          ))}
        </div>
        {type === "EQUIPMENT" && (
          <>
            <label htmlFor="attachment">Báo giá</label>
            <input
              id="attachment"
              name="attachment"
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              required
            />
          </>
        )}

        <div className="actions" style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="secondary ai-btn"
            style={{ color: "white" }}
            onClick={handleAiClassify}
            disabled={aiBusy}
          >
            {aiBusy ? "AI đang phân tích…" : "AI Gợi ý phân loại"}
          </button>
          <button
            type="button"
            className="secondary ai-btn"
            style={{ color: "white" }}
            onClick={handleAiRisk}
            disabled={aiBusy}
          >
            {aiBusy ? "AI đang tính toán…" : "AI Dự đoán rủi ro"}
          </button>
        </div>

        {aiClassifyResult && (
          <div className="ai-panel">
            <h3>Kết quả AI Phân loại</h3>
            <p>
              Loại đề xuất:{" "}
              <strong>{aiClassifyResult.predicted_request_type}</strong> (độ tin
              cậy:{" "}
              {(
                (aiClassifyResult.confidence_request_type || 0.9) * 100
              ).toFixed(0)}
              %)
            </p>
            <p>
              Phòng ban:{" "}
              <strong>{aiClassifyResult.predicted_department}</strong> | Biểu
              mẫu: Template {aiClassifyResult.predicted_template || "A"}
            </p>
            {aiClassifyResult.workflow_suggestion && (
              <p>
                <em>Gợi ý: {aiClassifyResult.workflow_suggestion}</em>
              </p>
            )}
          </div>
        )}

        {aiRiskResult && (
          <div className="ai-panel">
            <h3>Kết quả AI Đánh giá rủi ro</h3>
            <p>
              Điểm rủi ro:{" "}
              <span
                className={`badge badge-${
                  aiRiskResult.risk_score <= 2
                    ? "low"
                    : aiRiskResult.risk_score <= 3
                    ? "medium"
                    : "high"
                }`}
              >
                {aiRiskResult.risk_score}/5 ({aiRiskResult.risk_label})
              </span>
            </p>
            <p>
              Điều kiện Auto-Approve:{" "}
              <strong>
                {aiRiskResult.auto_approve_eligible ? "Đủ điều kiện" : "Không"}
              </strong>
            </p>
          </div>
        )}

        {message && (
          <p ref={errorRef} tabIndex="-1" aria-live="assertive">
            {message}
          </p>
        )}
        <button disabled={busy} style={{ marginTop: "1rem" }}>
          {busy ? "Đang xử lý…" : "Gửi phê duyệt"}
        </button>
      </form>
    </section>
  );
}

function Dashboard({ user, onLogout }) {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState("");
  const [summaryData, setSummaryData] = useState(null);
  const [auditVerifyData, setAuditVerifyData] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [opsMsg, setOpsMsg] = useState("");
  const [releases, setReleases] = useState([]);

  async function refresh() {
    setStatus("Đang tải danh sách…");
    try {
      const result = await api("/api/v1/requests?limit=50");
      setItems(result.items);
      setStatus(result.items.length ? "" : "Chưa có yêu cầu nào.");
    } catch (reason) {
      setStatus(`Không thể tải danh sách: ${reason.message}`);
    }
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
    return () => {
      active = false;
    };
  }, []);

  async function open(id) {
    try {
      setSelected((await api(`/api/v1/requests/${id}`)).request);
      setSummaryData(null);
      setAuditVerifyData(null);
    } catch (reason) {
      setStatus(`Không thể mở yêu cầu: ${reason.message}`);
    }
  }

  async function decide(outcome) {
    const reason =
      outcome === "APPROVE"
        ? null
        : window.prompt("Nhập lý do (10–2000 ký tự):");
    if (outcome !== "APPROVE" && (!reason || reason.trim().length < 10)) return;
    try {
      await api(`/api/v1/requests/${selected.id}/approval-decisions`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          outcome,
          reason,
          expected_version: selected.lock_version,
        }),
      });
      setSelected(null);
      await refresh();
    } catch (error) {
      setStatus(`Không thể quyết định: ${error.message}`);
    }
  }

  async function startExecution() {
    try {
      await api(`/api/v1/requests/${selected.id}/execution/start`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({ expected_version: selected.lock_version }),
      });
      await open(selected.id);
      await refresh();
    } catch (error) {
      setStatus(`Không thể bắt đầu thực hiện: ${error.message}`);
    }
  }

  async function submitExecution(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("evidence");
    try {
      const upload = new FormData();
      upload.append("file", file);
      await api(`/api/v1/requests/${selected.id}/execution/attachments`, {
        method: "POST",
        body: upload,
      });
      await api(`/api/v1/requests/${selected.id}/execution/submit`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          expected_version: selected.lock_version,
          result_note: form.get("result_note"),
          external_reference: form.get("external_reference"),
        }),
      });
      await open(selected.id);
      await refresh();
    } catch (error) {
      setStatus(`Không thể nộp kết quả: ${error.message}`);
    }
  }

  async function decideAcceptance(outcome) {
    const reason =
      outcome === "ACCEPT"
        ? null
        : window.prompt("Nêu lý do yêu cầu làm lại (10–2000 ký tự):");
    if (outcome === "REWORK" && (!reason || reason.trim().length < 10)) return;
    try {
      await api(`/api/v1/requests/${selected.id}/acceptance-decisions`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          outcome,
          reason,
          expected_version: selected.lock_version,
        }),
      });
      await open(selected.id);
      await refresh();
    } catch (error) {
      setStatus(`Không thể nghiệm thu: ${error.message}`);
    }
  }

  async function cancelRequest() {
    const reason = window.prompt("Nêu lý do hủy yêu cầu (10–2000 ký tự):");
    if (!reason || reason.trim().length < 10) return;
    try {
      await api(`/api/v1/requests/${selected.id}/cancel`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          reason,
          expected_version: selected.lock_version,
        }),
      });
      setSelected(null);
      await refresh();
    } catch (error) {
      setStatus(`Không thể hủy yêu cầu: ${error.message}`);
    }
  }

  async function handleAiSummarize() {
    if (!selected) return;
    setAiBusy(true);
    try {
      const title = selected.payload?.title || `Yêu cầu ${selected.code}`;
      const res = await api("/api/v1/ai/summarize", {
        method: "POST",
        body: JSON.stringify({
          title,
          request_type: selected.type_code,
          description: selected.payload?.reason || "",
          data: selected.payload,
          amount: selected.payload?.amount_vnd,
        }),
      });
      setSummaryData(res.data);
    } catch (err) {
      setStatus(`Không thể tóm tắt: ${err.message}`);
    } finally {
      setAiBusy(false);
    }
  }

  async function handleVerifyAudit() {
    if (!selected) return;
    setAiBusy(true);
    try {
      const res = await api(`/api/v1/requests/${selected.id}/audit/verify`);
      setAuditVerifyData(res);
    } catch (err) {
      setStatus(`Lỗi xác minh kiểm toán: ${err.message}`);
    } finally {
      setAiBusy(false);
    }
  }

  async function handleReplayOutbox(eventId) {
    if (!eventId) return;
    try {
      await api(`/api/v1/ops/outbox/${eventId}/replay`, { method: "POST" });
      setOpsMsg(`Đã phát lại sự kiện ${eventId} thành công.`);
    } catch (err) {
      setOpsMsg(`Lỗi phát lại outbox: ${err.message}`);
    }
  }

  async function handleLoadReleases() {
    try {
      const res = await api("/api/v1/config-releases");
      setReleases(res.releases || res.items || []);
    } catch (err) {
      setStatus(`Không tải được config releases: ${err.message}`);
    }
  }

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">Enterprise Approval System</p>
          <strong>{user.display_name}</strong>
          <div style={{ marginTop: "0.25rem" }}>
            {user.roles.map((r) => (
              <span key={r} className="role-tag">
                {r}
              </span>
            ))}
          </div>
        </div>
        <button className="secondary" onClick={onLogout}>
          Đăng xuất
        </button>
      </header>

      <main id="main" className="layout">
        {user.roles.includes("REQUESTER") && <RequestForm onCreated={refresh} />}

        <section className="panel" aria-labelledby="request-list-title">
          <div className="section-head">
            <h2 id="request-list-title">Danh sách yêu cầu</h2>
            <button className="secondary" onClick={refresh}>
              Làm mới
            </button>
          </div>
          <p aria-live="polite">{status}</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Loại</th>
                  <th>Trạng thái</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.code}</td>
                    <td>{item.type_code}</td>
                    <td>
                      <span className="status">{item.status}</span>
                    </td>
                    <td>
                      <button className="link" onClick={() => open(item.id)}>
                        Chi tiết
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {user.roles.includes("OPS_ADMIN") && (
          <section className="panel" aria-labelledby="ops-admin-title">
            <h2 id="ops-admin-title">Quản trị vận hành (Ops Admin)</h2>
            <p>Hỗ trợ kiểm soát luồng outbox và điều phối phân bổ người duyệt.</p>
            <div className="actions">
              <button
                className="secondary"
                onClick={() => {
                  const evId = window.prompt("Nhập UUID sự kiện Outbox cần replay:");
                  if (evId) handleReplayOutbox(evId.trim());
                }}
              >
                Phát lại sự kiện Outbox chết
              </button>
            </div>
            {opsMsg && <p aria-live="polite">{opsMsg}</p>}
          </section>
        )}

        {user.roles.includes("POLICY_ADMIN") && (
          <section className="panel" aria-labelledby="policy-admin-title">
            <div className="section-head">
              <h2 id="policy-admin-title">Quản lý phiên bản chính sách</h2>
              <button className="secondary" onClick={handleLoadReleases}>
                Tải danh sách Release
              </button>
            </div>
            <p>Kiểm soát quy tắc định tuyến đa bước và cấu hình nghiệp vụ.</p>
            {releases.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Phiên bản</th>
                      <th>Trạng thái</th>
                      <th>SHA-256</th>
                    </tr>
                  </thead>
                  <tbody>
                    {releases.map((rel) => (
                      <tr key={rel.id || rel.release_tag}>
                        <td>{rel.release_tag}</td>
                        <td>
                          <span className="status">{rel.status}</span>
                        </td>
                        <td>
                          <code>{(rel.sha256_hash || "").slice(0, 12)}…</code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {selected && (
          <section className="panel wide-panel" aria-labelledby="detail-title">
            <div className="section-head">
              <h2 id="detail-title">{selected.code}</h2>
              <button className="secondary" onClick={() => setSelected(null)}>
                Đóng
              </button>
            </div>

            <div className="actions" style={{ marginBottom: "1rem" }}>
              <button
                type="button"
                className="ai-btn"
                onClick={handleAiSummarize}
                disabled={aiBusy}
              >
                {aiBusy ? "Đang xử lý…" : "AI Tóm tắt yêu cầu"}
              </button>
              {user.roles.includes("AUDITOR") && (
                <button
                  type="button"
                  className="secondary"
                  onClick={handleVerifyAudit}
                  disabled={aiBusy}
                >
                  Kiểm tra toàn vẹn chuỗi Hash
                </button>
              )}
            </div>

            {summaryData && (
              <div className="ai-panel">
                <h3>AI Tóm tắt thông minh</h3>
                <p>
                  <strong>{summaryData.summary}</strong>
                </p>
                {summaryData.key_points?.length > 0 && (
                  <ul>
                    {summaryData.key_points.map((pt, idx) => (
                      <li key={idx}>{pt}</li>
                    ))}
                  </ul>
                )}
                {summaryData.sentiment && (
                  <p>
                    <em>Đánh giá tâm thế: {summaryData.sentiment}</em>
                  </p>
                )}
              </div>
            )}

            {auditVerifyData && (
              <div className="ai-panel">
                <h3>Xác minh toàn vẹn mật mã học (Audit Trail)</h3>
                <p>
                  Trạng thái chuỗi:{" "}
                  <span
                    className={`badge ${
                      auditVerifyData.valid ? "badge-low" : "badge-high"
                    }`}
                  >
                    {auditVerifyData.valid
                      ? "CHUỖI HỢP LỆ (VERIFIED)"
                      : "LỖI TOÀN VẸN"}
                  </span>
                </p>
                <p>Tổng số sự kiện kiểm toán: {auditVerifyData.total_events || 0}</p>
                {auditVerifyData.latest_hash && (
                  <p>
                    Hash mới nhất: <code>{auditVerifyData.latest_hash}</code>
                  </p>
                )}
              </div>
            )}

            <pre>{JSON.stringify(selected.payload, null, 2)}</pre>
            <ol>
              {selected.approval_steps.map((step) => (
                <li key={step.step_no}>
                  Cấp {step.step_no}: {step.state}
                </li>
              ))}
            </ol>

            {user.roles.includes("APPROVER") &&
              selected.status === "PENDING_APPROVAL" &&
              selected.approval_steps.some(
                (step) => step.state === "ACTIVE" && step.assignee_id === user.id
              ) && (
                <div className="actions">
                  <button onClick={() => decide("APPROVE")}>Duyệt</button>
                  <button className="danger" onClick={() => decide("REJECT")}>
                    Từ chối
                  </button>
                  <button
                    className="secondary"
                    onClick={() => decide("NEEDS_INFO")}
                  >
                    Yêu cầu bổ sung
                  </button>
                </div>
              )}

            {user.roles.includes("EXECUTOR") &&
              selected.status === "READY_FOR_EXECUTION" &&
              selected.workflow?.attempt?.executor_id === user.id && (
                <button onClick={startExecution}>Bắt đầu thực hiện</button>
              )}

            {user.roles.includes("EXECUTOR") &&
              selected.status === "IN_PROGRESS" &&
              selected.workflow?.attempt?.executor_id === user.id && (
                <form onSubmit={submitExecution} className="execution-form">
                  <h3>Nộp kết quả thực hiện</h3>
                  <label htmlFor="result_note">Mô tả kết quả</label>
                  <textarea
                    id="result_note"
                    name="result_note"
                    minLength="10"
                    maxLength="4000"
                    required
                  />
                  <label htmlFor="external_reference">Mã tham chiếu</label>
                  <input
                    id="external_reference"
                    name="external_reference"
                    maxLength="200"
                    required
                  />
                  <label htmlFor="evidence">Bằng chứng</label>
                  <input
                    id="evidence"
                    name="evidence"
                    type="file"
                    accept="application/pdf,image/jpeg,image/png"
                    required
                  />
                  <button>Nộp kết quả</button>
                </form>
              )}

            {user.roles.includes("ACCEPTOR") &&
              selected.status === "WAITING_FOR_ACCEPTANCE" &&
              selected.workflow?.acceptor_id === user.id && (
                <div className="actions">
                  <button onClick={() => decideAcceptance("ACCEPT")}>
                    Nghiệm thu
                  </button>
                  <button
                    className="danger"
                    onClick={() => decideAcceptance("REWORK")}
                  >
                    Yêu cầu làm lại
                  </button>
                </div>
              )}

            {selected.requester_id === user.id &&
              ["DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"].includes(
                selected.status
              ) && (
                <button className="danger" onClick={cancelRequest}>
                  Hủy yêu cầu
                </button>
              )}
          </section>
        )}
      </main>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState(undefined);

  async function load() {
    try {
      setUser((await api("/api/v1/auth/me")).user);
    } catch {
      setUser(null);
    }
  }

  useEffect(() => {
    initializeCsrf()
      .then(load)
      .catch(() => setUser(null));
  }, []);

  async function logout() {
    await api("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setUser(null);
  }

  if (user === undefined)
    return (
      <main id="main" className="loading" aria-live="polite">
        Đang khởi tạo…
      </main>
    );

  return user ? (
    <Dashboard user={user} onLogout={logout} />
  ) : (
    <Login onLogin={load} />
  );
}

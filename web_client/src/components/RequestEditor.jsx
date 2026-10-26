import { useEffect, useRef, useState } from "react";
import { api, idempotencyKey } from "../api.js";
import { fields, types, errorText } from "../domain.js";
import { Badge, command } from "./ui.jsx";
import { AiRequestAssist } from "./AiAssist.jsx";
export default function RequestEditor({ initial, onDone, onCancel }) {
  const [type, setType] = useState(initial?.type_code || "LEAVE"),
    [record, setRecord] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [files, setFiles] = useState([]),
    [notice, setNotice] = useState("");
  const createKey = useRef(idempotencyKey());
  const formRef = useRef(null);
  useEffect(() => {
    if (!initial?.id) return;
    let active = true;
    api(`/api/v1/requests/${initial.id}/history`)
      .then((data) => {
        if (active) setFiles(data.draft_attachments || []);
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [initial?.id]);
  async function removeFile(id) {
    setBusy(true);
    setError("");
    try {
      const result = await command(
        `request-drafts/${record.id}/attachments/${id}`,
        { expected_version: record.lock_version },
        "DELETE",
      );
      setRecord({ ...record, lock_version: result.lock_version });
      setFiles(files.filter((f) => f.id !== id));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function save(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const send = e.nativeEvent.submitter?.value === "send";
    const payload = Object.fromEntries(new FormData(form));
    delete payload.file;
    for (const [name, , kind] of fields[type]) {
      if (kind === "number") {
        if (payload[name] === "") delete payload[name];
        else payload[name] = Number(payload[name]);
      } else if (!payload[name]) delete payload[name];
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      let r = record;
      if (!r) {
        r = (
          await command(
            "request-drafts",
            { type_code: type },
            "POST",
            createKey.current,
          )
        ).request;
        setRecord(r);
      }
      let uploaded = files;
      const file = form.elements.file.files[0];
      if (file) {
        if (file.size > 10485760)
          throw new Error("Tệp không được vượt quá 10 MB.");
        const body = new FormData();
        body.append("file", file);
        const result = await api(`/api/v1/request-drafts/${r.id}/attachments`, {
          method: "POST",
          body,
        });
        uploaded = [...files, result.attachment];
        setFiles(uploaded);
        form.elements.file.value = "";
      }
      if (uploaded.some((f) => f.scan_state !== "CLEAN"))
        throw new Error(
          "Tệp đang chờ kiểm tra hoặc chưa hợp lệ. Nhấn Kiểm tra tệp rồi thử lại.",
        );
      const body = { expected_version: r.lock_version, payload };
      // Upload already links files to this draft; keep existing links across edits.
      if (type === "EQUIPMENT" && payload.amount_vnd)
        body.amount_vnd = payload.amount_vnd;
      await command(`request-drafts/${r.id}`, body, "PATCH");
      r = (await api(`/api/v1/requests/${r.id}`)).request;
      setRecord(r);
      if (send) {
        await command("requests/submit", {
          request_id: r.id,
          expected_version: r.lock_version,
          type_code: type,
          payload,
        });
        onDone(r.id);
      } else
        setNotice(
          "Đã lưu bản nháp. Bạn có thể tiếp tục chỉnh sửa hoặc gửi phê duyệt.",
        );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  async function checkFiles() {
    setBusy(true);
    try {
      const next = await Promise.all(
        files.map(
          async (f) => (await api(`/api/v1/attachments/${f.id}`)).attachment,
        ),
      );
      setFiles(next);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">HỒ SƠ ĐỀ XUẤT</p>
          <h2>
            {record
              ? "Chỉnh sửa " + (record.code || "bản nháp")
              : "Tạo yêu cầu mới"}
          </h2>
        </div>
        <button className="secondary" onClick={onCancel}>
          Quay lại
        </button>
      </div>
      <div className="type-picker">
        {Object.entries(types).map(([key, label]) => (
          <button
            key={key}
            disabled={!!record || busy}
            className={type === key ? "selected" : "secondary"}
            onClick={() => setType(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <form ref={formRef} onSubmit={save}>
        <fieldset disabled={busy}>
          <div className="form-grid">
            {fields[type].map(([name, label, kind]) => (
              <label
                key={type + name}
                className={kind === "textarea" ? "wide" : ""}
              >
                {label}
                {kind === "textarea" ? (
                  <textarea
                    name={name}
                    defaultValue={initial?.payload?.[name] || ""}
                    rows={3}
                  />
                ) : (
                  <input
                    name={name}
                    type={kind}
                    min={kind === "number" ? 1 : undefined}
                    defaultValue={initial?.payload?.[name] ?? ""}
                  />
                )}
              </label>
            ))}
          </div>
          <div className="upload-box">
            <label>
              Tài liệu đính kèm · PDF, JPG, PNG · tối đa 10 MB
              <input
                name="file"
                type="file"
                accept="application/pdf,image/jpeg,image/png"
              />
            </label>
            <p className="muted">
              Yêu cầu thiết bị cần báo giá hợp lệ khi gửi. Tệp đã gửi được giữ
              trong lịch sử phiên bản.
            </p>
            {files.map((f) => (
              <p key={f.id}>
                {f.original_name || f.id} <Badge value={f.scan_state} />{" "}
                <button
                  type="button"
                  className="link"
                  onClick={() => removeFile(f.id)}
                >
                  Bỏ khỏi bản nháp
                </button>
              </p>
            ))}
            {files.length > 0 && (
              <button type="button" className="secondary" onClick={checkFiles}>
                Kiểm tra tệp
              </button>
            )}
          </div>
          <AiRequestAssist
            type={type}
            getValues={() =>
              formRef.current
                ? Object.fromEntries(new FormData(formRef.current))
                : {}
            }
            onSuggestType={record ? undefined : setType}
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="success" role="status">
              {notice}
            </p>
          )}
          <div className="form-actions">
            <button name="action" value="draft" className="secondary">
              Lưu bản nháp
            </button>
            <button name="action" value="send">
              {busy
                ? "Đang xử lý…"
                : initial?.status === "NEEDS_INFO"
                  ? "Gửi lại phê duyệt"
                  : "Gửi phê duyệt"}
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}

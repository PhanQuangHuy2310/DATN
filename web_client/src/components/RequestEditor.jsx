import { useEffect, useRef, useState } from "react";
import { api, idempotencyKey } from "../api.js";
import { fields, types, errorText } from "../domain.js";
import { Badge, command } from "./ui.jsx";
export default function RequestEditor({ initial, onDone, onCancel }) {
  const [type, setType] = useState(initial?.type_code || "LEAVE"),
    [record, setRecord] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [files, setFiles] = useState([]),
    [notice, setNotice] = useState("");
  const [catalog, setCatalog] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const createKey = useRef(idempotencyKey());
  useEffect(() => {
    let active = true;
    api("/api/v1/meta/request-type-forms")
      .then((result) => {
        if (active) {
          const items = result.items || [];
          setCatalog(items);
          if (!initial?.id && items.length && !items.some((item) => item.code === type))
            setType(items[0].code);
          setCatalogError("");
        }
      })
      .catch((err) => {
        if (active) setCatalogError(errorText(err));
      })
      .finally(() => { if (active) setCatalogLoading(false); });
    return () => { active = false; };
  }, []);
  const current = catalog.find((entry) => entry.code === type);
  const schema = current?.form_schema;
  const formFields = schema?.properties
    ? Object.entries(schema.properties).map(([name, spec]) => {
        const legacy = fields[type]?.find(([field]) => field === name);
        const label = legacy?.[1] || name.replaceAll("_", " ");
        const inputType = spec.type === "integer" ? "number"
          : spec.format === "date" ? "date" : "text";
        return [name, label, legacy?.[2] === "textarea" ? "textarea" : inputType, spec];
      })
    : (fields[type] || []).map(([name, label, kind]) => [name, label, kind, {}]);
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
    for (const [name, , kind] of formFields) {
      if (kind === "number") {
        if (payload[name] === "") delete payload[name];
        else payload[name] = Number(payload[name]);
      } else if (!payload[name]) delete payload[name];
    }
    if (!current) {
      setError("Loại yêu cầu chưa có cấu hình đã công bố hoặc bạn chưa được cấp quyền tạo loại này.");
      return;
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
          viewed_release_id: current.release_id,
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
      <div className="request-type-catalog panel-subtle" aria-label="Danh mục biểu mẫu được phép sử dụng">
        <p className="muted">Chỉ hiển thị biểu mẫu đang hoạt động, có quy chế đã công bố và thuộc phạm vi quyền của bạn.</p>
        {catalogLoading && <p role="status">Đang tải biểu mẫu từ hệ thống…</p>}
        {catalogError && <p className="error" role="alert">Không tải được danh mục biểu mẫu: {catalogError}</p>}
        {!catalogLoading && !catalogError && catalog.length === 0 && <p role="status">Không có biểu mẫu khả dụng. Hãy liên hệ quản trị viên quy chế.</p>}
        <div className="type-picker">
          {catalog.map(({code, lifecycle}) => (
            <button type="button" key={code} disabled={!!record || busy}
              aria-pressed={type === code}
              className={type === code ? "selected" : "secondary"}
              onClick={() => { setType(code); setError(""); }}>
              <strong>{types[code] || code.replaceAll("_", " ")}</strong>
              <small> · Mẫu {lifecycle}</small>
            </button>
          ))}
        </div>
      </div>
      <form onSubmit={save} key={type}>
        <fieldset disabled={busy || catalogLoading || !!catalogError || !current}>
          <div className="form-grid">
            {formFields.map(([name, label, kind, spec]) => (
              <label
                key={type + name}
                className={kind === "textarea" ? "wide" : ""}
              >
                {label}
                {Array.isArray(spec.enum) ? (
                  <select name={name} defaultValue={initial?.payload?.[name] ?? ""}
                    required={schema?.required?.includes(name)}>
                    <option value="">— Chọn —</option>
                    {spec.enum.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                ) : kind === "textarea" ? (
                  <textarea name={name} defaultValue={initial?.payload?.[name] || ""}
                    required={schema?.required?.includes(name)} rows={3} maxLength={spec.maxLength} />
                ) : (
                  <input name={name} type={kind}
                    required={schema?.required?.includes(name)}
                    min={kind === "number" ? spec.minimum : undefined}
                    max={kind === "number" ? spec.maximum : undefined}
                    minLength={kind === "text" ? spec.minLength : undefined}
                    maxLength={kind === "text" ? spec.maxLength : undefined}
                    step={kind === "number" ? 1 : undefined}
                    defaultValue={initial?.payload?.[name] ?? ""} />
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

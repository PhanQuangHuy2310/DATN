import { useEffect, useRef, useState } from "react";
import { api, idempotencyKey } from "../api.js";
import { fields, types, errorText } from "../domain.js";
import { Badge, command } from "./ui.jsx";
import { AiRequestAssist } from "./AiAssist.jsx";
import RequestTypeMenu from "./RequestTypeMenu.jsx";

// String properties representing evidence are stored as sanitized filenames in
// the published schema, while the actual file bytes go through Attachment API.
const isEvidenceField = (name) => /(?:_file|_files|_pdf|_doc|_images|photo_evidence|board_resolution|handover_doc)$/.test(name);
export default function RequestEditor({ initial, onDone, onCancel }) {
  const [type, setType] = useState(initial?.type_code || ""),
    [record, setRecord] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [files, setFiles] = useState([]),
    [notice, setNotice] = useState("");
  const [catalog, setCatalog] = useState([]);
  const [menu, setMenu] = useState([]);
  const [chosenLabel, setChosenLabel] = useState("");
  const [stage, setStage] = useState(initial?.id ? "form" : "choose");
  const [colleagues, setColleagues] = useState([]);
  const [evidenceNames, setEvidenceNames] = useState({});
  const formRef = useRef(null);
  const formElementRef = useRef(null);
  const menuRef = useRef(null);
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
          const choices = result.approval_menu || items.map((item) => ({
            group: "Biểu mẫu đang hoạt động", label: item.name || item.code,
            code: item.code, lifecycle: item.lifecycle, description: "Quy trình được công bố",
            available: true,
          }));
          setMenu(choices);
          if (initial?.id && items.some((item) => item.code === initial.type_code))
            setChosenLabel(items.find((item) => item.code === initial.type_code).name);
          setCatalogError("");
        }
      })
      .catch((err) => {
        if (active) setCatalogError(errorText(err));
      })
      .finally(() => { if (active) setCatalogLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (stage !== "form") return;
    const handle = requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({behavior: "smooth", block: "start"});
      formRef.current?.querySelector("input:not([type=hidden]),select,textarea")?.focus({preventScroll:true});
    });
    return () => cancelAnimationFrame(handle);
  }, [stage, type]);
  useEffect(() => {
    let alive = true;
    api("/api/v1/meta/colleagues").then((result) => {
      if (alive) setColleagues(result.items || []);
    }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const current = catalog.find((entry) => entry.code === type);
  const schema = current?.form_schema;
  const formFields = schema?.properties
    ? Object.entries(schema.properties).filter(([name]) => name !== "title" && name !== "department_id").map(([name, spec]) => {
        const legacy = fields[type]?.find(([field]) => field === name);
        const label = current?.field_labels?.[name] || legacy?.[1] || name.replaceAll("_", " ");
        const inputType = spec.type === "integer" ? "number"
          : spec.format === "date" ? "date" : "text";
        return [name, label, isEvidenceField(name) && spec.type === "string" ? "evidence" :
          (legacy?.[2] === "textarea" ? "textarea" : inputType), spec];
      })
    : (fields[type] || []).filter(([name]) => name !== "title" && name !== "department_id").map(([name, label, kind]) => [name, label, kind, {}]);
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
    for (const [name, , kind] of formFields) if (kind === "evidence") {
      delete payload[`evidence_${name}`];
      delete payload[name];
      const previous = evidenceNames[name] || initial?.payload?.[name];
      if (previous) payload[name] = previous;
    }
    // Technical fields are server-owned. Only business information is editable.
    if (schema?.properties?.title) {
      const generated = chosenLabel || current?.name || types[type] || type;
      payload.title = initial?.payload?.title || `${generated} - ${new Date().toLocaleDateString("vi-VN")}`;
    }
    if (schema?.properties?.department_id && current?.department_id)
      payload.department_id = current.department_id;
    for (const [name, , kind] of formFields) {
      if (kind === "number") {
        if (payload[name] === "") delete payload[name];
        else payload[name] = Number(payload[name]);
      } else if (!payload[name]) delete payload[name];
    }
    if (!current || !type) {
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
      let uploaded = [...files];
      const incoming = [];
      for (const [name, , kind] of formFields) {
        if (kind === "evidence") {
          const field = form.elements[`evidence_${name}`];
          if (field?.files?.length) incoming.push({name, file:field.files[0], element:field});
        }
      }
      const general = form.elements.file;
      if (general?.files?.length) incoming.push({name:null,file:general.files[0],element:general});
      if (uploaded.length + incoming.length > 5) throw new Error("Mỗi hồ sơ có tối đa 5 tệp đính kèm.");
      for (const {name,file,element} of incoming) {
        if (file.size > 10485760) throw new Error("Mỗi tệp không được vượt quá 10 MB.");
        const body = new FormData();
        body.append("file", file);
        const result = await api(`/api/v1/request-drafts/${r.id}/attachments`, {method:"POST",body});
        uploaded.push(result.attachment);
        if (name) {
          const filename = result.attachment.original_name || file.name;
          payload[name] = filename;
          setEvidenceNames((previous) => ({...previous, [name]:filename}));
        }
        element.value = "";
      }
      setFiles(uploaded);
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
      {catalogLoading && <p role="status">Đang tải danh mục biểu mẫu và quyền tạo đơn…</p>}
      {catalogError && <p role="alert" className="error">Không tải được danh mục: {catalogError}</p>}
      {!catalogLoading && !catalogError && stage === "choose" && (
        <div ref={menuRef}><RequestTypeMenu options={menu} disabled={busy} onSelect={(choice) => {
          setType(choice.code);
          setChosenLabel(choice.label);
          setStage("form");
          setError("");
        }}/></div>
      )}
      {stage === "form" && <div ref={formRef} id="request-business-form">
        <div className="request-form-heading">
          <div>
            <p className="eyebrow">BƯỚC 2 / THÔNG TIN NGHIỆP VỤ</p>
            <strong>{chosenLabel || current?.name || types[type] || type}</strong>
            <small>Mẫu {current?.lifecycle || "?"} · Quy trình theo cấu hình đã công bố</small>
          </div>
          {!record && <button type="button" className="secondary" onClick={() => {
            setStage("choose");setType("");setError("");
            requestAnimationFrame(() => menuRef.current?.scrollIntoView({behavior:"smooth",block:"start"}));
          }}>← Đổi loại yêu cầu</button>}
        </div>
        {record?.code ? <p className="request-generated-code" role="status">Mã yêu cầu tự động: <strong>{record.code}</strong></p>
          : <p className="request-requester-note">Mã hồ sơ sẽ được hệ thống tự tạo khi lưu bản nháp hoặc gửi yêu cầu. Người yêu cầu, phòng ban, ngày tạo và người duyệt được xác định tự động. Bạn chỉ nhập các trường nghiệp vụ bên dưới.</p>}
      </div>}
      {stage === "form" && <form ref={formElementRef} onSubmit={save} key={type}>
        <fieldset disabled={busy || catalogLoading || !!catalogError || !current}>
          <div className="form-grid">
            {formFields.map(([name, label, kind, spec]) => (
              <label
                key={type + name}
                className={kind === "textarea" ? "wide" : ""}
              >
                {label}
                {kind === "evidence" ? (
                  <>
                    <input name={`evidence_${name}`} type="file"
                      accept="application/pdf,image/jpeg,image/png" />
                    {(evidenceNames[name] || initial?.payload?.[name]) &&
                      <small>Đã gắn: {evidenceNames[name] || initial?.payload?.[name]}</small>}
                    <small>PDF/JPG/PNG, tối đa 10MB. {schema?.required?.includes(name) ? "Bắt buộc khi gửi." : "Không bắt buộc."}</small>
                  </>
                ) : spec.format === "uuid" && name.endsWith("user_id") ? (
                  <select name={name} defaultValue={initial?.payload?.[name] ?? ""}
                    required={schema?.required?.includes(name)}>
                    <option value="">— Chọn người trong phòng ban —</option>
                    {colleagues.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}
                  </select>
                ) : Array.isArray(spec.enum) ? (
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
          <AiRequestAssist
            type={type}
            getValues={() =>
              formElementRef.current
                ? Object.fromEntries(new FormData(formElementRef.current))
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
      </form>}
    </section>
  );
}

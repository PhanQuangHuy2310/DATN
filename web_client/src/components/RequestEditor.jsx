import { useEffect, useRef, useState } from "react";
import { api, idempotencyKey, notify } from "../api.js";
import {
  fields,
  fieldLabels,
  resolveFieldLabel,
  types,
  errorText,
  riskLevels,
  approvalLevels,
  typeLevels,
  enumLabels,
} from "../domain.js";
import {
  formatThousandDots,
  isCurrencyField,
  parseDigits,
  vndToVietnameseWords,
} from "../formatters.js";
import { Badge, command } from "./ui.jsx";
import { AiRequestAssist } from "./AiAssist.jsx";
import RequestTypeMenu from "./RequestTypeMenu.jsx";
import RoutePreview from "./RoutePreview.jsx";
import { CardGridSkeleton, ConfirmDialog } from "./design.jsx";

// String properties representing evidence are stored as sanitized filenames in
// the published schema, while the actual file bytes go through Attachment API.
const isEvidenceField = (name) =>
  /(?:_file|_files|_pdf|_doc|_images|photo_evidence|board_resolution|handover_doc)$/.test(
    name,
  );

function CurrencyInput({ name, initialValue, isRequired, min, max }) {
  const [digits, setDigits] = useState(() => parseDigits(initialValue));
  const words = vndToVietnameseWords(digits);

  function handleChange(e) {
    const next = parseDigits(e.target.value);
    if (next.length <= 15) {
      setDigits(next);
    }
  }

  return (
    <div className="ds-currency-field">
      <div className="ds-currency-input-wrap">
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          required={isRequired}
          value={formatThousandDots(digits)}
          onChange={handleChange}
          placeholder="Nhập số tiền (ví dụ: 15.000.000)"
          aria-describedby={words ? `words-${name}` : undefined}
        />
        <span className="ds-currency-suffix" aria-hidden="true">
          VND
        </span>
      </div>
      <input type="hidden" name={name} value={digits} />
      {words ? (
        <small id={`words-${name}`} className="ds-currency-helper">
          Bằng chữ: <strong>{words}</strong>
        </small>
      ) : (
        (min != null || max != null) && (
          <small className="muted">
            {min != null ? `Tối thiểu ${Number(min).toLocaleString("vi-VN")} ₫` : ""}
            {min != null && max != null ? " · " : ""}
            {max != null ? `Tối đa ${Number(max).toLocaleString("vi-VN")} ₫` : ""}
          </small>
        )
      )}
    </div>
  );
}

function FormFieldControl({
  name,
  kind,
  spec,
  isRequired,
  initialValue,
  evidenceName,
  colleagues,
  fieldOptions,
  locked,
  selectedAppCode,
  onAppCodeChange,
}) {
  if (kind === "evidence") {
    const attached = evidenceName || initialValue;
    return (
      <>
        <input
          name={`evidence_${name}`}
          type="file"
          accept="application/pdf,image/jpeg,image/png"
        />
        {attached && <small className="ds-attached-hint">Đã gắn tệp: {attached}</small>}
        <small className="muted">
          Định dạng PDF/JPG/PNG, tối đa 10 MB.{" "}
          {isRequired ? "Bắt buộc đính kèm khi gửi." : "Tùy chọn."}
        </small>
      </>
    );
  }
  if (spec?.format === "uuid" && name.endsWith("user_id")) {
    return (
      <select name={name} defaultValue={initialValue ?? ""} required={isRequired}>
        <option value="">— Chọn đồng nghiệp trong phòng ban —</option>
        {colleagues.map((person) => (
          <option key={person.id} value={person.id}>
            {person.display_name}
          </option>
        ))}
      </select>
    );
  }
  if (locked) {
    const rawVal = initialValue ?? "";
    const displayVal = enumLabels[rawVal] || rawVal;
    return (
      <div className="ds-preset-field">
        <input type="hidden" name={name} value={rawVal} />
        <input
          type="text"
          value={displayVal}
          readOnly
          aria-readonly="true"
          className="is-preset"
        />
        <small className="muted">Được thiết lập sẵn theo biểu mẫu đã chọn</small>
      </div>
    );
  }
  const external = fieldOptions?.[name];
  if (external) {
    const filteredOptions =
      name === "requested_role" && selectedAppCode
        ? external.filter((opt) => !opt.app_code || opt.app_code === selectedAppCode)
        : external;
    return (
      <select
        name={name}
        defaultValue={initialValue ?? ""}
        required={isRequired}
        onChange={
          name === "app_code" && onAppCodeChange
            ? (e) => onAppCodeChange(e.target.value)
            : undefined
        }
      >
        <option value="">— Chọn trong danh mục hệ thống —</option>
        {filteredOptions.map((option) => (
          <option key={option.value} value={option.value} disabled={!option.available}>
            {option.label}
            {option.available ? "" : " (tạm ngưng phục vụ)"}
          </option>
        ))}
      </select>
    );
  }
  if (Array.isArray(spec?.enum)) {
    return (
      <select name={name} defaultValue={initialValue ?? ""} required={isRequired}>
        <option value="">— Chọn phương án —</option>
        {spec.enum.map((value) => (
          <option key={value} value={value}>
            {enumLabels[value] || value}
          </option>
        ))}
      </select>
    );
  }
  if (kind === "textarea") {
    return (
      <textarea
        name={name}
        defaultValue={initialValue || ""}
        required={isRequired}
        rows={3}
        maxLength={spec?.maxLength}
        placeholder={
          name === "reason"
            ? "Trình bày rõ mục đích, bối cảnh và nhu cầu thực tế…"
            : undefined
        }
      />
    );
  }
  if (kind === "number" && isCurrencyField(name)) {
    return (
      <CurrencyInput
        name={name}
        initialValue={initialValue}
        isRequired={isRequired}
        min={spec?.minimum}
        max={spec?.maximum}
      />
    );
  }
  return (
    <input
      name={name}
      type={kind}
      required={isRequired}
      min={kind === "number" ? spec?.minimum : undefined}
      max={kind === "number" ? spec?.maximum : undefined}
      minLength={kind === "text" ? spec?.minLength : undefined}
      maxLength={kind === "text" ? spec?.maxLength : undefined}
      step={kind === "number" ? 1 : undefined}
      defaultValue={initialValue ?? ""}
      placeholder={
        name === "title"
          ? "Nhập tiêu đề ngắn gọn, dễ nhận diện (ví dụ: Xin nghỉ phép 2 ngày đầu tháng 11)"
          : undefined
      }
    />
  );
}

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
  const [fieldOptions, setFieldOptions] = useState({});
  const [selectedAppCode, setSelectedAppCode] = useState(initial?.payload?.app_code || "");
  const [groups, setGroups] = useState([]);
  const [preset, setPreset] = useState({});
  const [evidenceNames, setEvidenceNames] = useState({});
  const formRef = useRef(null);
  const formElementRef = useRef(null);
  const menuRef = useRef(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const createKey = useRef(idempotencyKey());
  const submitKeys = useRef(new Map());
  const [confirmSend, setConfirmSend] = useState(false);
  const [circuitBreaker, setCircuitBreaker] = useState(null);

  useEffect(() => {
    let active = true;
    let busy = false;
    let retries = 0;
    let timer = null;
    let controller = null;
    const fetchCb = async () => {
      if (!active || busy) return;
      busy = true;
      controller = new AbortController();
      try {
        const data = await api("/api/v1/system/api-circuit-breaker-status", {
          timeoutMs: 12000,
          signal: controller.signal,
        });
        if (active) setCircuitBreaker(data);
        retries = 0;
      } catch {
        // Preserve last known restricted request types when the server is slow.
        retries = Math.min(4, retries + 1);
      } finally {
        busy = false;
        controller = null;
        if (active) {
          timer = window.setTimeout(fetchCb,
            document.visibilityState === "hidden" ? 120000
              : retries ? Math.min(60000, 8000 * 2 ** retries) : 30000);
        }
      }
    };
    const onVisible = () => {
      if (!active || document.visibilityState !== "visible" || busy) return;
      window.clearTimeout(timer);
      timer = null;
      void fetchCb();
    };
    void fetchCb();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const isTypeBlocked = Boolean(circuitBreaker?.disabled_request_types?.includes(type));
  const typeBlockedNotice =
    circuitBreaker?.disabled_type_notices?.[type] ||
    "Yêu cầu này hiện không thể sử dụng do kết nối API đang bị tắt bởi Quản trị viên.";

  const enrichedMenu = menu.map((m) => {
    const isBlocked = Boolean(circuitBreaker?.disabled_request_types?.includes(m.code));
    return {
      ...m,
      isBlocked,
      blockedNotice: isBlocked ? circuitBreaker?.disabled_type_notices?.[m.code] : null,
    };
  });

  useEffect(() => {
    let active = true;
    api("/api/v1/meta/request-type-forms")
      .then((result) => {
        if (active) {
          const items = result.items || [];
          setCatalog(items);
          const choices =
            result.approval_menu ||
            items.map((item) => ({
              group: "Biểu mẫu đang hoạt động",
              label: item.name || item.code,
              code: item.code,
              lifecycle: item.lifecycle,
              description: "Quy trình được công bố",
              available: true,
            }));
          setMenu(choices);
          setGroups(result.groups || []);
          if (initial?.id && items.some((item) => item.code === initial.type_code)) {
            setChosenLabel(items.find((item) => item.code === initial.type_code).name);
          }
          setCatalogError("");
        }
      })
      .catch((err) => {
        if (active) setCatalogError(errorText(err));
      })
      .finally(() => {
        if (active) setCatalogLoading(false);
      });
    return () => {
      active = false;
    };
  }, [initial?.id, initial?.type_code]);

  useEffect(() => {
    if (stage !== "form") return;
    const handle = requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      formRef.current
        ?.querySelector("input:not([type=hidden]):not([readonly]),select,textarea")
        ?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(handle);
  }, [stage, type]);

  useEffect(() => {
    let alive = true;
    api("/api/v1/meta/colleagues")
      .then((result) => {
        if (alive) setColleagues(result.items || []);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!type) return undefined;
    let alive = true;
    api(`/api/v1/integrations/options?type_code=${encodeURIComponent(type)}`)
      .then((result) => {
        if (alive) setFieldOptions(result.fields || {});
      })
      .catch(() => {
        if (alive) setFieldOptions({});
      });
    return () => {
      alive = false;
    };
  }, [type]);

  const current = catalog.find((entry) => entry.code === type);
  const schema = current?.form_schema;
  const formFields = schema?.properties
    ? Object.entries(schema.properties)
        .filter(([name]) => name !== "department_id")
        .map(([name, spec]) => {
          const legacy = fields[type]?.find(([field]) => field === name);
          const label =
            current?.field_labels?.[name] ||
            legacy?.[1] ||
            fieldLabels[name] ||
            resolveFieldLabel(name);
          const inputType =
            spec.type === "integer" || spec.type === "number"
              ? "number"
              : spec.format === "date"
                ? "date"
                : "text";
          const isLongText =
            legacy?.[2] === "textarea" ||
            ["reason", "description", "explanation", "task_description", "issue_description", "wfh_plan", "change_log", "rollback_plan", "specs", "specification"].includes(name);
          return [
            name,
            label,
            isEvidenceField(name) && spec.type === "string"
              ? "evidence"
              : isLongText && inputType === "text" && !Array.isArray(spec?.enum)
                ? "textarea"
                : inputType,
            spec,
          ];
        })
    : (fields[type] || [])
        .filter(([name]) => name !== "department_id")
        .map(([name, label, kind]) => [name, label, kind, {}]);

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

  function save(e) {
    e.preventDefault();
    const send = e.nativeEvent.submitter?.value === "send";
    // Submission starts the approval workflow; confirm first. Field values stay in the form.
    if (send) { setConfirmSend(true); return; }
    void persist(e.currentTarget, false);
  }

  async function persist(form, send) {
    if (send && isTypeBlocked) {
      setError(typeBlockedNotice);
      return;
    }
    const payload = Object.fromEntries(new FormData(form));
    delete payload.file;
    for (const [name, , kind] of formFields) {
      if (kind === "evidence") {
        delete payload[`evidence_${name}`];
        delete payload[name];
        const previous = evidenceNames[name] || initial?.payload?.[name];
        if (previous) payload[name] = previous;
      }
    }
    if (schema?.properties?.title) {
      const generated = chosenLabel || current?.name || types[type] || type;
      const typedTitle = String(payload.title || "").trim();
      payload.title =
        typedTitle ||
        initial?.payload?.title ||
        `${generated} - ${new Date().toLocaleDateString("vi-VN")}`;
    }
    if (schema?.properties?.department_id && current?.department_id) {
      payload.department_id = current.department_id;
    }
    for (const [name, , kind] of formFields) {
      if (kind === "number") {
        const cleaned = isCurrencyField(name) ? parseDigits(payload[name]) : payload[name];
        if (cleaned === "" || cleaned === undefined) delete payload[name];
        else payload[name] = Number(cleaned);
      } else if (!payload[name]) {
        delete payload[name];
      }
    }
    if (!current || !type) {
      setError(
        "Loại yêu cầu chưa có cấu hình đã công bố hoặc bạn chưa được cấp quyền tạo loại này.",
      );
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
          if (field?.files?.length) {
            incoming.push({ name, file: field.files[0], element: field });
          }
        }
      }
      const general = form.elements.file;
      if (general?.files?.length) {
        incoming.push({ name: null, file: general.files[0], element: general });
      }
      if (uploaded.length + incoming.length > 5) {
        throw new Error("Mỗi hồ sơ chỉ đính kèm tối đa 5 tệp tài liệu.");
      }
      // NOSONAR javascript:S9382
      for (const { name, file, element } of incoming) {
        if (file.size > 10485760) {
          throw new Error("Dung lượng mỗi tệp không được vượt quá 10 MB.");
        }
        const body = new FormData();
        body.append("file", file);
        const result = await api(`/api/v1/request-drafts/${r.id}/attachments`, {
          method: "POST",
          body,
        });
        uploaded.push(result.attachment);
        if (name) {
          const filename = result.attachment.original_name || file.name;
          payload[name] = filename;
          setEvidenceNames((previous) => ({ ...previous, [name]: filename }));
        }
        element.value = "";
      }
      setFiles(uploaded);
      if (uploaded.some((f) => f.scan_state !== "CLEAN")) {
        throw new Error(
          "Tệp đang chờ kiểm tra an toàn hoặc chưa hợp lệ. Nhấn Kiểm tra tệp rồi thử lại.",
        );
      }
      const body = { expected_version: r.lock_version, payload };
      const monetaryAmount =
        payload.amount_vnd ??
        payload.amount ??
        payload.estimated_budget ??
        payload.refund_amount ??
        payload.contract_value ??
        payload.estimated_cost ??
        payload.estimated_price ??
        payload.deal_value_vnd ??
        payload.salary_budget_vnd ??
        payload.residual_value_vnd;
      if (
        (type === "EQUIPMENT" && payload.amount_vnd) ||
        (typeof monetaryAmount === "number" &&
          Number.isInteger(monetaryAmount) &&
          monetaryAmount > 0 &&
          !["LEAVE", "ACCESS"].includes(type))
      ) {
        body.amount_vnd = payload.amount_vnd || monetaryAmount;
      }
      const saved = await command(`request-drafts/${r.id}`, body, "PATCH");
      r = {
        ...r,
        lock_version: saved.request?.lock_version ?? saved.lock_version ?? r.lock_version,
      };
      setRecord(r);
      if (send) {
        const versionKey = `${r.id}:${r.lock_version}`;
        if (!submitKeys.current.has(versionKey)) {
          submitKeys.current.set(versionKey, idempotencyKey());
        }
        try {
          await command(
            "requests/submit",
            {
              request_id: r.id,
              expected_version: r.lock_version,
              type_code: type,
              viewed_release_id: current?.release_id,
              payload,
            },
            "POST",
            submitKeys.current.get(versionKey),
          );
        } catch (submitError) {
          if (
            submitError?.message !== "REQUEST_TIMEOUT_UNKNOWN" &&
            !(submitError instanceof TypeError)
          ) {
            throw submitError;
          }
          const latest = await api(`/api/v1/requests/${r.id}`).catch(() => null);
          if (
            !latest?.request ||
            ["DRAFT", "NEEDS_INFO"].includes(latest.request.status)
          ) {
            throw submitError;
          }
          notify("Yêu cầu đã được gửi thành công (đã xác nhận lại với máy chủ)");
        }
        onDone(r.id);
      } else {
        setNotice("Đã lưu bản nháp. Bạn có thể tiếp tục chỉnh sửa hoặc gửi phê duyệt.");
      }
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
            {record ? "Chỉnh sửa " + (record.code || "bản nháp") : "Tạo yêu cầu mới"}
          </h2>
        </div>
        <button type="button" className="secondary" onClick={onCancel}>
          Quay lại
        </button>
      </div>
      {catalogLoading && (
        <output className="ds-loading" aria-live="polite" aria-busy="true">
          <span className="sr-only">Đang tải danh mục biểu mẫu và quyền tạo đơn…</span>
          <CardGridSkeleton count={6} />
        </output>
      )}
      {catalogError && (
        <p role="alert" className="error">
          Không tải được danh mục: {catalogError}
        </p>
      )}
      {!catalogLoading && !catalogError && stage === "choose" && (
        <div ref={menuRef}>
          <RequestTypeMenu
            options={enrichedMenu}
            groups={groups}
            disabled={busy}
            onSelect={(choice) => {
              setType(choice.code);
              setPreset(choice.preset || {});
              setSelectedAppCode(choice.preset?.app_code || "");
              setChosenLabel(choice.label);
              setStage("form");
              setError("");
            }}
          />
        </div>
      )}
      {stage === "form" && (
        <div ref={formRef} id="request-business-form">
          <div className="request-form-heading">
            <div>
              <p className="eyebrow">BƯỚC 2 / THÔNG TIN NGHIỆP VỤ</p>
              <strong>{chosenLabel || current?.name || types[type] || type}</strong>
              <small>
                Quy trình mẫu {current?.lifecycle || "A"} ·{" "}
                {riskLevels[
                  current?.risk_weight || typeLevels[type]?.risk_weight || 3
                ] || "Cấp 3"}{" "}
                ·{" "}
                {approvalLevels[
                  current?.approval_level || typeLevels[type]?.approval_level || 1
                ] || "Duyệt 1 cấp"}
              </small>
            </div>
            {!record && (
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setStage("choose");
                  setType("");
                  setPreset({});
                  setSelectedAppCode("");
                  setError("");
                  requestAnimationFrame(() =>
                    menuRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
                  );
                }}
              >
                ← Đổi loại yêu cầu
              </button>
            )}
          </div>
          {record?.code ? (
            <div className="request-generated-code">
              Mã hồ sơ: <strong>{record.code}</strong>
            </div>
          ) : (
            <p className="request-requester-note">
              Mã hồ sơ sẽ được hệ thống cấp tự động ngay khi lưu nháp hoặc gửi phê duyệt.
              Thông tin người đề nghị, phòng ban và tuyến duyệt được xác định tự động theo
              quy chế hiện hành.
            </p>
          )}
        </div>
      )}
      {isTypeBlocked && (
        <div className="eas-circuit-breaker-alert" role="alert">
          <div className="eas-cb-alert-icon">⚠️</div>
          <div className="eas-cb-alert-body">
            <h4 className="eas-cb-alert-title">TẠM NGƯNG TIẾP NHẬN YÊU CẦU NÀY</h4>
            <p className="eas-cb-alert-msg">{typeBlockedNotice}</p>
            <div className="eas-cb-alert-badge">
              Kết nối hệ thống tích hợp đang tạm ngắt
            </div>
          </div>
        </div>
      )}
      {stage === "form" && (
        <form ref={formElementRef} onSubmit={save} key={`${type}:${chosenLabel}`}>
          <fieldset
            disabled={
              busy ||
              catalogLoading ||
              Boolean(catalogError) ||
              (!current && !fields[type]?.length)
            }
          >
            <div className="form-grid">
              {formFields.map(([name, label, kind, spec]) => {
                const isReq = Boolean(schema?.required?.includes(name));
                return (
                  <label
                    key={type + name}
                    className={kind === "textarea" || name === "title" ? "wide" : ""}
                  >
                    <span className="label-text">
                      {label}
                      {isReq && (
                        <span className="ds-required-mark" aria-hidden="true">
                          {" "}
                          *
                        </span>
                      )}
                    </span>
                    <FormFieldControl
                      name={name}
                      kind={kind}
                      spec={spec}
                      isRequired={isReq}
                      initialValue={preset[name] ?? initial?.payload?.[name]}
                      evidenceName={evidenceNames[name]}
                      colleagues={colleagues}
                      fieldOptions={fieldOptions}
                      locked={name in preset}
                      selectedAppCode={selectedAppCode}
                      onAppCodeChange={setSelectedAppCode}
                    />
                  </label>
                );
              })}
            </div>
            <div className="upload-box">
              <label>
                Tài liệu đính kèm bổ sung (PDF, JPG, PNG · tối đa 10 MB / tệp)
                <input
                  name="file"
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                />
              </label>
              <p className="muted">
                Đề nghị mua sắm hoặc thanh toán chi phí cần đính kèm báo giá / hóa đơn hợp
                lệ. Tệp đã gửi được lưu trữ theo từng phiên bản hồ sơ.
              </p>
              {files.map((f) => (
                <p key={f.id}>
                  {f.original_name || "Tệp đính kèm"} <Badge value={f.scan_state} />{" "}
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
                  Kiểm tra trạng thái tệp
                </button>
              )}
            </div>
            <AiRequestAssist
              type={type}
              lifecycle={current?.lifecycle}
              riskWeight={current?.risk_weight || typeLevels[type]?.risk_weight}
              getValues={() =>
                formElementRef.current
                  ? Object.fromEntries(new FormData(formElementRef.current))
                  : {}
              }
              onSuggestType={record ? undefined : setType}
            />
            <RoutePreview
              type={type}
              getValues={() =>
                formElementRef.current
                  ? Object.fromEntries(new FormData(formElementRef.current))
                  : {}
              }
            />
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            {notice && <output className="success">{notice}</output>}
            <div className="form-actions">
              <button
                type="submit"
                name="action"
                value="draft"
                className="secondary"
              >
                Lưu bản nháp
              </button>
              <button
                type="submit"
                name="action"
                value="send"
                disabled={busy || isTypeBlocked}
                title={isTypeBlocked ? typeBlockedNotice : undefined}
                className={isTypeBlocked ? "btn-disabled-circuit-breaker" : ""}
              >
                {busy
                  ? "Đang xử lý…"
                  : isTypeBlocked
                    ? "Không thể gửi (API bị ngắt)"
                    : initial?.status === "NEEDS_INFO"
                      ? "Gửi lại phê duyệt"
                      : "Gửi phê duyệt"}
              </button>
            </div>
          </fieldset>
        </form>
      )}
      {confirmSend && (
        <ConfirmDialog
          title={
            initial?.status === "NEEDS_INFO"
              ? "Gửi lại yêu cầu phê duyệt?"
              : "Xác nhận gửi yêu cầu phê duyệt?"
          }
          message="Sau khi gửi, hồ sơ sẽ được chuyển trực tiếp tới người phê duyệt theo tuyến dự kiến và không thể tự ý chỉnh sửa trừ khi có yêu cầu bổ sung."
          confirmLabel="Gửi phê duyệt"
          onClose={() => setConfirmSend(false)}
          onConfirm={async () => {
            setConfirmSend(false);
            await persist(formElementRef.current, true);
          }}
        />
      )}
    </section>
  );
}

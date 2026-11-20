import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Modal, useResource, ResourceState } from "./ui.jsx";
import { date } from "../domain.js";

export const NAVIGATE_TEMPLATE_EVENT = "eas:navigate-template";

export function parseDynamicTypeAnnouncement(item) {
  if (!item || item.kind !== "REQUEST_TYPE_CREATED") return null;
  const firstChange =
    Array.isArray(item.changes) && item.changes.length > 0 && typeof item.changes[0] === "object"
      ? item.changes[0]
      : null;
  const typeCode = firstChange?.type_code || item.version || "";
  let createdByName = firstChange?.created_by_name || "";
  let createdByEmail = firstChange?.created_by_email || "";
  if (!createdByName && typeof item.summary === "string") {
    const byMatch =
      /Người tạo:\s*([^·(]+?)(?:\s*\(([^)]+)\))?(?:\s*·|$)/i.exec(item.summary) ||
      /của\s+([^.]+?)\.\s*Quy trình/i.exec(item.summary);
    if (byMatch) {
      createdByName = byMatch[1].trim();
      if (byMatch[2]) createdByEmail = byMatch[2].trim();
    }
  }
  const quotedTitleMatch = typeof item.title === "string" ? /«([^»]+)»/.exec(item.title) : null;
  const typeName = firstChange?.type_name || quotedTitleMatch?.[1] || item.title || typeCode;
  return {
    typeCode,
    typeName,
    createdByName: createdByName || "Người dùng",
    createdByEmail,
  };
}

export function openTemplateInCatalog(typeCode, onOpenTemplate) {
  if (!typeCode) return;
  if (typeof onOpenTemplate === "function") {
    onOpenTemplate(typeCode);
    return;
  }
  window.dispatchEvent(new CustomEvent(NAVIGATE_TEMPLATE_EVENT, { detail: { code: typeCode } }));
}

function UpdateBody({ item }) {
  const dyn = parseDynamicTypeAnnouncement(item);
  return (
    <div className="system-update">
      {dyn && (
        <div
          className="dynamic-type-creator-card"
          style={{
            padding: "10px 14px",
            marginBottom: "12px",
            borderRadius: "8px",
            background: "rgba(37, 99, 235, 0.08)",
            border: "1px solid rgba(37, 99, 235, 0.25)",
          }}
        >
          <div>
            <strong>Người tạo mẫu yêu cầu mới:</strong> {dyn.createdByName}
            {dyn.createdByEmail ? ` (${dyn.createdByEmail})` : ""}
          </div>
          <div style={{ marginTop: "4px" }}>
            <strong>Mẫu yêu cầu:</strong> {dyn.typeName} (Mã: <code>{dyn.typeCode}</code>)
          </div>
        </div>
      )}
      <p>{item.summary}</p>
      {item.changes?.length > 0 && (
        <>
          <h3>Thay đổi</h3>
          <ul>
            {item.changes.map((c, i) => (
              <li key={i}>{typeof c === "string" ? c : c?.title}</li>
            ))}
          </ul>
        </>
      )}
      {item.guidance?.length > 0 && (
        <>
          <h3>Hướng dẫn thao tác theo quy trình mới</h3>
          {/* A malformed announcement must never take the whole portal down. */}
          {item.guidance.map((g, i) =>
            typeof g === "string" ? (
              <p key={i}>{g}</p>
            ) : (
              <div key={i}>
                <strong>{g?.title}</strong>
                {Array.isArray(g?.steps) && (
                  <ol>
                    {g.steps.map((step, j) => (
                      <li key={j}>{step}</li>
                    ))}
                  </ol>
                )}
              </div>
            ),
          )}
        </>
      )}
    </div>
  );
}

/** Shows unread system-update announcements once after sign-in, oldest first. */
export function SystemUpdateDialog() {
  const [queue, setQueue] = useState([]);
  useEffect(() => {
    let active = true;
    api("/api/v1/announcements?unread=1")
      .then((r) => active && setQueue([...(r?.items || [])].reverse()))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  const current = queue[0];
  if (!current) return null;
  const dyn = parseDynamicTypeAnnouncement(current);
  const acknowledge = () => {
    api(`/api/v1/announcements/${current.id}/read`, { method: "POST", body: "{}", silent: true }).catch(() => {});
    setQueue((q) => q.slice(1));
  };
  return (
    <Modal key={current.id} title={current.title} onClose={acknowledge}>
      <UpdateBody item={current} />
      <div className="actions">
        {dyn?.typeCode && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              acknowledge();
              openTemplateInCatalog(dyn.typeCode);
            }}
          >
            Xem mẫu yêu cầu «{dyn.typeCode}» →
          </button>
        )}
        <button type="button" onClick={acknowledge}>
          Đã hiểu{queue.length > 1 ? ` (còn ${queue.length - 1})` : ""}
        </button>
      </div>
    </Modal>
  );
}

/** History of system updates, shown on the notifications page. */
export function SystemUpdateHistory({ onOpenTemplate }) {
  const r = useResource("/api/v1/announcements");
  const [open, setOpen] = useState(null);
  if (!r.data?.items?.length) return null;
  const openDyn = parseDynamicTypeAnnouncement(open);
  return (
    <section className="panel">
      <div className="section-head">
        <h2>Cập nhật hệ thống & Mẫu yêu cầu Dynamic mới</h2>
      </div>
      <ResourceState resource={r}>
        {r.data.items.map((a) => {
          const dyn = parseDynamicTypeAnnouncement(a);
          const markAndOpenTemplate = () => {
            if (!a.read_at) {
              api(`/api/v1/announcements/${a.id}/read`, { method: "POST", body: "{}", silent: true })
                .then(() => r.reload())
                .catch(() => {});
            }
            if (dyn?.typeCode) {
              openTemplateInCatalog(dyn.typeCode, onOpenTemplate);
            }
          };
          return (
            <article className={`notification ${a.read_at ? "is-read" : "is-unread"}`} key={a.id}>
              <div>
                <strong>
                  {dyn
                    ? `${dyn.createdByName} đã tạo mẫu yêu cầu mới «${dyn.typeName}» (${dyn.typeCode})`
                    : a.title}
                </strong>
                {dyn && (
                  <p style={{ margin: "4px 0", fontSize: "13px" }}>
                    Người tạo: <strong>{dyn.createdByName}</strong>
                    {dyn.createdByEmail ? ` (${dyn.createdByEmail})` : ""} · Mã mẫu: <code>{dyn.typeCode}</code>
                  </p>
                )}
                <p className="muted">
                  {date(a.created_at)} · {a.read_at ? "Đã đọc" : "Chưa đọc"}
                </p>
              </div>
              <div className="actions">
                {dyn?.typeCode && (
                  <button type="button" onClick={markAndOpenTemplate}>
                    Xem mẫu yêu cầu →
                  </button>
                )}
                <button type="button" className="secondary" onClick={() => setOpen(a)}>
                  Xem chi tiết
                </button>
              </div>
            </article>
          );
        })}
      </ResourceState>
      {open && (
        <Modal title={open.title} onClose={() => setOpen(null)}>
          <UpdateBody item={open} />
          {openDyn?.typeCode && (
            <div className="actions" style={{ marginTop: "12px" }}>
              <button
                type="button"
                onClick={() => {
                  const targetCode = openDyn.typeCode;
                  setOpen(null);
                  openTemplateInCatalog(targetCode, onOpenTemplate);
                }}
              >
                Xem mẫu yêu cầu «{openDyn.typeCode}» →
              </button>
            </div>
          )}
        </Modal>
      )}
    </section>
  );
}

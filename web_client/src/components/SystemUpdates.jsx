import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Modal, useResource, ResourceState } from "./ui.jsx";
import { date } from "../domain.js";

function UpdateBody({ item }) {
  return (
    <div className="system-update">
      <p>{item.summary}</p>
      {item.changes?.length > 0 && (
        <>
          <h3>Thay đổi</h3>
          <ul>
            {item.changes.map((c, i) => (
              <li key={i}>{c.title}</li>
            ))}
          </ul>
        </>
      )}
      {item.guidance?.length > 0 && (
        <>
          <h3>Hướng dẫn thao tác theo quy trình mới</h3>
          {item.guidance.map((g, i) => (
            <div key={i}>
              <strong>{g.title}</strong>
              <ol>
                {g.steps.map((step, j) => (
                  <li key={j}>{step}</li>
                ))}
              </ol>
            </div>
          ))}
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
  const acknowledge = () => {
    api(`/api/v1/announcements/${current.id}/read`, { method: "POST", body: "{}", silent: true }).catch(() => {});
    setQueue((q) => q.slice(1));
  };
  return (
    <Modal key={current.id} title={current.title} onClose={acknowledge}>
      <UpdateBody item={current} />
      <div className="actions">
        <button type="button" onClick={acknowledge}>
          Đã hiểu{queue.length > 1 ? ` (còn ${queue.length - 1})` : ""}
        </button>
      </div>
    </Modal>
  );
}

/** History of system updates, shown on the notifications page. */
export function SystemUpdateHistory() {
  const r = useResource("/api/v1/announcements");
  const [open, setOpen] = useState(null);
  if (!r.data?.items?.length) return null;
  return (
    <section className="panel">
      <div className="section-head">
        <h2>Cập nhật hệ thống</h2>
      </div>
      <ResourceState resource={r}>
        {r.data.items.map((a) => (
          <article className="notification" key={a.id}>
            <div>
              <strong>{a.title}</strong>
              <p className="muted">
                {date(a.created_at)} · {a.read_at ? "Đã đọc" : "Chưa đọc"}
              </p>
            </div>
            <div className="actions">
              <button type="button" className="secondary" onClick={() => setOpen(a)}>
                Xem chi tiết
              </button>
            </div>
          </article>
        ))}
      </ResourceState>
      {open && (
        <Modal title={open.title} onClose={() => setOpen(null)}>
          <UpdateBody item={open} />
        </Modal>
      )}
    </section>
  );
}

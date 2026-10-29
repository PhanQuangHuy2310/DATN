import { activityLabel } from "../activityLabels.js";
import { date } from "../domain.js";
import { ResourceState, useResource } from "./ui.jsx";

/** Authorized audit history: displays workflow transitions without raw JSON boxes. */
export default function ActivityTimeline({ id }) {
  const resource = useResource(`/api/v1/requests/${id}/audit`);
  const items = [...(resource.data?.items || [])].reverse();
  return (
    <section className="activity-timeline-section" aria-label="Dòng thời gian xử lý hồ sơ">
      <div className="section-head activity-timeline-heading">
        <div><h2>Dòng thời gian xử lý</h2><p className="muted">Cập nhật mới nhất ở trên, lưu từ nhật ký bất biến của hồ sơ.</p></div>
        <button type="button" className="secondary" onClick={resource.reload}>Cập nhật</button>
      </div>
      <ResourceState resource={resource}>
        {items.length ? (
          <ol className="activity-timeline">
            {items.map((event) => (
              <li key={event.id}>
                <div className="activity-timeline-point" aria-hidden="true" />
                <div className="activity-timeline-event">
                  <strong>{activityLabel(event.action)}</strong>
                  <small>{date(event.occurred_at)} · {event.actor_kind === "SYSTEM" ? "Hệ thống" : "Người tham gia"} · Bước {event.seq}</small>
                  {typeof event.details?.reason === "string" && event.details.reason && (
                    <p>{event.details.reason}</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        ) : <p className="empty">Chưa có hoạt động được ghi nhận.</p>}
      </ResourceState>
    </section>
  );
}

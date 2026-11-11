import { useState } from "react";
import { api } from "../api.js";
import { date } from "../domain.js";
import { EmptyState, PageHeader } from "./design.jsx";
import { ActionForm, ResourceState, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";

import { formatNotificationLabel } from "./notificationLabels.js";

export function Notifications({ onOpen }) {
  const [offset, setOffset] = useState(0),
    [limit, setLimit] = useState(20),
    [unread, setUnread] = useState(false);
  const r = useResource(
    `/api/v1/notifications?limit=${limit}&offset=${offset}&unread=${unread}`,
  );
  const unreadCount = Number(r.data?.unread_count) || 0;

  return (
    <div className="client-section">
      <PageHeader
        eyebrow="CẬP NHẬT HỆ THỐNG"
        title="Trung tâm thông báo"
        description="Theo dõi các thông báo phê duyệt, thực hiện, nghiệm thu và nhắc hạn xử lý dành cho bạn."
        action={
          <button
            type="button"
            className="secondary"
            onClick={r.reload}
            disabled={r.refreshing}
          >
            Làm mới
          </button>
        }
      />
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Danh sách thông báo</h2>
            <small className="muted">
              {unreadCount > 0
                ? `Bạn có ${unreadCount} thông báo chưa đọc`
                : "Tất cả thông báo đã được đọc"}
            </small>
          </div>
          <label className="inline ds-unread-toggle">
            <input
              type="checkbox"
              checked={unread}
              onChange={(e) => {
                setUnread(e.target.checked);
                setOffset(0);
              }}
            />{" "}
            Chỉ hiển thị chưa đọc
          </label>
        </div>
        <ResourceState resource={r}>
          {r.data?.items?.length ? (
            <div className="ds-notification-list">
              {r.data.items.map((n) => (
                <article
                  className={`notification ${n.read_at ? "is-read" : "is-unread"}`}
                  key={n.id}
                >
                  <div className="ds-notification-main">
                    <div className="ds-notification-title-row">
                      {!n.read_at && <span className="ds-unread-dot" aria-hidden="true" />}
                      <strong>{formatNotificationLabel(n.label)}</strong>
                    </div>
                    <p className="muted">
                      {date(n.created_at)} · {n.read_at ? "Đã đọc" : "Chưa đọc"}
                    </p>
                  </div>
                  <div className="actions">
                    {n.request_id && onOpen && (
                      <button
                        type="button"
                        className="secondary"
                        onClick={async () => {
                          if (!n.read_at) {
                            await api(`/api/v1/notifications/${n.id}/read`, {
                              method: "POST",
                              silent: true,
                            }).catch(() => {});
                            r.reload();
                          }
                          onOpen(n.request_id);
                        }}
                      >
                        Mở hồ sơ →
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
            </div>
          ) : (
            <EmptyState
              title={unread ? "Không có thông báo chưa đọc" : "Chưa có thông báo nào"}
              description="Khi có hồ sơ mới cần bạn xử lý hoặc có cập nhật từ người duyệt, thông báo sẽ xuất hiện tại đây."
            />
          )}
          <PageControls
            offset={offset}
            limit={limit}
            nextOffset={r.data?.next_offset}
            count={r.data?.items?.length || 0}
            title="thông báo"
            onPage={setOffset}
            onLimit={setLimit}
          />
        </ResourceState>
      </section>
    </div>
  );
}

export default Notifications;


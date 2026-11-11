import { useState } from "react";
import { api } from "../api.js";
import { date } from "../domain.js";
import { EmptyState, PageHeader } from "./design.jsx";
import { ActionForm, ResourceState, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";

const EVENT_NOTIFICATION_LABELS = {
  REQUEST_SUBMITTED: "Có hồ sơ yêu cầu mới vừa được gửi phê duyệt",
  APPROVAL_APPROVE: "Hồ sơ đã được phê duyệt ở bước hiện tại",
  APPROVAL_REJECT: "Hồ sơ yêu cầu đã bị từ chối",
  APPROVAL_NEEDS_INFO: "Người phê duyệt yêu cầu bổ sung thêm thông tin",
  AI_AUTO_APPROVED: "Hồ sơ đã được AI phê duyệt tự động theo quy chế",
  AI_AUTO_APPROVAL_REVOKED: "Quyết định duyệt tự động của AI đã được thu hồi để xét duyệt lại",
  DELEGATION_APPLIED: "Bạn nhận được hồ sơ chuyển tiếp theo ủy quyền phê duyệt",
  EXECUTION_STARTED: "Công việc thực hiện trên hồ sơ đã được tiếp nhận",
  EXECUTION_RESULT_SUBMITTED: "Kết quả thực hiện đã được nộp và chờ nghiệm thu",
  EXECUTION_ISSUE_BLOCKED: "Người thực hiện báo cáo vướng mắc phát sinh",
  EXECUTION_ISSUE_UNABLE_TO_CLAIM: "Người thực hiện báo không thể tiếp nhận công việc",
  ACCEPTANCE_ACCEPT: "Hồ sơ đã được nghiệm thu hoàn tất",
  ACCEPTANCE_REWORK: "Người nghiệm thu yêu cầu thực hiện lại công việc",
  REQUEST_CANCELLED: "Hồ sơ yêu cầu đã bị hủy bởi người tạo",
  ACTOR_REASSIGNED: "Bạn vừa được phân công xử lý hồ sơ",
  SLA_REMINDER: "Nhắc hạn xử lý hồ sơ sắp đến hạn SLA",
  SLA_BREACH: "Cảnh báo hồ sơ đã quá thời hạn xử lý SLA",
};

export function formatNotificationLabel(label) {
  if (!label) return "Thông báo cập nhật hồ sơ";
  const trimmed = String(label).trim();
  if (EVENT_NOTIFICATION_LABELS[trimmed]) return EVENT_NOTIFICATION_LABELS[trimmed];
  return trimmed;
}

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


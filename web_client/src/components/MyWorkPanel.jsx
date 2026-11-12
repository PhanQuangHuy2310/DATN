import { useState } from "react";
import { date } from "../domain.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";

const OPEN = new Set(["PENDING_APPROVAL", "NEEDS_INFO", "READY_FOR_EXECUTION", "IN_PROGRESS", "WAITING_FOR_ACCEPTANCE"]);

/** Work queues the signed-in employee owns, by role. Uses the same
 * /api/v1/requests tabs as the request hub, so scope stays server-enforced. */
const QUEUES = [
  { key: "approval", role: "APPROVER", label: "Chờ tôi phê duyệt", query: "tab=approval", empty: "Không có hồ sơ nào chờ bạn phê duyệt." },
  { key: "execution", role: "EXECUTOR", label: "Việc cần thực hiện", query: "tab=execution", empty: "Không có công việc nào đang giao cho bạn." },
  { key: "acceptance", role: "ACCEPTOR", label: "Chờ tôi nghiệm thu", query: "tab=acceptance", empty: "Không có kết quả nào chờ bạn nghiệm thu." },
  { key: "needs-info", role: "REQUESTER", label: "Đơn cần bổ sung", query: "tab=mine&status=NEEDS_INFO", empty: "Không có đơn nào cần bạn bổ sung thông tin." },
  { key: "mine-open", role: "REQUESTER", label: "Đơn đang chờ xử lý", query: "tab=mine", open: true, empty: "Bạn không có đơn nào đang chờ người khác xử lý." },
  // Read-only: the default list is already limited to the auditor's granted scope.
  { key: "audit", role: "AUDITOR", label: "Trong phạm vi kiểm toán", query: "", open: true, page: "audit", empty: "Chưa có hồ sơ đang mở trong phạm vi kiểm toán của bạn." },
];

function useQueue(queue, enabled) {
  const res = useResource(enabled ? `/api/v1/requests?${queue.query}&limit=50&offset=0` : "");
  const all = res.data?.items || [];
  const items = (queue.open ? all.filter((i) => OPEN.has(i.status) && i.status !== "NEEDS_INFO") : all)
    .slice()
    .sort((a, b) => Number(b.overdue) - Number(a.overdue) || String(a.due_at || "9").localeCompare(String(b.due_at || "9")));
  const more = res.data?.next_offset !== null && res.data?.next_offset !== undefined;
  return { res, items, more, overdue: items.filter((i) => i.overdue).length };
}

function dueText(item) {
  if (!item.due_at) return "Không áp dụng hạn";
  const hours = (Date.parse(item.due_at) - Date.now()) / 3600000;
  if (item.overdue || hours < 0) return `Quá hạn ${Math.max(1, Math.round(-hours))} giờ`;
  if (hours < 24) return `Còn ${Math.max(1, Math.round(hours))} giờ`;
  return `Hạn ${date(item.due_at)}`;
}

function QueueTab({ queue, data, active, onSelect }) {
  const count = data.res.data ? `${data.items.length}${data.more ? "+" : ""}` : "…";
  return <button type="button" role="tab" aria-selected={active} className={`mywork-tab ${active ? "is-active" : ""}`} onClick={onSelect}>
    <span className="mywork-tab-label">{queue.label}</span>
    <span className="mywork-tab-count">{count}</span>
    {data.overdue > 0 && <span className="mywork-tab-overdue">{data.overdue} quá hạn</span>}
  </button>;
}

function QueueList({ queue, data, onOpen, onShowAll }) {
  const rows = data.items.slice(0, 6);
  return <ResourceState resource={data.res}>
    {rows.length ? <ul className="mywork-list">{rows.map((item) => <li key={item.id}>
      <button type="button" className="mywork-row" onClick={() => onOpen(item.id)}>
        <span className="mywork-main">
          <strong>{item.title || item.type_name}</strong>
          <small>{item.code} · {item.type_name}{queue.key === "mine-open" || queue.key === "audit" ? ` · đang ở ${item.current_assignee_name || "hệ thống"}` : ` · ${item.requester_name}`}</small>
        </span>
        <Badge value={item.status} />
        <span className={`mywork-due ${item.overdue ? "is-overdue" : ""}`}>{dueText(item)}</span>
        <span aria-hidden="true" className="mywork-go">→</span>
      </button>
    </li>)}</ul> : <p className="muted mywork-empty">{queue.empty}</p>}
    {(data.items.length > rows.length || queue.page) && <button type="button" className="link" onClick={onShowAll}>{queue.page ? "Mở trang tra cứu & xác minh kiểm toán →" : `Xem tất cả ${data.items.length}${data.more ? "+" : ""} hồ sơ →`}</button>}
  </ResourceState>;
}

export default function MyWorkPanel({ user, onOpen, navigate }) {
  const roles = new Set(user?.roles || []);
  // One hook per known queue, always in the same order; queues the user has
  // no role for get an empty URL and never call the API.
  const approval = useQueue(QUEUES[0], roles.has(QUEUES[0].role));
  const execution = useQueue(QUEUES[1], roles.has(QUEUES[1].role));
  const acceptance = useQueue(QUEUES[2], roles.has(QUEUES[2].role));
  const needsInfo = useQueue(QUEUES[3], roles.has(QUEUES[3].role));
  const mineOpen = useQueue(QUEUES[4], roles.has(QUEUES[4].role));
  const audit = useQueue(QUEUES[5], roles.has(QUEUES[5].role));
  const data = { approval, execution, acceptance, "needs-info": needsInfo, "mine-open": mineOpen, audit };
  const queues = QUEUES.filter((q) => roles.has(q.role));
  const [picked, setPicked] = useState(null);
  if (!queues.length) return null;
  const current = queues.find((q) => q.key === picked) || queues.find((q) => data[q.key].items.length) || queues[0];
  return <section className="panel mywork" aria-label="Việc cần bạn xử lý">
    <div className="section-head"><h2>Việc cần bạn xử lý</h2></div>
    <div className="mywork-tabs" role="tablist" aria-label="Hàng đợi công việc">
      {queues.map((q) => <QueueTab key={q.key} queue={q} data={data[q.key]} active={q.key === current.key} onSelect={() => setPicked(q.key)} />)}
    </div>
    <QueueList queue={current} data={data[current.key]} onOpen={onOpen} onShowAll={() => navigate?.(current.page || "requests")} />
  </section>;
}

import { useEffect, useMemo, useState } from "react";
import { date, statuses, types } from "../domain.js";
import { formatVnd } from "../formatters.js";
import { Badge, ResourceState, useResource } from "./ui.jsx";
import { EmptyState, TableSkeleton } from "./design.jsx";
import { PageControls } from "./ux.jsx";
import { ClientPageHeader, ClientFilterSection } from "./clientDesign.jsx";
import {
  WORKFLOW_COLUMNS,
  allowedStages,
  requestStage,
  STATUS_STAGES,
} from "../clientWorkflow.js";

const STAGE_TITLES = {
  ...Object.fromEntries(WORKFLOW_COLUMNS.map((stage) => [stage.key, stage.title])),
  rejected: "Từ chối",
  cancelled: "Đã hủy",
};

function dayBoundary(day, end = false) {
  return day ? `${day}T${end ? "23:59:59" : "00:00:00"}+07:00` : "";
}

function RequestEntry({ item, onOpen, names }) {
  const typeLabel =
    item.type_name || names[item.type_code] || types[item.type_code] || "Yêu cầu";
  const displayTitle = item.title || typeLabel;
  return (
    <article className="client-request-entry">
      <div className="client-request-entry-head">
        <span className="ds-code-pill">{item.code || "Mới tạo"}</span>
        <Badge value={item.status} />
      </div>
      <strong className="client-request-entry-title">{displayTitle}</strong>
      <p className="muted client-request-entry-meta">
        {typeLabel}
        {item.amount_vnd > 0 ? ` · ${formatVnd(item.amount_vnd)}` : ""}
      </p>
      {item.requester_name && (
        <p className="client-request-sender">
          Người gửi: <strong>{item.requester_name}</strong>
          {item.department_name ? ` · ${item.department_name}` : ""}
        </p>
      )}
      {item.current_assignee_name && (
        <p className="client-request-assignee">
          Đang xử lý: <strong>{item.current_assignee_name}</strong>
        </p>
      )}
      {item.due_at && (
        <p
          className={
            item.overdue ? "client-request-due overdue" : "client-request-due"
          }
        >
          {item.overdue ? "Quá hạn: " : "Hạn xử lý: "}
          {date(item.due_at)}
        </p>
      )}
      <div className="client-request-entry-foot">
        <small>Cập nhật {date(item.updated_at)}</small>
        <button type="button" className="link" onClick={() => onOpen(item.id)}>
          Xem chi tiết →
        </button>
      </div>
    </article>
  );
}

export default function ClientRequests({
  user,
  onOpen,
  onNew,
  revision,
  initialQuery = "",
  initialStage = "mine",
}) {
  const stages = allowedStages(user);
  const [stage, setStage] = useState(() =>
    stages.some((x) => x.key === initialStage)
      ? initialStage
      : stages[0]?.key || "mine",
  );
  const [mode, setMode] = useState("table");
  const [search, setSearch] = useState(initialQuery);
  const [debounced, setDebounced] = useState(initialQuery);
  const [type, setType] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  // Work queues open with the most urgent items first; "Yêu cầu của tôi" by recency.
  const [sort, setSort] = useState(initialStage === "mine" ? "newest" : "urgent");
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [prevQuery, setPrevQuery] = useState(initialQuery);

  if (prevQuery !== initialQuery) {
    setPrevQuery(initialQuery);
    setSearch(initialQuery);
    setDebounced(initialQuery.trim());
    setOffset(0);
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setOffset(0);
    }, 320);
    return () => clearTimeout(timer);
  }, [search]);

  const active = stages.find((x) => x.key === stage) || stages[0];
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    tab: active?.filter || "mine",
  });
  if (debounced) params.set("q", debounced);
  if (type) params.set("type_code", type);
  if (departmentId) params.set("department_id", departmentId);
  if (status || active?.status) params.set("status", active?.status || status);
  if (from) params.set("created_from", dayBoundary(from));
  if (to) params.set("created_to", dayBoundary(to, true));

  const result = useResource(
    `/api/v1/requests?${params.toString()}&_revision=${revision}`,
  );
  const catalog = useResource("/api/v1/request-types");
  const departmentOptions = useResource("/api/v1/meta/departments");
  const departments = departmentOptions.data?.items || [];
  const names = Object.fromEntries(
    (catalog.data?.items || []).map((item) => [item.code, item.name]),
  );

  const rows = useMemo(() => {
    const items = [...(result.data?.items || [])];
    items.sort((a, b) => {
      if (sort === "urgent") {
        // Overdue first, then nearest due date; items without a deadline last.
        if (Boolean(a.overdue) !== Boolean(b.overdue)) return a.overdue ? -1 : 1;
        const dueA = Date.parse(a.due_at) || Infinity;
        const dueB = Date.parse(b.due_at) || Infinity;
        if (dueA !== dueB) return dueA - dueB;
      }
      const da =
        Date.parse(
          sort === "oldest"
            ? a.created_at || a.updated_at
            : a.updated_at || a.created_at,
        ) || 0;
      const db =
        Date.parse(
          sort === "oldest"
            ? b.created_at || b.updated_at
            : b.updated_at || b.created_at,
        ) || 0;
      return sort === "oldest" ? da - db : db - da;
    });
    return items;
  }, [result.data, sort]);

  const columns = stage === "mine" ? STATUS_STAGES : [stage];

  function reset() {
    setSearch("");
    setDebounced("");
    setType("");
    setDepartmentId("");
    setStatus("");
    setFrom("");
    setTo("");
    setSort("newest");
    setOffset(0);
  }

  return (
    <div className="client-requests">
      <ClientPageHeader
        eyebrow="KHÔNG GIAN LÀM VIỆC"
        title={stage === "mine" ? "Yêu cầu của tôi" : active?.title || "Danh sách hồ sơ"}
        description="Theo dõi đầy đủ tiêu đề đề xuất, người gửi, phòng ban, người đang phụ trách và hạn SLA của từng hồ sơ."
        action={
          (
            user?.permissions?.by_module?.requests_workflows
              ? Boolean(user.permissions.by_module.requests_workflows.can_create)
              : user.roles.includes("REQUESTER")
          ) ? (
            <button type="button" onClick={onNew}>
              ＋ Tạo yêu cầu mới
            </button>
          ) : null
        }
      />
      <nav className="client-stage-tabs" aria-label="Các bước xử lý yêu cầu">
        {stages.map((s) => (
          <button
            type="button"
            key={s.key}
            aria-current={stage === s.key ? "page" : undefined}
            aria-pressed={stage === s.key}
            className={stage === s.key ? "is-active" : ""}
            onClick={() => {
              setStage(s.key);
              setOffset(0);
              setStatus("");
            }}
          >
            {s.title}
          </button>
        ))}
      </nav>
      <ClientFilterSection
        advanced
        activeAdvancedCount={Number(Boolean(departmentId)) + Number(Boolean(status)) + Number(Boolean(from)) + Number(Boolean(to)) + Number(sort !== (stage === "mine" ? "newest" : "urgent"))}
        footer={
          <>
            <small className="muted client-result-summary" aria-live="polite">
              {active?.help || "Danh sách hồ sơ theo quyền được cấp"} · Hiển thị{" "}
              <strong>{rows.length}</strong> hồ sơ
            </small>
            <div className="actions">
              <button className="secondary" type="button" onClick={reset}>
                Đặt lại bộ lọc
              </button>
              <button className="secondary" type="button" onClick={result.reload}>
                Làm mới
              </button>
              <div
                className="client-view-toggle"
                role="group"
                aria-label="Kiểu hiển thị"
              >
                <button
                  type="button"
                  className={mode === "kanban" ? "is-active" : ""}
                  aria-pressed={mode === "kanban"}
                  onClick={() => setMode("kanban")}
                >
                  Bảng cột
                </button>
                <button
                  type="button"
                  className={mode === "table" ? "is-active" : ""}
                  aria-pressed={mode === "table"}
                  onClick={() => setMode("table")}
                >
                  Danh sách
                </button>
              </div>
            </div>
          </>
        }
      >
        <label>
          Tìm kiếm hồ sơ
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Mã REQ, tiêu đề đơn, tên người gửi…"
          />
        </label>
        <label>
          Loại yêu cầu
          <select
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">Tất cả loại yêu cầu</option>
            {(catalog.data?.items || []).map((t) => (
              <option key={t.code} value={t.code}>
                {t.name || types[t.code] || "Loại yêu cầu"}
              </option>
            ))}
          </select>
        </label>
        {departments.length > 1 && (
          <label>
            Phòng ban gửi
            <select
              value={departmentId}
              onChange={(e) => {
                setDepartmentId(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Tất cả phòng ban</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Trạng thái
          <select
            value={active?.status || status}
            disabled={Boolean(active?.status)}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">Tất cả trạng thái</option>
            {Object.entries(statuses).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Từ ngày
          <input
            type="date"
            value={from}
            max={to || undefined}
            onChange={(e) => {
              setFrom(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Đến ngày
          <input
            type="date"
            value={to}
            min={from || undefined}
            onChange={(e) => {
              setTo(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Sắp xếp
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="urgent">Ưu tiên xử lý (quá hạn, sắp đến hạn)</option>
            <option value="newest">Cập nhật mới nhất</option>
            <option value="oldest">Ngày tạo cũ trước</option>
          </select>
        </label>
      </ClientFilterSection>

      <ResourceState resource={result} skeleton={<TableSkeleton rows={5} cols={6} />}>
        <div id="client-request-results">
          {rows.length === 0 ? (
            <section className="panel">
              <EmptyState
                title="Chưa có hồ sơ phù hợp"
                description="Thử đặt lại bộ lọc tìm kiếm hoặc chuyển sang giai đoạn công việc khác."
              />
            </section>
          ) : mode === "kanban" ? (
            <div className="client-kanban" aria-label="Bảng tiến trình xử lý">
              {columns.map((column) => {
                const colItems = rows.filter(
                  (r) => requestStage(r.status) === column,
                );
                return (
                  <section key={column} className="client-kanban-column">
                    <h2>
                      {STAGE_TITLES[column]} <span>{colItems.length}</span>
                    </h2>
                    <div className="client-kanban-cards">
                      {colItems.map((item) => (
                        <RequestEntry
                          key={item.id}
                          item={item}
                          onOpen={onOpen}
                          names={names}
                        />
                      ))}
                      {!colItems.length && (
                        <p className="muted client-empty-column">
                          Chưa có hồ sơ ở cột này
                        </p>
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
          ) : (
            <section className="panel table-panel">
              <div className="table-wrap">
                <table className="responsive-records">
                  <thead>
                    <tr>
                      <th>Mã hồ sơ</th>
                      <th>Tiêu đề & Nghiệp vụ</th>
                      <th>Người gửi / Phòng ban</th>
                      <th>Trạng thái</th>
                      <th>Người đang xử lý</th>
                      <th>Hạn xử lý</th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((item) => {
                      const typeLabel =
                        item.type_name ||
                        names[item.type_code] ||
                        types[item.type_code] ||
                        "Yêu cầu";
                      return (
                        <tr
                          key={item.id}
                          className={item.overdue ? "is-overdue" : undefined}
                        >
                          <td data-label="Mã hồ sơ" className="request-code">
                            {item.code}
                          </td>
                          <td data-label="Tiêu đề & Nghiệp vụ">
                            <strong>{item.title || typeLabel}</strong>
                            <small className="ds-cell-sub">
                              {typeLabel}
                              {item.amount_vnd > 0
                                ? ` · ${formatVnd(item.amount_vnd)}`
                                : ""}
                            </small>
                          </td>
                          <td data-label="Người gửi / Phòng ban">
                            <span>{item.requester_name || "—"}</span>
                            {item.department_name && (
                              <small className="ds-cell-sub">
                                {item.department_name}
                              </small>
                            )}
                          </td>
                          <td data-label="Trạng thái">
                            <Badge value={item.status} />
                          </td>
                          <td data-label="Người đang xử lý">
                            {item.current_assignee_name || "—"}
                          </td>
                          <td
                            data-label="Hạn xử lý"
                            className={item.overdue ? "overdue" : ""}
                          >
                            {item.due_at ? date(item.due_at) : "—"}
                            <small className="ds-cell-sub">
                              Cập nhật {date(item.updated_at)}
                            </small>
                          </td>
                          <td data-label="Thao tác">
                            <button
                              type="button"
                              className="link"
                              onClick={() => onOpen(item.id)}
                            >
                              Xem chi tiết →
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          <PageControls
            offset={offset}
            limit={limit}
            nextOffset={result.data?.next_offset}
            count={rows.length}
            title="hồ sơ"
            targetId="client-request-results"
            onPage={setOffset}
            onLimit={setLimit}
          />
        </div>
      </ResourceState>
    </div>
  );
}

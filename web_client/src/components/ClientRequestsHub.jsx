import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { ApiBaseContext, WORKSPACE_API } from "../apiBase.js";
import { date } from "../domain.js";
import { usePermission } from "../hooks/usePermission.jsx";
import ClientRequests from "./ClientRequests.jsx";
import {
  CardGridSkeleton,
  EmptyState,
  PageHeader,
  PageTabs,
  TableSkeleton,
} from "./design.jsx";
import { Badge, ResourceState, useResource } from "./ui.jsx";

const WorkflowDiagrams = lazy(() => import("./WorkflowDiagrams.jsx"));
const RequestWorkflowsPage = lazy(() => import("./RequestWorkflowsPage.jsx"));
const AiProcessGuide = lazy(() => import("./AiProcessGuide.jsx"));

const STAGES = [
  ["YEU_CAU", "1. Yêu cầu"],
  ["PHE_DUYET", "2. Phê duyệt"],
  ["THUC_HIEN", "3. Thực hiện"],
  ["NGHIEM_THU", "4. Nghiệm thu"],
  ["HOAN_THANH", "5. Hoàn thành"],
];
const STAGE_SUMMARY_KEYS = {
  YEU_CAU: "stage_1_yeu_cau",
  PHE_DUYET: "stage_2_phe_duyet",
  THUC_HIEN: "stage_3_thuc_hien",
  NGHIEM_THU: "stage_4_nghiem_thu",
  HOAN_THANH: "stage_5_hoan_thanh",
};
const QUEUE_ROLES = {
  APPROVER: "approval",
  EXECUTOR: "execution",
  ACCEPTOR: "acceptance",
};

/** Request templates with their lifecycle, SLA, steps and linked integrations.
 * A template whose integration is switched off by the admin cannot be used. */
function CatalogTab({ onNew }) {
  const catalog = useResource(`${WORKSPACE_API}/request-catalog`);
  const reloadCatalog = catalog.reload;
  useEffect(() => {
    reloadCatalog();
    const timer = setInterval(reloadCatalog, 15000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload is recreated each render
  }, []);
  const { canCreate } = usePermission("requests_workflows");
  const [query, setQuery] = useState("");
  const [lifecycle, setLifecycle] = useState("ALL");
  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (catalog.data?.items || []).filter(
      (t) =>
        (lifecycle === "ALL" || t.category_code === lifecycle) &&
        (!q ||
          t.name.toLowerCase().includes(q) ||
          (t.request_type || "").toLowerCase().includes(q)),
    );
  }, [catalog.data, query, lifecycle]);

  return (
    <ResourceState resource={catalog} skeleton={<CardGridSkeleton count={6} />}>
      <div className="panel client-filter-toolbar" style={{ marginBottom: 16 }}>
        <div className="client-filter-fields">
          <label>
            Tìm mẫu yêu cầu
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Nhập tên biểu mẫu hoặc nhóm nghiệp vụ…"
            />
          </label>
          <label>
            Phân loại quy trình
            <select value={lifecycle} onChange={(e) => setLifecycle(e.target.value)}>
              <option value="ALL">Tất cả phân loại (A, B, C)</option>
              <option value="A">Loại A — Chỉ phê duyệt</option>
              <option value="B">Loại B — Phê duyệt & Thực hiện</option>
              <option value="C">Loại C — Phê duyệt, Thực hiện & Nghiệm thu</option>
            </select>
          </label>
        </div>
      </div>
      {items.length === 0 ? (
        <section className="panel">
          <EmptyState
            title="Không tìm thấy biểu mẫu phù hợp"
            description="Thử nhập từ khóa khác hoặc chọn tất cả phân loại quy trình."
          />
        </section>
      ) : (
        <div className="request-catalog-grid">
          {items.map((t) => (
            <article
              key={t.code}
              className={`panel request-catalog-card${t.is_api_enabled ? "" : " is-unavailable"}`}
            >
              <div className="section-head">
                <h3 style={{ margin: 0 }}>{t.name}</h3>
                <span className={`badge badge-cat-${t.category_code.toLowerCase()}`}>
                  Loại {t.category_code}
                </span>
              </div>
              <p className="muted" style={{ margin: "4px 0" }}>
                {t.request_type} · Cam kết SLA:{" "}
                {t.sla_hours ? `${t.sla_hours} giờ` : "Theo quy chế"}
              </p>
              <ol className="request-catalog-steps">
                {t.workflow_steps.map((s) => (
                  <li key={s.step}>
                    <strong>{s.name}</strong>{" "}
                    <small className="muted">({s.actor})</small>
                  </li>
                ))}
              </ol>
              {t.linked_apis.length > 0 && (
                <p className="muted" style={{ fontSize: 12 }}>
                  Hệ thống tích hợp:{" "}
                  {t.linked_apis
                    .map(
                      (a) =>
                        `${a.source_system}${a.is_enabled ? "" : " (đang tạm ngắt)"}`,
                    )
                    .join(", ")}
                </p>
              )}
              {!t.is_api_enabled && (
                <p className="request-catalog-warning" role="alert">
                  {t.unavailable_notice}
                </p>
              )}
              {canCreate && (
                <button
                  type="button"
                  className="primary"
                  disabled={!t.is_api_enabled}
                  title={t.is_api_enabled ? undefined : t.unavailable_notice}
                  onClick={() => onNew({ type_code: t.code })}
                >
                  Tạo yêu cầu →
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </ResourceState>
  );
}

/** Every request the user takes part in, filtered by the 5 business stages. */
function StageBoardTab({ onOpen, revision }) {
  const board = useResource(`${WORKSPACE_API}/my-requests?r=${revision}`);
  const [stage, setStage] = useState("ALL");
  const [search, setSearch] = useState("");
  const summary = board.data?.summary || {};
  const needle = search.trim().toLocaleLowerCase("vi-VN");
  const rows = (board.data?.items || []).filter(
    (r) =>
      (stage === "ALL" || r.current_stage === stage) &&
      (!needle ||
        `${r.request_code || ""} ${r.title || ""} ${r.request_type || ""} ${r.user_role_in_request || ""}`
          .toLocaleLowerCase("vi-VN")
          .includes(needle)),
  );

  return (
    <ResourceState resource={board} skeleton={<TableSkeleton rows={5} cols={7} />}>
      <div className="stage-filter-row" role="group" aria-label="Lọc theo giai đoạn">
        <button
          type="button"
          aria-pressed={stage === "ALL"}
          className={stage === "ALL" ? "stage-chip is-active" : "stage-chip"}
          onClick={() => setStage("ALL")}
        >
          Tất cả <strong>{summary.total_requests ?? 0}</strong>
        </button>
        {STAGES.map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={stage === key}
            className={stage === key ? "stage-chip is-active" : "stage-chip"}
            onClick={() => setStage(key)}
          >
            {label} <strong>{summary[STAGE_SUMMARY_KEYS[key]] ?? 0}</strong>
          </button>
        ))}
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <label style={{ display: "grid", gap: 6, maxWidth: 420, fontSize: 13, fontWeight: 600 }}>
          Lọc nhanh theo mã hoặc tiêu đề hồ sơ
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nhập mã REQ hoặc tiêu đề…"
          />
        </label>
      </div>

      {rows.length === 0 ? (
        <section className="panel">
          <EmptyState
            title="Chưa có hồ sơ ở giai đoạn này"
            description="Các hồ sơ bạn tạo, phê duyệt, thực hiện hoặc nghiệm thu sẽ hiển thị đầy đủ tại đây."
          />
        </section>
      ) : (
        <section className="panel table-panel">
          <div className="table-wrap">
            <table className="responsive-records">
              <thead>
                <tr>
                  <th>Mã hồ sơ</th>
                  <th>Tiêu đề yêu cầu</th>
                  <th>Nghiệp vụ</th>
                  <th>Giai đoạn</th>
                  <th>Trạng thái</th>
                  <th>Vai trò của bạn</th>
                  <th>Ngày tạo</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.request_id}>
                    <td data-label="Mã hồ sơ">
                      <button
                        type="button"
                        className="link"
                        onClick={() => onOpen(r.request_id)}
                      >
                        <strong>{r.request_code}</strong>
                      </button>
                    </td>
                    <td data-label="Tiêu đề yêu cầu">
                      <strong>{r.title || r.request_type}</strong>
                    </td>
                    <td data-label="Nghiệp vụ">
                      {r.request_type}{" "}
                      <small className="muted">(Loại {r.category_code})</small>
                    </td>
                    <td data-label="Giai đoạn">{r.current_stage_label}</td>
                    <td data-label="Trạng thái">
                      <Badge value={r.final_status} />
                    </td>
                    <td data-label="Vai trò của bạn">{r.user_role_in_request}</td>
                    <td data-label="Ngày tạo">{date(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </ResourceState>
  );
}

export default function ClientRequestsHub({
  user,
  onOpen,
  onNew,
  revision,
  initialTab = "catalog",
}) {
  const perms = usePermission("requests_workflows");
  const canConfigure = perms.canUpdate || perms.canDelete;
  const queue = Object.entries(QUEUE_ROLES).find(([role]) =>
    user.roles.includes(role),
  )?.[1];
  const tabs = [
    ["catalog", "Tạo yêu cầu mới"],
    ["board", "Theo dõi 5 giai đoạn"],
    ...(user.roles.includes("REQUESTER") ? [["mine", "Yêu cầu của tôi"]] : []),
    ...(queue ? [["assigned", "Việc được giao"]] : []),
    ...(canConfigure ? [["config", "Cấu hình mẫu yêu cầu"]] : []),
    ["diagrams", "Sơ đồ luồng"],
    ["ai", "Quy trình AI"],
  ];
  const [tab, setTab] = useState(() =>
    tabs.some(([key]) => key === initialTab) ? initialTab : "catalog",
  );
  return (
    <>
      <PageHeader
        eyebrow="LUỒNG CÔNG VIỆC"
        title="Yêu cầu & Quy trình"
        description="Khởi tạo đề xuất mới theo danh mục chuẩn, theo dõi tiến trình và xử lý công việc xuyên suốt 5 giai đoạn nghiệp vụ."
      />
      <PageTabs
        label="Yêu cầu & Quy trình"
        value={tab}
        onChange={setTab}
        tabs={tabs}
      />
      <div style={{ marginTop: 16 }}>
        {tab === "catalog" && <CatalogTab onNew={onNew} />}
        {tab === "board" && <StageBoardTab onOpen={onOpen} revision={revision} />}
        {tab === "mine" && (
          <ClientRequests
            key="mine"
            initialStage="mine"
            user={user}
            revision={revision}
            onOpen={onOpen}
            onNew={() => onNew({})}
          />
        )}
        {tab === "assigned" && (
          <ClientRequests
            key="assigned"
            initialStage={queue}
            user={user}
            revision={revision}
            onOpen={onOpen}
            onNew={() => onNew({})}
          />
        )}
        <Suspense fallback={<CardGridSkeleton count={4} />}>
          {tab === "config" && (
            <ApiBaseContext.Provider value={WORKSPACE_API}>
              <RequestWorkflowsPage />
            </ApiBaseContext.Provider>
          )}
          {tab === "ai" && (
            <AiProcessGuide user={user} onOpen={onOpen} portal="client" />
          )}
          {tab === "diagrams" && <WorkflowDiagrams />}
        </Suspense>
      </div>
    </>
  );
}

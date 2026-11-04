import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { ApiBaseContext, WORKSPACE_API } from "../apiBase.js";
import { date, statuses } from "../domain.js";
import { usePermission } from "../hooks/usePermission.jsx";
import ClientRequests from "./ClientRequests.jsx";
import { EmptyState, PageHeader, PageTabs } from "./design.jsx";
import { ResourceState, useResource } from "./ui.jsx";
import WorkflowDiagrams from "./WorkflowDiagrams.jsx";

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
const QUEUE_ROLES = { APPROVER: "approval", EXECUTOR: "execution", ACCEPTOR: "acceptance" };

/** Request templates with their lifecycle, SLA, steps and linked integrations.
 * A template whose integration is switched off by the admin cannot be used. */
function CatalogTab({ onNew }) {
  const catalog = useResource(`${WORKSPACE_API}/request-catalog`);
  // Integration switches change at any time: refresh on open and every 15 s.
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
        (!q || t.name.toLowerCase().includes(q) || (t.request_type || "").toLowerCase().includes(q)),
    );
  }, [catalog.data, query, lifecycle]);
  return (
    <ResourceState resource={catalog}>
      <div className="client-filter-fields" style={{ marginBottom: 12 }}>
        <label>
          Tìm mẫu yêu cầu
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tên mẫu hoặc nhóm" />
        </label>
        <label>
          Phân loại
          <select value={lifecycle} onChange={(e) => setLifecycle(e.target.value)}>
            <option value="ALL">Tất cả</option>
            <option value="A">Loại A — chỉ phê duyệt</option>
            <option value="B">Loại B — phê duyệt + thực hiện</option>
            <option value="C">Loại C — phê duyệt + thực hiện + nghiệm thu</option>
          </select>
        </label>
      </div>
      {items.length === 0 ? (
        <EmptyState title="Không có mẫu phù hợp" description="Thử từ khoá hoặc phân loại khác." />
      ) : (
        <div className="request-catalog-grid">
          {items.map((t) => (
            <article key={t.code} className={`panel request-catalog-card${t.is_api_enabled ? "" : " is-unavailable"}`}>
              <div className="section-head">
                <h3 style={{ margin: 0 }}>{t.name}</h3>
                <span className={`badge badge-cat-${t.category_code.toLowerCase()}`}>Loại {t.category_code}</span>
              </div>
              <p className="muted" style={{ margin: "4px 0" }}>
                {t.request_type} · SLA {t.sla_hours ? `${t.sla_hours} giờ` : "theo cấu hình"}
              </p>
              <ol className="request-catalog-steps">
                {t.workflow_steps.map((s) => (
                  <li key={s.step}>
                    <strong>{s.name}</strong> <small className="muted">{s.actor}</small>
                  </li>
                ))}
              </ol>
              {t.linked_apis.length > 0 && (
                <p className="muted" style={{ fontSize: 12 }}>
                  Hệ thống liên kết: {t.linked_apis.map((a) => `${a.source_system}${a.is_enabled ? "" : " (đang tắt)"}`).join(", ")}
                </p>
              )}
              {!t.is_api_enabled && (
                <p className="request-catalog-warning" role="alert">{t.unavailable_notice}</p>
              )}
              {canCreate && (
                <button
                  type="button"
                  className="primary"
                  disabled={!t.is_api_enabled}
                  title={t.is_api_enabled ? undefined : t.unavailable_notice}
                  onClick={() => onNew({ type_code: t.code })}
                >
                  Tạo yêu cầu
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </ResourceState>
  );
}

/** Every request the user takes part in, filtered by the 5 business stages.
 * Actions (approve, execute, accept…) are on the request detail, checked by
 * the workflow API for the user's role on that request. */
function StageBoardTab({ onOpen, revision }) {
  const board = useResource(`${WORKSPACE_API}/my-requests?r=${revision}`);
  const [stage, setStage] = useState("ALL");
  const summary = board.data?.summary || {};
  const rows = (board.data?.items || []).filter((r) => stage === "ALL" || r.current_stage === stage);
  return (
    <ResourceState resource={board}>
      <div className="stage-filter-row" role="group" aria-label="Lọc theo giai đoạn">
        <button type="button" aria-pressed={stage === "ALL"} className={stage === "ALL" ? "stage-chip is-active" : "stage-chip"} onClick={() => setStage("ALL")}>
          Tất cả <strong>{summary.total_requests ?? 0}</strong>
        </button>
        {STAGES.map(([key, label]) => (
          <button key={key} type="button" aria-pressed={stage === key} className={stage === key ? "stage-chip is-active" : "stage-chip"} onClick={() => setStage(key)}>
            {label} <strong>{summary[STAGE_SUMMARY_KEYS[key]] ?? 0}</strong>
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <EmptyState title="Chưa có yêu cầu ở giai đoạn này" description="Yêu cầu bạn tạo, duyệt, thực hiện hoặc nghiệm thu sẽ hiện ở đây." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mã</th>
                <th>Tiêu đề</th>
                <th>Loại</th>
                <th>Giai đoạn</th>
                <th>Trạng thái</th>
                <th>Vai trò của bạn</th>
                <th>Ngày tạo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.request_id}>
                  <td>
                    <button type="button" className="link" onClick={() => onOpen(r.request_id)}>{r.request_code}</button>
                  </td>
                  <td>{r.title}</td>
                  <td>{r.request_type} <small className="muted">(Loại {r.category_code})</small></td>
                  <td>{r.current_stage_label}</td>
                  <td>{statuses[r.final_status] || r.final_status}</td>
                  <td>{r.user_role_in_request}</td>
                  <td>{date(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ResourceState>
  );
}

export default function ClientRequestsHub({ user, onOpen, onNew, revision, initialTab = "catalog" }) {
  const perms = usePermission("requests_workflows");
  const canConfigure = perms.canUpdate || perms.canDelete;
  const queue = Object.entries(QUEUE_ROLES).find(([role]) => user.roles.includes(role))?.[1];
  const tabs = [
    ["catalog", "Tạo yêu cầu mới"],
    ["board", "Theo dõi 5 giai đoạn"],
    ...(user.roles.includes("REQUESTER") ? [["mine", "Yêu cầu của tôi"]] : []),
    ...(queue ? [["assigned", "Việc được giao"]] : []),
    ...(canConfigure ? [["config", "Cấu hình mẫu yêu cầu"]] : []),
    ["diagrams", "Sơ đồ luồng"],
    ["ai", "Quy trình AI"],
  ];
  const [tab, setTab] = useState(() => (tabs.some(([key]) => key === initialTab) ? initialTab : "catalog"));
  return (
    <>
      <PageHeader
        eyebrow="LUỒNG CÔNG VIỆC"
        title="Yêu cầu & Quy trình"
        description="Tạo yêu cầu theo mẫu, theo dõi và xử lý yêu cầu qua 5 giai đoạn: Yêu cầu → Phê duyệt → Thực hiện → Nghiệm thu → Hoàn thành."
      />
      <PageTabs label="Yêu cầu & Quy trình" value={tab} onChange={setTab} tabs={tabs} />
      <div style={{ marginTop: 16 }}>
        {tab === "catalog" && <CatalogTab onNew={onNew} />}
        {tab === "board" && <StageBoardTab onOpen={onOpen} revision={revision} />}
        {tab === "mine" && <ClientRequests key="mine" initialStage="mine" user={user} revision={revision} onOpen={onOpen} onNew={() => onNew({})} />}
        {tab === "assigned" && <ClientRequests key="assigned" initialStage={queue} user={user} revision={revision} onOpen={onOpen} onNew={() => onNew({})} />}
        <Suspense fallback={<p className="muted" role="status">Đang tải…</p>}>
          {tab === "config" && (
            <ApiBaseContext.Provider value={WORKSPACE_API}>
              <RequestWorkflowsPage />
            </ApiBaseContext.Provider>
          )}
          {tab === "ai" && <AiProcessGuide user={user} onOpen={onOpen} portal="client" />}
        </Suspense>
        {tab === "diagrams" && <WorkflowDiagrams />}
      </div>
    </>
  );
}

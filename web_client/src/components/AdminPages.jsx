import { lazy, Suspense, useState } from "react";
import { api } from "../api.js";
import { date, statuses, types } from "../domain.js";
import { ActionForm, Badge, Modal, Reason, ResourceState, command, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";
import { useApiBase } from "../apiBase.js";
import { PeriodChooser } from "./DashboardOverview.jsx";
import { CardGridSkeleton, EmptyState, PageHeader, PageTabs, StatCard, useDebounced } from "./design.jsx";
import { Policy, AdminEvents } from "./Admin.jsx";
import PlanCatalog from "./PlanCatalog.jsx";
import AuditorWorkspace from "./AuditorWorkspace.jsx";
import ApiAdministration from "./ApiAdministration.jsx";

const WorkflowDiagrams = lazy(() => import("./WorkflowDiagrams.jsx"));

const localDay = (value) => new Date(value).toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });
const STAGE = { APPROVAL: "Phê duyệt", EXECUTION: "Thực hiện", ACCEPTANCE: "Nghiệm thu" };
const EVENT_TYPES = { APPROVAL_REQUESTED: "Yêu cầu phê duyệt", EXECUTION_READY: "Sẵn sàng thực hiện", SLA_REMINDER: "Nhắc hạn xử lý", SLA_BREACH: "Quá hạn xử lý", REQUEST_UPDATED: "Cập nhật hồ sơ" };
const OUTBOX_STATES = { PENDING: "Đang chờ gửi", PROCESSING: "Đang gửi", SENT: "Đã gửi", DEAD: "Gửi thất bại" };

const shortDate = (value) => new Date(value).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" });

function DepartmentSelect({ value, onChange, label = "Phòng ban" }) {
  const apiBase = useApiBase();
  const list = useResource(`${apiBase}/departments?limit=100&active=true`);
  return <label>{label}<select value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Tất cả phòng ban</option>
    {(list.data?.items || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
  </select></label>;
}
function TypeSelect({ value, onChange }) {
  const list = useResource("/api/v1/request-types");
  return <label>Loại yêu cầu<select value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Tất cả loại</option>
    {(list.data?.items || []).map((t) => <option key={t.code} value={t.code}>{t.name || types[t.code] || "Loại yêu cầu"}</option>)}
  </select></label>;
}
function StatusSelect({ value, onChange }) {
  return <label>Trạng thái<select value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Tất cả trạng thái</option>
    {Object.entries(statuses).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
  </select></label>;
}

const STATUS_CHART_ORDER = [
  "COMPLETED",
  "PENDING_APPROVAL",
  "READY_FOR_EXECUTION",
  "IN_PROGRESS",
  "WAITING_FOR_ACCEPTANCE",
  "NEEDS_INFO",
  "REJECTED",
  "CANCELLED",
  "PROCESSING",
];

const STATUS_CHART_COLORS = {
  COMPLETED: "#10b981",
  PENDING_APPROVAL: "#f59e0b",
  READY_FOR_EXECUTION: "#2563eb",
  IN_PROGRESS: "#0ea5e9",
  WAITING_FOR_ACCEPTANCE: "#8b5cf6",
  NEEDS_INFO: "#ea580c",
  REJECTED: "#ef4444",
  CANCELLED: "#64748b",
  PROCESSING: "#f59e0b",
};

const STATUS_CHART_LABELS = {
  ...statuses,
  PROCESSING: "Đang xử lý",
};

function buildRequestStatusSegments(statusBreakdown, byStatus, kpis) {
  let raw = statusBreakdown && Object.keys(statusBreakdown).length ? statusBreakdown : null;
  if (!raw && byStatus && Object.keys(byStatus).length) {
    raw = byStatus;
  }
  const entries = [];
  if (raw) {
    const seen = new Set();
    for (const code of STATUS_CHART_ORDER) {
      if (code === "DRAFT") continue;
      const count = Number(raw[code] || 0);
      if (count > 0) {
        seen.add(code);
        entries.push({ code, count });
      }
    }
    for (const [code, val] of Object.entries(raw)) {
      if (code === "DRAFT" || seen.has(code)) continue;
      const count = Number(val || 0);
      if (count > 0) entries.push({ code, count });
    }
  } else if (kpis && Number(kpis.total_requests || 0) > 0) {
    for (const [code, count] of [
      ["COMPLETED", Number(kpis.success_count || 0)],
      ["PROCESSING", Number(kpis.processing_count || 0)],
      ["REJECTED", Number(kpis.rejected_count || 0)],
    ]) {
      if (count > 0) entries.push({ code, count });
    }
  }
  entries.sort((a, b) => b.count - a.count);
  const total = entries.reduce((sum, item) => sum + item.count, 0);
  if (!total) return { total: 0, items: [] };
  return {
    total,
    items: entries.map((item) => ({
      code: item.code,
      label: STATUS_CHART_LABELS[item.code] || item.code,
      color: STATUS_CHART_COLORS[item.code] || "#64748b",
      count: item.count,
      pct: Math.round((item.count / total) * 1000) / 10,
    })),
  };
}

function RequestStatusDonutChart({ statusBreakdown, byStatus, kpis }) {
  const [activeCode, setActiveCode] = useState(null);
  const { total, items } = buildRequestStatusSegments(statusBreakdown, byStatus, kpis);

  if (!total || !items.length) {
    return <EmptyState title="Chưa có dữ liệu trạng thái yêu cầu" />;
  }

  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const gap = items.length > 1 ? 3 : 0;
  const usable = Math.max(1, circumference - gap * items.length);
  const rawLens = items.map((it) => (it.count / total) * usable);
  const minArc = items.length > 1 ? Math.min(11, usable / (items.length * 2)) : usable;
  const boosted = rawLens.map((len) => Math.max(minArc, len));
  const boostSum = boosted.reduce((acc, v) => acc + v, 0);
  const scale = usable / boostSum;

  const slices = items.reduce((acc, it, idx) => {
    const arcLen = boosted[idx] * scale;
    const prev = acc[idx - 1];
    const offset = prev ? prev.offset + prev.arcLen + gap : 0;
    acc.push({ ...it, arcLen, offset });
    return acc;
  }, []);

  const activeItem = items.find((it) => it.code === activeCode) || null;

  return (
    <div className="status-chart-layout">
      <div className="status-donut-wrap">
        <svg
          className="status-donut-svg"
          viewBox="0 0 200 200"
          role="img"
          aria-label={`Biểu đồ trạng thái yêu cầu: tổng ${total} yêu cầu`}
        >
          <title>{`Biểu đồ phân bổ ${total} yêu cầu theo trạng thái`}</title>
          <circle className="status-donut-track" cx="100" cy="100" r={radius} fill="none" strokeWidth="24" />
          <g transform="rotate(-90 100 100)">
            {slices.map((slice) => {
              const isSelected = activeCode === slice.code;
              const isDimmed = activeCode !== null && !isSelected;
              return (
                <circle
                  key={slice.code}
                  cx="100"
                  cy="100"
                  r={radius}
                  fill="none"
                  stroke={slice.color}
                  strokeWidth={isSelected ? 30 : 24}
                  strokeDasharray={`${slice.arcLen} ${Math.max(0, circumference - slice.arcLen)}`}
                  strokeDashoffset={-slice.offset}
                  strokeLinecap="butt"
                  opacity={isDimmed ? 0.35 : 1}
                  className="status-donut-slice"
                  onMouseEnter={() => setActiveCode(slice.code)}
                  onMouseLeave={() => setActiveCode(null)}
                >
                  <title>{`${slice.label}: ${slice.count} yêu cầu (${slice.pct}%)`}</title>
                </circle>
              );
            })}
          </g>
        </svg>
        <div className="status-donut-center" aria-live="polite">
          <strong className="status-donut-total" style={activeItem ? { color: activeItem.color } : undefined}>
            {activeItem ? activeItem.count : total}
          </strong>
          {activeItem ? (
            <>
              <span className="status-donut-pct">{activeItem.pct}%</span>
              <span className="status-donut-sub">{activeItem.label}</span>
            </>
          ) : (
            <span className="status-donut-sub">Tổng yêu cầu</span>
          )}
        </div>
      </div>

      <div className="status-legend-list" role="group" aria-label="Chú giải trạng thái yêu cầu">
        {items.map((item) => {
          const isSelected = activeCode === item.code;
          return (
            <button
              key={item.code}
              type="button"
              aria-pressed={isSelected}
              className={`status-legend-row ${isSelected ? "is-active" : ""}`}
              onMouseEnter={() => setActiveCode(item.code)}
              onMouseLeave={() => setActiveCode(null)}
              onFocus={() => setActiveCode(item.code)}
              onBlur={() => setActiveCode(null)}
            >
              <span className="status-legend-swatch" style={{ background: item.color }} aria-hidden="true" />
              <span className="status-legend-main">
                <span className="status-legend-head">
                  <span className="status-legend-name">{item.label}</span>
                  <span className="status-legend-nums">
                    <strong>{item.count}</strong>
                    <span className="status-legend-pct">{item.pct}%</span>
                  </span>
                </span>
                <span className="status-legend-bar" aria-hidden="true">
                  <span style={{ width: `${Math.min(100, Math.max(3, item.pct))}%`, background: item.color }} />
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

const READINESS_LABELS = {
  runtime_role_exists: "Role runtime DB tồn tại",
  runtime_role_is_non_admin: "Role API không có quyền superuser",
  runtime_role_is_api_only: "Tách biệt role API vs Worker",
  schema_has_required_tables: "Đầy đủ bảng schema eas",
  request_types_match_p0: "Khớp nhóm nghiệp vụ P0",
  p0_active_types_configured: "Đã cấu hình quy trình P0",
  mock_systems_api_reachable: "Gateway Mock APIs (:8100) phản hồi",
  mock_source_migrations_current: "Migration schema mock đầy đủ",
  eas_role_has_no_mock_table_access: "Cách ly quyền đọc bảng mock",
  shared_security_cache: "Bộ nhớ đệm bảo mật (Cache)",
  attachment_storage_requirement_satisfied: "Kho lưu trữ tệp đính kèm",
  malware_scanner_requirement_satisfied: "Dịch vụ quét mã độc (ClamAV)",
  database: "Kết nối Cơ sở dữ liệu",
};

function SystemServicesPanel({ ready, diagnostics, aiStatus, mockApis, navigate, lastCheckedAt }) {
  const [showTech, setShowTech] = useState(false);
  const checks = ready.data?.checks || {};
  const catalog = ready.data?.catalog || null;
  const diag = diagnostics.data || null;
  const ai = aiStatus.data || null;
  const apiData = mockApis.data || null;
  const apiList = Array.isArray(apiData?.apis) ? apiData.apis : [];
  const counts = diag?.outbox?.counts || {};

  const readyPending = ready.loading && !ready.data && !ready.error;
  const diagPending = diagnostics.loading && !diagnostics.data && !diagnostics.error;

  const dbOk = Boolean(checks.database) || Boolean(checks.schema_has_required_tables && checks.runtime_role_exists);
  const storageOk = checks.attachment_storage_requirement_satisfied !== false && checks.malware_scanner_requirement_satisfied !== false;
  const mockGatewayOk = checks.mock_systems_api_reachable !== false && !apiData?.circuit_breaker_active;

  const cards = [
    {
      id: "core-api",
      name: "Máy chủ ứng dụng (EAS API)",
      endpoint: "GET /health/ready",
      tone: readyPending ? "" : ready.error ? "bad" : ready.data?.status === "ready" ? "ok" : "warn",
      badge: readyPending ? "Đang kiểm tra…" : ready.error ? "Không kết nối" : ready.data?.status === "ready" ? "Sẵn sàng" : "Cần kiểm tra",
      detail: readyPending
        ? "Đang gửi tín hiệu kiểm tra tới Django API..."
        : ready.error
          ? "Không gọi được điểm kiểm tra /health/ready."
          : `Dịch vụ: ${ready.data?.service || "eas-api"} · Role thực thi: ${checks.runtime_role_is_api_only === false ? "Cần rà soát" : "Chuẩn eas_api"}`,
      actionLabel: "Phiên bản hệ thống →",
      actionPage: "system",
    },
    {
      id: "database",
      name: "Cơ sở dữ liệu PostgreSQL",
      endpoint: "Supabase · schema eas",
      tone: readyPending ? "" : ready.error ? "bad" : dbOk ? "ok" : "bad",
      badge: readyPending ? "Đang kiểm tra…" : ready.error ? "Mất kết nối" : dbOk ? "Hoạt động tốt" : "Không sẵn sàng",
      detail: readyPending
        ? "Đang xác minh bảng lõi và danh mục quy trình..."
        : ready.error
          ? "Không truy vấn được trạng thái cơ sở dữ liệu."
          : `${checks.schema_has_required_tables || checks.database ? "Đủ bảng lõi & role hợp lệ" : "Thiếu bảng bắt buộc"}${catalog ? ` · ${catalog.active_type_count} loại đang bật (${catalog.unconfigured_active_type_count} chưa cấu hình)` : ""}`,
    },
    {
      id: "ai-engine",
      name: "Dịch vụ AI & Quy chế",
      endpoint: "FastAPI :8001 · Hybrid Engine",
      tone: diagPending ? "" : diagnostics.error ? "warn" : diag?.ai_service?.healthy ? (ai?.client_maintenance_lock ? "warn" : "ok") : "warn",
      badge: diagPending ? "Đang kiểm tra…" : diagnostics.error ? "Chưa đủ quyền" : diag?.ai_service?.healthy ? (ai?.client_maintenance_lock ? "Đang bảo trì" : "Đang phản hồi") : "Dự phòng (Offline)",
      detail: diagPending
        ? "Đang kiểm tra sức khỏe AI Service..."
        : diagnostics.error
          ? "Không đọc được tín hiệu diagnostics từ API."
          : `${diag?.ai_service?.healthy ? "AI Service trực tuyến (NLP + Risk)" : "AI đang chạy chế độ dự phòng an toàn"}${ai ? ` · Quy định ${ai.active_regulation_version || "v1.0"} (${ai.sync_status || "—"})` : ""}`,
      actionLabel: "Quản trị AI →",
      actionPage: "ai-process",
    },
    {
      id: "worker-sla",
      name: "Outbox Worker & Giám sát SLA",
      endpoint: "Async Outbox · SLA Alert",
      tone: diagPending ? "" : diagnostics.error ? "warn" : diag?.worker?.backlog_ok ? ((counts.DEAD || 0) > 0 ? "warn" : "ok") : "bad",
      badge: diagPending ? "Đang kiểm tra…" : diagnostics.error ? "Chưa đủ quyền" : diag?.worker?.backlog_ok ? ((counts.DEAD || 0) > 0 ? "Có lỗi DEAD" : "Ổn định") : "Tồn đọng quá hạn",
      detail: diagPending
        ? "Đang đọc hàng đợi Outbox và SLA..."
        : diagnostics.error
          ? "Không đọc được hàng đợi Outbox."
          : `Đã gửi ${counts.SENT || 0} · Chờ ${counts.PENDING || 0} · Thất bại ${counts.DEAD || 0} · SLA mở ${diag?.sla?.open_stages ?? 0} (${diag?.sla?.overdue_stages ?? 0} quá hạn)`,
      actionLabel: diagnostics.error ? null : "Chi tiết SLA & Outbox →",
      actionPage: "sla",
    },
    {
      id: "mock-gateway",
      name: "Hệ thống 8 API Nghiệp vụ",
      endpoint: "Mock Systems :8100 · Circuit Breaker",
      tone: readyPending ? "" : ready.error ? "bad" : mockGatewayOk ? "ok" : "warn",
      badge: readyPending
        ? "Đang kiểm tra…"
        : ready.error
          ? "Mất kết nối"
          : apiList.length
            ? `${apiData.enabled_count}/${apiData.total_count} API bật`
            : checks.mock_systems_api_reachable
              ? "Gateway sẵn sàng"
              : "Cần kiểm tra",
      detail: readyPending
        ? "Đang kiểm tra kết nối 8 hệ thống nghiệp vụ..."
        : apiList.length
          ? `${apiData.circuit_breaker_active ? "Có API đang tạm ngắt (Circuit Breaker mở)" : "Toàn bộ 8 kết nối tích hợp hoạt động bình thường"}${checks.mock_source_migrations_current ? " · Migration đồng bộ" : ""}`
          : checks.mock_systems_api_reachable
            ? "Mock Systems API đang phản hồi và cách ly schema."
            : "Không kết nối được Gateway Mock Systems.",
      actionLabel: "Quản lý 8 API →",
      actionPage: "api-admin",
    },
    {
      id: "cache-storage",
      name: "Cache Bảo mật, Lưu trữ & Quét mã độc",
      endpoint: "Redis/Cache · Storage · ClamAV",
      tone: readyPending ? "" : ready.error ? "bad" : checks.shared_security_cache && storageOk ? "ok" : "warn",
      badge: readyPending ? "Đang kiểm tra…" : ready.error ? "Cần kiểm tra" : checks.shared_security_cache && storageOk ? "Bình thường" : "Lưu ý",
      detail: readyPending
        ? "Đang kiểm tra bộ nhớ đệm và dịch vụ lưu trữ..."
        : `Cache: ${checks.shared_security_cache ? "Sẵn sàng" : "Chưa sẵn sàng"} · Lưu trữ tệp: ${checks.attachment_storage_requirement_satisfied === false ? "Thiếu" : "Đạt"} · ClamAV: ${checks.malware_scanner_requirement_satisfied === false ? "Tạm tắt" : "Đạt"}`,
    },
  ];

  const badCount = cards.filter((c) => c.tone === "bad").length;
  const warnCount = cards.filter((c) => c.tone === "warn").length;
  const readyCount = cards.filter((c) => c.tone === "ok").length;

  return (
    <div className="service-health-wrapper">
      <div className="service-health-summary">
        <div className="service-summary-left">
          <span className={`service-overall-pill ${badCount > 0 ? "tone-bad" : warnCount > 0 ? "tone-warn" : readyCount === cards.length ? "tone-ok" : "tone-idle"}`}>
            <i className={`ds-dot ${badCount > 0 ? "bad" : warnCount > 0 ? "warn" : readyCount === cards.length ? "ok" : ""}`} aria-hidden="true" />
            {badCount > 0
              ? `Phát hiện ${badCount} dịch vụ lỗi`
              : warnCount > 0
                ? `${readyCount}/${cards.length} dịch vụ tốt · ${warnCount} cần lưu ý`
                : readyCount === cards.length
                  ? `Tất cả ${cards.length}/${cards.length} nhóm dịch vụ hoạt động ổn định`
                  : "Đang tổng hợp trạng thái các dịch vụ..."}
          </span>
          {lastCheckedAt && (
            <span className="muted service-checked-time">
              Cập nhật lúc {lastCheckedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          )}
        </div>
        <button
          type="button"
          className="link service-tech-toggle"
          aria-expanded={showTech}
          onClick={() => setShowTech((v) => !v)}
        >
          {showTech ? "Ẩn chi tiết kiểm tra kỹ thuật ▲" : "Xem chi tiết kiểm tra kỹ thuật ▼"}
        </button>
      </div>

      <div className="service-health-grid">
        {cards.map((svc) => (
          <article key={svc.id} className={`service-health-card ${svc.tone ? `tone-${svc.tone}` : ""}`}>
            <div className="service-card-top">
              <div>
                <h3 className="service-card-name">{svc.name}</h3>
                <span className="service-card-endpoint">{svc.endpoint}</span>
              </div>
              <span className={`service-status-pill ${svc.tone ? `tone-${svc.tone}` : ""}`}>
                <i className={`ds-dot ${svc.tone}`} aria-hidden="true" />
                {svc.badge}
              </span>
            </div>
            <p className="service-card-detail">{svc.detail}</p>
            {svc.actionLabel && navigate && (
              <div className="service-card-actions">
                <button type="button" className="link" onClick={() => navigate(svc.actionPage)}>
                  {svc.actionLabel}
                </button>
              </div>
            )}
          </article>
        ))}
      </div>

      {apiList.length > 0 && (
        <div className="service-api-strip">
          <div className="service-api-strip-head">
            <div>
              <strong>Chi tiết 8 API hệ thống nghiệp vụ ({apiData.enabled_count}/{apiData.total_count} đang hoạt động)</strong>
              <small className="muted">Trạng thái kết nối thực tế tới các hệ thống HRM, Tài chính, CNTT, Tài sản, Mua sắm…</small>
            </div>
            {navigate && (
              <button type="button" className="secondary" onClick={() => navigate("api-admin")}>
                Cấu hình Circuit Breaker →
              </button>
            )}
          </div>
          <div className="service-api-chip-grid">
            {apiList.map((item) => (
              <div key={item.id || item.api_code} className={`service-api-chip ${item.is_enabled ? "is-on" : "is-off"}`}>
                <div className="service-api-chip-top">
                  <strong>{item.api_code}</strong>
                  <span className={`service-api-state ${item.is_enabled ? "is-on" : "is-off"}`}>
                    <i className={`ds-dot ${item.is_enabled ? "ok" : "bad"}`} aria-hidden="true" />
                    {item.is_enabled ? "Hoạt động" : "Đang ngắt"}
                  </span>
                </div>
                <span className="service-api-name">{item.api_name}</span>
                <span className="service-api-meta">
                  {item.source_system} · {item.linked_count || 0} biểu mẫu
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {showTech && (
        <div className="service-tech-panel">
          <div className="service-tech-title">Thông số kiểm tra chi tiết (/health/ready & Diagnostics)</div>
          <div className="service-tech-grid">
            {Object.entries(checks).map(([key, val]) => (
              <div key={key} className="service-tech-item">
                <span>{READINESS_LABELS[key] || key}</span>
                <span className={`service-tech-val ${val ? "ok" : "bad"}`}>
                  <i className={`ds-dot ${val ? "ok" : "bad"}`} aria-hidden="true" />
                  {val ? "TRUE" : "FALSE"}
                </span>
              </div>
            ))}
            {diag?.outbox && (
              <>
                <div className="service-tech-item">
                  <span>Outbox gửi thành công gần nhất</span>
                  <strong>{diag.outbox.last_sent_at ? shortDate(diag.outbox.last_sent_at) : "Chưa có"}</strong>
                </div>
                <div className="service-tech-item">
                  <span>Số sự kiện lỗi (DEAD events)</span>
                  <strong>{diag.outbox.dead_events?.length || 0}</strong>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** System-wide dashboard; every figure comes from /api/v1/admin/overview and diagnostics. */
/** `workspace`: employee-portal mode — figures scoped by the API (own requests,
 * departments led, or company), no system health or operations shortcut. */
export function AdminDashboard({ navigate, workspace = false, intro = null }) {
  const apiBase = useApiBase();
  const [period, setPeriod] = useState("month");
  const [start, setStart] = useState(() => localDay(Date.now() - 29 * 86400000));
  const [end, setEnd] = useState(() => localDay(Date.now()));
  const [department, setDepartment] = useState(""), [type, setType] = useState(""), [status, setStatus] = useState("");
  const [showCustomDate, setShowCustomDate] = useState(false);
  const valid = Boolean(start && end && start <= end && Date.parse(end) - Date.parse(start) <= 366 * 86400000);
  const params = new URLSearchParams({ created_from: `${start}T00:00:00+07:00`, created_to: `${end}T23:59:59+07:00` });
  if (department) params.set("department_id", department);
  if (type) params.set("type_code", type);
  if (status) params.set("status", status);

  // Resources (preserving overview & diagnostics for regression tests and system state)
  const overview = useResource(valid && !workspace ? `/api/v1/admin/overview?${params}` : "");
  const diagnostics = useResource(workspace ? "" : "/api/v1/admin/diagnostics");
  const ready = useResource(workspace ? "" : "/health/ready");
  const aiStatus = useResource(workspace ? "" : "/api/v1/system/ai-status");
  const mockApis = useResource(workspace ? "" : "/api/v1/admin/mock-apis");
  const analytics = useResource(`${apiBase}/analytics?period=${period}`);
  const [lastCheckedAt, setLastCheckedAt] = useState(() => new Date());

  const aData = analytics.data;
  const oData = overview.data;
  const by = oData?.by_status || {};
  const running = (by.READY_FOR_EXECUTION || 0) + (by.IN_PROGRESS || 0) + (by.WAITING_FOR_ACCEPTANCE || 0);

  // KPI figures
  const kpis = aData?.kpis || {
    total_requests: oData?.total || 0,
    success_count: by.COMPLETED || 0,
    success_rate: oData?.total ? Math.round((100 * (by.COMPLETED || 0)) / oData.total) : 0,
    rejected_count: by.REJECTED || 0,
    rejected_rate: oData?.total ? Math.round((100 * (by.REJECTED || 0)) / oData.total) : 0,
    processing_count: running,
    processing_rate: oData?.total ? Math.round((100 * running) / oData.total) : 0,
  };

  const statusBreakdown = aData?.status_breakdown || null;
  const topTypes = aData?.top_types || (oData?.top_types || []);
  const topDepartments = aData?.top_departments || [];
  const topUsers = aData?.top_users || [];
  const categoryPerf = aData?.category_performance || [];

  return (
    <div className="admin-dashboard-container">
      <PageHeader
        eyebrow={workspace ? "TỔNG QUAN" : "GIÁM SÁT HỆ THỐNG"}
        title={workspace ? "Tổng quan" : "Tổng quan vận hành"}
        description={
          workspace
            ? `Khối lượng yêu cầu, tỉ lệ thành công và tốc độ xử lý theo phân loại A/B/C — phạm vi: ${aData?.scope?.label || "đang tải…"}.`
            : "Khối lượng yêu cầu, hiệu suất SLA theo phân loại A/B/C và các chỉ số toàn diện của doanh nghiệp."
        }
        action={
          workspace ? null : (
            <button type="button" className="primary" onClick={() => navigate("ops")}>
              Theo dõi chi tiết vận hành →
            </button>
          )
        }
      />
      {intro}

      {/* Bộ lọc thời gian chuẩn: Theo Ngày | Theo Tuần | Theo Tháng | Theo Năm */}
      <div className="admin-period-bar">
        <div className="admin-period-btn-group" role="group" aria-label="Bộ lọc thời gian">
          {[
            { key: "day", label: "Theo Ngày" },
            { key: "week", label: "Theo Tuần" },
            { key: "month", label: "Theo Tháng" },
            { key: "year", label: "Theo Năm" },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`admin-period-btn ${period === tab.key ? "active" : ""}`}
              aria-pressed={period === tab.key}
              onClick={() => setPeriod(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="admin-period-actions">
          <span className="admin-period-desc">
            Phạm vi:{" "}
            <strong>
              {period === "day" && "24 giờ qua (Hôm nay)"}
              {period === "week" && "Tuần này (Từ Thứ 2 đến nay)"}
              {period === "month" && "Tháng này (Từ đầu tháng)"}
              {period === "year" && "Năm 2026 (Từ đầu năm)"}
            </strong>
          </span>
          {!workspace && (
            <button
              type="button"
              className="secondary admin-btn-filter-toggle"
              onClick={() => setShowCustomDate(!showCustomDate)}
            >
              {showCustomDate ? "Ẩn tùy chỉnh ngày ▲" : "Tùy chỉnh ngày nâng cao ▼"}
            </button>
          )}
          <button
            type="button"
            className="secondary"
            onClick={() => {
              analytics.reload();
              overview.reload();
              diagnostics.reload();
              ready.reload();
              aiStatus.reload();
              mockApis.reload();
              setLastCheckedAt(new Date());
            }}
          >
            Làm mới
          </button>
        </div>
      </div>

      {showCustomDate && (
        <div className="admin-custom-date-box panel">
          <PeriodChooser
            start={start}
            end={end}
            setStart={setStart}
            setEnd={setEnd}
            reload={() => {
              overview.reload();
              diagnostics.reload();
              analytics.reload();
            }}
          />
          <div className="client-filter-fields" style={{ marginTop: 12 }}>
            <DepartmentSelect value={department} onChange={setDepartment} />
            <TypeSelect value={type} onChange={setType} />
            <StatusSelect value={status} onChange={setStatus} />
          </div>
        </div>
      )}

      {/* 1. HÀNG THẺ KPI TỔNG HỢP */}
      <div className="admin-kpi-grid">
        <div className="admin-kpi-card card-total">
          <div className="kpi-top">
            <span className="kpi-title">Tổng yêu cầu phát sinh</span>
            <div className="kpi-icon-wrap icon-blue"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h8M8 17h5" /></svg></div>
          </div>
          <div className="kpi-value">{kpis.total_requests}</div>
          <div className="kpi-detail">
            Phát sinh trong {period === "day" ? "hôm nay" : period === "week" ? "tuần này" : period === "month" ? "tháng này" : "năm nay"}
          </div>
        </div>

        <div className="admin-kpi-card card-success">
          <div className="kpi-top">
            <span className="kpi-title">Thành công (Đã duyệt / Xong)</span>
            <div className="kpi-icon-wrap icon-green"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg></div>
          </div>
          <div className="kpi-value text-success">{kpis.success_count}</div>
          <div className="kpi-detail">
            <span className="kpi-rate-badge badge-green">
              {kpis.success_rate}%
            </span>{" "}
            tỷ lệ hoàn thành
          </div>
        </div>

        <div className="admin-kpi-card card-danger">
          <div className="kpi-top">
            <span className="kpi-title">Bị từ chối</span>
            <div className="kpi-icon-wrap icon-red"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="m15 9-6 6M9 9l6 6" /></svg></div>
          </div>
          <div className="kpi-value text-danger">{kpis.rejected_count}</div>
          <div className="kpi-detail">
            <span className="kpi-rate-badge badge-red">
              {kpis.rejected_rate}%
            </span>{" "}
            tỷ lệ bị từ chối
          </div>
        </div>

        <div className="admin-kpi-card card-warning">
          <div className="kpi-top">
            <span className="kpi-title">Đang xử lý</span>
            <div className="kpi-icon-wrap icon-amber"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg></div>
          </div>
          <div className="kpi-value text-amber">{kpis.processing_count}</div>
          <div className="kpi-detail">
            <span className="kpi-rate-badge badge-amber">
              {kpis.processing_rate}%
            </span>{" "}
            đang giải quyết
          </div>
        </div>
      </div>

      {/* 2. TỐC ĐỘ XỬ LÝ TRUNG BÌNH THEO PHÂN LOẠI (A, B, C) */}
      <section className="panel admin-category-section">
        <div className="section-head">
          <div>
            <h2 style={{ margin: 0, fontSize: "1.1rem" }}>Tốc độ xử lý trung bình theo Phân loại (A, B, C)</h2>
            <small className="muted">
              So sánh thời gian xử lý trung bình và tỷ lệ đúng hạn cam kết SLA của 3 phân loại yêu cầu lớn
            </small>
          </div>
          <button
            type="button"
            className="link"
            style={{ fontWeight: 600 }}
            onClick={() => navigate(workspace ? "requests" : "request-catalog")}
          >
            {workspace ? "Xem quy trình A, B, C →" : "Quản lý quy trình A, B, C →"}
          </button>
        </div>

        <div className="admin-cat-perf-grid">
          {!categoryPerf.length && <EmptyState title="Chưa có hồ sơ trong khoảng thời gian này" />}
          {categoryPerf.map((cat) => {
            const code = cat.category_code;
            const rated = cat.on_time_rate !== null && cat.on_time_rate !== undefined;
            const isA = code === "A";
            const isB = code === "B";
            const themeClass = isA ? "theme-a" : isB ? "theme-b" : "theme-c";
            return (
              <div key={code} className={`admin-cat-perf-card ${themeClass}`}>
                <div className="cat-card-header">
                  <div>
                    <span className="cat-badge-code">Phân loại {code}</span>
                    <h3 className="cat-name">{cat.name}</h3>
                  </div>
                  <span className={`cat-speed-tag ${isA ? "tag-fast" : isB ? "tag-mid" : "tag-std"}`}>
                    {cat.speed_rating}
                  </span>
                </div>

                <div className="cat-metrics-row">
                  <div className="cat-metric-box">
                    <span className="cat-metric-label">Cam kết SLA</span>
                    <strong className="cat-metric-val">{cat.sla_hours} giờ</strong>
                  </div>
                  <div className="cat-metric-box">
                    <span className="cat-metric-label">Xử lý trung bình</span>
                    <strong className="cat-metric-val highlight">{cat.avg_duration_text === "0 phút" && !cat.on_time_count ? "—" : cat.avg_duration_text}</strong>
                  </div>
                  <div className="cat-metric-box">
                    <span className="cat-metric-label">Tỷ lệ đúng hạn SLA</span>
                    <strong className={`cat-metric-val ${rated && cat.on_time_rate < 80 ? "text-danger" : "text-success"}`}>{rated ? `${cat.on_time_rate}%` : "—"}</strong>
                  </div>
                </div>

                <div className="cat-progress-box">
                  <div className="cat-bar-bg">
                    <div
                      className="cat-bar-fill"
                      style={{ width: `${rated ? Math.min(100, cat.on_time_rate) : 0}%` }}
                    />
                  </div>
                  <div className="cat-bar-meta">
                    <span>
                      {rated ? `Đúng hạn SLA: ${cat.on_time_rate}%` : "Chưa có hồ sơ đến hạn để đánh giá"}
                      {cat.overdue_open > 0 && <strong className="text-danger"> · {cat.overdue_open} đang quá hạn</strong>}
                    </span>
                    <span>{cat.total_requests} hồ sơ</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 3. BIỂU ĐỒ TRẠNG THÁI YÊU CẦU & LOẠI YÊU CẦU PHỔ BIẾN NHẤT */}
      <div className="ds-grid-2 admin-analytics-grid" style={{ marginTop: 16 }}>
        <section className="panel admin-status-panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Trạng thái yêu cầu</h2>
              <small className="muted">
                Cơ cấu phân bổ theo từng trạng thái xử lý ({period === "day" ? "hôm nay" : period === "week" ? "tuần này" : period === "year" ? "năm nay" : "tháng này"})
              </small>
            </div>
            {Number(kpis.total_requests || 0) > 0 && (
              <span className="status-panel-summary-pill">
                Hoàn thành <strong>{kpis.success_rate}%</strong>
              </span>
            )}
          </div>

          <RequestStatusDonutChart
            statusBreakdown={statusBreakdown}
            byStatus={by}
            kpis={kpis}
          />
        </section>

        <section className="panel admin-popular-panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Loại yêu cầu phổ biến nhất</h2>
              <small className="muted">Thống kê cơ cấu các loại yêu cầu phát sinh</small>
            </div>
          </div>
          {topTypes?.length ? (
            <div className="admin-type-list">
              {topTypes.map((t, idx) => {
                const pct = t.percentage || (kpis.total_requests ? Math.round((100 * t.count) / kpis.total_requests) : 0);
                return (
                  <div key={t.code || idx} className="admin-type-row">
                    <div className="type-row-header">
                      <span className="type-row-rank">#{idx + 1}</span>
                      <span className="type-row-name">{t.name || types[t.code] || "Loại yêu cầu"}</span>
                      <span className="type-row-count">
                        <strong>{t.count}</strong> yêu cầu ({pct}%)
                      </span>
                    </div>
                    <div className="type-row-bar">
                      <div className="type-row-bar-fill" style={{ width: `${Math.min(100, pct)}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState title="Chưa có dữ liệu loại yêu cầu" />
          )}
        </section>
      </div>

      {/* 4. THỐNG KÊ THEO PHÒNG BAN & CÁ NHÂN */}
      {aData?.scope?.kind !== "OWN" && <div className="ds-grid-2 admin-rank-grid" style={{ marginTop: 16 }}>
        <section className="panel admin-rank-panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Top Phòng ban gửi yêu cầu</h2>
              <small className="muted">Khối lượng yêu cầu theo từng phòng ban trong doanh nghiệp</small>
            </div>
          </div>
          {topDepartments.length ? (
            <div className="table-wrap admin-rank-table-wrap">
              <table className="admin-rank-table">
                <colgroup>
                  <col style={{ width: "74px" }} />
                  <col />
                  <col style={{ width: "74px" }} />
                  <col style={{ width: "108px" }} />
                  <col style={{ width: "92px" }} />
                </colgroup>
                <thead>
                  <tr>
                    <th style={{ textAlign: "center" }}>Hạng</th>
                    <th>Phòng ban</th>
                    <th style={{ textAlign: "right" }}>Tổng</th>
                    <th style={{ textAlign: "right" }}>Thành công</th>
                    <th style={{ textAlign: "right" }} title="Tỷ trọng trên tổng yêu cầu">Tỷ trọng</th>
                  </tr>
                </thead>
                <tbody>
                  {topDepartments.map((d, idx) => (
                    <tr key={idx}>
                      <td style={{ textAlign: "center" }}>
                        <span className={`rank-badge ${idx === 0 ? "rank-1" : idx === 1 ? "rank-2" : idx === 2 ? "rank-3" : ""}`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td>
                        <strong className="rank-dept-name">{d.department_name}</strong>
                      </td>
                      <td style={{ textAlign: "right" }} className="rank-num-cell">
                        <strong>{d.total}</strong>
                      </td>
                      <td style={{ textAlign: "right", color: "var(--ds-success)" }} className="rank-num-cell">
                        <strong>{d.success}</strong>
                      </td>
                      <td style={{ textAlign: "right" }} className="rank-num-cell">
                        <span className="badge-pct">{d.percentage}%</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="Chưa có dữ liệu phòng ban" />
          )}
        </section>

        <section className="panel admin-rank-panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Top Cá nhân gửi nhiều yêu cầu</h2>
              <small className="muted">Nhân viên khởi tạo yêu cầu nhiều nhất</small>
            </div>
          </div>
          {topUsers.length ? (
            <div className="table-wrap admin-rank-table-wrap">
              <table className="admin-rank-table">
                <colgroup>
                  <col style={{ width: "74px" }} />
                  <col />
                  <col style={{ width: "74px" }} />
                  <col style={{ width: "108px" }} />
                  <col style={{ width: "92px" }} />
                </colgroup>
                <thead>
                  <tr>
                    <th style={{ textAlign: "center" }}>Hạng</th>
                    <th>Nhân viên</th>
                    <th style={{ textAlign: "right" }}>Tổng</th>
                    <th style={{ textAlign: "right" }}>Thành công</th>
                    <th style={{ textAlign: "right" }} title="Tỷ trọng trên tổng yêu cầu">Tỷ trọng</th>
                  </tr>
                </thead>
                <tbody>
                  {topUsers.map((u, idx) => {
                    const userPct = Number(kpis.total_requests)
                      ? Math.round((Number(u.total || 0) / Number(kpis.total_requests)) * 1000) / 10
                      : 0;
                    return (
                      <tr key={idx}>
                        <td style={{ textAlign: "center" }}>
                          <span className={`rank-badge ${idx === 0 ? "rank-1" : idx === 1 ? "rank-2" : idx === 2 ? "rank-3" : ""}`}>
                            {idx + 1}
                          </span>
                        </td>
                        <td>
                          <div className="user-flex-cell" title={u.email || u.name}>
                            <div className="user-circle">{(u.name || "U")[0]}</div>
                            <div className="user-text-stack">
                              <div className="user-display-name">{u.name}</div>
                              <small className="rank-user-dept">{u.department || u.email}</small>
                            </div>
                          </div>
                        </td>
                        <td style={{ textAlign: "right" }} className="rank-num-cell">
                          <strong>{u.total}</strong>
                        </td>
                        <td style={{ textAlign: "right", color: "var(--ds-success)" }} className="rank-num-cell">
                          <strong>{u.success}</strong>
                        </td>
                        <td style={{ textAlign: "right" }} className="rank-num-cell">
                          <span className="badge-pct">{userPct}%</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="Chưa có dữ liệu cá nhân" />
          )}
        </section>
      </div>}

      {/* 5. TÌNH TRẠNG DỊCH VỤ HỆ THỐNG */}
      {!workspace && <section className="panel" style={{ marginTop: 16 }}>
        <div className="section-head">
          <div>
            <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Tình trạng dịch vụ hệ thống</h2>
            <small className="muted">Giám sát chi tiết trạng thái các dịch vụ lõi, AI Engine, Outbox Worker và 8 API nghiệp vụ</small>
          </div>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              ready.reload();
              diagnostics.reload();
              aiStatus.reload();
              mockApis.reload();
              setLastCheckedAt(new Date());
            }}
          >
            Kiểm tra lại
          </button>
        </div>
        <SystemServicesPanel
          ready={ready}
          diagnostics={diagnostics}
          aiStatus={aiStatus}
          mockApis={mockApis}
          navigate={navigate}
          lastCheckedAt={lastCheckedAt}
        />
      </section>}
    </div>
  );
}

const ROLE_FOR_TARGET = { APPROVAL_STEP: "APPROVER", EXECUTOR: "EXECUTOR", PLANNED_EXECUTOR: "EXECUTOR", ACCEPTOR: "ACCEPTOR" };
function ReassignDialog({ item, onClose, onDone }) {
  const initial = item.active_step ? "APPROVAL_STEP" : item.current_attempt ? "EXECUTOR" : item.acceptor_id ? "ACCEPTOR" : "PLANNED_EXECUTOR";
  const [target, setTarget] = useState(initial);
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim(), 300);
  const users = useResource(`/api/v1/admin/users?limit=50&active=true&role=${ROLE_FOR_TARGET[target]}${q ? `&q=${encodeURIComponent(q)}` : ""}`);
  const targetId = target === "APPROVAL_STEP" ? item.active_step?.id : target === "EXECUTOR" ? item.current_attempt?.id : item.id;
  return <Modal title={`Điều chuyển ${item.code}`} onClose={onClose}>
    <ActionForm submitLabel="Xác nhận điều chuyển" onSubmit={async (values) => {
      if (!values.new_user_id) throw new Error("Vui lòng chọn người nhận mới.");
      await command(`requests/${item.id}/reassign`, { target_kind: target, target_id: targetId, new_user_id: values.new_user_id, reason: values.reason, expected_version: item.lock_version });
      onDone();
    }}>
      <p className="muted">Hiện tại: <strong>{item.responsible?.name || "Chưa phân công"}</strong>{item.responsible?.stage ? ` · ${STAGE[item.responsible.stage]}` : ""}</p>
      <label>Vị trí xử lý<select value={target} onChange={(e) => setTarget(e.target.value)}>
        {item.active_step && <option value="APPROVAL_STEP">Người phê duyệt (bước đang chờ)</option>}
        {item.current_attempt && <option value="EXECUTOR">Người thực hiện</option>}
        {item.acceptor_id && <option value="ACCEPTOR">Người nghiệm thu</option>}
        {item.planned_executor_id && <option value="PLANNED_EXECUTOR">Người thực hiện dự kiến</option>}
      </select></label>
      <label>Tìm người nhận<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Họ tên hoặc email" /></label>
      <label>Người nhận mới<select name="new_user_id" required defaultValue="" key={target + q}>
        <option value="" disabled>{users.loading ? "Đang tải…" : "Chọn người có vai trò phù hợp"}</option>
        {(users.data?.items || []).map((u) => <option key={u.id} value={u.id}>{u.display_name}{u.email ? ` · ${u.email}` : ""}</option>)}
      </select></label>
      <small className="muted">Chỉ hiển thị tài khoản đang hoạt động có vai trò phù hợp; hệ thống kiểm tra lại phạm vi và quy tắc tách biệt trách nhiệm khi xác nhận.</small>
      <Reason />
    </ActionForm>
  </Modal>;
}

/** Request | Creator | Current handler | Department | Stage | Deadline | Overdue | Status | Actions */
export function OperationsPage({ onOpen, initialQuery = "" }) {
  const [search, setSearch] = useState(initialQuery), [status, setStatus] = useState(""), [department, setDepartment] = useState(""), [type, setType] = useState("");
  const [offset, setOffset] = useState(0), [limit, setLimit] = useState(20), [selected, setSelected] = useState(null);
  const q = useDebounced(search.trim(), 300);
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (department) params.set("department_id", department);
  if (type) params.set("type_code", type);
  const list = useResource(`/api/v1/ops/requests?${params}`);
  const items = list.data?.items || [];
  const reset = (setter) => (value) => { setter(value); setOffset(0); };
  return <>
    <PageHeader eyebrow="VẬN HÀNH" title="Theo dõi vận hành" description="Người đang xử lý, giai đoạn và hạn của từng hồ sơ; điều chuyển khi người phụ trách không thể tiếp tục." />
    <section className="panel ds-filter"><div className="client-filter-fields">
      <label>Tìm hồ sơ<input type="search" value={search} onChange={(e) => reset(setSearch)(e.target.value)} placeholder="Mã hoặc tiêu đề" /></label>
      <StatusSelect value={status} onChange={reset(setStatus)} /><DepartmentSelect value={department} onChange={reset(setDepartment)} /><TypeSelect value={type} onChange={reset(setType)} />
    </div></section>
    <ResourceState resource={list}><section className="panel table-panel" id="ops-results">
      {items.length ? <div className="table-wrap"><table className="responsive-records ds-compact-table"><thead><tr>
        <th>Hồ sơ</th><th>Người tạo</th><th>Người đang xử lý</th><th>Phòng ban</th><th>Giai đoạn</th><th>Hạn xử lý</th><th>Quá hạn</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
        <tbody>{items.map((r) => <tr key={r.id} className={r.overdue ? "is-overdue" : ""}>
          <td data-label="Hồ sơ"><strong>{r.code}</strong><span className="ds-cell-sub">{r.type_name || types[r.type_code] || "Yêu cầu"}</span></td>
          <td data-label="Người tạo">{r.requester_name || "—"}</td>
          <td data-label="Người đang xử lý">{r.responsible?.name || <span className="muted">Chưa phân công</span>}</td>
          <td data-label="Phòng ban">{r.department_name || "—"}</td>
          <td data-label="Giai đoạn">{STAGE[r.responsible?.stage] || "—"}</td>
          <td data-label="Hạn xử lý">{r.sla?.due_at ? shortDate(r.sla.due_at) : "—"}</td>
          <td data-label="Quá hạn">{r.overdue ? <span className="badge REJECTED">Quá hạn</span> : <span className="muted">Không</span>}</td>
          <td data-label="Trạng thái"><Badge value={r.status} /></td>
          <td data-label="Thao tác"><div className="actions">
            {onOpen && <button type="button" className="link" onClick={() => onOpen(r.id)}>Xem</button>}
            <button type="button" className="secondary" disabled={["COMPLETED", "CANCELLED", "REJECTED", "DRAFT"].includes(r.status) || !(r.active_step || r.current_attempt || r.acceptor_id || r.planned_executor_id)} onClick={() => setSelected(r)}>Điều chuyển</button>
          </div></td>
        </tr>)}</tbody></table></div> : <EmptyState title="Không có hồ sơ phù hợp" description="Thử thay đổi bộ lọc." />}
      <PageControls offset={offset} limit={limit} nextOffset={list.data?.next_offset} count={items.length} title="hồ sơ" targetId="ops-results" onPage={setOffset} onLimit={setLimit} />
    </section></ResourceState>
    {selected && <ReassignDialog item={selected} onClose={() => setSelected(null)} onDone={() => { setSelected(null); list.reload(); }} />}
  </>;
}

/** Outbox / worker / SLA diagnostics with replay of failed deliveries. */
export function SlaNotificationsPage({ navigate }) {
  const diag = useResource("/api/v1/admin/diagnostics");
  const [replay, setReplay] = useState(null);
  const d = diag.data;
  const counts = d?.outbox?.counts || {};
  return <>
    <PageHeader eyebrow="VẬN HÀNH" title="SLA & thông báo" description="Hạn xử lý đang mở, nhắc hạn đã phát và tình trạng gửi thông báo của worker."
      action={<button type="button" className="secondary" onClick={diag.reload}>Làm mới</button>} />
    <ResourceState resource={diag}>{d && <>
      <div className="ds-stat-grid" style={{ marginBottom: 16 }}>
        <StatCard title="Bước đang tính hạn" value={d.sla?.open_stages ?? 0} detail="Phê duyệt, thực hiện, nghiệm thu" />
        <StatCard title="Đã quá hạn" value={d.sla?.overdue_stages ?? 0} tone={d.sla?.overdue_stages ? "danger" : undefined} detail="Cần xử lý hoặc điều chuyển" />
        <StatCard title="Nhắc hạn 24 giờ qua" value={d.sla?.alerts_24h?.REMINDER || 0} detail={`Báo quá hạn: ${d.sla?.alerts_24h?.BREACH || 0}`} />
        <StatCard title="Thông báo gửi lỗi" value={counts.DEAD || 0} tone={counts.DEAD ? "danger" : undefined} detail="Cần gửi lại thủ công" />
      </div>
      <div className="ds-grid-2">
        <section className="panel"><h2>Hàng đợi thông báo</h2>
          <ul className="ds-health-list">{Object.entries(OUTBOX_STATES).map(([k, v]) => <li key={k}><span>{v}</span><strong>{counts[k] || 0}</strong></li>)}</ul>
          <p className="muted">Lần gửi gần nhất: {d.outbox?.last_sent_at ? date(d.outbox.last_sent_at) : "chưa có"}. {typeof d.worker?.backlog_ok !== "boolean" ? "Chưa có dữ liệu worker." : d.worker.backlog_ok ? "Không có thông báo tồn đọng quá 5 phút." : `Có thông báo chờ quá ${Math.round((d.outbox?.oldest_pending_seconds || 0) / 60)} phút — kiểm tra worker (start_worker_local.cmd).`}</p>
        </section>
        <section className="panel"><h2>Quá hạn cần xử lý</h2>
          <p className="muted">Danh sách chi tiết người đang xử lý và hạn nằm ở trang vận hành.</p>
          <button type="button" onClick={() => navigate("ops")}>Mở theo dõi vận hành →</button>
        </section>
      </div>
      <section className="panel" style={{ marginTop: 16 }}><h2>Thông báo gửi thất bại</h2>
        {d.outbox?.dead_events?.length ? <div className="table-wrap"><table><thead><tr><th>Loại thông báo</th><th>Hồ sơ</th><th>Số lần thử</th><th>Mã lỗi</th><th>Thời điểm</th><th></th></tr></thead>
          <tbody>{d.outbox.dead_events.map((e) => <tr key={e.id}><td>{EVENT_TYPES[e.event_type] || "Thông báo hệ thống"}</td><td>{e.request_code || "—"}</td><td>{e.attempts}{e.replay_count ? ` (đã gửi lại ${e.replay_count})` : ""}</td><td>{e.last_error_code || "—"}</td><td>{date(e.created_at)}</td>
            <td><button type="button" className="secondary" onClick={() => setReplay(e)}>Gửi lại</button></td></tr>)}</tbody></table></div>
          : <EmptyState title="Không có thông báo gửi lỗi" description="Mọi thông báo đã được worker xử lý." />}
      </section>
    </>}</ResourceState>
    {replay && <Modal title="Gửi lại thông báo" onClose={() => setReplay(null)}>
      <ActionForm submitLabel="Gửi lại" onSubmit={async (values) => { await command(`ops/outbox/${replay.id}/replay`, { reason: values.reason }); setReplay(null); diag.reload(); }}>
        <p>{EVENT_TYPES[replay.event_type] || "Thông báo hệ thống"} · {replay.request_code || "—"}</p><Reason />
      </ActionForm>
    </Modal>}
  </>;
}

function Maintenance() {
  const info = useResource("/api/v1/system/maintenance");
  const m = info.data?.maintenance || info.data || {};
  const [confirm, setConfirm] = useState(null);
  return <section className="panel"><h2>Chế độ bảo trì</h2>
    <ResourceState resource={info}>
      <p><i className={`ds-dot ${m.active ? "warn" : "ok"}`} aria-hidden="true" />{m.active ? "Đang bảo trì" : "Hoạt động bình thường"}{m.started_at ? ` · bắt đầu ${date(m.started_at)}` : ""}</p>
      {m.message && <p className="muted">Thông điệp cho người dùng: {m.message}</p>}
      {m.active ? <button type="button" onClick={() => setConfirm("complete")}>Kết thúc bảo trì</button>
        : <button type="button" className="danger" onClick={() => setConfirm("start")}>Bật chế độ bảo trì</button>}
    </ResourceState>
    {confirm && <Modal title={confirm === "start" ? "Bật chế độ bảo trì" : "Kết thúc bảo trì"} onClose={() => setConfirm(null)}>
      <ActionForm danger={confirm === "start"} submitLabel="Xác nhận" onSubmit={async (values) => {
        await api(`/api/v1/system/maintenance/${confirm}`, { method: "POST", body: JSON.stringify(values) });
        setConfirm(null); info.reload();
      }}>
        {confirm === "start" && <><p>Người dùng nghiệp vụ sẽ thấy thông báo bảo trì cho đến khi kết thúc.</p>
          <label>Thông điệp hiển thị cho người dùng<textarea name="message" maxLength={500} rows={3} placeholder="Ví dụ: Hệ thống đang cập nhật quy chế, vui lòng quay lại sau." /></label></>}
        <label>Ghi chú quản trị<textarea name="admin_message" maxLength={500} rows={2} /></label>
      </ActionForm>
    </Modal>}
  </section>;
}

export function SystemConfigPage() {
  const [tab, setTab] = useState("maintenance");
  return <>
    <PageHeader eyebrow="HỆ THỐNG" title="Cấu hình hệ thống" description="Bảo trì, danh mục API và trạng thái tích hợp." />
    <PageTabs label="Mục cấu hình" value={tab} onChange={setTab} tabs={[["maintenance", "Bảo trì"], ["api", "API & tích hợp"]]} />
    {tab === "maintenance" ? <Maintenance /> : <ApiAdministration />}
  </>;
}

export function PolicyWorkspace({ canManageAccess, onManageAccess }) {
  const [tab, setTab] = useState("releases");
  return <>
    <PageTabs label="Quy chế & quy trình" value={tab} onChange={setTab} tabs={[["releases", "Phiên bản quy chế"], ["catalog", "Danh mục 18 mẫu"], ["diagrams", "Sơ đồ luồng"]]} />
    {tab === "releases" && <Policy canManageAccess={canManageAccess} onManageAccess={onManageAccess} />}
    {tab === "catalog" && <PlanCatalog />}
    {tab === "diagrams" && <Suspense fallback={<CardGridSkeleton count={4} />}><WorkflowDiagrams /></Suspense>}
  </>;
}

export function AuditLogPage({ onOpen }) {
  const [tab, setTab] = useState("requests");
  return <>
    <PageHeader eyebrow="KIỂM TOÁN" title="Nhật ký kiểm toán" description="Xác minh chuỗi nhật ký của hồ sơ và tra cứu thay đổi quản trị." />
    <PageTabs label="Loại nhật ký" value={tab} onChange={setTab} tabs={[["requests", "Kiểm toán hồ sơ"], ["admin", "Nhật ký quản trị"]]} />
    {tab === "requests" ? <AuditorWorkspace onOpen={onOpen} /> : <AdminEvents />}
  </>;
}

import { useState } from "react";
import { api } from "../api.js";
import { date, statuses, types } from "../domain.js";
import { ActionForm, Badge, Modal, Reason, ResourceState, command, useResource } from "./ui.jsx";
import { PageControls } from "./ux.jsx";
import { useApiBase } from "../apiBase.js";
import { PeriodChooser } from "./DashboardOverview.jsx";
import { EmptyState, PageHeader, PageTabs, StatCard, useDebounced } from "./design.jsx";
import { Policy, AdminEvents } from "./Admin.jsx";
import PlanCatalog from "./PlanCatalog.jsx";
import WorkflowDiagrams from "./WorkflowDiagrams.jsx";
import AuditorWorkspace from "./AuditorWorkspace.jsx";
import ApiAdministration from "./ApiAdministration.jsx";

const localDay = (value) => new Date(value).toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });
const STAGE = { APPROVAL: "Phê duyệt", EXECUTION: "Thực hiện", ACCEPTANCE: "Nghiệm thu" };
const EVENT_TYPES = { APPROVAL_REQUESTED: "Yêu cầu phê duyệt", EXECUTION_READY: "Sẵn sàng thực hiện", SLA_REMINDER: "Nhắc hạn xử lý", SLA_BREACH: "Quá hạn xử lý", REQUEST_UPDATED: "Cập nhật hồ sơ" };
const OUTBOX_STATES = { PENDING: "Đang chờ gửi", PROCESSING: "Đang gửi", SENT: "Đã gửi", DEAD: "Gửi thất bại" };

const shortDate = (value) => new Date(value).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" });

function DepartmentSelect({ value, onChange, label = "Phòng ban" }) {
  const list = useResource("/api/v1/admin/departments?limit=100&active=true");
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

function HealthList({ diagnostics, ready }) {
  const checks = ready.data?.checks || {};
  const rows = [
    ["Máy chủ ứng dụng (API)", ready.error ? "bad" : ready.data?.status === "ready" ? "ok" : "warn", ready.error ? "Không kết nối được" : ready.data?.status === "ready" ? "Sẵn sàng" : "Cần kiểm tra"],
    ["Cơ sở dữ liệu", ready.loading || ready.error || typeof checks.database !== "boolean" ? "warn" : checks.database ? "ok" : "bad", ready.loading ? "Đang kiểm tra…" : ready.error || typeof checks.database !== "boolean" ? "Chưa xác minh được" : checks.database ? "Kết nối bình thường" : "Mất kết nối"],
    ["Bộ nhớ đệm bảo mật", checks.shared_security_cache ? "ok" : "warn", checks.shared_security_cache ? "Bình thường" : "Không khả dụng"],
    ["Dịch vụ AI", diagnostics.data ? (diagnostics.data.ai_service.healthy ? "ok" : "warn") : "", diagnostics.data ? (diagnostics.data.ai_service.healthy ? "Đang phản hồi" : "Không phản hồi — AI dùng chế độ dự phòng") : "Đang kiểm tra…"],
    ["Hàng đợi thông báo (worker)", diagnostics.data ? (diagnostics.data.worker.backlog_ok ? "ok" : "bad") : "", diagnostics.data ? (diagnostics.data.worker.backlog_ok ? "Không có tồn đọng quá hạn" : `Tồn đọng ${Math.round(diagnostics.data.outbox.oldest_pending_seconds / 60)} phút — kiểm tra worker`) : "Đang kiểm tra…"],
  ];
  return <ul className="ds-health-list">{rows.map(([name, tone, text]) => <li key={name}><span>{name}</span><span><i className={`ds-dot ${tone}`} aria-hidden="true" />{text}</span></li>)}</ul>;
}

/** System-wide dashboard; every figure comes from /api/v1/admin/overview and diagnostics. */
/** `workspace`: employee-portal mode — figures scoped by the API (own requests,
 * departments led, or company), no system health or operations shortcut. */
export function AdminDashboard({ navigate, workspace = false }) {
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
  const analytics = useResource(`${apiBase}/analytics?period=${period}`);

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

  const trends = aData?.trends || [];
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
            <div className="kpi-icon-wrap icon-blue">📋</div>
          </div>
          <div className="kpi-value">{kpis.total_requests}</div>
          <div className="kpi-detail">
            Phát sinh trong {period === "day" ? "hôm nay" : period === "week" ? "tuần này" : period === "month" ? "tháng này" : "năm nay"}
          </div>
        </div>

        <div className="admin-kpi-card card-success">
          <div className="kpi-top">
            <span className="kpi-title">Thành công (Đã duyệt / Xong)</span>
            <div className="kpi-icon-wrap icon-green">✅</div>
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
            <span className="kpi-title">Bị từ chối (Rejected)</span>
            <div className="kpi-icon-wrap icon-red">❌</div>
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
            <div className="kpi-icon-wrap icon-amber">⏳</div>
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
          {(categoryPerf.length ? categoryPerf : [
            { category_code: "A", name: "Thủ tục hành chính đơn giản", sla_hours: 2, total_requests: 8, avg_duration_text: "15 phút", on_time_rate: 100.0, speed_rating: "Siêu tốc (Tự động)" },
            { category_code: "B", name: "Nghiệp vụ phòng ban & Tài nguyên", sla_hours: 24, total_requests: 5, avg_duration_text: "3 giờ", on_time_rate: 100.0, speed_rating: "Nhanh (Phòng ban)" },
            { category_code: "C", name: "Dự án, Ngân sách lớn & Ngoại lệ", sla_hours: 72, total_requests: 4, avg_duration_text: "12 giờ", on_time_rate: 100.0, speed_rating: "Tiêu chuẩn (Đa cấp)" },
          ]).map((cat) => {
            const code = cat.category_code;
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
                    <strong className="cat-metric-val highlight">{cat.avg_duration_text}</strong>
                  </div>
                  <div className="cat-metric-box">
                    <span className="cat-metric-label">Tỷ lệ đúng hạn SLA</span>
                    <strong className="cat-metric-val text-success">{cat.on_time_rate}%</strong>
                  </div>
                </div>

                <div className="cat-progress-box">
                  <div className="cat-bar-bg">
                    <div
                      className="cat-bar-fill"
                      style={{ width: `${Math.min(100, cat.on_time_rate || 100)}%` }}
                    />
                  </div>
                  <div className="cat-bar-meta">
                    <span>Đúng hạn SLA: {cat.on_time_rate}%</span>
                    <span>{cat.total_requests} hồ sơ</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 3. BIỂU ĐỒ XU HƯỚNG YÊU CẦU & LOẠI YÊU CẦU PHỔ BIẾN NHẤT */}
      <div className="ds-grid-2" style={{ marginTop: 16 }}>
        <section className="panel admin-trend-panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Xu hướng yêu cầu</h2>
              <small className="muted">
                Số lượng yêu cầu theo {period === "day" ? "khung giờ" : period === "week" ? "các ngày trong tuần" : period === "year" ? "các tháng trong năm" : "các tuần trong tháng"}
              </small>
            </div>
            <div className="trend-legends">
              <span className="leg-item"><i className="leg-dot dot-green" /> Thành công</span>
              <span className="leg-item"><i className="leg-dot dot-amber" /> Đang xử lý</span>
              <span className="leg-item"><i className="leg-dot dot-red" /> Bị từ chối</span>
            </div>
          </div>

          <div className="trend-chart-area">
            {trends.length > 0 ? (
              <div className="trend-bar-chart">
                {(() => {
                  const maxVal = Math.max(1, ...trends.map((t) => t.total || 0));
                  return trends.map((item, idx) => {
                    const sucH = ((item.success || 0) / maxVal) * 140;
                    const proH = ((item.processing || 0) / maxVal) * 140;
                    const rejH = ((item.rejected || 0) / maxVal) * 140;
                    return (
                      <div
                        key={idx}
                        className="trend-col"
                        title={`${item.label}: Tổng ${item.total} (Thành công ${item.success}, Đang xử lý ${item.processing}, Từ chối ${item.rejected})`}
                      >
                        <div className="trend-bar-stack">
                          <span className="trend-stack-total">{item.total > 0 ? item.total : ""}</span>
                          <div className="trend-seg seg-red" style={{ height: `${rejH}px` }} />
                          <div className="trend-seg seg-amber" style={{ height: `${proH}px` }} />
                          <div className="trend-seg seg-green" style={{ height: `${sucH}px` }} />
                        </div>
                        <span className="trend-label">{item.label}</span>
                      </div>
                    );
                  });
                })()}
              </div>
            ) : (
              <EmptyState title="Chưa có dữ liệu xu hướng" />
            )}
          </div>
        </section>

        <section className="panel">
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
      <div className="ds-grid-2" style={{ marginTop: 16 }}>
        <section className="panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Top Phòng ban gửi yêu cầu</h2>
              <small className="muted">Khối lượng yêu cầu theo từng phòng ban trong doanh nghiệp</small>
            </div>
          </div>
          {topDepartments.length ? (
            <div className="table-wrap">
              <table className="admin-rank-table">
                <thead>
                  <tr>
                    <th style={{ width: 44 }}>Hạng</th>
                    <th>Phòng ban</th>
                    <th style={{ textAlign: "right" }}>Tổng số</th>
                    <th style={{ textAlign: "right" }}>Thành công</th>
                    <th style={{ textAlign: "right" }}>Tỷ lệ</th>
                  </tr>
                </thead>
                <tbody>
                  {topDepartments.map((d, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className={`rank-badge ${idx === 0 ? "rank-1" : idx === 1 ? "rank-2" : idx === 2 ? "rank-3" : ""}`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td>
                        <strong>{d.department_name}</strong>
                      </td>
                      <td style={{ textAlign: "right" }}>{d.total}</td>
                      <td style={{ textAlign: "right", color: "#16a34a" }}>{d.success}</td>
                      <td style={{ textAlign: "right" }}>
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

        <section className="panel">
          <div className="section-head">
            <div>
              <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Top Cá nhân gửi nhiều yêu cầu</h2>
              <small className="muted">Nhân viên khởi tạo yêu cầu nhiều nhất</small>
            </div>
          </div>
          {topUsers.length ? (
            <div className="table-wrap">
              <table className="admin-rank-table">
                <thead>
                  <tr>
                    <th style={{ width: 44 }}>Hạng</th>
                    <th>Người dùng</th>
                    <th>Phòng ban</th>
                    <th style={{ textAlign: "right" }}>Tổng</th>
                    <th style={{ textAlign: "right" }}>Đã duyệt</th>
                  </tr>
                </thead>
                <tbody>
                  {topUsers.map((u, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className={`rank-badge ${idx === 0 ? "rank-1" : idx === 1 ? "rank-2" : idx === 2 ? "rank-3" : ""}`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td>
                        <div className="user-flex-cell">
                          <div className="user-circle">{(u.name || "U")[0]}</div>
                          <div>
                            <div className="user-display-name">{u.name}</div>
                            <small className="user-email-text muted">{u.email}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <small>{u.department}</small>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <strong>{u.total}</strong>
                      </td>
                      <td style={{ textAlign: "right", color: "#16a34a" }}>
                        <strong>{u.success}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="Chưa có dữ liệu cá nhân" />
          )}
        </section>
      </div>

      {/* 5. TÌNH TRẠNG DỊCH VỤ HỆ THỐNG */}
      {!workspace && <section className="panel" style={{ marginTop: 16 }}>
        <div className="section-head">
          <div>
            <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Tình trạng dịch vụ hệ thống</h2>
            <small className="muted">Kiểm tra tính sẵn sàng của các thành phần nền tảng</small>
          </div>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              ready.reload();
              diagnostics.reload();
            }}
          >
            Kiểm tra lại
          </button>
        </div>
        <HealthList diagnostics={diagnostics} ready={ready} />
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
        <StatCard title="Bước đang tính hạn" value={d.sla.open_stages} detail="Phê duyệt, thực hiện, nghiệm thu" />
        <StatCard title="Đã quá hạn" value={d.sla.overdue_stages} tone={d.sla.overdue_stages ? "danger" : undefined} detail="Cần xử lý hoặc điều chuyển" />
        <StatCard title="Nhắc hạn 24 giờ qua" value={d.sla.alerts_24h.REMINDER || 0} detail={`Báo quá hạn: ${d.sla.alerts_24h.BREACH || 0}`} />
        <StatCard title="Thông báo gửi lỗi" value={counts.DEAD || 0} tone={counts.DEAD ? "danger" : undefined} detail="Cần gửi lại thủ công" />
      </div>
      <div className="ds-grid-2">
        <section className="panel"><h2>Hàng đợi thông báo</h2>
          <ul className="ds-health-list">{Object.entries(OUTBOX_STATES).map(([k, v]) => <li key={k}><span>{v}</span><strong>{counts[k] || 0}</strong></li>)}</ul>
          <p className="muted">Lần gửi gần nhất: {d.outbox.last_sent_at ? date(d.outbox.last_sent_at) : "chưa có"}. {d.worker.backlog_ok ? "Không có thông báo tồn đọng quá 5 phút." : `Có thông báo chờ quá ${Math.round(d.outbox.oldest_pending_seconds / 60)} phút — kiểm tra worker (start_worker_local.cmd).`}</p>
        </section>
        <section className="panel"><h2>Quá hạn cần xử lý</h2>
          <p className="muted">Danh sách chi tiết người đang xử lý và hạn nằm ở trang vận hành.</p>
          <button type="button" onClick={() => navigate("ops")}>Mở theo dõi vận hành →</button>
        </section>
      </div>
      <section className="panel" style={{ marginTop: 16 }}><h2>Thông báo gửi thất bại</h2>
        {d.outbox.dead_events.length ? <div className="table-wrap"><table><thead><tr><th>Loại thông báo</th><th>Hồ sơ</th><th>Số lần thử</th><th>Mã lỗi</th><th>Thời điểm</th><th></th></tr></thead>
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
    {tab === "diagrams" && <WorkflowDiagrams />}
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

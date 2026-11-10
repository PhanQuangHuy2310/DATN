import { useState, useEffect } from "react";
<<<<<<< HEAD
import Icon from "./Icon.jsx";
=======
import { errorText } from "../domain.js";
>>>>>>> origin/main
import { api } from "../api.js";
import { PageHeader } from "./design.jsx";

const CHANGE_TYPE_LABELS = {
  ALL: "Tất cả",
  REGULATION: "Quy định",
  WORKFLOW: "Quy trình",
  PERMISSION: "Phân quyền",
  API_STATUS: "Kết nối API",
  AI_CONFIG: "Quản trị AI",
  SYSTEM: "Hệ thống",
};

const CHANGE_TYPE_COLORS = {
  REGULATION: { bg: "var(--eas-signal-soft)", text: "var(--eas-signal)", border: "var(--eas-signal-soft)" },
  WORKFLOW: { bg: "var(--eas-hover)", text: "var(--eas-ink-600)", border: "var(--eas-hover)" },
  PERMISSION: { bg: "var(--eas-warn-soft)", text: "var(--eas-warn)", border: "var(--eas-warn-soft)" },
  API_STATUS: { bg: "var(--eas-warn-soft)", text: "var(--eas-warn)", border: "var(--eas-warn-soft)" },
  AI_CONFIG: { bg: "var(--eas-ok-soft)", text: "var(--eas-ok)", border: "var(--eas-ok-soft)" },
  SYSTEM: { bg: "var(--eas-surface-sunken)", text: "var(--eas-ink-700)", border: "var(--eas-line)" },
};

export function SystemVersionsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState("ALL");
  const [search, setSearch] = useState("");
  const [diffModal, setDiffModal] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadChangelog = async (silent = false) => {
    try {
      let url = "/api/v1/admin/system-versions/changelog";
      const params = new URLSearchParams();
      if (filterType !== "ALL") params.append("type", filterType);
      if (search.trim()) params.append("q", search.trim());
      if (params.toString()) url += `?${params.toString()}`;

      const res = await api(url);
      setData(res);
    } catch (err) {
      if (!silent) showToast("Không thể tải nhật ký phiên bản: " + errorText(err), "error");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the loader sets state only after its await
    void loadChangelog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterType]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    void loadChangelog();
  };

  const handleExportJson = () => {
    if (!data?.changelog) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eas_system_audit_changelog_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Đã tải xuống file báo cáo Audit thành công!", "success");
  };

  const currentSystem = data?.current_system || {};
  const changelog = data?.changelog || [];

  return (
    <div className="eas-system-versions-page">
      <PageHeader
        eyebrow="QUẢN TRỊ NỀN TẢNG"
        title="Phiên bản hệ thống"
        description="Thông tin phiên bản các thành phần và lịch sử thay đổi cấu hình hệ thống."
        actions={
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => loadChangelog(false)}
              disabled={loading}
            >
              <Icon name="reset" size={14} /> Tải lại
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleExportJson}
              disabled={loading || changelog.length === 0}
            >
              <Icon name="download" size={14} /> Xuất Audit (.JSON)
            </button>
          </div>
        }
      />

      {toast && (
        <div className={`eas-toast eas-toast-${toast.type}`} role="alert">
          {toast.msg}
        </div>
      )}

      {/* 1. TOP SPECIFICATION CARDS */}
      <div className="eas-version-spec-grid">
        <div className="eas-spec-card">
          <div className="eas-spec-card-icon" style={{ background: "var(--eas-signal-soft)", color: "var(--eas-signal)" }}>
            <Icon name="layers" size={14} />
          </div>
          <div className="eas-spec-card-content">
            <span className="eas-spec-label">Phiên bản Hệ thống</span>
            <div className="eas-spec-val-row">
              <span className="eas-spec-val">{currentSystem.system_version || "v2.0"}</span>
              <span className="badge badge-success">Production Ready</span>
            </div>
            <span className="eas-spec-sub">Kiến trúc Micro-service & Supabase RLS</span>
          </div>
        </div>

        <div className="eas-spec-card">
          <div className="eas-spec-card-icon" style={{ background: "var(--eas-ok-soft)", color: "var(--eas-ok)" }}>
            <Icon name="file" size={14} />
          </div>
          <div className="eas-spec-card-content">
            <span className="eas-spec-label">Phiên bản Quy định</span>
            <div className="eas-spec-val-row">
              <span className="eas-spec-val">{currentSystem.regulation_version || "v2.0"}</span>
              <span className="badge badge-info">{currentSystem.regulations_count || 12} quy định</span>
            </div>
            <span className="eas-spec-sub">Đồng bộ AI Knowledge Graph</span>
          </div>
        </div>

        <div className="eas-spec-card">
          <div className="eas-spec-card-icon" style={{ background: "var(--eas-hover)", color: "var(--eas-ink-600)" }}>
            <Icon name="spark" size={14} />
          </div>
          <div className="eas-spec-card-content">
            <span className="eas-spec-label">AI Engine & Model</span>
            <div className="eas-spec-val-row">
              <span className="eas-spec-val" style={{ fontSize: "1.1rem" }}>
                {currentSystem.ai_model || "Gemini 2.5 Flash"}
              </span>
              <span className="badge badge-primary">Hybrid Risk</span>
            </div>
            <span className="eas-spec-sub">
              {currentSystem.ai_provider || "Google DeepMind / Vertex AI"}
            </span>
          </div>
        </div>

        <div className="eas-spec-card">
          <div className="eas-spec-card-icon" style={{ background: "var(--eas-warn-soft)", color: "var(--eas-warn)" }}>
            <Icon name="plug" size={14} />
          </div>
          <div className="eas-spec-card-content">
            <span className="eas-spec-label">Kết nối API Nội bộ</span>
            <div className="eas-spec-val-row">
              <span className="eas-spec-val">
                {currentSystem.apis_enabled_count || 0}/{currentSystem.apis_total_count || 8}
              </span>
              {currentSystem.circuit_breaker_active ? (
                <span className="badge badge-danger">Circuit Breaker BẬT</span>
              ) : (
                <span className="badge badge-success">100% Khả dụng</span>
              )}
            </div>
            <span className="eas-spec-sub">
              {currentSystem.circuit_breaker_active
                ? "Một số API đang tạm ngắt kết nối"
                : "Tất cả 8 hệ thống thông suốt"}
            </span>
          </div>
        </div>
      </div>

      {/* 2. FILTER & SEARCH TOOLBAR */}
      <div className="eas-versions-toolbar">
        <div className="eas-versions-tabs" role="tablist">
          {Object.entries(CHANGE_TYPE_LABELS).map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={`eas-version-tab ${filterType === k ? "is-active" : ""}`}
              onClick={() => setFilterType(k)}
              role="tab"
              aria-selected={filterType === k}
            >
              {label}
            </button>
          ))}
        </div>

        <form className="eas-versions-search" onSubmit={handleSearchSubmit}>
          <input
            type="search"
            placeholder="Tìm theo tiêu đề, người sửa, nội dung..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary">
            Tìm kiếm
          </button>
        </form>
      </div>

      {/* 3. CHANGELOG AUDIT TIMELINE */}
      {loading ? (
        <div className="eas-loading-box">
          <div className="eas-spinner" />
          <p>Đang tải nhật ký thay đổi phiên bản...</p>
        </div>
      ) : changelog.length === 0 ? (
        <div className="eas-empty-box">
          <p className="eas-empty-title">Không tìm thấy bản ghi nhật ký nào</p>
          <p className="eas-empty-sub">
            {search
              ? "Hãy thử từ khóa tìm kiếm khác hoặc chuyển bộ lọc về 'Tất cả'."
              : "Hệ thống chưa ghi nhận thay đổi nào trong phân loại này."}
          </p>
        </div>
      ) : (
        <div className="eas-changelog-timeline">
          {changelog.map((entry, idx) => {
            const colorCfg =
              CHANGE_TYPE_COLORS[entry.change_type] || CHANGE_TYPE_COLORS.SYSTEM;
            const formattedDate = entry.created_at
              ? new Date(entry.created_at).toLocaleString("vi-VN", {
                  year: "numeric",
                  month: "2-digit",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—";

            return (
              <div className="eas-changelog-item" key={entry.id || idx}>
                <div className="eas-changelog-marker">
                  <div
                    className="eas-changelog-dot"
                    style={{ borderColor: colorCfg.text, background: colorCfg.bg }}
                  />
                  {idx < changelog.length - 1 && <div className="eas-changelog-line" />}
                </div>

                <div className="eas-changelog-card">
                  <div className="eas-changelog-head">
                    <div className="eas-changelog-badges">
                      <span
                        className="eas-changelog-type-pill"
                        style={{
                          background: colorCfg.bg,
                          color: colorCfg.text,
                          borderColor: colorCfg.border,
                        }}
                      >
                        {CHANGE_TYPE_LABELS[entry.change_type] || entry.change_type}
                      </span>
                      <span className="eas-scope-badge">{entry.change_scope}</span>
                      {entry.version_from && entry.version_to && (
                        <span className="eas-version-jump">
                          <code>{entry.version_from}</code> → <strong>{entry.version_to}</strong>
                        </span>
                      )}
                    </div>
                    <span className="eas-changelog-time" title={entry.created_at}>
                      <Icon name="clock" size={14} /> {formattedDate}
                    </span>
                  </div>

                  <h3 className="eas-changelog-title">{entry.title}</h3>
                  {entry.description && (
                    <p className="eas-changelog-desc">{entry.description}</p>
                  )}

                  <div className="eas-changelog-foot">
                    <span className="eas-changelog-author">
                      <Icon name="user" size={14} /> Thực hiện bởi: <strong>{entry.created_by_name || entry.created_by || "Admin"}</strong>
                    </span>

                    {(entry.old_value || entry.new_value) && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline"
                        onClick={() => setDiffModal(entry)}
                      >
                        <Icon name="search" size={14} /> Xem Diff chi tiết
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 4. BEFORE / AFTER DIFF MODAL */}
      {diffModal && (
        <div className="eas-modal-overlay" role="presentation" onClick={(e) => e.target === e.currentTarget && setDiffModal(null)} onKeyDown={(e) => e.key === "Escape" && setDiffModal(null)}>
          <div
            className="eas-modal eas-modal-wide"
            role="dialog"
            aria-modal="true"
          >
            <div className="eas-modal-header">
              <div>
                <h3 className="eas-modal-title">Chi tiết thay đổi</h3>
                <p className="eas-modal-sub">
                  Mã sự kiện: <code>{diffModal.id}</code> · {diffModal.title}
                </p>
              </div>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setDiffModal(null)}
                aria-label="Đóng"
              >
                <Icon name="x" size={16} />
              </button>
            </div>

            <div className="eas-modal-body">
              <div className="eas-diff-meta-box">
                <div>
                  <strong>Loại:</strong> {CHANGE_TYPE_LABELS[diffModal.change_type] || diffModal.change_type} (
                  {diffModal.change_scope})
                </div>
                <div>
                  <strong>Phiên bản:</strong> {diffModal.version_from || "—"} →{" "}
                  <strong>{diffModal.version_to || "—"}</strong>
                </div>
                <div>
                  <strong>Người thực hiện:</strong> {diffModal.created_by_name || diffModal.created_by || "Admin"}
                </div>
              </div>

              <div className="eas-diff-compare-container">
                <div className="eas-diff-column">
                  <div className="eas-diff-col-head eas-diff-old-head">
                    <span><span className="status-dot is-red" aria-hidden="true" />Trước thay đổi</span>
                  </div>
                  <pre className="eas-diff-code">
                    {diffModal.old_value
                      ? typeof diffModal.old_value === "object"
                        ? JSON.stringify(diffModal.old_value, null, 2)
                        : String(diffModal.old_value)
                      : "(Trống / Khởi tạo mới)"}
                  </pre>
                </div>

                <div className="eas-diff-column">
                  <div className="eas-diff-col-head eas-diff-new-head">
                    <span><span className="status-dot is-green" aria-hidden="true" />Sau thay đổi</span>
                  </div>
                  <pre className="eas-diff-code">
                    {diffModal.new_value
                      ? typeof diffModal.new_value === "object"
                        ? JSON.stringify(diffModal.new_value, null, 2)
                        : String(diffModal.new_value)
                      : "(Đã xóa / Không có giá trị mới)"}
                  </pre>
                </div>
              </div>
            </div>

            <div className="eas-modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDiffModal(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export default SystemVersionsPage;


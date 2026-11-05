import { useState, useEffect } from "react";
import { useApiBase } from "../apiBase.js";
import { usePermission } from "../hooks/usePermission.jsx";
import { api } from "../api.js";
import { errorText } from "../domain.js";
import { PageHeader } from "./design.jsx";

const CATEGORIES = [
  "Tất cả",
  "Thời gian & Nghỉ phép",
  "Hạn mức & Phê duyệt",
  "Bảo mật & Kỹ thuật",
  "Vận hành & Kỷ luật",
  "Quy định chung",
];

export function RegulationsManagementPage() {
  const apiBase = useApiBase();
  // Buttons follow the rights the admin granted on module "regulations".
  const { canCreate, canUpdate, canDelete } = usePermission("regulations");
  const [toast, setToast] = useState(null);
  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };
  const [regulations, setRegulations] = useState([]);
  const [aiState, setAiState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("Tất cả");

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRegulation, setEditingRegulation] = useState(null);
  const [viewingRegulation, setViewingRegulation] = useState(null);
  const [deletingRegulation, setDeletingRegulation] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Form inputs
  const [formCode, setFormCode] = useState("");
  const [formTitle, setFormTitle] = useState("");
  const [formCategory, setFormCategory] = useState("Thời gian & Nghỉ phép");
  const [formContent, setFormContent] = useState("");
  const [formSummary, setFormSummary] = useState("");

  const loadData = async (silent = false) => {
    try {
      const res = await api(`${apiBase}/regulations`);
      setRegulations(res.regulations || []);
      setAiState(res.ai_state || null);
    } catch (err) {
      if (!silent) showToast("Không thể tải danh sách quy định: " + errorText(err), "error");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the loader sets state only after its await
    loadData();
    // Auto-refresh periodically if AI is currently syncing/learning
    const timer = setInterval(() => {
      loadData(true);
    }, 2500);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCreateModal = () => {
    const nextMajor = (aiState?.global_major_version || 1) + 1;
    setFormCode(`REG-${String(nextMajor).padStart(3, "0")}`);
    setFormTitle("");
    setFormCategory("Thời gian & Nghỉ phép");
    setFormContent("");
    setFormSummary("");
    setShowCreateModal(true);
  };

  const openEditModal = (reg) => {
    setEditingRegulation(reg);
    setFormCode(reg.code || "");
    setFormTitle(reg.title || "");
    setFormCategory(reg.category || "Quy định chung");
    setFormContent(reg.content || "");
    setFormSummary("");
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!formTitle.trim() || !formContent.trim()) {
      showToast("Vui lòng nhập đầy đủ tiêu đề và nội dung quy định", "warning");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api(`${apiBase}/regulations`, {
        method: "POST",
        body: JSON.stringify({
          code: formCode.trim(),
          title: formTitle.trim(),
          category: formCategory,
          content: formContent.trim(),
        }),
      });
      showToast(res.message || "Đã thêm quy định mới và nâng phiên bản hệ thống!", "success");
      setShowCreateModal(false);
      loadData();
    } catch (err) {
      showToast("Lỗi khi thêm quy định: " + errorText(err), "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!formTitle.trim() || !formContent.trim()) {
      showToast("Vui lòng nhập đầy đủ tiêu đề và nội dung quy định", "warning");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api(`${apiBase}/regulations/${editingRegulation.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: formTitle.trim(),
          category: formCategory,
          content: formContent.trim(),
          change_summary: formSummary.trim(),
        }),
      });
      showToast(res.message || "Đã cập nhật quy định và nâng phiên bản nhỏ!", "success");
      setEditingRegulation(null);
      loadData();
    } catch (err) {
      showToast("Lỗi khi cập nhật quy định: " + errorText(err), "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteSubmit = async () => {
    if (!deletingRegulation) return;
    setSubmitting(true);
    try {
      const res = await api(`${apiBase}/regulations/${deletingRegulation.id}`, {
        method: "DELETE",
      });
      showToast(res.message || "Đã gỡ bỏ quy định và nâng phiên bản lớn!", "success");
      setDeletingRegulation(null);
      loadData();
    } catch (err) {
      showToast("Lỗi khi xóa quy định: " + errorText(err), "error");
    } finally {
      setSubmitting(false);
    }
  };

  const openViewModal = async (reg) => {
    setViewingRegulation(reg);
    try {
      const res = await api(`${apiBase}/regulations/${reg.id}`);
      if (res.regulation) {
        setViewingRegulation(res.regulation);
      }
    } catch {}
  };

  // Filter regulations
  const filteredRegulations = regulations.filter((r) => {
    const matchCat = selectedCategory === "Tất cả" || r.category === selectedCategory;
    const matchSearch =
      !search ||
      r.title?.toLowerCase().includes(search.toLowerCase()) ||
      r.code?.toLowerCase().includes(search.toLowerCase()) ||
      r.content?.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  const activeVersion = aiState?.active_regulation_version || "v1.0";
  const targetVersion = aiState?.target_regulation_version || activeVersion;
  const isSyncing = aiState?.client_maintenance_lock || aiState?.sync_status !== "COMPLETED";

  return (
    <div className="page-container regulations-page">
      <PageHeader
        eyebrow="TRI THỨC & AI"
        title="Quy định công ty & Semantic Versioning"
        description="Quản lý bộ quy định nghiệp vụ, tự động đánh số phiên bản Semantic (Major/Minor) và đồng bộ tri thức sang AI Engine."
      />

      {/* Top Meta Cards */}
      <div className="eas-meta-cards-row">
        <div className="eas-meta-stat-card primary-border">
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Phiên bản quy định hiện hành</span>
            <span className="version-pill current-version">{activeVersion}</span>
          </div>
          <div className="eas-meta-stat-value">{activeVersion}</div>
          <div className="eas-meta-stat-sub">
            Toàn bộ luồng phê duyệt và AI đang vận hành theo bản này
          </div>
        </div>

        <div className="eas-meta-stat-card">
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Tổng số điều khoản quy định</span>
            <span className="eas-badge-neutral">{regulations.length} điều khoản</span>
          </div>
          <div className="eas-meta-stat-value">{regulations.length}</div>
          <div className="eas-meta-stat-sub">
            {CATEGORIES.length - 1} danh mục quy chế nghiệp vụ
          </div>
        </div>

        <div className={`eas-meta-stat-card ${isSyncing ? "warning-border" : "success-border"}`}>
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Trạng thái đồng bộ AI Engine</span>
            {isSyncing ? (
              <span className="eas-badge-warning pulse">ĐANG HUẤN LUYỆN ({aiState?.progress_percent || 0}%)</span>
            ) : (
              <span className="eas-badge-success">ĐÃ ĐỒNG BỘ 100%</span>
            )}
          </div>
          <div className="eas-meta-stat-value">
            {isSyncing ? `${aiState?.progress_percent || 0}%` : "Sẵn sàng"}
          </div>
          <div className="eas-meta-stat-sub">
            {isSyncing
              ? `AI đang học phiên bản ${targetVersion} (${aiState?.current_step_label || "Đang xử lý..."})`
              : `Mô hình Gemini & Scikit-Learn đang áp dụng ${activeVersion}`}
          </div>
        </div>
      </div>

      {/* Live AI Training Alert Banner */}
      {isSyncing && (
        <div className="ai-training-banner">
          <div className="ai-training-banner-icon">🤖</div>
          <div className="ai-training-banner-content">
            <strong>AI Engine đang trong quá trình học và cập nhật quy định ({targetVersion})</strong>
            <p>
              Bước hiện tại ({aiState?.progress_percent || 25}%): {aiState?.current_step_label}.
              Web Client đang ở chế độ bảo trì để đảm bảo an toàn nghiệp vụ.
            </p>
            <div className="ai-progress-track">
              <div
                className="ai-progress-bar-fill"
                style={{ width: `${aiState?.progress_percent || 25}%` }}
              ></div>
            </div>
          </div>
        </div>
      )}

      {/* Action Toolbar */}
      <div className="regulations-toolbar">
        <div className="regulations-search-group">
          <div className="search-input-wrapper">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Tìm kiếm theo mã, tiêu đề, nội dung quy định..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="eas-input"
            />
          </div>
          <div className="category-chips">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                className={`category-chip ${selectedCategory === cat ? "active" : ""}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {canCreate && (
          <button type="button" className="btn-primary btn-add-regulation" onClick={openCreateModal}>
            <span>+</span> Thêm quy định mới
          </button>
        )}
      </div>

      {/* Regulations Table / Grid */}
      <div className="regulations-table-container">
        {loading ? (
          <div className="eas-empty-state">
            <div className="eas-spinner"></div>
            <p>Đang tải danh sách quy định...</p>
          </div>
        ) : filteredRegulations.length === 0 ? (
          <div className="eas-empty-state">
            <span className="empty-icon">📋</span>
            <p>Không tìm thấy quy định nào phù hợp với bộ lọc.</p>
          </div>
        ) : (
          <div className="regulations-list">
            {filteredRegulations.map((reg) => (
              <div key={reg.id} className="regulation-card">
                <div className="regulation-card-header">
                  <div className="regulation-code-tag">
                    <span className="reg-code">{reg.code}</span>
                    <span className="reg-category">{reg.category}</span>
                    <span className="reg-version">v{reg.version_string || "1.0"}</span>
                  </div>
                  <div className="regulation-actions">
                    <button
                      type="button"
                      className="btn-action btn-view"
                      title="Xem chi tiết & Lịch sử phiên bản"
                      onClick={() => openViewModal(reg)}
                    >
                      👁 Xem
                    </button>
                    {canUpdate && (
                      <button
                        type="button"
                        className="btn-action btn-edit"
                        title="Chỉnh sửa (Tăng Minor Version)"
                        onClick={() => openEditModal(reg)}
                      >
                        ✎ Sửa
                      </button>
                    )}
                    {canDelete && (
                      <button
                        type="button"
                        className="btn-action btn-delete"
                        title="Xóa quy định (Tăng Major Version)"
                        onClick={() => setDeletingRegulation(reg)}
                      >
                        ✕ Xóa
                      </button>
                    )}
                  </div>
                </div>

                <h3 className="regulation-card-title">{reg.title}</h3>
                <p className="regulation-card-content">{reg.content}</p>

                <div className="regulation-card-footer">
                  <span className="reg-updated-at">
                    🕒 Cập nhật: {reg.updated_at ? new Date(reg.updated_at).toLocaleString("vi-VN") : "Ban đầu"}
                  </span>
                  <span className="reg-policy-version-badge">
                    Mã phiên bản: <strong>{reg.version_string ? `v${reg.version_string}` : "v1.0"}</strong>
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Semantic Versioning Rules Card Info */}
      <div className="versioning-rules-notice-box">
        <div className="notice-icon">💡</div>
        <div className="notice-body">
          <h4>Quy tắc đánh số phiên bản tự động (Semantic Versioning):</h4>
          <ul>
            <li>
              <strong>Sửa nội dung điều khoản hiện có:</strong> Tự động tăng <strong>Phiên bản nhỏ (Minor Version)</strong> (Ví dụ: từ <code>{activeVersion}</code> lên <code>v{aiState?.global_major_version || 1}.{(aiState?.global_minor_version || 0) + 1}</code>).
            </li>
            <li>
              <strong>Thêm mới hoặc Xóa điều khoản:</strong> Tự động tăng <strong>Phiên bản lớn (Major Version)</strong> (Ví dụ: từ <code>{activeVersion}</code> lên <code>v{(aiState?.global_major_version || 1) + 1}.0</code>).
            </li>
            <li>
              <strong>Tự động học AI:</strong> Mọi thao tác Thêm / Sửa / Xóa đều kích hoạt luồng đồng bộ sang AI Service và tạm khóa Web Client trong ít giây cho tới khi hoàn tất.
            </li>
          </ul>
        </div>
      </div>

      {/* MODAL: Thêm quy định mới */}
      {showCreateModal && (
        <div className="eas-modal-overlay">
          <div className="eas-modal-card">
            <div className="eas-modal-header">
              <h3>Thêm quy định mới</h3>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setShowCreateModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="eas-modal-form">
              <div className="version-bump-alert major">
                <span className="alert-icon">⚡</span>
                <div className="alert-text">
                  <strong>Thao tác này sẽ tăng Major Version:</strong> Hệ thống sẽ nâng phiên bản từ <strong>{activeVersion}</strong> lên <strong>v{(aiState?.global_major_version || 1) + 1}.0</strong> và đẩy AI Service học lại.
                </div>
              </div>

              <div className="form-row two-cols">
                <div className="form-group">
                  <label htmlFor="regulationsmanagementpage-field-392">Mã quy định:</label>
                  <input id="regulationsmanagementpage-field-392"
                    type="text"
                    className="eas-input"
                    value={formCode}
                    onChange={(e) => setFormCode(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="regulationsmanagementpage-field-402">Danh mục quy chế:</label>
                  <select id="regulationsmanagementpage-field-402"
                    className="eas-select"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                  >
                    {CATEGORIES.filter((c) => c !== "Tất cả").map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="regulationsmanagementpage-field-418">Tiêu đề quy định:</label>
                <input id="regulationsmanagementpage-field-418"
                  type="text"
                  className="eas-input"
                  placeholder="Ví dụ: Quy định thời gian phê duyệt yêu cầu khẩn cấp"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="regulationsmanagementpage-field-430">Nội dung chi tiết điều khoản:</label>
                <textarea id="regulationsmanagementpage-field-430"
                  className="eas-textarea"
                  rows={6}
                  placeholder="Mô tả chi tiết nội dung quy định, điều kiện áp dụng, các trường hợp ngoại lệ..."
                  value={formContent}
                  onChange={(e) => setFormContent(e.target.value)}
                  required
                />
              </div>

              <div className="eas-modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Hủy bỏ
                </button>
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting ? "Đang lưu & Huấn luyện AI..." : "Ban hành & Huấn luyện AI (v" + ((aiState?.global_major_version || 1) + 1) + ".0)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Chỉnh sửa quy định */}
      {editingRegulation && (
        <div className="eas-modal-overlay">
          <div className="eas-modal-card">
            <div className="eas-modal-header">
              <h3>Chỉnh sửa quy định: {editingRegulation.code}</h3>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setEditingRegulation(null)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="eas-modal-form">
              <div className="version-bump-alert minor">
                <span className="alert-icon">📝</span>
                <div className="alert-text">
                  <strong>Thao tác chỉnh sửa sẽ tăng Minor Version:</strong> Hệ thống sẽ nâng phiên bản từ <strong>{activeVersion}</strong> lên <strong>v{aiState?.global_major_version || 1}.{(aiState?.global_minor_version || 0) + 1}</strong>.
                </div>
              </div>

              <div className="form-row two-cols">
                <div className="form-group">
                  <label htmlFor="regulationsmanagementpage-field-483">Mã quy định (Cố định):</label>
                  <input id="regulationsmanagementpage-field-483"
                    type="text"
                    className="eas-input"
                    value={formCode}
                    disabled
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="regulationsmanagementpage-field-492">Danh mục quy chế:</label>
                  <select id="regulationsmanagementpage-field-492"
                    className="eas-select"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                  >
                    {CATEGORIES.filter((c) => c !== "Tất cả").map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="regulationsmanagementpage-field-508">Tiêu đề quy định:</label>
                <input id="regulationsmanagementpage-field-508"
                  type="text"
                  className="eas-input"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="regulationsmanagementpage-field-519">Nội dung chi tiết điều khoản:</label>
                <textarea id="regulationsmanagementpage-field-519"
                  className="eas-textarea"
                  rows={6}
                  value={formContent}
                  onChange={(e) => setFormContent(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="regulationsmanagementpage-field-530">Tóm tắt nội dung thay đổi (Changelog):</label>
                <input id="regulationsmanagementpage-field-530"
                  type="text"
                  className="eas-input"
                  placeholder="Ví dụ: Bổ sung định mức công tác phí cho khu vực miền núi..."
                  value={formSummary}
                  onChange={(e) => setFormSummary(e.target.value)}
                />
              </div>

              <div className="eas-modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setEditingRegulation(null)}
                >
                  Hủy bỏ
                </button>
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting
                    ? "Đang lưu & Huấn luyện AI..."
                    : `Cập nhật & Huấn luyện AI (v${aiState?.global_major_version || 1}.${(aiState?.global_minor_version || 0) + 1})`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Xác nhận xóa quy định */}
      {deletingRegulation && (
        <div className="eas-modal-overlay">
          <div className="eas-modal-card danger-modal">
            <div className="eas-modal-header">
              <h3>Xác nhận gỡ bỏ quy định</h3>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setDeletingRegulation(null)}
              >
                ✕
              </button>
            </div>

            <div className="eas-modal-body">
              <div className="version-bump-alert major">
                <span className="alert-icon">🚨</span>
                <div className="alert-text">
                  <strong>Xóa điều khoản sẽ tăng Major Version:</strong> Nâng phiên bản hệ thống lên <strong>v{(aiState?.global_major_version || 1) + 1}.0</strong> và đẩy AI Service học lại.
                </div>
              </div>

              <p>
                Bạn có chắc chắn muốn gỡ bỏ quy định:
                <br />
                <strong>{deletingRegulation.code} — {deletingRegulation.title}</strong>?
              </p>
              <p className="danger-subtext">
                Điều khoản này sẽ bị ngừng áp dụng trong toàn bộ quy trình phê duyệt của công ty.
              </p>
            </div>

            <div className="eas-modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setDeletingRegulation(null)}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={handleDeleteSubmit}
                disabled={submitting}
              >
                {submitting ? "Đang xử lý..." : "Xác nhận gỡ bỏ & Nâng Major Version"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Xem chi tiết & Lịch sử phiên bản */}
      {viewingRegulation && (
        <div className="eas-modal-overlay">
          <div className="eas-modal-card view-modal">
            <div className="eas-modal-header">
              <div>
                <h3>{viewingRegulation.code} — {viewingRegulation.title}</h3>
                <span className="reg-category">{viewingRegulation.category}</span>
              </div>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setViewingRegulation(null)}
              >
                ✕
              </button>
            </div>

            <div className="eas-modal-body">
              <div className="regulation-view-section">
                <h4>Nội dung điều khoản hiện tại (Phiên bản v{viewingRegulation.version_string || "1.0"})</h4>
                <div className="regulation-full-text">{viewingRegulation.content}</div>
              </div>

              {viewingRegulation.history && viewingRegulation.history.length > 0 && (
                <div className="regulation-history-section">
                  <h4>Lịch sử thay đổi điều khoản này ({viewingRegulation.history.length} bản ghi):</h4>
                  <div className="history-timeline">
                    {viewingRegulation.history.map((h, idx) => (
                      <div key={h.id || idx} className="history-timeline-item">
                        <div className="timeline-badge">v{h.version_string}</div>
                        <div className="timeline-content">
                          <div className="timeline-header">
                            <span className="timeline-action">{h.action_type}</span>
                            <span className="timeline-time">
                              {h.created_at ? new Date(h.created_at).toLocaleString("vi-VN") : ""}
                            </span>
                          </div>
                          <p className="timeline-summary">{h.change_summary || "Cập nhật điều khoản"}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="eas-modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setViewingRegulation(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
          {toast && (
        <div className={`eas-toast-notification ${toast.type}`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
export default RegulationsManagementPage;

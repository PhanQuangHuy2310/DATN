import { useEffect, useMemo, useState } from "react";
import { useApiBase } from "../apiBase.js";
import { api } from "../api.js";
import { PermissionGuard } from "./PermissionGuard.jsx";
import { Modal } from "./ui.jsx";

const STAGE_LABELS = {
  YEU_CAU: "1. Khởi tạo yêu cầu",
  PHE_DUYET: "2. Phê duyệt",
  THUC_HIEN: "3. Thực hiện",
  NGHIEM_THU: "4. Nghiệm thu",
  HOAN_THANH: "5. Hoàn thành / Lưu trữ",
};

const CATEGORY_META = {
  A: {
    badge: "badge-success",
    color: "#16a34a",
    sla: "4 giờ",
    summary: "Tự động hóa hoàn toàn / Rủi ro thấp",
    condition: "Trọng số >= 80%, AI đối chiếu quy định tự động, không cần phê duyệt thủ công.",
  },
  B: {
    badge: "badge-primary",
    color: "#2563eb",
    sla: "24 giờ",
    summary: "Phê duyệt cấp Phòng ban / Rủi ro trung bình",
    condition: "Trọng số 50 - 79%, Trưởng phòng trực tiếp duyệt, có phân công thực hiện và nghiệm thu.",
  },
  C: {
    badge: "badge-warning",
    color: "#ea580c",
    sla: "48 giờ",
    summary: "Phê duyệt Đa cấp & Ban Giám Đốc / Trọng yếu",
    condition: "Trọng số < 50%, Ban Giám Đốc & Hội đồng thẩm định duyệt, quản lý ngân sách / rủi ro cao.",
  },
};

export default function RequestWorkflowsPage() {
  const apiBase = useApiBase();
  const [categories, setCategories] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [mockApis, setMockApis] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [toast, setToast] = useState(null);

  // Modals state
  const [editingCategory, setEditingCategory] = useState(null);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [deletingTemplate, setDeletingTemplate] = useState(null);
  const [viewingWorkflow, setViewingWorkflow] = useState(null);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Load all data
  const loadData = async () => {
    try {
      const [catRes, tplRes, apiRes] = await Promise.all([
        api(`${apiBase}/workflow-categories`),
        api(`${apiBase}/request-templates`),
        api(`${apiBase}/mock-apis`),
      ]);
      setCategories(catRes.items || []);
      setTemplates(tplRes.items || []);
      setMockApis(apiRes.items || []);
    } catch (err) {
      showToast("Lỗi tải dữ liệu: " + (err.message || "Không thể kết nối"), "error");
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the loader sets state only after its await
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // Switch category of a template directly in the table
  const handleCategoryChange = async (template, newCategory) => {
    if (template.category_code === newCategory) return;
    try {
      const res = await api(`${apiBase}/request-templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({ category_code: newCategory }),
      });
      if (res.success && res.item) {
        setTemplates((prev) =>
          prev.map((t) => (t.id === template.id ? res.item : t))
        );
        showToast(
          `Đã chuyển mẫu "${template.name}" sang Phân loại ${newCategory}. Quy trình xử lý đã tự động cập nhật theo chuẩn Nhóm ${newCategory}!`,
          "success"
        );
      }
    } catch (err) {
      showToast("Lỗi khi chuyển phân loại: " + (err.message || "Không thể cập nhật"), "error");
    }
  };

  // Update weight directly in the table
  const handleWeightChange = async (template, newWeight) => {
    const val = Math.max(0, Math.min(100, parseInt(newWeight, 10) || 0));
    try {
      const res = await api(`${apiBase}/request-templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({ automation_weight: val }),
      });
      if (res.success && res.item) {
        setTemplates((prev) =>
          prev.map((t) => (t.id === template.id ? { ...t, automation_weight: val } : t))
        );
        showToast(`Đã lưu trọng số tự động hóa ${val}% cho mẫu "${template.name}".`, "success");
      }
    } catch (err) {
      showToast("Lỗi lưu trọng số: " + err.message, "error");
    }
  };

  // Save standard category workflow steps
  const handleSaveCategory = async (catData) => {
    try {
      const res = await api(`${apiBase}/workflow-categories/${catData.category_code}`, {
        method: "PATCH",
        body: JSON.stringify(catData),
      });
      if (res.success) {
        setEditingCategory(null);
        showToast(
          `Đã cập nhật quy trình chuẩn Nhóm ${catData.category_code}. Các mẫu liên quan đã được đồng bộ!`,
          "success"
        );
        loadData();
      }
    } catch (err) {
      showToast("Lỗi lưu quy trình: " + err.message, "error");
    }
  };

  // Save template edit
  const handleSaveTemplate = async (tplData) => {
    try {
      const isNew = !tplData.id;
      const url = isNew
        ? `${apiBase}/request-templates`
        : `${apiBase}/request-templates/${tplData.id}`;
      const method = isNew ? "POST" : "PATCH";

      const res = await api(url, {
        method,
        body: JSON.stringify(tplData),
      });

      if (res.success) {
        setEditingTemplate(null);
        setCreatingTemplate(false);
        showToast(
          isNew
            ? `Tạo mẫu yêu cầu "${tplData.name}" thành công!`
            : `Đã cập nhật mẫu yêu cầu "${tplData.name}"!`,
          "success"
        );
        loadData();
      }
    } catch (err) {
      showToast("Lỗi lưu mẫu: " + err.message, "error");
    }
  };

  // Delete template
  const handleDeleteTemplate = async (template) => {
    try {
      const res = await api(`${apiBase}/request-templates/${template.id}`, {
        method: "DELETE",
      });
      if (res.success) {
        setDeletingTemplate(null);
        showToast(
          res.action === "soft_deleted"
            ? `Đã ẩn mẫu "${template.name}" do có hồ sơ lịch sử tham chiếu.`
            : `Đã xóa hoàn toàn mẫu "${template.name}".`,
          "success"
        );
        loadData();
      }
    } catch (err) {
      showToast("Lỗi xóa mẫu: " + err.message, "error");
    }
  };

  // Filtered templates list
  const filteredTemplates = useMemo(() => {
    return templates.filter((tpl) => {
      const matchSearch =
        !search ||
        (tpl.name && tpl.name.toLowerCase().includes(search.toLowerCase())) ||
        (tpl.code && tpl.code.toLowerCase().includes(search.toLowerCase())) ||
        (tpl.request_type && tpl.request_type.toLowerCase().includes(search.toLowerCase()));
      const matchCat = categoryFilter === "ALL" || tpl.category_code === categoryFilter;
      return matchSearch && matchCat;
    });
  }, [templates, search, categoryFilter]);

  return (
    <div className="admin-workflows-page">
      {/* Toast Notification */}
      {toast && (
        <div className={`rw-toast rw-toast-${toast.type}`} role="alert">
          <span>{toast.message}</span>
          <button type="button" onClick={() => setToast(null)}>×</button>
        </div>
      )}

      {/* Page Header */}
      <div className="rw-header-banner">
        <div>
          <span className="eyebrow">QUẢN TRỊ LUỒNG DOANH NGHIỆP</span>
          <h1 className="rw-title">Yêu cầu & Quy trình</h1>
          <p className="rw-subtitle">
            Cấu hình 3 phân loại quy trình chuẩn (A, B, C), trọng số tự động hóa AI và danh mục mẫu yêu cầu toàn hệ thống.
          </p>
        </div>
        <div className="rw-header-actions">
          <PermissionGuard module="requests_workflows" action="create">
            <button
              type="button"
              className="rw-btn-primary"
              onClick={() => setCreatingTemplate(true)}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span>Tạo mẫu yêu cầu mới</span>
            </button>
          </PermissionGuard>
        </div>
      </div>

      {/* =========================================================================
          KHU VỰC 1: CẤU HÌNH 3 PHÂN LOẠI QUY TRÌNH (A, B, C)
          ========================================================================= */}
      <section className="rw-section">
        <div className="rw-section-header">
          <div>
            <h2 className="rw-section-title">Khu vực 1: Quy trình chuẩn 3 Phân loại lớn (A, B, C)</h2>
            <p className="rw-section-desc">
              Mỗi phân loại đại diện cho một cấp độ rủi ro và phương thức phê duyệt. Thay đổi tại đây sẽ tự động lan truyền đến tất cả các mẫu yêu cầu thuộc phân loại đó.
            </p>
          </div>
        </div>

        <div className="rw-categories-grid">
          {categories.map((cat) => {
            const meta = CATEGORY_META[cat.category_code] || CATEGORY_META.B;
            const steps = cat.workflow_steps || [];
            return (
              <div key={cat.category_code} className={`rw-category-card rw-cat-${cat.category_code.toLowerCase()}`}>
                <div className="rw-cat-header">
                  <div className="rw-cat-badge-wrap">
                    <span className="rw-cat-letter">{cat.category_code}</span>
                    <div>
                      <h3 className="rw-cat-name">{cat.name}</h3>
                      <span className="rw-cat-sla">Cam kết SLA: <strong>{cat.sla_hours} giờ</strong></span>
                    </div>
                  </div>
                  <PermissionGuard module="requests_workflows" action="update">
                    <button
                      type="button"
                      className="rw-btn-secondary rw-btn-sm"
                      onClick={() => setEditingCategory({ ...cat })}
                    >
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                      <span>Sửa quy trình chuẩn</span>
                    </button>
                  </PermissionGuard>
                </div>

                <p className="rw-cat-desc">{cat.description || meta.summary}</p>
                <div className="rw-cat-condition">
                  <strong>Điều kiện kích hoạt:</strong> {meta.condition}
                </div>

                {/* Visual Workflow Steps Flow */}
                <div className="rw-steps-container">
                  <div className="rw-steps-title">Chuỗi bước xử lý ({steps.length} bước):</div>
                  <div className="rw-steps-timeline">
                    {steps.map((st, idx) => (
                      <div key={idx} className="rw-step-node">
                        <div className="rw-step-circle">{st.step || idx + 1}</div>
                        <div className="rw-step-info">
                          <span className="rw-step-name">{st.name}</span>
                          <span className="rw-step-actor">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                              <circle cx="12" cy="7" r="4" />
                            </svg>
                            {st.actor || "Người phụ trách"}
                          </span>
                        </div>
                        {idx < steps.length - 1 && <div className="rw-step-arrow">→</div>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* =========================================================================
          KHU VỰC 2: DANH SÁCH CÁC MẪU YÊU CẦU (FORM TEMPLATES)
          ========================================================================= */}
      <section className="rw-section" style={{ marginTop: 32 }}>
        <div className="rw-section-header">
          <div>
            <h2 className="rw-section-title">Khu vực 2: Danh sách các Mẫu Yêu cầu (Form Templates)</h2>
            <p className="rw-section-desc">
              Quản lý các biểu mẫu yêu cầu, gán phân loại A/B/C, điều chỉnh thanh trượt trọng số tự động hóa và liên kết API tích hợp.
            </p>
          </div>
          <div className="rw-filter-bar">
            {/* Category tabs filter */}
            <div className="rw-cat-tabs">
              <button
                type="button"
                className={categoryFilter === "ALL" ? "is-active" : ""}
                onClick={() => setCategoryFilter("ALL")}
              >
                Tất cả ({templates.length})
              </button>
              <button
                type="button"
                className={categoryFilter === "A" ? "is-active" : ""}
                onClick={() => setCategoryFilter("A")}
              >
                Loại A ({templates.filter((t) => t.category_code === "A").length})
              </button>
              <button
                type="button"
                className={categoryFilter === "B" ? "is-active" : ""}
                onClick={() => setCategoryFilter("B")}
              >
                Loại B ({templates.filter((t) => t.category_code === "B").length})
              </button>
              <button
                type="button"
                className={categoryFilter === "C" ? "is-active" : ""}
                onClick={() => setCategoryFilter("C")}
              >
                Loại C ({templates.filter((t) => t.category_code === "C").length})
              </button>
            </div>
            {/* Search Input */}
            <div className="rw-search-wrap">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="search"
                placeholder="Tìm kiếm mẫu, mã code..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="rw-search-input"
              />
            </div>
          </div>
        </div>

        {/* Templates Data Table */}
        <div className="rw-table-card">
          <div className="table-wrap">
            <table className="rw-table">
              <thead>
                <tr>
                  <th>Tên mẫu yêu cầu</th>
                  <th>Loại nghiệp vụ</th>
                  <th style={{ minWidth: 170 }}>Thuộc phân loại</th>
                  <th style={{ minWidth: 200 }}>Trọng số (Weight)</th>
                  <th>API tích hợp</th>
                  <th>Quy trình hiện tại</th>
                  <th style={{ textAlign: "right" }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredTemplates.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="rw-empty-cell">
                      Không tìm thấy mẫu yêu cầu nào phù hợp.
                    </td>
                  </tr>
                ) : (
                  filteredTemplates.map((tpl) => {
                    const stepsCount = (tpl.workflow_steps || []).length;
                    const weight = tpl.automation_weight ?? 50;
                    return (
                      <tr key={tpl.id} className={!tpl.is_active ? "rw-row-inactive" : ""}>
                        {/* Name & Code */}
                        <td>
                          <div className="rw-tpl-name-cell">
                            <strong>{tpl.name}</strong>
                            <code className="rw-code-badge">{tpl.code}</code>
                          </div>
                        </td>

                        {/* Request Type */}
                        <td>
                          <span className="rw-type-pill">{tpl.request_type || "Chung"}</span>
                        </td>

                        {/* Category Dropdown (AUTO-UPDATE LOGIC) */}
                        <td>
                          <div className="rw-category-select-wrap">
                            <select
                              value={tpl.category_code}
                              onChange={(e) => handleCategoryChange(tpl, e.target.value)}
                              className={`rw-cat-select rw-cat-select-${tpl.category_code.toLowerCase()}`}
                              title="Thay đổi phân loại sẽ tự động cập nhật lại các bước quy trình"
                            >
                              <option value="A">Phân loại A (Tự động - 4h)</option>
                              <option value="B">Phân loại B (Phòng ban - 24h)</option>
                              <option value="C">Phân loại C (Đa cấp - 48h)</option>
                            </select>
                            <span className="rw-auto-sync-hint">⚡ Tự động đổi quy trình</span>
                          </div>
                        </td>

                        {/* Weight Slider / Direct Edit */}
                        <td>
                          <div className="rw-weight-control">
                            <div className="rw-weight-top">
                              <span className={`rw-weight-tag rw-weight-${weight >= 80 ? "high" : weight >= 50 ? "mid" : "low"}`}>
                                {weight}% · {weight >= 80 ? "Tự động cao" : weight >= 50 ? "Bán tự động" : "Thủ công"}
                              </span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="100"
                              step="5"
                              value={weight}
                              onChange={(e) => {
                                const val = parseInt(e.target.value, 10);
                                setTemplates((prev) =>
                                  prev.map((t) => (t.id === tpl.id ? { ...t, automation_weight: val } : t))
                                );
                              }}
                              onMouseUp={(e) => handleWeightChange(tpl, e.target.value)}
                              onTouchEnd={(e) => handleWeightChange(tpl, e.target.value)}
                              className="rw-weight-slider"
                              title="Kéo để điều chỉnh tính tự động của mẫu này"
                            />
                          </div>
                        </td>

                        {/* Linked API */}
                        <td>
                          {tpl.api_name ? (
                            <div>
                              <div
                                className={`rw-api-badge ${tpl.is_api_enabled === false ? "rw-api-badge-disabled" : ""}`}
                                style={tpl.is_api_enabled === false ? { background: "#FEF2F2", color: "#DC2626", borderColor: "#FECACA" } : {}}
                                title={tpl.unavailable_notice || `Hệ thống nguồn: ${tpl.api_source_system || "Mock"}`}
                              >
                                <span className={`rw-api-dot ${tpl.is_api_enabled === false ? "dot-disabled" : ""}`} style={tpl.is_api_enabled === false ? { background: "#DC2626" } : {}} />
                                <span className="rw-api-text">{tpl.api_name} {tpl.is_api_enabled === false ? "(Đã ngắt kết nối)" : ""}</span>
                              </div>
                              {tpl.is_api_enabled === false && (
                                <div className="rw-api-disabled-warning" style={{ fontSize: 11, color: "#DC2626", marginTop: 4, fontWeight: 600 }}>
                                  ⚠️ Yêu cầu này hiện không thể sử dụng do kết nối API [{tpl.api_source_system || tpl.api_name}] đang bị tắt
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="muted" style={{ fontSize: 12 }}>Chưa liên kết</span>
                          )}
                        </td>

                        {/* Current Workflow Summary & Quick View Button */}
                        <td>
                          <button
                            type="button"
                            className="rw-btn-link"
                            onClick={() => setViewingWorkflow(tpl)}
                            title="Xem chi tiết các bước quy trình"
                          >
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                              <polygon points="5 3 19 12 5 21 5 3" />
                            </svg>
                            <span>{stepsCount} bước (Nhóm {tpl.category_code})</span>
                          </button>
                        </td>

                        {/* Actions (Guarded with PermissionGuard) */}
                        <td style={{ textAlign: "right" }}>
                          <div className="rw-actions-cell">
                            {/* View Detail */}
                            <button
                              type="button"
                              className="rw-action-btn"
                              title="Xem chi tiết mẫu & Xem trước form"
                              onClick={() => setViewingWorkflow(tpl)}
                            >
                              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            </button>

                            {/* Edit Template */}
                            <PermissionGuard module="requests_workflows" action="update">
                              <button
                                type="button"
                                className="rw-action-btn"
                                title="Chỉnh sửa mẫu yêu cầu"
                                onClick={() => setEditingTemplate({ ...tpl })}
                              >
                                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                                </svg>
                              </button>
                            </PermissionGuard>

                            {/* Delete Template */}
                            <PermissionGuard module="requests_workflows" action="delete">
                              <button
                                type="button"
                                className="rw-action-btn rw-action-danger"
                                title="Xóa mẫu yêu cầu"
                                onClick={() => setDeletingTemplate(tpl)}
                              >
                                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polyline points="3 6 5 6 21 6" />
                                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                </svg>
                              </button>
                            </PermissionGuard>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* =========================================================================
          MODAL 1: SỬA QUY TRÌNH CHUẨN CỦA PHÂN LOẠI (A, B, C)
          ========================================================================= */}
      {editingCategory && (
        <Modal
          title={`Chỉnh sửa Quy trình Chuẩn Nhóm ${editingCategory.category_code}`}
          onClose={() => setEditingCategory(null)}
        >
          <div className="rw-modal-form">
            <label className="rw-form-label">
              Tên phân loại
              <input
                type="text"
                value={editingCategory.name}
                onChange={(e) =>
                  setEditingCategory({ ...editingCategory, name: e.target.value })
                }
                className="rw-input"
              />
            </label>

            <div className="rw-form-row">
              <label className="rw-form-label">
                Cam kết thời gian SLA (giờ)
                <input
                  type="number"
                  min="1"
                  max="336"
                  value={editingCategory.sla_hours}
                  onChange={(e) =>
                    setEditingCategory({
                      ...editingCategory,
                      sla_hours: parseInt(e.target.value, 10) || 1,
                    })
                  }
                  className="rw-input"
                />
              </label>
              <label className="rw-form-label">
                Mô tả phân loại
                <input
                  type="text"
                  value={editingCategory.description || ""}
                  onChange={(e) =>
                    setEditingCategory({
                      ...editingCategory,
                      description: e.target.value,
                    })
                  }
                  className="rw-input"
                />
              </label>
            </div>

            <div className="rw-steps-builder">
              <div className="rw-steps-builder-header">
                <strong>Danh sách các bước quy trình:</strong>
                <button
                  type="button"
                  className="rw-btn-secondary rw-btn-sm"
                  onClick={() => {
                    const curSteps = editingCategory.workflow_steps || [];
                    const nextNum = curSteps.length + 1;
                    setEditingCategory({
                      ...editingCategory,
                      workflow_steps: [
                        ...curSteps,
                        {
                          step: nextNum,
                          name: `Bước ${nextNum}: Xử lý nghiệp vụ`,
                          actor: "Người phụ trách",
                          stage: "THUC_HIEN",
                        },
                      ],
                    });
                  }}
                >
                  + Thêm bước xử lý
                </button>
              </div>

              <div className="rw-builder-list">
                {(editingCategory.workflow_steps || []).map((step, idx) => (
                  <div key={idx} className="rw-builder-row">
                    <span className="rw-builder-idx">{idx + 1}</span>
                    <input
                      type="text"
                      placeholder="Tên bước"
                      value={step.name}
                      onChange={(e) => {
                        const newSteps = [...editingCategory.workflow_steps];
                        newSteps[idx] = { ...newSteps[idx], name: e.target.value };
                        setEditingCategory({ ...editingCategory, workflow_steps: newSteps });
                      }}
                      className="rw-input rw-flex-1"
                    />
                    <input
                      type="text"
                      placeholder="Vai trò phụ trách"
                      value={step.actor}
                      onChange={(e) => {
                        const newSteps = [...editingCategory.workflow_steps];
                        newSteps[idx] = { ...newSteps[idx], actor: e.target.value };
                        setEditingCategory({ ...editingCategory, workflow_steps: newSteps });
                      }}
                      className="rw-input"
                      style={{ width: 140 }}
                    />
                    <select
                      value={step.stage || "THUC_HIEN"}
                      onChange={(e) => {
                        const newSteps = [...editingCategory.workflow_steps];
                        newSteps[idx] = { ...newSteps[idx], stage: e.target.value };
                        setEditingCategory({ ...editingCategory, workflow_steps: newSteps });
                      }}
                      className="rw-input"
                      style={{ width: 160 }}
                    >
                      <option value="YEU_CAU">1. Khởi tạo</option>
                      <option value="PHE_DUYET">2. Phê duyệt</option>
                      <option value="THUC_HIEN">3. Thực hiện</option>
                      <option value="NGHIEM_THU">4. Nghiệm thu</option>
                      <option value="HOAN_THANH">5. Hoàn thành</option>
                    </select>
                    {editingCategory.workflow_steps.length > 2 && (
                      <button
                        type="button"
                        className="rw-btn-icon-danger"
                        title="Xóa bước này"
                        onClick={() => {
                          const newSteps = editingCategory.workflow_steps.filter((_, i) => i !== idx);
                          setEditingCategory({
                            ...editingCategory,
                            workflow_steps: newSteps.map((st, i) => ({ ...st, step: i + 1 })),
                          });
                        }}
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="rw-modal-footer">
              <button
                type="button"
                className="secondary"
                onClick={() => setEditingCategory(null)}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                className="rw-btn-primary"
                onClick={() => handleSaveCategory(editingCategory)}
              >
                Lưu quy trình chuẩn & Lan truyền
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* =========================================================================
          MODAL 2: TẠO MỚI / CHỈNH SỬA MẪU YÊU CẦU (TEMPLATE FORM BUILDER)
          ========================================================================= */}
      {(creatingTemplate || editingTemplate) && (
        <TemplateEditorModal
          template={editingTemplate || { category_code: "B", automation_weight: 50, workflow_steps: [] }}
          categories={categories}
          mockApis={mockApis}
          onClose={() => {
            setCreatingTemplate(false);
            setEditingTemplate(null);
          }}
          onSave={handleSaveTemplate}
        />
      )}

      {/* =========================================================================
          MODAL 3: XEM CHI TIẾT SƠ ĐỒ QUY TRÌNH CỦA MẪU
          ========================================================================= */}
      {viewingWorkflow && (
        <Modal
          title={`Chi tiết quy trình: ${viewingWorkflow.name}`}
          onClose={() => setViewingWorkflow(null)}
        >
          <div className="rw-view-workflow-content">
            <div className="rw-view-workflow-badges">
              <span className={`rw-badge rw-badge-${viewingWorkflow.category_code.toLowerCase()}`}>
                Nhóm {viewingWorkflow.category_code}
              </span>
              <span>Trọng số: <strong>{viewingWorkflow.automation_weight}%</strong></span>
              <span>Mã mẫu: <code>{viewingWorkflow.code}</code></span>
              {viewingWorkflow.api_name && <span>API: <strong>{viewingWorkflow.api_name}</strong></span>}
            </div>

            <h4 style={{ margin: "20px 0 10px" }}>Các bước xử lý tuần tự:</h4>
            <div className="rw-detail-steps-list">
              {(viewingWorkflow.workflow_steps || []).map((step, idx) => (
                <div key={idx} className="rw-detail-step-card">
                  <div className="rw-detail-step-num">{idx + 1}</div>
                  <div className="rw-detail-step-body">
                    <div className="rw-detail-step-title">{step.name}</div>
                    <div className="rw-detail-step-sub">
                      <span>Phụ trách: <strong>{step.actor || "Người xử lý"}</strong></span>
                      <span> · Giai đoạn: <strong>{STAGE_LABELS[step.stage] || step.stage}</strong></span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="rw-modal-footer">
              <button
                type="button"
                className="secondary"
                onClick={() => setViewingWorkflow(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* =========================================================================
          MODAL 4: XÁC NHẬN XÓA MẪU YÊU CẦU
          ========================================================================= */}
      {deletingTemplate && (
        <Modal
          title="Xác nhận xóa mẫu yêu cầu"
          onClose={() => setDeletingTemplate(null)}
        >
          <div className="rw-confirm-delete">
            <p>
              Bạn có chắc chắn muốn xóa mẫu yêu cầu <strong>"{deletingTemplate.name}"</strong> (Mã: <code>{deletingTemplate.code}</code>)?
            </p>
            <p className="muted" style={{ fontSize: 13 }}>
              Nếu mẫu này đã từng được sử dụng để tạo hồ sơ trong hệ thống, hệ thống sẽ thực hiện ẩn an toàn (soft delete) để bảo toàn lịch sử dữ liệu và tính toàn vẹn kiểm toán.
            </p>
            <div className="rw-modal-footer">
              <button
                type="button"
                className="secondary"
                onClick={() => setDeletingTemplate(null)}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                className="danger"
                onClick={() => handleDeleteTemplate(deletingTemplate)}
              >
                Xác nhận xóa
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// Sub-component: Template Editor Modal
function TemplateEditorModal({ template, mockApis, onClose, onSave }) {
  const isNew = !template.id;
  const [formData, setFormData] = useState({
    id: template.id || undefined,
    name: template.name || "",
    code: template.code || "",
    request_type: template.request_type || "Hành chính & Quản trị",
    category_code: template.category_code || "B",
    automation_weight: template.automation_weight ?? 50,
    linked_api_id: template.linked_api_id || "",
    form_schema: template.form_schema || { fields: [] },
  });

  const [activeTab, setActiveTab] = useState("general");

  // When category changes in form, populate recommended weight
  const handleCatSelect = (cat) => {
    const recommendedWeight = cat === "A" ? 85 : cat === "B" ? 65 : 30;
    setFormData((prev) => ({
      ...prev,
      category_code: cat,
      automation_weight: recommendedWeight,
    }));
  };

  // Add field to form schema
  const addField = () => {
    const curFields = formData.form_schema?.fields || [];
    const newField = {
      id: `field_${Date.now()}`,
      label: `Trường thông tin ${curFields.length + 1}`,
      type: "text",
      required: true,
    };
    setFormData({
      ...formData,
      form_schema: {
        ...formData.form_schema,
        fields: [...curFields, newField],
      },
    });
  };

  const removeField = (idx) => {
    const curFields = formData.form_schema?.fields || [];
    setFormData({
      ...formData,
      form_schema: {
        ...formData.form_schema,
        fields: curFields.filter((_, i) => i !== idx),
      },
    });
  };

  const updateField = (idx, key, val) => {
    const curFields = [...(formData.form_schema?.fields || [])];
    curFields[idx] = { ...curFields[idx], [key]: val };
    setFormData({
      ...formData,
      form_schema: {
        ...formData.form_schema,
        fields: curFields,
      },
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert("Vui lòng nhập tên mẫu yêu cầu");
      return;
    }
    onSave(formData);
  };

  const fields = formData.form_schema?.fields || [];

  return (
    <Modal
      title={isNew ? "Tạo Mẫu Yêu Cầu Mới" : `Chỉnh sửa Mẫu: ${template.name}`}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="rw-modal-form">
        {/* Modal Tabs */}
        <div className="rw-modal-tabs">
          <button
            type="button"
            className={activeTab === "general" ? "is-active" : ""}
            onClick={() => setActiveTab("general")}
          >
            1. Cấu hình chung
          </button>
          <button
            type="button"
            className={activeTab === "fields" ? "is-active" : ""}
            onClick={() => setActiveTab("fields")}
          >
            2. Thiết kế trường Form ({fields.length})
          </button>
        </div>

        {activeTab === "general" ? (
          <>
            <div className="rw-form-row">
              <label className="rw-form-label rw-flex-2">
                Tên mẫu yêu cầu *
                <input
                  type="text"
                  required
                  placeholder="Ví dụ: Đăng ký nghỉ phép có lương..."
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="rw-input"
                />
              </label>
              <label className="rw-form-label rw-flex-1">
                Mã mẫu (Code)
                <input
                  type="text"
                  placeholder="Ví dụ: TPL_LEAVE"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  className="rw-input"
                />
              </label>
            </div>

            <div className="rw-form-row">
              <label className="rw-form-label rw-flex-1">
                Loại nghiệp vụ
                <input
                  type="text"
                  placeholder="Ví dụ: Nhân sự (HR), Hạ tầng IT..."
                  value={formData.request_type}
                  onChange={(e) => setFormData({ ...formData, request_type: e.target.value })}
                  className="rw-input"
                />
              </label>

              <label className="rw-form-label rw-flex-1">
                Thuộc phân loại lớn *
                <select
                  value={formData.category_code}
                  onChange={(e) => handleCatSelect(e.target.value)}
                  className="rw-input"
                >
                  <option value="A">Phân loại A (Tự động - SLA 4h)</option>
                  <option value="B">Phân loại B (Phòng ban - SLA 24h)</option>
                  <option value="C">Phân loại C (Đa cấp - SLA 48h)</option>
                </select>
              </label>
            </div>

            <div className="rw-form-row">
              <label className="rw-form-label rw-flex-1">
                Trọng số tự động hóa AI (Weight): <strong>{formData.automation_weight}%</strong>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={formData.automation_weight}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      automation_weight: parseInt(e.target.value, 10),
                    })
                  }
                  className="rw-weight-slider"
                  style={{ marginTop: 8 }}
                />
              </label>

              <label className="rw-form-label rw-flex-1">
                API tích hợp liên kết
                <select
                  value={formData.linked_api_id || ""}
                  onChange={(e) => setFormData({ ...formData, linked_api_id: e.target.value })}
                  className="rw-input"
                >
                  <option value="">-- Không liên kết API ngoài --</option>
                  {mockApis.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.api_name} ({a.source_system})
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="rw-notice-box">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              <span>
                Khi chọn <strong>Nhóm {formData.category_code}</strong>, quy trình xử lý của mẫu này sẽ được tự động đồng bộ theo đúng các bước chuẩn của Nhóm {formData.category_code}.
              </span>
            </div>
          </>
        ) : (
          <div className="rw-fields-designer">
            <div className="rw-fields-designer-header">
              <span>Định nghĩa các ô nhập dữ liệu của biểu mẫu:</span>
              <button
                type="button"
                className="rw-btn-secondary rw-btn-sm"
                onClick={addField}
              >
                + Thêm trường mới
              </button>
            </div>

            {fields.length === 0 ? (
              <div className="rw-empty-fields">Chưa có trường dữ liệu nào. Nhấn "+ Thêm trường mới" để bắt đầu.</div>
            ) : (
              <div className="rw-fields-list">
                {fields.map((f, idx) => (
                  <div key={f.id || idx} className="rw-field-item">
                    <span className="rw-field-idx">{idx + 1}</span>
                    <input
                      type="text"
                      placeholder="Nhãn trường (Ví dụ: Số ngày nghỉ, Lý do...)"
                      value={f.label}
                      onChange={(e) => updateField(idx, "label", e.target.value)}
                      className="rw-input rw-flex-2"
                      required
                    />
                    <select
                      value={f.type || "text"}
                      onChange={(e) => updateField(idx, "type", e.target.value)}
                      className="rw-input rw-flex-1"
                    >
                      <option value="text">Văn bản (Text)</option>
                      <option value="number">Số (Number)</option>
                      <option value="date">Ngày tháng (Date)</option>
                      <option value="textarea">Văn bản dài (Textarea)</option>
                      <option value="select">Lựa chọn (Select)</option>
                      <option value="file">Đính kèm file (File)</option>
                    </select>
                    <label className="rw-checkbox-label">
                      <input
                        type="checkbox"
                        checked={f.required ?? true}
                        onChange={(e) => updateField(idx, "required", e.target.checked)}
                      />
                      <span>Bắt buộc</span>
                    </label>
                    <button
                      type="button"
                      className="rw-btn-icon-danger"
                      title="Xóa trường này"
                      onClick={() => removeField(idx)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="rw-modal-footer">
          <button type="button" className="secondary" onClick={onClose}>
            Hủy bỏ
          </button>
          <button type="submit" className="rw-btn-primary">
            {isNew ? "Tạo mẫu yêu cầu" : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </Modal>
  );
}


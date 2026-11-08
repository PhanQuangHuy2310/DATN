import { useState, useEffect } from "react";
import { errorText } from "../domain.js";
import { api } from "../api.js";
import { PageHeader } from "./design.jsx";

export function ApiAdministration() {
  const [apis, setApis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState(null);

  // Payload modal state
  const [viewingPayload, setViewingPayload] = useState(null);

  // Circuit breaker confirmation modal
  const [confirmToggleApi, setConfirmToggleApi] = useState(null);
  const [toggling, setToggling] = useState(false);

  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadApis = async (silent = false) => {
    try {
      const res = await api("/api/v1/admin/mock-apis");
      setApis(res.apis || []);
    } catch (err) {
      if (!silent) showToast("Không thể tải danh sách API: " + errorText(err), "error");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the loader sets state only after its await
    loadApis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToggleClick = (apiItem) => {
    if (apiItem.is_enabled) {
      // Confirming DISABLING an API (Circuit Breaker)
      setConfirmToggleApi(apiItem);
    } else {
      // Re-enabling directly
      executeToggle(apiItem);
    }
  };

  const executeToggle = async (apiItem) => {
    setToggling(true);
    try {
      const res = await api(`/api/v1/admin/mock-apis/${apiItem.id}/toggle`, {
        method: "PATCH",
      });
      showToast(res.message || "Đã cập nhật trạng thái kết nối API!", "success");
      setConfirmToggleApi(null);
      loadApis(true);
    } catch (err) {
      showToast("Lỗi khi điều khiển Circuit Breaker: " + errorText(err), "error");
    } finally {
      setToggling(false);
    }
  };

  const filteredApis = apis.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.api_name?.toLowerCase().includes(q) ||
      a.api_code?.toLowerCase().includes(q) ||
      a.source_system?.toLowerCase().includes(q) ||
      a.endpoint_path?.toLowerCase().includes(q) ||
      a.data_provided?.toLowerCase().includes(q)
    );
  });

  const totalApis = apis.length;
  const enabledCount = apis.filter((a) => a.is_enabled).length;
  const disabledCount = totalApis - enabledCount;
  const circuitBreakerActive = disabledCount > 0;

  // Calculate total affected request types
  const affectedRequestsCount = apis
    .filter((a) => !a.is_enabled)
    .reduce((acc, curr) => acc + (curr.linked_count || 0), 0);

  return (
    <div className="page-container api-admin-page">
      <PageHeader
        eyebrow="HỆ THỐNG"
        title="Quản lý API & Circuit Breaker"
        description="Giám sát 8 kết nối API nội bộ (HR, Finance, IT, CRM, Assets, Facilities, Procurement, Travel), xem cấu trúc dữ liệu JSON và điều khiển ngắt mạch kết nối (Circuit Breaker)."
      />

      {/* Top 3 Meta Cards */}
      <div className="eas-meta-cards-row">
        <div className="eas-meta-stat-card">
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Tổng số kết nối API</span>
            <span className="eas-badge-neutral">{totalApis} Hệ thống</span>
          </div>
          <div className="eas-meta-stat-value">{totalApis} API</div>
          <div className="eas-meta-stat-sub">Đồng bộ dữ liệu ngữ cảnh với AI Engine</div>
        </div>

        <div className={`eas-meta-stat-card ${circuitBreakerActive ? "warning-border" : "success-border"}`}>
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Trạng thái Circuit Breaker</span>
            {circuitBreakerActive ? (
              <span className="eas-badge-danger pulse">ĐÃ KÍCH HOẠT ({disabledCount} BỊ NGẮT)</span>
            ) : (
              <span className="eas-badge-success">TẤT CẢ KẾT NỐI HOẠT ĐỘNG (8/8)</span>
            )}
          </div>
          <div className="eas-meta-stat-value">
            {circuitBreakerActive ? `${enabledCount}/${totalApis} Bật` : "100% Online"}
          </div>
          <div className="eas-meta-stat-sub">
            {circuitBreakerActive
              ? `Có ${disabledCount} kết nối API bị tắt. Các yêu cầu liên quan bị tạm ngưng.`
              : "Toàn bộ API thông suốt, dữ liệu biểu mẫu nạp bình thường."}
          </div>
        </div>

        <div className={`eas-meta-stat-card ${affectedRequestsCount > 0 ? "warning-border" : ""}`}>
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Mẫu yêu cầu chịu ảnh hưởng</span>
            {affectedRequestsCount > 0 ? (
              <span className="eas-badge-warning">{affectedRequestsCount} mẫu bị khóa</span>
            ) : (
              <span className="eas-badge-neutral">0 mẫu bị khóa</span>
            )}
          </div>
          <div className="eas-meta-stat-value">{affectedRequestsCount}</div>
          <div className="eas-meta-stat-sub">
            {affectedRequestsCount > 0
              ? "Người dùng tại web_client bị khóa nút gửi đối với các mẫu này."
              : "Tất cả các loại yêu cầu có thể tạo và gửi bình thường."}
          </div>
        </div>
      </div>

      {/* Active Circuit Breaker Notice Banner */}
      {circuitBreakerActive && (
        <div className="circuit-breaker-active-banner">
          <div className="cb-banner-icon">⚡</div>
          <div className="cb-banner-content">
            <strong>CẢNH BÁO CIRCUIT BREAKER ĐANG KÍCH HOẠT:</strong>
            <p>
              Có <strong>{disabledCount} API</strong> đang bị ngắt kết nối. Toàn bộ <strong>{affectedRequestsCount} mẫu yêu cầu</strong> liên quan đã tự động chuyển sang trạng thái <strong>Tạm ngưng</strong> trên cả Web Client và Web Admin với thông báo rõ ràng cho người dùng.
            </p>
          </div>
        </div>
      )}

      {/* Search Toolbar */}
      <div className="api-admin-toolbar">
        <div className="api-search-wrapper">
          <span className="api-search-icon">🔍</span>
          <input
            type="text"
            className="eas-input"
            placeholder="Tìm kiếm theo tên API, endpoint, hệ thống nguồn..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="api-status-summary-pills">
          <span className="status-pill active-pill">🟢 Đang bật: {enabledCount}</span>
          {disabledCount > 0 && (
            <span className="status-pill disabled-pill">🔴 Đã ngắt: {disabledCount}</span>
          )}
        </div>
      </div>

      {/* API Cards List */}
      <div className="api-cards-container">
        {loading ? (
          <div className="eas-empty-state">
            <div className="eas-spinner"></div>
            <p>Đang tải danh mục kết nối API...</p>
          </div>
        ) : filteredApis.length === 0 ? (
          <div className="eas-empty-state">
            <span className="empty-icon">🔌</span>
            <p>Không tìm thấy API nào phù hợp.</p>
          </div>
        ) : (
          <div className="api-cards-grid">
            {filteredApis.map((apiItem) => {
              const isEnabled = apiItem.is_enabled;
              return (
                <div
                  key={apiItem.id}
                  className={`api-card ${isEnabled ? "api-card-enabled" : "api-card-disabled"}`}
                >
                  <div className="api-card-topbar">
                    <div className="api-system-info">
                      <span className="api-system-badge">{apiItem.source_system}</span>
                      <span className="api-code-tag">{apiItem.api_code}</span>
                    </div>

                    {/* Circuit Breaker Toggle Switch */}
                    <div className="circuit-breaker-toggle-wrap">
                      <label className="cb-switch" title={isEnabled ? "Bấm để ngắt kết nối (Circuit Breaker)" : "Bấm để kích hoạt lại kết nối"} aria-label={isEnabled ? "Bấm để ngắt kết nối (Circuit Breaker)" : "Bấm để kích hoạt lại kết nối"}>
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          onChange={() => handleToggleClick(apiItem)}
                          disabled={toggling}
                        />
                        <span className="cb-slider round"></span>
                      </label>
                      <span className={`cb-status-label ${isEnabled ? "status-on" : "status-off"}`}>
                        {isEnabled ? "BẬT" : "NGẮT"}
                      </span>
                    </div>
                  </div>

                  <h3 className="api-card-name">{apiItem.api_name}</h3>

                  <div className="api-endpoint-box">
                    <span className="api-method-badge">{apiItem.http_method || "GET"}</span>
                    <code className="api-endpoint-code">{apiItem.endpoint_path}</code>
                  </div>

                  <div className="api-data-provided">
                    <span className="data-provided-label">Dữ liệu cung cấp:</span>
                    <p className="data-provided-desc">{apiItem.data_provided}</p>
                  </div>

                  {/* Linked Request Templates */}
                  <div className="api-linked-requests">
                    <div className="linked-requests-header">
                      <span>Mẫu yêu cầu sử dụng API này ({apiItem.linked_count || 0}):</span>
                    </div>
                    <div className="linked-request-chips">
                      {apiItem.linked_requests && apiItem.linked_requests.length > 0 ? (
                        apiItem.linked_requests.map((r) => (
                          <span
                            key={r.code}
                            className={`linked-chip ${isEnabled ? "" : "chip-disabled"}`}
                            title={isEnabled ? `Mẫu: ${r.name}` : `[TẠM NGƯNG] ${r.name}`}
                          >
                            {!isEnabled && <span className="disabled-icon">⚠️ </span>}
                            {r.name}
                          </span>
                        ))
                      ) : (
                        <span className="no-linked-chip">Chưa có mẫu nào liên kết</span>
                      )}
                    </div>
                  </div>

                  {/* Card Footer Actions */}
                  <div className="api-card-footer">
                    <span className="api-circuit-indicator">
                      {isEnabled ? (
                        <span className="status-dot green"></span>
                      ) : (
                        <span className="status-dot red"></span>
                      )}
                      {isEnabled ? "Kết nối thông suốt" : "Circuit Breaker: Tạm ngưng"}
                    </span>

                    <button
                      type="button"
                      className="btn-action btn-view-payload"
                      onClick={() => setViewingPayload(apiItem)}
                    >
                      👁 Xem thử JSON Payload
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* MODAL: Xem thử JSON Payload Mẫu */}
      {viewingPayload && (
        <div className="eas-modal-overlay">
          <div className="eas-modal-card json-viewer-modal">
            <div className="eas-modal-header">
              <div>
                <h3>Cấu trúc dữ liệu JSON mẫu: {viewingPayload.api_code}</h3>
                <span className="api-system-badge">{viewingPayload.source_system}</span>
              </div>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setViewingPayload(null)}
              >
                ✕
              </button>
            </div>

            <div className="eas-modal-body">
              <div className="json-endpoint-meta">
                <span className="api-method-badge">{viewingPayload.http_method || "GET"}</span>
                <code>{viewingPayload.endpoint_path}</code>
              </div>

              <div className="json-viewer-container">
                <pre className="json-code-block">
                  {JSON.stringify(viewingPayload.mock_payload || { status: "OK", source: viewingPayload.api_code }, null, 2)}
                </pre>
              </div>

              <p className="json-viewer-note">
                Dữ liệu trên là snapshot mẫu từ <code>ai_service/data/mock/</code> được AI Engine nạp làm ngữ cảnh để chấm điểm rủi ro và xác thực điều kiện phê duyệt.
              </p>
            </div>

            <div className="eas-modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  navigator.clipboard?.writeText(JSON.stringify(viewingPayload.mock_payload || {}, null, 2));
                  showToast("Đã sao chép JSON payload vào bộ nhớ tạm!", "info");
                }}
              >
                📋 Sao chép JSON
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => setViewingPayload(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Xác nhận ngắt kết nối API (Circuit Breaker) */}
      {confirmToggleApi && (
        <div className="eas-modal-overlay">
          <div className="eas-modal-card danger-modal">
            <div className="eas-modal-header">
              <h3>Xác nhận Ngắt kết nối API (Circuit Breaker)</h3>
              <button
                type="button"
                className="eas-modal-close"
                onClick={() => setConfirmToggleApi(null)}
              >
                ✕
              </button>
            </div>

            <div className="eas-modal-body">
              <div className="circuit-breaker-warning-box">
                <span className="cb-warn-icon">⚠️</span>
                <div className="cb-warn-text">
                  <strong>CẢNH BÁO TẠM NGƯNG YÊU CẦU:</strong>
                  <p>
                    Ngắt kết nối <strong>{confirmToggleApi.api_name}</strong> ({confirmToggleApi.source_system}) sẽ khiến toàn bộ <strong>{confirmToggleApi.linked_count || 0} mẫu yêu cầu</strong> liên quan chuyển sang trạng thái <strong>Tạm ngưng</strong> trên cả Web Admin và Web Client!
                  </p>
                </div>
              </div>

              <div className="affected-requests-preview">
                <span className="preview-label">Các mẫu đơn sẽ bị khóa nút gửi:</span>
                <ul>
                  {(confirmToggleApi.linked_requests || []).map((r) => (
                    <li key={r.code}>
                      <strong>{r.name}</strong> <code>({r.code})</code>
                    </li>
                  ))}
                </ul>
              </div>

              <p className="cb-confirm-question">
                Bạn có chắc chắn muốn ngắt kết nối API này không?
              </p>
            </div>

            <div className="eas-modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setConfirmToggleApi(null)}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={() => executeToggle(confirmToggleApi)}
                disabled={toggling}
              >
                {toggling ? "Đang xử lý..." : "Xác nhận Ngắt kết nối (Tắt API)"}
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

export default ApiAdministration;

import { useState, useEffect } from "react";
import { errorText } from "../domain.js";
import { api } from "../api.js";
import { PageHeader } from "./design.jsx";

const JOB_STATUS = { QUEUED: "Chờ xử lý", RUNNING: "Đang học", APPLIED: "Đã áp dụng", FAILED: "Thất bại, giữ luật cũ" };

export function AiEngineManagementPage() {
  const [toast, setToast] = useState(null);
  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };
  const [aiState, setAiState] = useState(null);
  const [retraining, setRetraining] = useState(false);

  // Quick Tester state
  const [testType, setTestType] = useState("");
  const [testAmount, setTestAmount] = useState("0");
  const [testDays, setTestDays] = useState("1");
  const [requestTypes, setRequestTypes] = useState([]);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const fetchAiStatus = () =>
    api("/api/v1/admin/ai-engine/status")
      .then(setAiState)
      .catch(() => {});

  useEffect(() => {
    let active = true;
    // Poll every 1.5s for real-time stepper updates.
    const poll = () =>
      api("/api/v1/admin/ai-engine/status")
        .then((res) => active && setAiState(res))
        .catch(() => {});
    void poll();
    const interval = setInterval(() => { void poll(); }, 1500);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      const res = await api("/api/v1/admin/ai-engine/retrain", {
        method: "POST",
      });
      showToast(res.message || "Đã kích hoạt chu trình huấn luyện lại AI!", "info");
      void fetchAiStatus();
    } catch (err) {
      showToast("Lỗi khi kích hoạt huấn luyện AI: " + errorText(err), "error");
    } finally {
      setRetraining(false);
    }
  };

  useEffect(() => {
    void api("/api/v1/admin/request-templates")
      .then((res) => {
        const items = (res?.items || []).filter((t) => t.is_active);
        setRequestTypes(items);
        if (items.length) setTestType((cur) => cur || items[0].code);
      })
      .catch(() => {});
  }, []);

  // Asks the live AI engine (rules currently applied); nothing is stored.
  const handleRunAiTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api("/api/v1/admin/ai-engine/test", {
        method: "POST",
        body: JSON.stringify({
          request_type: testType,
          amount: Number(testAmount) || 0,
          days: parseInt(testDays, 10) || 0,
        }),
      });
      setTestResult({ ...res, testedAt: new Date().toLocaleTimeString("vi-VN") });
    } catch (err) {
      showToast("AI chưa trả lời: " + errorText(err), "error");
    } finally {
      setTesting(false);
    }
  };

  const isLocked = aiState?.client_maintenance_lock;
  const progressPercent = aiState?.progress_percent !== undefined ? aiState.progress_percent : 100;
  const currentStep = aiState?.current_step_index || 4;
  const targetVersion = aiState?.target_regulation_version || "v1.0";
  const activeVersion = aiState?.active_regulation_version || "v1.0";
  const steps = aiState?.steps_detail || [];
  const jobs = aiState?.jobs || [];

  return (
    <div className="page-container ai-engine-page">
      <PageHeader
        eyebrow="TRI THỨC & AI"
        title="Quản trị AI Engine & Giám sát Huấn luyện"
        description="Giám sát mô hình AI, theo dõi tiến trình 4 bước huấn luyện lại theo thời gian thực và quản lý khóa bảo trì Web Client."
      />

      {/* Top 3 Metric Cards */}
      <div className="eas-meta-cards-row">
        {/* Model Specs */}
        <div className="eas-meta-stat-card ai-spec-card">
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Mô hình AI & Nhà cung cấp</span>
            <span className="eas-badge-neutral">Hybrid Architecture</span>
          </div>
          <div className="ai-model-provider-title">
            {aiState?.provider_name || "Scikit-Learn Local Pipeline (Gemini Fallback: Chưa cấu hình Key)"}
          </div>
          <div className="ai-model-name-sub">
            <code>{aiState?.model_name || "nlp_risk_pipeline_v2 (Local Scikit-Learn / XGBoost)"}</code>
          </div>
        </div>

        {/* Regulation Versions */}
        <div className="eas-meta-stat-card">
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Phiên bản Quy định nghiệp vụ</span>
            <span className="version-pill current-version">{activeVersion}</span>
          </div>
          <div className="version-compare-display">
            <div className="version-col">
              <span className="version-col-title">Đang hoạt động:</span>
              <span className="version-val active">{activeVersion}</span>
            </div>
            <span className="version-arrow">➔</span>
            <div className="version-col">
              <span className="version-col-title">Mục tiêu huấn luyện:</span>
              <span className="version-val target">{targetVersion}</span>
            </div>
          </div>
        </div>

        {/* Web Client Gatekeeper Status */}
        <div className={`eas-meta-stat-card ${isLocked ? "danger-border" : "success-border"}`}>
          <div className="eas-meta-stat-header">
            <span className="eas-meta-stat-label">Cổng Web Client (Gatekeeper)</span>
            {isLocked ? (
              <span className="eas-badge-danger pulse">ĐÃ KHÓA CLIENT (BẢO TRÌ)</span>
            ) : (
              <span className="eas-badge-success">MỞ KHÓA HOÀN TOÀN</span>
            )}
          </div>
          <div className="eas-meta-stat-value">
            {isLocked ? "Bảo trì" : "Hoạt động"}
          </div>
          <div className="eas-meta-stat-sub">
            {isLocked
              ? "Người dùng Web Client bị chuyển ra màn hình chờ và chặn đăng nhập cho đến khi AI học xong."
              : "Toàn bộ nhân viên truy cập và tạo yêu cầu bình thường với phiên bản mới nhất."}
          </div>
        </div>
      </div>

      {/* Visual Stepper & Progress Bar Section */}
      <div className="ai-stepper-panel">
        <div className="ai-stepper-panel-header">
          <div>
            <h2 className="ai-stepper-title">Tiến trình Huấn luyện & Đồng bộ Quy định</h2>
            <p className="ai-stepper-subtitle">
              Quy trình 4 giai đoạn tự động kích hoạt khi có thay đổi trong bộ quy chế công ty.
            </p>
          </div>
          <div className="ai-stepper-status-group">
            <button
              type="button"
              className="btn-primary btn-retrain-ai"
              onClick={handleRetrain}
              disabled={isLocked || retraining}
            >
              {isLocked ? (
                <>
                  <span className="eas-spinner-inline"></span> Đang huấn luyện AI ({progressPercent}%)...
                </>
              ) : (
                <>
                  <span>🔄</span> Huấn luyện lại AI (Re-train thủ công)
                </>
              )}
            </button>
          </div>
        </div>

        {/* Animated Progress Bar */}
        <div className="ai-main-progress-container">
          <div className="ai-progress-labels">
            <span className="ai-progress-step-text">
              {isLocked
                ? `Đang thực hiện bước ${currentStep}/4: ${aiState?.current_step_label || ""}`
                : `Hệ thống sẵn sàng: ${aiState?.current_step_label || "Đã áp dụng quy định " + activeVersion}`}
            </span>
            <span className="ai-progress-percentage">{progressPercent}%</span>
          </div>
          <div className="ai-progress-track large">
            <div
              className={`ai-progress-bar-fill large ${isLocked ? "active-stripes" : "completed-fill"}`}
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
        </div>

        {/* 4-Step Cards */}
        <div className="ai-steps-grid">
          {steps.map((st, idx) => {
            const stepNum = st.step || idx + 1;
            const isCompleted = stepNum < currentStep || (!isLocked && progressPercent === 100);
            const isRunning = isLocked && stepNum === currentStep;

            let cardStatusClass = "step-waiting";
            if (isCompleted) cardStatusClass = "step-completed";
            else if (isRunning) cardStatusClass = "step-running";

            return (
              <div key={st.code || stepNum} className={`ai-step-card ${cardStatusClass}`}>
                <div className="ai-step-card-top">
                  <div className="ai-step-badge">
                    {isCompleted ? "✓" : stepNum}
                  </div>
                  <span className="ai-step-status-tag">
                    {isCompleted ? "ĐÃ HOÀN TẤT" : isRunning ? "ĐANG THỰC HIỆN" : "CHỜ"}
                  </span>
                </div>

                <div className="ai-step-card-body">
                  <h4 className="ai-step-name">{st.title || `Bước ${stepNum}: ${st.code}`}</h4>
                  <p className="ai-step-desc">{st.label}</p>
                </div>

                <div className="ai-step-card-footer">
                  <div className="ai-step-mini-progress">
                    <div
                      className="ai-step-mini-bar"
                      style={{
                        width: isCompleted ? "100%" : isRunning ? "60%" : "0%",
                      }}
                    ></div>
                  </div>
                  <span className="ai-step-percent-tag">{st.percent || stepNum * 25}%</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Interactive Quick Policy Simulator */}
      <div className="ai-simulator-panel">
        <div className="ai-simulator-header">
          <div>
            <h3>Công cụ Kiểm thử Quyết định AI (Quick Policy Simulator)</h3>
            <p>
              Nhập nội dung yêu cầu mẫu để xem AI diễn giải, phân loại rủi ro và áp dụng quy định <strong>{activeVersion}</strong>.
            </p>
          </div>
          <span className="ai-chip-active-version">Phiên bản: {activeVersion}</span>
        </div>

        <div className="ai-simulator-body">
          <div className="ai-simulator-input-col">
            <label className="simulator-label" htmlFor="ai-test-type">Loại yêu cầu</label>
            <select id="ai-test-type" className="eas-select" value={testType} onChange={(e) => setTestType(e.target.value)}>
              {requestTypes.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.name} (Nhóm {t.category_code})
                </option>
              ))}
            </select>
            <label className="simulator-label" htmlFor="ai-test-amount">Số tiền (VNĐ)</label>
            <input id="ai-test-amount" className="eas-input" type="number" min="0" step="1000" value={testAmount} onChange={(e) => setTestAmount(e.target.value)} />
            <label className="simulator-label" htmlFor="ai-test-days">Số ngày</label>
            <input id="ai-test-days" className="eas-input" type="number" min="0" max="365" value={testDays} onChange={(e) => setTestDays(e.target.value)} />
            <button type="button" className="btn-primary btn-run-test" onClick={handleRunAiTest} disabled={testing || !testType}>
              {testing ? "AI đang đánh giá..." : "Chạy kiểm tra với AI"}
            </button>
          </div>

          <div className="ai-simulator-result-col">
            <span className="simulator-label">Quyết định của AI Engine</span>
            {testing ? (
              <div className="simulator-loading">
                <div className="eas-spinner"></div>
                <p>Đang gửi yêu cầu mẫu tới AI…</p>
              </div>
            ) : testResult ? (
              <div className="simulator-result-card">
                <div className="result-header">
                  <span className={`result-tag ${testResult.decision === "auto_approve" ? "tag-auto" : "tag-review"}`}>
                    {testResult.decision === "auto_approve" ? "✓ ĐỦ ĐIỀU KIỆN TỰ DUYỆT" : "⚠ CHUYỂN NGƯỜI DUYỆT"}
                  </span>
                  <span className="result-time">{testResult.testedAt}</span>
                </div>
                <div className="result-grid">
                  <div className="result-item">
                    <span className="r-label">Loại yêu cầu:</span>
                    <strong className="r-val">{testResult.request_type?.name} (Nhóm {testResult.request_type?.lifecycle}, rủi ro {testResult.request_type?.risk_weight}/5)</strong>
                  </div>
                  <div className="result-item">
                    <span className="r-label">Bộ luật áp dụng:</span>
                    <strong className="r-val">{testResult.policy_version || "Mặc định"}</strong>
                  </div>
                </div>
                <div className="result-notes">
                  <span className="r-notes-label">{testResult.reason}</span>
                  <ul>
                    {testResult.detail_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="simulator-placeholder">
                <p>Chọn loại yêu cầu, nhập số tiền/số ngày rồi bấm "Chạy kiểm tra với AI".</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {jobs.length > 0 && (
        <div className="ai-simulator-panel">
          <div className="ai-simulator-header">
            <h3>Lịch sử các lượt AI học quy định</h3>
          </div>
          <div className="table-scroll">
            <table className="eas-table">
              <thead>
                <tr>
                  <th>Thời điểm</th>
                  <th>Phiên bản</th>
                  <th>Trạng thái</th>
                  <th>Lần thử</th>
                  <th>Lý do / lỗi</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td>{j.created_at ? new Date(j.created_at).toLocaleString("vi-VN") : "—"}</td>
                    <td>{j.target_version}</td>
                    <td>{JOB_STATUS[j.status] || j.status}</td>
                    <td>{j.attempts}</td>
                    <td>{j.error || j.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
export default AiEngineManagementPage;

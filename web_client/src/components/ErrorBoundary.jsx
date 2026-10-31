import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Structured error logging for enterprise diagnostics
    console.error("UI Uncaught Render Error:", {
      error: error?.message || String(error),
      stack: error?.stack,
      componentStack: errorInfo?.componentStack,
      timestamp: new Date().toISOString(),
    });
    if (typeof this.props.onError === "function") {
      this.props.onError(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    if (typeof this.props.onReset === "function") {
      this.props.onReset();
    }
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = "/";
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return typeof this.props.fallback === "function"
          ? this.props.fallback({ error: this.state.error, reset: this.handleRetry })
          : this.props.fallback;
      }

      return (
        <main className="auth-shell" role="alert" aria-live="assertive">
          <section className="panel" style={{ maxWidth: "600px", margin: "2rem auto", textAlign: "left" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
              <span
                style={{
                  fontSize: "2rem",
                  lineHeight: 1,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  backgroundColor: "#fee2e2",
                  color: "#dc2626",
                }}
                aria-hidden="true"
              >
                !
              </span>
              <div>
                <h1 style={{ margin: 0, fontSize: "1.25rem", color: "#111827" }}>
                  {this.props.title || "Đã xảy ra sự cố hiển thị"}
                </h1>
                <small className="muted">Giao diện gặp lỗi ngoài dự kiến và đã được ngắt an toàn.</small>
              </div>
            </div>

            <p style={{ margin: "1rem 0", color: "#4b5563", fontSize: "0.95rem" }}>
              Hệ thống đã cách ly lỗi để bảo vệ phiên làm việc và dữ liệu của bạn. Bạn có thể thử tải lại khối này
              hoặc làm mới trang để tiếp tục.
            </p>

            <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.5rem", flexWrap: "wrap" }}>
              <button type="button" onClick={this.handleRetry}>
                Thử tải lại
              </button>
              <button type="button" className="secondary" onClick={this.handleReload}>
                Tải lại toàn trang
              </button>
              <button type="button" className="link" onClick={this.handleGoHome}>
                Về trang chủ →
              </button>
            </div>

            {import.meta.env.DEV && this.state.error && (
              <details style={{ marginTop: "1.5rem", padding: "0.75rem", background: "#f3f4f6", borderRadius: "6px" }}>
                <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: "0.85rem", color: "#374151" }}>
                  Chi tiết kỹ thuật (dành cho Nhà phát triển)
                </summary>
                <pre
                  style={{
                    marginTop: "0.5rem",
                    padding: "0.5rem",
                    fontSize: "0.75rem",
                    overflowX: "auto",
                    background: "#1f2937",
                    color: "#f9fafb",
                    borderRadius: "4px",
                  }}
                >
                  {String(this.state.error?.stack || this.state.error)}
                </pre>
              </details>
            )}
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}


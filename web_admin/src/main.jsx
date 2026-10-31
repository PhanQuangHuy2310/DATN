import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "../../web_client/src/App.jsx";
import ErrorBoundary from "../../web_client/src/components/ErrorBoundary.jsx";
import "../../web_client/src/styles.css";
import "../../web_client/src/eas-enhancements.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary title="Sự cố hiển thị Trung tâm Quản trị">
      <App portal="admin" />
    </ErrorBoundary>
  </StrictMode>,
);

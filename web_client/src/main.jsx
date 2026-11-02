import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import "./styles.css";
import "./eas-enhancements.css";
import "./client-refactor.css";
import "./design-system.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary>
      <App portal="client" />
    </ErrorBoundary>
  </StrictMode>,
);

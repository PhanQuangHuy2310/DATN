import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";
import "./eas-enhancements.css";

// React StrictMode deliberately mounts effects twice in development, causing
// duplicate API reads. Keep it opt-in for local debugging of Supabase sessions.
// Enable with VITE_REACT_STRICT_MODE=true when diagnosing component effects.
const app = <App />;
createRoot(document.getElementById("root")).render(
  import.meta.env.DEV && import.meta.env.VITE_REACT_STRICT_MODE !== "true"
    ? app
    : <StrictMode>{app}</StrictMode>,
);

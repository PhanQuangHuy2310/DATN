import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "../../web_client/src/App.jsx";
import "../../web_client/src/styles.css";
import "../../web_client/src/eas-enhancements.css";

createRoot(document.getElementById("root")).render(
  <StrictMode><App portal="admin" /></StrictMode>,
);

import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  envDir: resolve(fileURLToPath(new URL(".", import.meta.url)), ".."),
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
      // The AI service is internal-only (X-Internal-Secret); browsers reach AI
      // features through Django at /api/v1/ai/* and /api/v1/requests/*/ai-assessments.
    },
  },
});

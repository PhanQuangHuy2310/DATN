import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
export default defineConfig({
  plugins: [react()],
  envDir: resolve(root, ".."),
  publicDir: resolve(root, "../web_client/public"),
  resolve: {
    alias: {
      react: resolve(root, "node_modules/react"),
      "react-dom": resolve(root, "node_modules/react-dom"),
    },
    dedupe: ["react", "react-dom"],
  },
  server: {
    fs: { allow: [resolve(root, "..")] },
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
});

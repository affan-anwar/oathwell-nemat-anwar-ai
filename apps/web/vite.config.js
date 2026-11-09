import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
// The same headers are used by nginx in Dockerfile.web. The dev server needs inline scripts for hot reload, so only preview gets them.
const headers = JSON.parse(readFileSync(new URL("./security-headers.json", import.meta.url), "utf8"));
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": api } },
  preview: { port: 4173, proxy: { "/api": api }, headers },
  test: { environment: "jsdom", exclude: ["e2e/**", "node_modules/**"] },
});

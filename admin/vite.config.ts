import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Đích proxy /api, /static: mặc định backend dev :8000; smoke test đặt ADMIN_API_TARGET để không đụng server đang chạy
const apiTarget = process.env.ADMIN_API_TARGET || "http://127.0.0.1:8000";

// Vite config: React + Tailwind, admin on 5174 with /api proxy
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // VITE_CACHE_DIR cho phép smoke test dùng cache riêng, không đụng cache của dev server đang chạy
  cacheDir: process.env.VITE_CACHE_DIR || undefined,
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "./src"),
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/static": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});

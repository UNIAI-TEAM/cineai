import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // VITE_CACHE_DIR cho phép smoke test dùng cache riêng, không đụng cache của dev server đang chạy
  cacheDir: process.env.VITE_CACHE_DIR || undefined,
})

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // In development, proxy API calls to avoid CORS issues
    proxy: {
      "/api": {
        target:      "http://localhost:8001",
        rewrite:     (path) => path.replace(/^\/api/, ""),
        changeOrigin: true,
      },
      "/events": {
        target:      "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});

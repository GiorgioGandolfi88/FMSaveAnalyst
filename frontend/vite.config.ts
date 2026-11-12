import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development run the API with `python -m fmsa --dev` (port 8765, token "dev").
export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
});

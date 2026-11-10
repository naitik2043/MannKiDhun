import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const frontendRoot = fileURLToPath(new URL("./frontend", import.meta.url));

export default defineConfig({
  root: frontendRoot,
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/predict": process.env.MANNKIDHUN_API_URL || process.env.MOODWAVE_API_URL || "http://127.0.0.1:5001",
      "/api": process.env.MANNKIDHUN_API_URL || process.env.MOODWAVE_API_URL || "http://127.0.0.1:5001",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.FRONTEND_PORT ?? 3100),
    strictPort: true,
  },
  preview: {
    port: Number(process.env.FRONTEND_PORT ?? 3100),
    strictPort: true,
  },
});

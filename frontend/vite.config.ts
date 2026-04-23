import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/voice": "http://localhost:8000",
      "/persona": "http://localhost:8000",
      "/scenario": "http://localhost:8000",
      "/dialogue": "http://localhost:8000",
      "/audio": "http://localhost:8000",
      "/generate": "http://localhost:8000",
    },
  },
});

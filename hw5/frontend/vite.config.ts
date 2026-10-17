import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard runs on the usual Vite port; the FastAPI backend allows this origin (CORS).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});

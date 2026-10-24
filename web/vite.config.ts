import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173 (spec section 2, rule 5). Never touch 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});

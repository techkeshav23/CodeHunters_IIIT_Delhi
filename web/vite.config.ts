import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { swStamp } from "./scripts/sw-stamp.mjs";

// Dev server on 5173 (spec section 2, rule 5). Never touch 8000.
// swStamp gives the offline service worker (public/sw.js) a per-build cache name.
export default defineConfig({
  plugins: [react(), swStamp()],
  server: {
    port: 5173,
    strictPort: true,
  },
});

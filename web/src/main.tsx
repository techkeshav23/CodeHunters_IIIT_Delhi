import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/anek-latin/600.css";
import "@fontsource/anek-latin/700.css";
import "@fontsource/anek-latin/800.css";
import "@fontsource/anek-devanagari/600.css";
import "@fontsource/anek-devanagari/700.css";
import "@fontsource/anek-devanagari/800.css";
import "@fontsource/noto-sans/400.css";
import "@fontsource/noto-sans/600.css";
import "@fontsource/noto-sans/700.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "@fontsource/noto-sans-devanagari/700.css";
import "./styles.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Installable app: the service worker (public/sw.js) keeps the app shell for
// offline starts and never caches API calls. Production builds only, so the
// dev server is never cached.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`).catch(() => {
      // Without the worker the app still works online.
    });
  });
}

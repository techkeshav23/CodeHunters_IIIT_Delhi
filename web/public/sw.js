/* CareCompass service worker.
   Keeps the app shell (index.html, JS, CSS, fonts, icons) so the app opens
   without a network. It never touches the API: /v1/... and /health always go
   straight to the network, so triage answers are always live. When offline,
   API calls fail and the app shows its own error state.

   The build (scripts/sw-stamp.mjs) fills in BUILD_ID and BUILD_FILES, so each
   deploy gets a new cache and old caches are deleted on activate. */

const BUILD_ID = "__BUILD_ID__";
const BUILD_FILES = []; // __BUILD_FILES__

const CACHE_PREFIX = "carecompass-shell-";
const CACHE = CACHE_PREFIX + BUILD_ID;

// Files from public/ that the shell needs.
const PUBLIC_FILES = [
  "/index.html",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/icon-192.png",
  "/icon-512.png",
  "/icon-maskable-512.png",
  "/apple-touch-icon.png",
];

// Same-origin paths that must never be answered from a cache.
const NETWORK_ONLY = ["/v1", "/health", "/docs", "/redoc", "/openapi.json"];

function isNetworkOnly(pathname) {
  return NETWORK_ONLY.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

self.addEventListener("install", (event) => {
  const urls = Array.from(new Set([...PUBLIC_FILES, ...BUILD_FILES]));
  event.waitUntil(
    caches
      .open(CACHE)
      // cache: "reload" skips the HTTP cache so the shell matches this deploy.
      .then((cache) => cache.addAll(urls.map((url) => new Request(url, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k.startsWith(CACHE_PREFIX) && k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Not calling respondWith() leaves the request to the browser, exactly as if
  // there were no service worker: API calls and other sites always hit the network.
  if (url.origin !== self.location.origin) return;
  if (isNetworkOnly(url.pathname)) return;

  if (req.mode === "navigate") {
    // Network first so a new deploy shows up at once; the cached shell when offline.
    event.respondWith(fetch(req).catch(() => fromCache("/index.html").then((hit) => hit || Response.error())));
    return;
  }

  if (url.pathname.startsWith("/assets/")) {
    // Hashed file names never change content, so a cached copy is always right.
    event.respondWith(
      fromCache(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok && res.type === "basic") {
              const copy = res.clone();
              caches.open(CACHE).then((cache) => cache.put(req, copy));
            }
            return res;
          }),
      ),
    );
    return;
  }

  // Manifest and icons: cached copy if this build has one, else the network.
  event.respondWith(fromCache(req).then((hit) => hit || fetch(req)));
});

function fromCache(request) {
  return caches.open(CACHE).then((cache) => cache.match(request));
}

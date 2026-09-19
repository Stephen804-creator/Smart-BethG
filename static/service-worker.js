// Smart BethG - minimal app-shell service worker.
//
// Scope, deliberately: this caches the static shell (CSS/JS/icons/pages)
// so the app installs and opens instantly. It does NOT cache or fake
// /api/* or /auth/* responses - chat requires a live network connection
// to a real AI provider, and pretending otherwise would mean serving a
// stale or fabricated reply while offline. That is not acceptable per
// this project's "no fake AI response" rule, so those requests always
// go straight to the network with no offline fallback.

const CACHE_NAME = "smart-bethg-shell-v1";
const SHELL_ASSETS = [
  "/",
  "/chat",
  "/login",
  "/static/css/main.css",
  "/static/js/app.js",
  "/static/js/chat.js",
  "/static/js/login.js",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never touch API or auth traffic - always live, never cached/faked.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/auth/")) {
    return;
  }

  if (event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

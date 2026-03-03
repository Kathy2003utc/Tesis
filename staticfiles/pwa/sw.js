const CACHE_NAME = "pwa-pedidos-v3";

// Precarga solo lo público / esencial
const CORE_CACHE = [
  "/offline/",
  "/static/pwa/manifest.json",
  "/static/pwa/icons/icon-192.png",
  "/static/pwa/icons/icon-512.png",
];

function isHtmlResponse(res) {
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  return ct.includes("text/html");
}

function isCacheablePage(url) {
  // Páginas que SÍ quieres poder ver offline (ya visitadas)
  const allow = [
    "/login/",
    "/administrador/dashboard/",
    "/mesero/dashboard/",
    "/cajero/dashboard/",
    "/cocinero/pedidos/",
  ];
  return allow.includes(url.pathname);
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_CACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : null)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== "GET") return;

  // Ignorar WebSocket
  if (url.protocol === "ws:" || url.protocol === "wss:") return;

  // NAVEGACIÓN (HTML)
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then(async (res) => {
          // Solo cachear si:
          // - es HTML
          // - status 200 (no 302)
          // - está en la lista allow
          if (res.ok && isHtmlResponse(res) && isCacheablePage(url)) {
            const copy = res.clone();
            const cache = await caches.open(CACHE_NAME);
            await cache.put(req, copy);
          }
          return res;
        })
        .catch(async () => {
          // Offline: si es una página permitida, intenta devolver la cache
          if (isCacheablePage(url)) {
            const cached = await caches.match(req);
            if (cached) return cached;
          }
          return caches.match("/offline/");
        })
    );
    return;
  }

  // RECURSOS (CSS/JS/IMG): cache-first
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;

      return fetch(req).then(async (res) => {
        // Cachear recursos exitosos
        if (res.ok) {
          const copy = res.clone();
          const cache = await caches.open(CACHE_NAME);
          await cache.put(req, copy);
        }
        return res;
      });
    })
  );
});

/* ================= PUSH ================= */

self.addEventListener("push", function (event) {

  if (!event.data) return;

  const data = event.data.json();

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.message,
      icon: "/static/pwa/icons/icon-192.png",
      badge: "/static/pwa/icons/icon-192.png",
      data: {
        url: data.url || "/cajero/dashboard/"
      }
    })
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();

  const url = event.notification.data.url;

  event.waitUntil(
    clients.matchAll({ type: "window" }).then(windowClients => {

      for (let client of windowClients) {
        if (client.url.includes(url) && "focus" in client) {
          return client.focus();
        }
      }

      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});


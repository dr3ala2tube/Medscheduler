// MedScheduler Service Worker
// Strategy:
//   - /api/*  → network-only  (live data, never cache)
//   - everything else → cache-first, update cache in background

const CACHE = 'medscheduler-v1';

const PRECACHE = [
  '/',
  'https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js',
  'https://www.gstatic.com/firebasejs/10.7.1/firebase-auth-compat.js',
];

// ── Install: pre-cache the app shell ─────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// ── Activate: delete old cache versions ──────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // API calls: always go to network (never serve stale schedule data)
  if (url.pathname.startsWith('/api/')) return;

  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      const networkFetch = fetch(event.request).then(response => {
        // Cache successful same-origin responses
        if (response.ok && url.origin === self.location.origin) {
          caches.open(CACHE).then(cache => cache.put(event.request, response.clone()));
        }
        return response;
      });
      // Return cached version immediately; update cache in background
      return cached || networkFetch;
    })
  );
});

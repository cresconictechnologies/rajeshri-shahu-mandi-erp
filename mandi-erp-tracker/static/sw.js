// Progressive Web App Service Worker for Rajarshi Shahu Mandi ERP
const CACHE_NAME = 'mandi-erp-pwa-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/login',
  '/login.html',
  '/portal',
  '/portal.html',
  '/accounts',
  '/accounts.html',
  '/admin',
  '/admin.html',
  '/app',
  '/app.html',
  '/manifest.json',
  '/static/manifest.json',
  '/static/theme.css',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Never cache dynamic API network calls
  if (event.request.url.includes('/api/')) {
    return;
  }

  // Static assets: cache-first with network fallback
  if (
    event.request.url.includes('/static/') ||
    event.request.url.includes('/icons/') ||
    event.request.url.includes('manifest.json')
  ) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }

  // Navigation / HTML pages: network-first with cache fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request).then((matching) => {
          return matching || caches.match('/login') || caches.match('/portal');
        });
      })
    );
    return;
  }

  // Default: network with cache fallback
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

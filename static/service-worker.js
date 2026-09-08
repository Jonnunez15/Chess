const CACHE_NAME = 'chess-analytics-v2';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      )
    )
  );

  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Never cache API requests
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
    );
    return;
  }

  // Always try the newest version of JS/CSS first
  if (
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css')
  ) {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();

          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(request, copy);
            });

          return response;
        })
        .catch(() =>
          caches.match(request)
        )
    );

    return;
  }

  // Everything else: network first, cache fallback
  event.respondWith(
    fetch(request)
      .then(response => {
        const copy = response.clone();

        caches.open(CACHE_NAME)
          .then(cache => {
            cache.put(request, copy);
          });

        return response;
      })
      .catch(() =>
        caches.match(request)
      )
  );
});

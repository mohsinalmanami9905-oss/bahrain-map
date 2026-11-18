// Service worker: offline app shell + local map data (MIT)
importScripts('precache-list.js');
const VERSION = '1c265cae45';
const SHELL = 'bm-shell-' + VERSION;
const DATA = 'bm-data-v1';      // map data stays across app updates
const RUNTIME = 'bm-rt-v1';     // extra glyph ranges etc.

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(SHELL);
    await c.addAll(self.PRECACHE.map((u) => new Request(u, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== SHELL && k !== DATA && k !== RUNTIME) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function rangeFromCache(req, cached) {
  const blob = await cached.blob();
  const m = /bytes=(\d+)-(\d*)/.exec(req.headers.get('range') || '');
  if (!m) return new Response(blob, { status: 200, headers: { 'Content-Type': 'application/octet-stream', 'Content-Length': String(blob.size) } });
  const start = +m[1]; const end = m[2] ? Math.min(+m[2], blob.size - 1) : blob.size - 1;
  const part = blob.slice(start, end + 1);
  return new Response(part, { status: 206, headers: {
    'Content-Type': 'application/octet-stream', 'Content-Length': String(part.size),
    'Content-Range': `bytes ${start}-${end}/${blob.size}`, 'Accept-Ranges': 'bytes' } });
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // satellite tiles etc: network only
  if (url.pathname.endsWith('.pmtiles')) {
    e.respondWith((async () => {
      const cached = await caches.match(url.origin + url.pathname, { cacheName: DATA });
      if (cached) return rangeFromCache(req, cached);
      return fetch(req);
    })());
    return;
  }
  if (url.pathname.endsWith('/data/meta.json')) { // network first (update check)
    e.respondWith(fetch(req).catch(() => caches.match(req, { ignoreSearch: true })));
    return;
  }
  e.respondWith((async () => {
    if (req.mode === 'navigate') {
      const shell = await caches.match(new URL('./', self.registration.scope).href) || await caches.match(new URL('index.html', self.registration.scope).href);
      if (shell) { e.waitUntil(fetch(req).then(async (r) => { if (r.ok) (await caches.open(SHELL)).put(new URL('./', self.registration.scope).href, r); }).catch(() => {})); return shell; }
      return fetch(req);
    }
    const hit = await caches.match(req, { ignoreSearch: true });
    if (hit) return hit;
    try {
      const r = await fetch(req);
      if (r.ok && (url.pathname.includes('/fonts/') || url.pathname.includes('/sprites/') || url.pathname.includes('/icons/'))) {
        const c = await caches.open(RUNTIME); c.put(req, r.clone());
      }
      return r;
    } catch (err) {
      if (url.pathname.endsWith('.pbf')) return new Response(new Uint8Array(0), { status: 200, headers: { 'Content-Type': 'application/x-protobuf' } });
      throw err;
    }
  })());
});

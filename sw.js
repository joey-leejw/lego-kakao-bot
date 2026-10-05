// 웹푸시 수신용 서비스 워커
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (_) { d = { body: event.data && event.data.text() }; }
  const opts = {
    body: d.body || '오늘의 레고 소식이 도착했어요',
    icon: d.icon || 'icon-192.png',
    badge: 'badge-72.png',
    tag: d.tag || 'daily',
    renotify: true,
    data: { url: d.url || './' },
  };
  if (d.image) opts.image = d.image;
  event.waitUntil(self.registration.showNotification(d.title || '레고 소식', opts));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || './';
  event.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of all) {
      if ('navigate' in c) { try { await c.navigate(url); return c.focus(); } catch (_) {} }
    }
    return self.clients.openWindow(url);
  })());
});

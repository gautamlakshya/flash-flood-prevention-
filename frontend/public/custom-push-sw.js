// Standards-based Web Push Notification Listener for Flash Flood Early Warning System (FFEWS)
self.addEventListener('push', function(event) {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = {
        title: 'Flash Flood Alert: Chungthang',
        body: event.data.text()
      };
    }
  }

  const title = data.title || '🚨 Flash Flood Warning — Chungthang Basin';
  const severity = data.severity || 'WARNING';

  const options = {
    body: data.body || 'Flash flood warning issued for Chungthang Basin (Teesta River). Evacuate low-lying riverbanks immediately.',
    icon: '/icons/pwa-192x192.png',
    badge: '/icons/pwa-192x192.png',
    tag: data.tag || 'ffews-alert',
    renotify: true,
    requireInteraction: true,
    vibrate: [300, 100, 300, 100, 300],
    data: data.data || { url: '/alerts' }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (let i = 0; i < clientList.length; i++) {
        let client = clientList[i];
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

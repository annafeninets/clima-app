self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data?.json() || {};
  } catch {
    payload = { body: event.data?.text() || "" };
  }
  const title = payload.title || "Clima";
  const options = {
    body: payload.body || "Откройте Clima, чтобы посмотреть образ на сегодня.",
    data: { url: "/" }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data?.url || "/"));
});

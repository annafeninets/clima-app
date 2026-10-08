import { request } from "../core/api.js";

export function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

export function isPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function isIOSWithoutPWA() {
  const userAgent = navigator.userAgent || "";
  const isIOS = /iPhone|iPad|iPod/i.test(userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isStandalone = navigator.standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches;
  return isIOS && !isStandalone;
}

export async function registerServiceWorker() {
  const registration = await navigator.serviceWorker.register("/service-worker.js");
  await navigator.serviceWorker.ready;
  return registration;
}

export async function subscribeToPush(vapidPublicKey) {
  if (!vapidPublicKey) throw new Error("Push-уведомления сейчас недоступны.");
  const registration = await registerServiceWorker();
  const current = await registration.pushManager.getSubscription();
  return current || registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
  });
}

export async function unsubscribeFromPush() {
  const registration = await navigator.serviceWorker.getRegistration("/");
  if (!registration) return false;
  const subscription = await registration.pushManager.getSubscription();
  return subscription ? subscription.unsubscribe() : false;
}

export async function getCurrentSubscription() {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  return subscription || null;
}

export async function sendSubscriptionToServer(subscription, settings) {
  return request("/push/subscribe", {
    method: "POST",
    body: {
      subscription: subscription.toJSON(),
      time: settings.time,
      timezone: settings.timeZone
    }
  });
}

export function requestNotificationPermission() {
  return Notification.requestPermission();
}

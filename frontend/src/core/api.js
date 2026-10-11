import { state } from "./state.js?v=20261008-03";

export async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  let body = options.body;
  if (body !== undefined && !(body instanceof Blob) && !(body instanceof ArrayBuffer)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${state.api.replace(/\/+$/, "")}${path}`, {
      ...options, headers, body, signal: options.signal,
    });
  } catch {
    throw new Error(`Не удалось подключиться к API ${state.api}. Проверьте, что backend запущен и CORS разрешает адрес frontend.`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    let message = `Ошибка сервера (${response.status})`;
    if (contentType.includes("json")) {
      try { message = (await response.json()).message || message; } catch { /* Keep the HTTP status message. */ }
    }
    if (response.status === 401 && state.token) {
      window.dispatchEvent(new Event("clima:unauthorized"));
    }
    throw new ApiError(message, response.status);
  }

  if (contentType.includes("application/json")) {
    const payload = await response.json();
    if (!payload.success) throw new ApiError(payload.message || "Не удалось выполнить запрос", response.status);
    return payload.data;
  }
  return response.blob();
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const photoCache = new Map();
const MAX_PHOTO_CACHE_SIZE = 50; // Limit cache size to prevent memory leaks

export function photoUrl(photo) {
  if (!photo) return Promise.resolve("");
  if (/^data:image\//i.test(photo) || /^blob:/i.test(photo)) return Promise.resolve(photo);
  const path = photo.startsWith("/") ? photo : `/${photo}`;

  // Check if we have a cached entry
  const cached = photoCache.get(path);
  if (cached) {
    // Update access time for LRU
    cached.accessTime = Date.now();

    // If we have the blob URL cached, return it immediately
    if (cached.url !== null) {
      return Promise.resolve(cached.url);
    }
    // If we have a promise pending, return it
    if (cached.promise !== null) {
      return cached.promise;
    }
  }

  // Create a new promise for this photo
  let resolvePromise, rejectPromise;
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });

  // Store the promise in cache (waiting for resolution)
  const cacheEntry = { url: null, promise, accessTime: Date.now() };
  photoCache.set(path, cacheEntry);

  // Fetch the photo and create blob URL
  request(path)
    .then((blob) => {
      const blobURL = URL.createObjectURL(blob);
      // Update cache with the resolved URL
      const updatedEntry = { url: blobURL, promise: null, accessTime: Date.now() };
      photoCache.set(path, updatedEntry);
      resolvePromise(blobURL);
    })
    .catch((error) => {
      // On error, remove from cache and reject promise
      photoCache.delete(path);
      rejectPromise(error);
    });

  // Check if we need to evict old entries to stay within cache size limits
  if (photoCache.size > MAX_PHOTO_CACHE_SIZE) {
    // Find the least recently used entry
    let lruPath = null;
    let lruTime = Infinity;

    for (const [cachePath, cacheEntry] of photoCache.entries()) {
      if (cacheEntry.accessTime < lruTime) {
        lruTime = cacheEntry.accessTime;
        lruPath = cachePath;
      }
    }

    // Remove the LRU entry and revoke its blob URL if it exists
    if (lruPath !== null) {
      const lruEntry = photoCache.get(lruPath);
      if (lruEntry && lruEntry.url !== null) {
        try {
          URL.revokeObjectURL(lruEntry.url);
        } catch (e) {
          // Ignore errors in revoking (might already be revoked)
        }
      }
      photoCache.delete(lruPath);
    }
  }

  return promise;
}
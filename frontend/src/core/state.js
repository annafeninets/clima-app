export const STORAGE_KEYS = {
  token: "clima.token",
  login: "clima.login",
  theme: "clima.theme",
  vapid: "clima.vapid",
  timeZone: "clima.timeZone",
  place: "clima.place",
};

export const SEASONS = ["WINTER", "SPRING", "SUMMER", "AUTUMN"];
export const SEASON_LABELS = { WINTER: "Зима", SPRING: "Весна", SUMMER: "Лето", AUTUMN: "Осень" };
export const PARTS = {
  TOP: "Верх",
  BOTTOM: "Низ",
  SHOES: "Обувь",
  OUTERWEAR: "Верхняя одежда",
  ACCESSORY: "Аксессуары",
  ONE_PIECE: "Платье / комбинезон"
};

const config = (typeof window !== "undefined" && window.CLIMA_CONFIG) || {};
const apiFromConfig = typeof config.apiBaseUrl === "string" && config.apiBaseUrl
  ? config.apiBaseUrl
  : "http://127.0.0.1:8000";

export const state = {
  api: apiFromConfig.replace(/\/+$/, ""),
  token: localStorage.getItem(STORAGE_KEYS.token) || "",
  login: localStorage.getItem(STORAGE_KEYS.login) || "",
  theme: localStorage.getItem(STORAGE_KEYS.theme) || "LIGHT",
  publicVapidKey: localStorage.getItem(STORAGE_KEYS.vapid) || config.vapidPublicKey || "",
  page: "home",
  outfits: [],
  wardrobe: [],
  wardrobeStatus: { is_complete: true, missing: [] },
  favorites: [],
  history: [],
  profile: {},
  settings: {},
  location: "",
  selectedPlace: readStoredPlace(),
  planDate: "",
  planOccasion: "everyday",
  filter: "ALL",
  search: "",
  settingsTab: "profile",
  authMode: "login",
  homeError: "",
  wardrobeHintMissing: []
};

// Разбор ?missing=top,shoes из URL — с защитой от отсутствия window
try {
  const missingFromUrl = new URLSearchParams(window.location.search).get("missing");
  const wardrobeHintCategories = new Set([
    "top", "outerwear", "bottom", "shoes", "bag", "hat", "accessories"
  ]);
  state.wardrobeHintMissing = missingFromUrl
    ? missingFromUrl.split(",").filter((category) => wardrobeHintCategories.has(category))
    : [];
  if (state.wardrobeHintMissing.length) state.page = "wardrobe";
} catch {
  state.wardrobeHintMissing = [];
}

export function clearSession() {
  state.token = "";
  state.login = "";
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.login);
  localStorage.removeItem(STORAGE_KEYS.timeZone);
}

export function saveSession(token, login) {
  state.token = token;
  state.login = login;
  localStorage.setItem(STORAGE_KEYS.token, token);
  localStorage.setItem(STORAGE_KEYS.login, login);
}

function readStoredPlace() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.place);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setPlace(place) {
  if (!place?.name) return;
  state.selectedPlace = place;
  state.location = place.name;
  try {
    localStorage.setItem(STORAGE_KEYS.place, JSON.stringify(place));
    if (place.countryCode) localStorage.setItem("clima.country", place.countryCode);
  } catch {
    /* ignore quota */
  }
}

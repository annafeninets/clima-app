// Общее состояние выбранного места. Им пользуются и вкладка «Подбор аутфита»,
// и «Настройки»: выбор в одном поле сразу виден в другом, переживает перерисовку страницы
// и перезагрузку (localStorage). Координаты нужны, чтобы погода считалась по выбранному
// городу, а не по первому совпадению имени (Springfield, IL ≠ Springfield, MO).

import { state, STORAGE_KEYS } from "./state.js?v=20261008-03";
import { foldName, formatPlace, hasCoordinates } from "../services/placeFormat.js?v=20261010-01";

const listeners = new Set();

export function subscribePlace(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify(place, source) {
  for (const listener of [...listeners]) {
    try {
      listener(place, source);
    } catch (error) {
      console.error("place listener failed", error);
    }
  }
}

function persist(place) {
  try {
    if (place) localStorage.setItem(STORAGE_KEYS.place, JSON.stringify(place));
    else localStorage.removeItem(STORAGE_KEYS.place);
  } catch {
    /* квота или приватный режим — не критично */
  }
}

export function selectPlace(place, source = null) {
  if (!place?.name) return;
  const clean = {
    name: place.name,
    region: place.region || "",
    country: place.country || "",
    countryCode: place.countryCode || "",
    lat: hasCoordinates(place) ? Number(place.lat) : null,
    lon: hasCoordinates(place) ? Number(place.lon) : null,
    population: place.population || 0,
  };
  state.selectedPlace = clean;
  state.location = clean.name;
  persist(clean);
  notify(clean, source);
}

export function clearSelectedPlace(source = null) {
  if (!state.selectedPlace) return;
  state.selectedPlace = null;
  persist(null);
  notify(null, source);
}

/** Выбранное место актуально, только если совпадает с городом из профиля. */
export function currentPlace() {
  const place = state.selectedPlace;
  if (!place || !state.location) return null;
  return foldName(place.name) === foldName(state.location) ? place : null;
}

/** Профиль мог измениться на другом устройстве — устаревшие координаты выбрасываем. */
export function reconcilePlace() {
  if (state.selectedPlace && !currentPlace()) {
    state.selectedPlace = null;
    persist(null);
  }
}

export function placeFieldValue() {
  const place = currentPlace();
  return place ? formatPlace(place) : state.location || "";
}

export function coordinateQuery(place = currentPlace()) {
  return hasCoordinates(place) ? `&lat=${place.lat}&lon=${place.lon}` : "";
}

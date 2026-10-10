// Единое форматирование места: «Город, Регион, Страна» и разбор текста поля обратно в название города.
// Лёгкий модуль без зависимостей — его используют и поле ввода, и хранилище выбранного места.

let regionNames = null;
try {
  regionNames = new Intl.DisplayNames(["ru"], { type: "region" });
} catch {
  regionNames = null;
}

export function countryLabel(code) {
  if (!code) return "";
  const upper = String(code).toUpperCase();
  try {
    return regionNames?.of(upper) || upper;
  } catch {
    return upper;
  }
}

function sameText(a, b) {
  return String(a || "").trim().toLowerCase() === String(b || "").trim().toLowerCase();
}

/** Регион показываем, только если он не повторяет название города («Moscow, Moscow»). */
export function placeParts(place) {
  if (!place?.name) return [];
  const parts = [place.name];
  if (place.region && !sameText(place.region, place.name)) parts.push(place.region);
  const country = place.country || countryLabel(place.countryCode);
  if (country && !sameText(country, place.name)) parts.push(country);
  return parts;
}

export function formatPlace(place) {
  return placeParts(place).join(", ");
}

/** Короткая подпись для подсказки: «Регион, Страна». */
export function placeSubtitle(place) {
  return placeParts(place).slice(1).join(", ");
}

/** Из текста поля («Москва, Москва, Россия») получаем название города для API. */
export function placeNameFromText(text) {
  return String(text || "").split(",")[0].trim();
}

export function foldName(value) {
  return String(value || "").trim().toLowerCase().replaceAll("ё", "е");
}

export function hasCoordinates(place) {
  return Number.isFinite(Number(place?.lat)) && Number.isFinite(Number(place?.lon))
    && place?.lat !== null && place?.lon !== null && place?.lat !== "" && place?.lon !== "";
}

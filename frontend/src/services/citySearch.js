// Локальный датасет GeoNames (~34k городов) для мгновенного автокомплита.
// Nominatim / Open-Meteo подключаются как fallback в CityAutocomplete, если
// локально мало совпадений (кириллица, редкие населённые пункты).

import { toLatin } from "../utils/transliteration.js";
import { levenshtein } from "../utils/levenshtein.js";

let cities = null;
let loading = null;

function regionNames() {
  try {
    return new Intl.DisplayNames(["ru"], { type: "region" });
  } catch {
    return null;
  }
}

const display = regionNames();

export function countryLabel(code) {
  if (!code) return "";
  try {
    return display?.of(code.toUpperCase()) || code.toUpperCase();
  } catch {
    return code.toUpperCase();
  }
}

export function formatPlace(place) {
  const region = place.region || "";
  const country = place.country || countryLabel(place.countryCode);
  const extra = [region, country].filter(Boolean);
  return extra.length ? `${place.name}, ${extra.join(", ")}` : place.name;
}

function asPlace(row) {
  return {
    name: row.name,
    countryCode: String(row.country || row.countryCode || "").toUpperCase(),
    country: row.countryName || countryLabel(row.country || row.countryCode),
    region: row.region || "",
    lat: row.lat ?? null,
    lon: row.lon ?? null,
    population: Number(row.population) || 0,
    alt: row.alt || "",
    ascii: row.ascii || "",
  };
}

function haystack(place) {
  return `${place.name} ${place.ascii} ${place.alt} ${toLatin(place.name)}`.toLowerCase();
}

export async function loadCities() {
  if (cities) return cities;
  if (!loading) {
    loading = fetch("/src/data/cities.json")
      .then((response) => {
        if (!response.ok) throw new Error("cities.json unavailable");
        return response.json();
      })
      .then((rows) => {
        cities = Array.isArray(rows) ? rows.map(asPlace) : [];
        return cities;
      })
      .catch((error) => {
        console.error("Failed to load local cities dataset", error);
        cities = [];
        return cities;
      });
  }
  return loading;
}

function scorePlace(place, query) {
  const q = query.toLowerCase();
  const qLatin = toLatin(query).toLowerCase();
  const name = place.name.toLowerCase();
  const latin = toLatin(place.name).toLowerCase();
  const alt = (place.alt || "").toLowerCase();
  const words = `${name} ${latin} ${alt}`.split(/[\s\-/,]+/);
  if (words.some((word) => word.startsWith(q) || (qLatin && word.startsWith(qLatin)))) return 0;
  const blob = haystack(place);
  if (blob.includes(q) || (qLatin && blob.includes(qLatin))) return 1;
  const dist = Math.min(
    levenshtein(q, name.slice(0, Math.max(q.length, 4))),
    qLatin ? levenshtein(qLatin, latin.slice(0, Math.max(qLatin.length, 4))) : 99,
  );
  if (query.length >= 3 && dist <= 2) return 2 + dist;
  return -1;
}

export async function searchCities(query, { country = "", limit = 12 } = {}) {
  const data = await loadCities();
  const trimmed = (query || "").trim();
  if (!trimmed) return getDefaultCitiesByCountry(country, limit);
  const matches = [];
  for (const place of data) {
    const score = scorePlace(place, trimmed);
    if (score < 0) continue;
    const countryBoost = country && place.countryCode === country.toUpperCase() ? -0.2 : 0;
    matches.push({ place, score: score + countryBoost });
  }
  matches.sort((a, b) => a.score - b.score || b.place.population - a.place.population);
  return matches.slice(0, limit).map((entry) => entry.place);
}

export async function getDefaultCitiesByCountry(countryCode, limit = 80) {
  const data = await loadCities();
  const code = (countryCode || "").toUpperCase();
  const pool = code ? data.filter((place) => place.countryCode === code) : data;
  return pool
    .slice()
    .sort((a, b) => b.population - a.population || a.name.localeCompare(b.name, "ru"))
    .slice(0, Math.max(30, Math.min(limit, 100)));
}

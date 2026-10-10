import { setPlace, state } from "../core/state.js?v=20261008-03";
import { setUserCountry, useUserCountry } from "../hooks/useUserCountry.js";
import { fetchPlaces, resolveUserCountry } from "../services/placeSearch.js";
import { formatPlace, getDefaultCitiesByCountry, searchCities } from "../services/citySearch.js";
import { mountCombobox } from "../utils/autocomplete.js";

const memoryCache = new Map();

function cacheKey(query, country) {
  return `${(country || "").toUpperCase()}::${query.trim().toLowerCase()}`;
}

function toOption(place) {
  return {
    title: place.name,
    subtitle: [place.region, place.country || place.countryCode].filter(Boolean).join(", "),
    value: formatPlace(place),
    meta: place,
  };
}

function mergePlaces(primary, secondary, limit) {
  const seen = new Set();
  const result = [];
  for (const place of [...primary, ...secondary]) {
    if (!place?.name) continue;
    const key = `${place.name.casefold?.() || place.name.toLowerCase()}|${(place.countryCode || "").toUpperCase()}|${place.region || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(place);
    if (result.length >= limit) break;
  }
  return result;
}

/**
 * Гибрид: локальный cities.json (мгновенно) + /places/search (Open-Meteo/Nominatim).
 */
export class CityAutocomplete {
  constructor(input, options = {}) {
    this.input = input;
    this.onChange = options.onChange || ((place) => setPlace(place));
    this.destroyCombobox = mountCombobox(input, {
      debounceMs: options.debounceMs ?? 250,
      load: (query, ctx) => this._load(query, ctx),
      onSelect: (place) => {
        if (place?.countryCode) setUserCountry(place.countryCode);
        this.onChange(place);
      },
    }).destroy;
    resolveUserCountry().catch(() => {});
  }

  async _load(query, { signal, empty }) {
    const country = useUserCountry();
    const key = cacheKey(query, country);
    if (memoryCache.has(key)) return memoryCache.get(key).map(toOption);

    const limit = empty ? 80 : 12;
    const local = empty
      ? await getDefaultCitiesByCountry(country, limit)
      : await searchCities(query, { country, limit });

    let remote = [];
    const needsRemote = empty ? local.length < 30 : local.length < 5 || /[а-яё]/i.test(query);
    if (needsRemote) {
      try {
        remote = await fetchPlaces({
          query,
          country,
          seed: empty ? (state.location || "") : "",
          limit: empty ? 50 : 12,
          signal,
        });
      } catch {
        remote = [];
      }
    }
    const merged = mergePlaces(empty ? [...local, ...remote] : [...remote, ...local], [], limit);
    const fallback = merged.length ? merged : await getDefaultCitiesByCountry("", 50);
    memoryCache.set(key, fallback);
    return fallback.map(toOption);
  }

  destroy() {
    this.destroyCombobox?.();
  }
}

export function initCityAutocomplete(input, options = {}) {
  if (!input) return null;
  return new CityAutocomplete(input, options);
}

export default CityAutocomplete;

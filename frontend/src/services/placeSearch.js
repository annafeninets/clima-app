import { request } from "../core/api.js";
import { setUserCountry, useUserCountry } from "../hooks/useUserCountry.js";

let countryLookup;

export async function resolveUserCountry() {
  const stored = typeof localStorage !== "undefined" && localStorage.getItem("clima.country");
  if (stored) return stored.toUpperCase();
  if (!countryLookup) {
    countryLookup = request("/places/context")
      .then((context) => {
        if (context?.countryCode) setUserCountry(context.countryCode);
        return context?.countryCode?.toUpperCase() || useUserCountry();
      })
      .catch(() => useUserCountry());
  }
  return countryLookup;
}

export async function fetchPlaces({ query = "", country = "", seed = "", limit = 10 } = {}) {
  const params = new URLSearchParams();
  params.set("q", query);
  if (country) params.set("country", country);
  if (seed) params.set("seed", seed);
  params.set("limit", String(limit));
  return request(`/places/search?${params.toString()}`);
}

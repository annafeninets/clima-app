// Import utilities and cities data
import { toLatin, toCyrillic } from '../utils/transliteration.js';
import { levenshtein } from '../utils/levenshtein.js';
// Load cities data (assuming JSON import is supported via inline import with assertion)
import citiesData from '../data/cities.json' assert { type: 'json' };

// Prepare search index: for each city, we'll store normalized name variants for matching
// We'll create an array of objects with original city and various normalized forms for comparison.
const processedCities = citiesData.map(city => {
  const name = city.name;
  // Generate variants: original, lowercase, transliterated to latin, transliterated to cyrillic (if applicable)
  // We'll also generate lowercase versions for case-insensitive comparison.
  const lower = name.toLowerCase();
  const latin = toLatin(name);
  const latinLower = latin.toLowerCase();
  // For Cyrillic input, we might also want to try toCyrillic on latin? Actually, toCyrillic(latin) should give back original if latin was from Cyrillic.
  // But we'll generate both.
  const cyrillic = toCyrillic(name); // This will attempt to convert Latin to Cyrillic; if name is already Cyrillic, it might not change much.
  const cyrillicLower = cyrillic.toLowerCase();

  // We'll keep an array of variants to match against.
  const variants = [
    { original: name, lower: lower },
    { original: latin, lower: latinLower },
    { original: cyrillic, lower: cyrillicLower }
  ];

  return { city, variants };
});

/**
 * Search for cities matching the query.
 * @param {string} query - The search string.
 * @param {number} limit - Maximum number of results to return.
 * @returns {Array} Array of city objects sorted by match quality.
 */
export function searchCities(query, limit = 10) {
  if (!query) {
    // If query is empty, we return empty array; the caller (component) will handle showing default list.
    return [];
  }

  const queryLower = query.toLowerCase();
  const queryLatin = toLatin(query);
  const queryLatinLower = queryLatin.toLowerCase();
  const queryCyrillic = toCyrillic(query);
  const queryCyrillicLower = queryCyrillic.toLowerCase();

  // We'll create an array of match objects with score and city.
  const matches = [];

  for (const proc of processedCities) {
    const { city, variants } = proc;
    let bestMatchType = null; // 0: exact start, 1: contains start, 2: fuzzy
    let bestDistance = Infinity;

    // We'll check each variant of the city name against each variant of the query?
    // For simplicity, we'll check the original lowercase and also the transliterated versions.
    // We'll compute distance between query and each variant's original (or lower?) but we need to consider start-of-word.

    // Instead, we'll compute a score based on:
    // 1. Whether the query (or its transliteration) matches the start of any word in the city name variant.
    // 2. If not, whether it contains any word.
    // 3. If not, compute Levenshtein distance (if <=2) and consider as fuzzy.

    // We'll split the city name variant into words (by spaces and hyphens?).
    // For simplicity, we'll just check if the query is a prefix of the variant (after lowercasing) or contains it.

    // We'll check each variant of the city.
    for (const { original, lower } of variants) {
      // Check for start-of-word match: we need to see if any word in the city name starts with the query.
      // We'll split the city name into words by non-word characters (spaces, hyphens).
      const words = original.toLowerCase().split(/[\s\-]+/);
      const startsWithQuery = words.some(word => word.startsWith(queryLower));
      const startsWithQueryLatin = words.some(word => word.startsWith(queryLatinLower));
      const startsWithQueryCyrillic = words.some(word => word.startsWith(queryCyrillicLower));

      if (startsWithQuery || startsWithQueryLatin || startsWithQueryCyrillic) {
        // This is a start-of-word match (priority 0)
        if (bestMatchType === null || bestMatchType > 0) {
          bestMatchType = 0;
          bestDistance = 0; // exact start match distance considered 0
        }
        continue; // no need to check other variants for this city? we can break but we'll just note.
      }

      // Check for contains (anywhere in the string)
      const containsQuery = lower.includes(queryLower) ||
                            (latin && latinLower.includes(queryLatinLower)) ||
                            (cyrillic && cyrillicLower.includes(queryCyrillicLower));
      if (containsQuery) {
        if (bestMatchType === null || bestMatchType > 1) {
          bestMatchType = 1;
          bestDistance = 0; // contains match distance considered 0 (but lower priority than start)
        }
        continue;
      }

      // Fuzzy match: Levenshtein distance <= 2
      // We'll compute distance between the query and the lowercased original (or we could try variants).
      // We'll compute distance for each variant and take the minimum.
      const distOriginal = levenshtein(queryLower, lower);
      const distLatin = latin ? levenshtein(queryLatinLower, latinLower) : Infinity;
      const distCyrillic = cyrillic ? levenshtein(queryCyrillicLower, cyrillicLower) : Infinity;
      const minDist = Math.min(distOriginal, distLatin, distCyrillic);

      if (minDist <= 2) {
        if (bestMatchType === null || bestMatchType > 2) {
          bestMatchType = 2;
          bestDistance = minDist;
        }
      }
    }

    // If we have a match for this city, add to matches with a score that prioritizes match type and then distance.
    if (bestMatchType !== null) {
      // We want to sort by match type (lower is better) and then by distance (lower is better).
      matches.push({ city, matchType: bestMatchType, distance: bestDistance });
    }
  }

  // Sort matches: first by matchType (asc), then by distance (asc), then by city name (for stability)
  matches.sort((a, b) => {
    if (a.matchType !== b.matchType) return a.matchType - b.matchType;
    if (a.distance !== b.distance) return a.distance - b.distance;
    // Tie-break by name (case-insensitive)
    return a.city.name.localeCompare(b.city.name, undefined, { sensitivity: 'base' });
  });

  // Extract just the city objects, up to limit
  return matches.slice(0, limit).map(m => m.city);
}

/**
 * Get default cities for a given country code (ISO 2-letter).
 * Returns an array of city objects for that country, sorted by name.
 * If no cities found for the country, returns empty array.
 */
export function getDefaultCitiesByCountry(countryCode) {
  if (!countryCode) return [];
  const filtered = citiesData.filter(city => city.country.toUpperCase() === countryCode.toUpperCase());
  // Sort by name (case-insensitive)
  filtered.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
  return filtered;
}

// Export the raw cities data if needed elsewhere
export { citiesData };
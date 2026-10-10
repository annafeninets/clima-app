// Generate a larger cities.json for testing
import { writeFileSync } from 'fs';

// List of base cities with real data (name, region, country, lat, lon, timezone)
// We'll start with a few and then generate variations.
const baseCities = [
  { name: 'Москва', region: 'Москва', country: 'RU', lat: 55.7558, lon: 37.6173, timezone: 'Europe/Moscow' },
  { name: 'Санкт-Петербург', region: 'Ленинградская область', country: 'RU', lat: 59.9343, lon: 30.3351, timezone: 'Europe/Moscow' },
  { name: 'Новосибирск', region: 'Новосибирская область', country: 'RU', lat: 55.0084, lon: 82.9357, timezone: 'Asia/Novosibirsk' },
  { name: 'Екатеринбург', region: 'Свердловская область', country: 'RU', lat: 56.8389, lon: 60.6057, timezone: 'Asia/Yekaterinburg' },
  { name: 'Казань', region: 'Татарстан', country: 'RU', lat: 55.7887, lon: 49.1221, timezone: 'Europe/Moscow' },
  { name: 'Нижний Новгород', region: 'Нижегородская область', country: 'RU', lat: 56.3269, lon: 44.0075, timezone: 'Europe/Moscow' },
  { name: 'Самара', region: 'Самарская область', country: 'RU', lat: 53.2001, lon: 50.15, timezone: 'Europe/Samara' },
  { name: 'Омск', region: 'Омская область', country: 'RU', lat: 54.9884, lon: 73.3242, timezone: 'Asia/Omsk' },
  { name: 'Ростов-на-Дону', region: 'Ростовская область', country: 'RU', lat: 47.2357, lon: 39.7015, timezone: 'Europe/Rostov' },
  { name: 'Уфа', region: 'Башкортостан', country: 'RU', lat: 54.7351, lon: 55.9587, timezone: 'Asia/Yekaterinburg' },
  { name: 'Красноярск', region: 'Красноярский край', country: 'RU', lat: 56.0184, lon: 92.8672, timezone: 'Asia/Krasnoyarsk' },
  { name: 'Воронеж', region: 'Воронежская область', country: 'RU', lat: 51.672, lon: 39.2108, timezone: 'Europe/Moscow' },
  { name: 'Пермь', region: 'Пермский край', country: 'RU', lat: 58.0105, lon: 56.2502, timezone: 'Europe/Perm' },
  { name: 'Волгоград', region: 'Волгоградская область', country: 'RU', lat: 48.708, lon: 44.5133, timezone: 'Europe/Volgograd' },
  { name: 'Краснодар', region: 'Краснодарский край', country: 'RU', lat: 45.0355, lon: 38.9753, timezone: 'Europe/Moscow' },
  { name: 'Лондон', region: 'Greater London', country: 'GB', lat: 51.5074, lon: -0.1278, timezone: 'Europe/London' },
  { name: 'Париж', region: 'Île-de-France', country: 'FR', lat: 48.8566, lon: 2.3522, timezone: 'Europe/Paris' },
  { name: 'Берлин', region: 'Berlin', country: 'DE', lat: 52.5200, lon: 13.4050, timezone: 'Europe/Berlin' },
  { name: 'Мадрид', region: 'Community of Madrid', country: 'ES', lat: 40.4168, lon: -3.7038, timezone: 'Europe/Madrid' },
  { name: 'Рим', region: 'Lazio', country: 'IT', lat: 41.9028, lon: 12.4964, timezone: 'Europe/Rome' },
  { name: 'Амстердам', region: 'Noord-Holland', country: 'NL', lat: 52.3676, lon: 4.9041, timezone: 'Europe/Amsterdam' },
  { name: 'Вена', region: '', country: 'AT', lat: 48.2082, lon: 16.3738, timezone: 'Europe/Vienna' },
  { name: 'Будапешт', region: '', country: 'HU', lat: 47.4979, lon: 19.0402, timezone: 'Europe/Budapest' },
  { name: 'Варшава', region: '', country: 'PL', lat: 52.2297, lon: 21.0122, timezone: 'Europe/Warsaw' },
  { name: 'Прага', region: '', country: 'CZ', lat: 50.0755, lon: 14.4378, timezone: 'Europe/Prague' },
  { name: 'Стокгольм', region: '', country: 'SE', lat: 59.3293, lon: 18.0686, timezone: 'Europe/Stockholm' },
  { name: 'Осло', region: '', country: 'NO', lat: 59.9139, lon: 10.7522, timezone: 'Europe/Oslo' },
  { name: 'Копенгаген', region: '', country: 'DK', lat: 55.6761, lon: 12.5683, timezone: 'Europe/Copenhagen' },
  { name: 'Хельсинки', region: '', country: 'FI', lat: 60.1699, lon: 24.9384, timezone: 'Europe/Helsinki' },
  { name: 'Афины', region: '', country: 'GR', lat: 37.9838, lon: 23.7275, timezone: 'Europe/Athens' },
  { name: 'Стамбул', region: '', country: 'TR', lat: 41.0082, lon: 28.9674, timezone: 'Europe/Istanbul' },
  { name: 'Москва', region: 'Московская область', country: 'RU', lat: 55.7558, lon: 37.6173, timezone: 'Europe/Moscow' }, // duplicate for variation
];

// Function to generate a random offset
function randomOffset(max) {
  return (Math.random() * 2 - 1) * max; // [-max, max]
}

// Function to generate a city id from name and country
function makeId(name, country) {
  const clean = name.toLowerCase().replace(/[\s\-]/g, '');
  return `${clean}-${country.toLowerCase()}`;
}

// List of countries to randomly assign (ISO 2-letter)
const countries = ['RU', 'US', 'GB', 'FR', 'DE', 'ES', 'IT', 'JP', 'CN', 'IN', 'BR', 'CA', 'AU', 'ZA', 'EG'];

// Timezone mapping (simplistic: we'll assign based on country or random from a list)
const timezonesByCountry = {
  RU: ['Europe/Moscow', 'Europe/Samara', 'Asia/Yekaterinburg', 'Asia/Omsk', 'Asia/Novosibirsk', 'Asia/Krasnoyarsk', 'Asia/Irkutsk', 'Asia/Yakutsk', 'Asia/Vladivostok'],
  US: ['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu'],
  GB: ['Europe/London'],
  FR: ['Europe/Paris'],
  DE: ['Europe/Berlin'],
  ES: ['Europe/Madrid'],
  IT: ['Europe/Rome'],
  JP: ['Asia/Tokyo'],
  CN: ['Asia/Shanghai', 'Asia/Urumqi'],
  IN: ['Asia/Kolkata'],
  BR: ['America/Sao_Paulo', 'America/Manaus'],
  CA: ['America/Toronto', 'America/Vancouver', 'America/Edmonton'],
  AU: ['Australia/Sydney', 'Australia/Melbourne', 'Australia/Perth'],
  ZA: ['Africa/Johannesburg'],
  EG: ['Africa/Cairo'],
};

// Default timezone list
const defaultTimezones = ['Europe/Moscow', 'America/New_York', 'Europe/London', 'Europe/Paris', 'Asia/Tokyo'];

// Generate cities array
let cities = [];
let idMap = new Set(); // to avoid duplicate ids

// Helper to add a city if id is unique
function addCity(city) {
  const id = makeId(city.name, city.country);
  if (idMap.has(id)) {
    // Try to make unique by adding a number
    let suffix = 2;
    let newId = `${id}${suffix}`;
    while (idMap.has(newId)) {
      suffix++;
      newId = `${id}${suffix}`;
    }
    city.id = newId;
    idMap.add(newId);
  } else {
    city.id = id;
    idMap.add(id);
  }
  cities.push(city);
}

// Add base cities
baseCities.forEach(city => {
  addCity({ ...city });
});

// Generate variations: for each base city, create 3 variants
baseCities.forEach(base => {
  for (let i = 0; i < 3; i++) {
    // Choose a random country (could be same as base or different)
    const country = countries[Math.floor(Math.random() * countries.length)];
    // Pick a random timezone for that country
    const tzList = timezonesByCountry[country] || defaultTimezones;
    const timezone = tzList[Math.floor(Math.random() * tzList.length)];
    // Slightly adjust coordinates
    const latOffset = randomOffset(0.5); // ~0.5 degrees ~ 50 km
    const lonOffset = randomOffset(0.5);
    // Create a variant name: sometimes add a direction, sometimes keep same
    const variantTypes = ['', 'Северный', 'Южный', 'Восточный', 'Западный', 'North', 'South', 'East', 'West'];
    const variantPrefix = variantTypes[Math.floor(Math.random() * variantTypes.length)];
    const name = variantPrefix ? `${variantPrefix} ${base.name}` : base.name;
    // Region: we can keep base region or randomize
    const region = base.region; // keep simple
    addCity({
      name,
      region,
      country,
      lat: base.lat + latOffset,
      lon: base.lon + lonOffset,
      timezone,
    });
  }
});

// Also add some completely random cities around the world
const randomCitiesCount = 50;
for (let i = 0; i < randomCitiesCount; i++) {
  const country = countries[Math.floor(Math.random() * countries.length)];
  const tzList = timezonesByCountry[country] || defaultTimezones;
  const timezone = tzList[Math.floor(Math.random() * tzList.length)];
  // Random lat/lon within bounds
  const lat = -90 + Math.random() * 180;
  const lon = -180 + Math.random() * 360;
  // Generate a plausible city name: we'll use a combination of syllables
  const syllables = ['ка', 'но', 'во', 'гор', 'дон', 'град', 'бург', 'стал', 'лин', ' поли', 'града', 'вет'];
  const name = syllables[Math.floor(Math.random() * syllables.length)] + syllables[Math.floor(Math.random() * syllables.length)];
  const region = 'Регион'; // placeholder
  addCity({
    name,
    region,
    country,
    lat,
    lon,
    timezone,
  });
}

// Sort cities by name for consistency
cities.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));

// Write to file
writeFileSync('./cities.json', JSON.stringify(cities, null, 2));
console.log(`Generated ${cities.length} cities`);
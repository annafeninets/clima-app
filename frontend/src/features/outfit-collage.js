import { photoUrl } from "../core/api.js";
import { escapeHTML, icon } from "../ui/helpers.js";

const OUTERWEAR_MARKERS = [
  "куртк", "пальто", "плащ", "пиджак", "жакет", "блейзер", "парка", "ветровк",
  "анорак", "пухов", "тренч", "дубл", "шуб", "бомбер", "косух", "дождевик",
  "пончо", "накидк", "дафлкот", "jacket", "coat", "anorak", "parka", "trench",
  "raincoat", "poncho", "cape", "blazer"
];
const BAG_MARKERS = [
  "сумк", "рюкзак", "клатч", "кошелек", "кошелёк", "bag", "backpack", "purse",
  "wallet"
];
const HAT_MARKERS = [
  "шапк", "шляп", "кепк", "бейсболк", "берет", "панам", "шарф", "платок", "снуд",
  "палантин", "hat", "cap", "beanie", "scarf"
];

function normalize(value) {
  return String(value || "").toLocaleLowerCase("ru").replaceAll("ё", "е");
}

function hasMarker(value, markers) {
  return markers.some((marker) => value.includes(marker));
}

function values(value) {
  return value == null ? [] : Array.isArray(value) ? value.filter(Boolean) : [value];
}

function classifyItem(item) {
  const type = normalize(item.type);
  if (hasMarker(type, BAG_MARKERS)) return "bag";
  if (hasMarker(type, HAT_MARKERS)) return "hat";
  if (item.part === "SHOES") return "shoes";
  if (item.part === "BOTTOM") return "bottom";
  if (item.part === "OUTERWEAR" || hasMarker(type, OUTERWEAR_MARKERS)) return "outerwear";
  if (item.part === "TOP" || item.part === "ONE_PIECE") return "top";
  return "accessories";
}

function normalizeOutfit(outfit) {
  const zones = {
    hat: values(outfit.hat),
    top: values(outfit.top),
    outerwear: values(outfit.outerwear),
    bottom: values(outfit.bottom),
    shoes: values(outfit.shoes),
    bag: values(outfit.bag),
    accessories: values(outfit.accessories)
  };
  for (const item of values(outfit.items)) {
    const zone = classifyItem(item);
    const alreadyIncluded = Object.values(zones).some((zoneItems) =>
      zoneItems.some((existing) =>
        existing === item || (existing.id && existing.id === item.id)
      )
    );
    if (!alreadyIncluded) {
      zones[zone].push(item);
    }
  }
  return zones;
}

async function itemMarkup(item) {
  const src = await photoUrl(item.photo);
  const image = src
    ? `<img src="${escapeHTML(src)}" alt="${escapeHTML(`${item.color || ""} ${item.type || "вещь"}`.trim())}" loading="lazy" />`
    : `<div class="collage-placeholder">${icon("hanger")}</div>`;
  return `<figure class="collage-item">${image}<figcaption>${escapeHTML(item.color || "")} ${escapeHTML(item.type || "Вещь")}</figcaption></figure>`;
}

async function zoneMarkup(name, items) {
  if (!items.length) return "";
  const cards = await Promise.all(items.map(itemMarkup));
  return `<div class="collage-zone zone-${name}">${cards.join("")}</div>`;
}

export async function OutfitCollage(outfit) {
  const zones = normalizeOutfit(outfit);
  const [hat, top, outerwear, bottom, shoes, bag, accessories] = await Promise.all([
    zoneMarkup("hat", zones.hat),
    zoneMarkup("top", zones.top),
    zoneMarkup("outerwear", zones.outerwear),
    zoneMarkup("bottom", zones.bottom),
    zoneMarkup("shoes", zones.shoes),
    zoneMarkup("bag", zones.bag),
    zoneMarkup("accessories", zones.accessories)
  ]);
  const upper = top || outerwear
    ? `<div class="collage-zone zone-upper ${top && outerwear ? "has-both" : "single-zone"}">${top}${outerwear}</div>`
    : "";
  const hasBag = Boolean(bag);
  return `<div class="outfit-collage ${hasBag ? "has-bag" : "no-bag"}">${hat}${upper}${bottom}${shoes}${bag}${accessories}</div>`;
}

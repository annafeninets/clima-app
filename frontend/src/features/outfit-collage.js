/**
 * Анатомический коллаж образа.
 *
 * Схема:
 *   ┌──────────────┬──────────┐
 *   │   ПАЛЬТО     │          │  ← главный кадр (3:4)
 *   ├──────────────┤  ШАПКА   │
 *   │   СВИТЕР     │          │
 *   ├──────────────┼──────────┤
 *   │   ЮБКА       │  СУМКА   │
 *   ├──────────────┤          │
 *   │   БОТИНКИ    │          │
 *   └──────────────┴──────────┘
 *
 * Левая колонка — вертикаль тела (сверху вниз).
 * Правая панель — аксессуары.
 * Все фото — object-fit: contain, без обрезки, на едином фоне.
 */

import { icon } from "../ui/helpers.js";
import { photoUrl } from "../core/api.js";

const PART_LABEL = {
  OUTERWEAR: "Верх. одежда",
  TOP: "Верх",
  BOTTOM: "Низ",
  SHOES: "Обувь",
  ACCESSORY: "Аксессуар",
  HAT: "Головной",
  SCARF: "Шарф",
  BAG: "Сумка",
  ONE_PIECE: "Платье",
  MIXED: "Вещь"
};

// Головные аксессуары — в правую панель, но по анатомии выше остальных.
const HEAD_PARTS = new Set(["HAT", "SCARF"]);
const HAND_PARTS = new Set(["ACCESSORY", "BAG"]);

function isHeadAccessory(item) {
  if (HEAD_PARTS.has(item?.part)) return true;
  if (item?.part !== "ACCESSORY") return false;
  const type = String(item?.type || "").toLowerCase();
  return (
    type.includes("шапк") || type.includes("кепк") ||
    type.includes("берет") || type.includes("панам") ||
    type.includes("шарф") || type.includes("снуд") ||
    type.includes("перчатк") ||
    type.includes("hat") || type.includes("scarf")
  );
}

function placeholder() {
  return `<div class="c-ph">${icon("image")}</div>`;
}

async function resolvePhoto(item) {
  const raw = item?.photo || item?.image || item?.photoUrl || item?.imageUrl || "";
  if (!raw) return "";
  try {
    const resolved = await photoUrl(raw);
    return resolved || raw;
  } catch {
    return raw;
  }
}

async function cell(item, zone, opts = {}) {
  const label = item?.type || item?.name || PART_LABEL[item?.part] || "";
  const partLabel = PART_LABEL[item?.part] || "";
  const src = await resolvePhoto(item);
  const photo = src
    ? `<img src="${src}" alt="${label}" loading="lazy">`
    : placeholder();
  const tag = opts.main ? `<span class="c-tag">Главный</span>` : "";
  const partBadge = partLabel
    ? `<span class="c-part">${partLabel}</span>`
    : "";
  const caption = label
    ? `<figcaption class="c-cap"><span class="dot"></span>${label}</figcaption>`
    : "";
  return `<div class="c-cell ${zone}">${photo}${tag}${partBadge}${caption}</div>`;
}

export async function OutfitCollage(outfit) {
  const items = Array.isArray(outfit?.items) ? outfit.items : [];

  const outer = items.find(i => i.part === "OUTERWEAR");
  const onePiece = items.find(i => i.part === "ONE_PIECE");
  const top = items.find(i => i.part === "TOP");
  const bottom = items.find(i => i.part === "BOTTOM");
  const shoes = items.find(i => i.part === "SHOES");

  const headAcc = items.filter(isHeadAccessory);
  const handAcc = items.filter(i => HAND_PARTS.has(i.part) && !isHeadAccessory(i));

  const mainItem = onePiece || outer || top || bottom || shoes || null;

  const leftZones = [];
  if (onePiece) {
    leftZones.push({ item: onePiece, zone: "c-onepiece" });
  } else {
    if (outer) leftZones.push({ item: outer, zone: "c-outer" });
    if (top) leftZones.push({ item: top, zone: "c-top" });
    if (bottom) leftZones.push({ item: bottom, zone: "c-bottom" });
  }
  if (shoes) leftZones.push({ item: shoes, zone: "c-shoes" });

  const rightZones = [
    ...headAcc.map(i => ({ item: i, zone: "c-head" })),
    ...handAcc.map(i => ({ item: i, zone: "c-acc" }))
  ];

  if (!leftZones.length && !rightZones.length) {
    return `<div class="outfit-collage collage--empty"><div class="c-empty">${placeholder()}</div></div>`;
  }

  const mods = [
    rightZones.length ? "" : "collage--no-acc",
    `collage--rows-${leftZones.length}`
  ].filter(Boolean).join(" ");

  const leftHtml = await Promise.all(
    leftZones.map(({ item, zone }) =>
      cell(item, zone, { main: item === mainItem })
    )
  );
  const rightHtml = await Promise.all(
    rightZones.map(({ item, zone }) => cell(item, zone))
  );

  return `<div class="outfit-collage ${mods}">
    <div class="c-left">${leftHtml.join("")}</div>
    ${rightHtml.length ? `<div class="c-right">${rightHtml.join("")}</div>` : ""}
  </div>`;
}
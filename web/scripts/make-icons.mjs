// Draws the app icons into public/ from the compass mark in src/ui/Brand.tsx.
// Run after changing the logo or the brand colours:  npm run icons
//
// Colours are the light-theme tokens from src/styles.css (:root):
//   --brand (neem) #0d5a50, --brand-ink #ffffff, --haldi #d99a06.

import { writeFileSync } from "node:fs";
import { Resvg } from "@resvg/resvg-js";

const BRAND = "#0d5a50";
const BRAND_INK = "#ffffff";
const HALDI = "#d99a06";

// Same shapes as BrandMark (viewBox 0 0 40 40), without the tile.
const needle = `
  <circle cx="20" cy="20" r="12.5" fill="none" stroke="${BRAND_INK}" stroke-opacity="0.35" stroke-width="1.5"/>
  <path d="M20 7.5 L24.2 20 L20 18.6 L15.8 20 Z" fill="${HALDI}"/>
  <path d="M20 32.5 L15.8 20 L20 21.4 L24.2 20 Z" fill="${BRAND_INK}"/>
  <circle cx="20" cy="20" r="1.8" fill="${BRAND}"/>`;

const svg = (body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">${body}\n</svg>\n`;

// Rounded tile, exactly like the logo in the app. Corners are transparent.
const tile = svg(`<rect width="40" height="40" rx="12" fill="${BRAND}"/>${needle}`);

// Full-bleed square for platforms that cut their own shape (iOS home screen).
const square = svg(`<rect width="40" height="40" fill="${BRAND}"/>${needle}`);

// Maskable: full bleed, mark shrunk to 90% so it sits well inside the
// 80% safe circle that Android launchers keep (ring ends at ~30% radius).
const maskable = svg(
  `<rect width="40" height="40" fill="${BRAND}"/><g transform="translate(20 20) scale(0.9) translate(-20 -20)">${needle}</g>`,
);

const out = new URL("../public/", import.meta.url);

function png(name, source, size) {
  const data = new Resvg(source, { fitTo: { mode: "width", value: size } }).render().asPng();
  writeFileSync(new URL(name, out), data);
  console.log(`public/${name}  ${size}x${size}  ${data.length} bytes`);
}

png("icon-192.png", tile, 192);
png("icon-512.png", tile, 512);
png("icon-maskable-512.png", maskable, 512);
png("apple-touch-icon.png", square, 180);
writeFileSync(new URL("favicon.svg", out), tile);
console.log("public/favicon.svg");

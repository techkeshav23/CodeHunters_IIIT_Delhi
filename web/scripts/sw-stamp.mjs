// Vite build plugin: after the build is written, fills in dist/sw.js (copied
// from public/sw.js) with a build id and the list of built files to precache.
// The build id is a hash of everything in dist/, so a new deploy gets a new
// cache name and an unchanged rebuild keeps the old one.

import { createHash } from "node:crypto";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

// Font subsets the app never shows (UI and answers are Hindi, English, Hinglish).
// They stay out of the precache; the worker still caches them if a page asks.
const UNUSED_FONT_SUBSET = /-(cyrillic|greek|vietnamese)(-ext)?-/;

function shouldPrecache(file) {
  if (file === "sw.js" || file.endsWith(".map")) return false;
  if (file.endsWith(".woff")) return false; // every browser with service workers takes .woff2
  if (file.endsWith(".woff2")) return !UNUSED_FONT_SUBSET.test(file);
  return true;
}

function listFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name);
    return entry.isDirectory() ? listFiles(full) : [full];
  });
}

export function swStamp() {
  let outDir = "dist";
  let base = "/";
  return {
    name: "carecompass:sw-stamp",
    apply: "build",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
      base = config.base;
    },
    writeBundle(_options, bundle) {
      const swPath = join(outDir, "sw.js");
      const template = readFileSync(swPath, "utf8");

      const hash = createHash("sha256");
      for (const full of listFiles(outDir).sort()) {
        const rel = relative(outDir, full).split(sep).join("/");
        if (rel === "sw.js") continue;
        hash.update(rel).update(readFileSync(full));
      }
      hash.update(template);
      const buildId = hash.digest("hex").slice(0, 12);

      const precache = Object.keys(bundle).filter(shouldPrecache).sort().map((f) => base + f);

      const stamped = template
        .replace('"__BUILD_ID__"', JSON.stringify(buildId))
        .replace("[]; // __BUILD_FILES__", `${JSON.stringify(precache, null, 2)};`);
      if (stamped.includes("__BUILD_ID__") || stamped.includes("__BUILD_FILES__")) {
        throw new Error("sw-stamp: placeholders not found in public/sw.js");
      }
      writeFileSync(swPath, stamped);
      this.info?.(`sw.js stamped: build ${buildId}, ${precache.length} files to precache`);
    },
  };
}

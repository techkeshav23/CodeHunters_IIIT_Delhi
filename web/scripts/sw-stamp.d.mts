import type { Plugin } from "vite";

/** Fills in dist/sw.js with a build id and the precache list (see sw-stamp.mjs). */
export function swStamp(): Plugin;

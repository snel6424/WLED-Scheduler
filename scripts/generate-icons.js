#!/usr/bin/env node
/**
 * Generates app/static/js/icons.js and app/lucide_icons.json from the
 * Lucide icon set (lucide-static npm package).
 *
 * Run once after cloning, or any time a Lucide update is wanted:
 *
 *   cd scripts
 *   npm install
 *   node generate-icons.js
 *
 * Output:
 *   ../app/static/js/icons.js    — JS module: ICONS const, PICKER_ICONS const,
 *                                  plus the helper functions preserved from the
 *                                  original file (historyIcon, scheduleIcon).
 *   ../app/lucide_icons.json     — JSON dict keyed by the same camelCase keys,
 *                                  loaded at startup by pages.py for server-side
 *                                  Jinja rendering of stored icon overrides.
 *
 * Both files are committed to the repo; this script is only needed to
 * refresh them when Lucide ships new icons.
 */

'use strict';

const fs   = require('fs');
const path = require('path');

const ICONS_DIR = path.join(__dirname, 'node_modules', 'lucide-static', 'icons');
const OUT_JS    = path.join(__dirname, '..', 'app', 'static', 'js', 'icons.js');
const OUT_JSON  = path.join(__dirname, '..', 'app', 'lucide_icons.json');

if (!fs.existsSync(ICONS_DIR)) {
  console.error(`Lucide icons not found at ${ICONS_DIR}`);
  console.error('Run: npm install');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Existing utility keys — these are referenced throughout the codebase as
// ICONS.moon, ICONS.sun, etc. They must stay in ICONS under their original
// names regardless of how Lucide names its icons. Each maps to a Lucide icon
// filename (without the .svg extension).
//
// Design decisions already confirmed with the project owner:
//   moon         → "moon"          (plain crescent)
//   sun          → "sun"           (centered 8-ray sun)
//   sunHorizon   → "sunrise"       (one icon for both sunrise & sunset badges)
//   history key  → "clock"         (same visual as today, plain clock face)
//   devices key  → "monitor"       (clean flat panel)
//   alertTriangle→ "triangle-alert"(Lucide renamed this from alert-triangle)
// ---------------------------------------------------------------------------
const UTILITY_ALIASES = {
  moon:          'moon',
  sun:           'sun',
  sunHorizon:    'sunrise',
  clock:         'clock',
  bulb:          'lightbulb',
  plus:          'plus',
  chevronRight:  'chevron-right',
  calendar:      'calendar',
  devices:       'monitor',
  history:       'clock',
  gear:          'settings',
  sparkle:       'sparkles',
  pencil:        'pencil',
  close:         'x',
  globe:         'globe',
  bolt:          'zap',
  palette:       'palette',
  brightness:    'sun',
  pin:           'map-pin',
  chevronLeft:   'chevron-left',
  wifi:          'wifi',
  shieldCheck:   'shield-check',
  alertTriangle: 'triangle-alert',
  skipForward:   'skip-forward',
  crosshair:     'crosshair',
  trash:         'trash-2',
  info:          'info',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toCamelCase(kebab) {
  return kebab.replace(/-([a-z0-9])/g, (_, c) => c.toUpperCase());
}

function toLabel(kebab) {
  return kebab.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

/**
 * Strip the outer <svg> tag, normalise whitespace and XML comments, then
 * rebuild with the project's standard attributes:
 *   viewBox="0 0 24 24" width="22" height="22" fill="none"
 *   stroke="currentColor" stroke-width="1.8"
 *   stroke-linecap="round" stroke-linejoin="round"
 *
 * Lucide's raw files use stroke-width="2" and include xmlns + a comment line;
 * we replace both so every icon is visually consistent at the project's
 * slightly lighter 1.8 weight.
 */
function normalizeSvg(raw) {
  const match = raw.match(/<svg[^>]*>([\s\S]*?)<\/svg>/i);
  if (!match) return '';
  const inner = match[1]
    .replace(/<!--[\s\S]*?-->/g, '')  // strip XML comments (Lucide adds one per file)
    .replace(/\s+/g, ' ')             // collapse whitespace
    .trim();
  return `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

// ---------------------------------------------------------------------------
// Read Lucide icons
// ---------------------------------------------------------------------------

const files = fs.readdirSync(ICONS_DIR)
  .filter(f => f.endsWith('.svg'))
  .sort();

console.log(`Reading ${files.length} Lucide icons…`);

const lucideByFileName = {};  // 'arrow-right' → normalised svg string

for (const file of files) {
  const name = file.replace('.svg', '');
  const raw  = fs.readFileSync(path.join(ICONS_DIR, file), 'utf-8');
  lucideByFileName[name] = normalizeSvg(raw);
}

// camelCase-keyed icons for JS ICONS object and PICKER_ICONS
const lucideByCamelKey = {};  // arrowRight → svg
for (const [name, svg] of Object.entries(lucideByFileName)) {
  lucideByCamelKey[toCamelCase(name)] = svg;
}

// ---------------------------------------------------------------------------
// Build utility alias entries (original key → lucide svg)
// ---------------------------------------------------------------------------

const utilityEntries = {};
for (const [utilKey, lucideName] of Object.entries(UTILITY_ALIASES)) {
  if (lucideByFileName[lucideName]) {
    utilityEntries[utilKey] = lucideByFileName[lucideName];
  } else {
    console.warn(`  WARNING: Lucide icon '${lucideName}' not found for alias '${utilKey}'`);
  }
}

// ---------------------------------------------------------------------------
// PICKER_ICONS — all Lucide icons alphabetically by camelCase key
// ---------------------------------------------------------------------------

const pickerIcons = Object.keys(lucideByCamelKey).sort().map(key => {
  // Convert camelCase key back to a human-readable label
  const label = key.replace(/([A-Z0-9])/g, ' $1').trim();
  // Title-case the first letter
  const labelTitled = label.charAt(0).toUpperCase() + label.slice(1);
  return { key, label: labelTitled };
});

console.log(`Building PICKER_ICONS with ${pickerIcons.length} entries…`);

// ---------------------------------------------------------------------------
// Helper functions (preserved from the original icons.js)
// ---------------------------------------------------------------------------

const HELPER_FUNCTIONS = `
/**
 * Picks an icon + tint for a history entry, by execution status
 * rather than the schedule's trigger mood. Status (did it actually
 * work) is the more useful signal in a log of past actions.
 */
function historyIcon(status) {
  if (status === "success") return { icon: ICONS.bulb, className: "icon-avatar--sun" };
  if (status === "failed") return { icon: ICONS.alertTriangle, className: "icon-avatar--danger" };
  return { icon: ICONS.skipForward, className: "icon-avatar--moon" };
}

/**
 * Picks an icon + avatar tint for a schedule.
 * Background tint is always derived from trigger_type / time-of-day.
 * The glyph comes from schedule.icon (picker override) when set, falling
 * back to the same auto-derived sun/moon glyph.
 */
function scheduleIcon(schedule) {
  const customGlyph = schedule.icon && ICONS[schedule.icon] ? ICONS[schedule.icon] : null;

  if (schedule.trigger_type === "sunrise") {
    return { icon: customGlyph ?? ICONS.sun, className: "icon-avatar--sun" };
  }
  if (schedule.trigger_type === "sunset") {
    return { icon: customGlyph ?? ICONS.moon, className: "icon-avatar--moon" };
  }
  // trigger_type === "time": morning hours read as "sun", evening/night as "moon"
  const hour = schedule.time_of_day ? Number(schedule.time_of_day.split(":")[0]) : 12;
  const isEvening = hour < 5 || hour >= 18;
  const className = isEvening ? "icon-avatar--moon" : "icon-avatar--sun";
  const defaultGlyph = isEvening ? ICONS.moon : ICONS.sun;
  return { icon: customGlyph ?? defaultGlyph, className };
}
`;

// ---------------------------------------------------------------------------
// Read Lucide package version for attribution comment
// ---------------------------------------------------------------------------

let lucideVersion = 'unknown';
try {
  const pkg = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'node_modules', 'lucide-static', 'package.json'), 'utf-8')
  );
  lucideVersion = pkg.version;
} catch {}

// ---------------------------------------------------------------------------
// Render icons.js
// ---------------------------------------------------------------------------

// ICONS object: all Lucide icons (camelCase) + utility aliases
const allIconEntries = [
  ...Object.entries(lucideByCamelKey),
  ...Object.entries(utilityEntries),
].map(([k, v]) => {
  // Escape backslashes and single quotes inside the SVG string
  const escaped = v.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  return `  ${k}: '${escaped}'`;
});

const pickerEntries = pickerIcons.map(
  ({ key, label }) => `  { key: '${key}', label: '${label.replace(/'/g, "\\'")}' }`
);

const jsContent = [
  `/**`,
  ` * WLED Scheduler — icons`,
  ` *`,
  ` * All icons are from Lucide v${lucideVersion} (https://lucide.dev),`,
  ` * ISC licensed. SVG content is normalised to stroke-width 1.8 and`,
  ` * 22×22 display size to match this project's visual conventions.`,
  ` *`,
  ` * DO NOT EDIT BY HAND. Regenerate with:`,
  ` *   cd scripts && npm install && node generate-icons.js`,
  ` *`,
  ` * After regenerating, rebuild the Docker image so the new icons.js`,
  ` * and lucide_icons.json are baked in:`,
  ` *   docker compose up --build -d`,
  ` */`,
  ``,
  `/* eslint-disable */`,
  `const ICONS = {`,
  allIconEntries.join(',\n'),
  `};`,
  ``,
  `/**`,
  ` * All ${pickerIcons.length} Lucide icons available in the icon picker, alphabetically.`,
  ` * Keys match ICONS keys above. The picker's search input filters this list.`,
  ` */`,
  `const PICKER_ICONS = [`,
  pickerEntries.join(',\n'),
  `];`,
  HELPER_FUNCTIONS,
].join('\n');

fs.writeFileSync(OUT_JS, jsContent, 'utf-8');
console.log(`Wrote ${OUT_JS} (${(jsContent.length / 1024).toFixed(0)} KB)`);

// ---------------------------------------------------------------------------
// Render lucide_icons.json (server-side rendering in pages.py)
// ---------------------------------------------------------------------------

const jsonPayload = { ...lucideByCamelKey, ...utilityEntries };
const jsonContent = JSON.stringify(jsonPayload);
fs.writeFileSync(OUT_JSON, jsonContent, 'utf-8');
console.log(`Wrote ${OUT_JSON} (${(jsonContent.length / 1024).toFixed(0)} KB)`);

console.log('Done.');

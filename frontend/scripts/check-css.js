#!/usr/bin/env node
// Design-token guard. Runs as part of `npm run lint` (and so in CI).
//
// The token file (src/styles/colors_and_type.css) is the only place a colour,
// small font size, radius, z-index layer or breakpoint may be spelled out.
// Everything else must reference a token, so the design cannot drift again the
// way it had by 2026-09 (441 colour literals, 22 breakpoints, three pinks).
//
// Zero dependencies on purpose — same as optimize-images.js.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(here, '..', 'src');
const TOKEN_FILE = path.join(SRC, 'styles', 'colors_and_type.css');
// Files allowed to carry literals: the token file itself, and third-party brand
// marks (Google's sign-in button colours are Google's, not ours).
const ALLOW_LITERALS = new Set([TOKEN_FILE, path.join(SRC, 'components', 'GoogleSignInButton', 'GoogleSignInButton.jsx')]);

const MAX_WIDTHS = new Set([375, 480, 640, 768, 900, 1100]);
const MIN_WIDTHS = new Set([769, 901, 1101]);
const DURATIONS = new Set(['.15s', '.2s', '.3s']);

const STRICT_OUTLINE = true;

const files = [];
(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(css|jsx)$/.test(e.name)) files.push(p);
  }
})(SRC);

const errors = [];
const warnings = [];
const rel = (f) => path.relative(path.join(here, '..'), f);
const lineOf = (s, idx) => s.slice(0, idx).split('\n').length;

// Tokens defined in the token file, and custom properties set anywhere
// (component-local ones like --arr-w are legitimate).
const tokenSrc = fs.readFileSync(TOKEN_FILE, 'utf8');
const defined = new Set([...tokenSrc.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]));
const definedAnywhere = new Set(defined);
const used = new Map();

for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  // `--x: v` in CSS, or `'--x': v` in a JSX style object.
  for (const m of src.matchAll(/(--[a-z0-9-]+)['"]?\s*:/g)) definedAnywhere.add(m[1]);
  for (const m of src.matchAll(/var\((--[a-z0-9-]+)/g)) used.set(m[1], (used.get(m[1]) || 0) + 1);
  if (f === TOKEN_FILE) continue;

  // Strip things that legitimately contain '#' or 'px' but are not styling:
  // data URIs / url() contents and JSX comments.
  const scan = src.replace(/url\([^)]*\)/g, 'url()').replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '));
  const isCss = f.endsWith('.css');

  if (!ALLOW_LITERALS.has(f)) {
    for (const m of scan.matchAll(/#[0-9a-f]{3,8}\b|\brgba?\(|\bhsla?\(/gi)) {
      // '#' followed by hex inside a JSX string could be an id/route ("#obsah");
      // only flag it where it sits in a style position.
      const before = scan.slice(Math.max(0, m.index - 40), m.index);
      if (!isCss && m[0].startsWith('#') && !/(color|background|fill|stroke|border|shadow|style)[^;{]*$/i.test(before)) continue;
      // `check-css: allow` on the line, or the line above, opts a site out —
      // for colours handed to a library that writes raw SVG attributes (QR
      // code, Leaflet), where var() cannot be used.
      const ln = lineOf(scan, m.index);
      const lines = src.split('\n');
      if (/check-css: allow/.test((lines[ln - 1] || '') + (lines[ln - 2] || ''))) continue;
      errors.push(`${rel(f)}:${lineOf(scan, m.index)} colour literal ${m[0]} — use a token from colors_and_type.css`);
    }
  }
  if (!isCss) continue;

  for (const m of scan.matchAll(/border-radius:\s*9{3,4}px/g)) errors.push(`${rel(f)}:${lineOf(scan, m.index)} literal pill radius — use var(--radius-pill)`);
  for (const m of scan.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g)) {
    const v = parseFloat(m[1]);
    if (v >= 10 && v <= 18) errors.push(`${rel(f)}:${lineOf(scan, m.index)} font-size ${m[1]}px — use a --text-* token`);
    else if (v !== Math.floor(v)) errors.push(`${rel(f)}:${lineOf(scan, m.index)} fractional font-size ${m[1]}px`);
  }
  for (const m of scan.matchAll(/(max|min)-width\s*:\s*(\d+)px/g)) {
    const w = +m[2];
    const ok = m[1] === 'max' ? MAX_WIDTHS.has(w) : MIN_WIDTHS.has(w);
    // Only @media preludes — a max-width on an element is layout, not a
    // breakpoint, even when it shares a line with a one-line media block.
    const at = scan.lastIndexOf('@media', m.index);
    if (at < 0 || scan.slice(at, m.index).includes('{')) continue;
    if (!ok) errors.push(`${rel(f)}:${lineOf(scan, m.index)} breakpoint ${m[1]}-width:${w}px is off the scale (see colors_and_type.css)`);
  }
  for (const m of scan.matchAll(/z-index:\s*(-?\d+)/g)) {
    // A `/* z-local */` mark on the line opts out: stacking inside an
    // `isolation:isolate` box (e.g. above Leaflet's panes) never reaches the page.
    const line = src.split('\n')[lineOf(scan, m.index) - 1] || '';
    if (line.includes('z-local')) continue;
    if (Math.abs(+m[1]) > 5) errors.push(`${rel(f)}:${lineOf(scan, m.index)} z-index:${m[1]} — use a --z-* layer token`);
  }
  for (const m of scan.matchAll(/outline:\s*(none|0)\b/g)) {
    // `/* focus-ok */` on the line: the ring is drawn elsewhere (a wrapper, or
    // a :focus-visible rule that follows). Say where in the comment.
    const line = src.split('\n')[lineOf(scan, m.index) - 1] || '';
    if (line.includes('focus-ok')) continue;
    (STRICT_OUTLINE ? errors : warnings).push(`${rel(f)}:${lineOf(scan, m.index)} outline:none — keyboard focus must stay visible (:focus-visible ring)`);
  }
  for (const m of scan.matchAll(/transition:[^;}]*/g)) {
    for (const d of m[0].matchAll(/\.\d+s\b/g)) {
      if (!DURATIONS.has(d[0]) && parseFloat(d[0]) < 0.4) warnings.push(`${rel(f)}:${lineOf(scan, m.index)} transition ${d[0]} — use --dur-fast/base/slow`);
    }
  }
}

for (const name of used.keys()) {
  if (!definedAnywhere.has(name)) errors.push(`var(${name}) is used but never defined`);
}
for (const name of defined) {
  if (!used.has(name) && !['--text-page-title'].includes(name)) warnings.push(`token ${name} is defined in colors_and_type.css but never used`);
}

for (const w of warnings) console.warn('warn ', w);
for (const e of errors) console.error('error', e);
console.log(`check-css: ${errors.length} error(s), ${warnings.length} warning(s) across ${files.length} files`);
process.exit(errors.length ? 1 : 0);

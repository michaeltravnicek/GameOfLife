/**
 * Build-time image optimizer.
 *
 * Reads the large source originals from `image-src/` (which is NOT served by
 * Vite, so the multi-MB JPEG/PNG never ship) and writes compressed WebP into
 * `public/img/` (git-ignored, regenerated on every build via the `images` /
 * `prebuild` / `predev` npm scripts).
 *
 * Output per source file:
 *   gallery/<name>.jpg  -> img/<name>.webp          decorative full-screen bg (mid)
 *                          img/<name>-mobile.webp   phones (small + heavy compression)
 *                          img/<name>-desktop.webp  large screens (lighter compression)
 *   assets/<name>.png   -> img/<name>.webp          tiling grain texture (downscaled)
 *   logos/<name>.png    -> img/<name>.webp          logo/stamp (downscaled, alpha kept)
 *
 * Idempotent: skips an output that is already newer than its source.
 */
import { readdir, mkdir, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(root, 'image-src');
const OUT = path.join(root, 'public', 'img');

// Photographic backgrounds: one mid file for decorative stages, plus a
// mobile/desktop pair for the prominent/interactive surfaces.
const GALLERY_VARIANTS = [
  // Decorative full-screen page backgrounds — always behind dark overlays +
  // grain, so a small, heavily-compressed file is invisible-quality but light
  // enough to also serve to phones.
  { suffix: '', width: 1100, quality: 50 },
  { suffix: '-mobile', width: 768, quality: 52 },
  { suffix: '-desktop', width: 1600, quality: 70 },
];

async function isStale(src, out) {
  if (!existsSync(out)) return true;
  const [s, o] = await Promise.all([stat(src), stat(out)]);
  return s.mtimeMs > o.mtimeMs;
}

async function emit(src, out, build) {
  if (!(await isStale(src, out))) return false;
  await build();
  return true;
}

async function processGallery(dir) {
  const files = (await readdir(dir)).filter((f) => /\.(jpe?g|png)$/i.test(f));
  for (const f of files) {
    const src = path.join(dir, f);
    const base = f.replace(/\.[^.]+$/, '');
    for (const v of GALLERY_VARIANTS) {
      const out = path.join(OUT, `${base}${v.suffix}.webp`);
      const made = await emit(src, out, () =>
        sharp(src)
          .rotate() // honor EXIF orientation
          .resize({ width: v.width, withoutEnlargement: true })
          .webp({ quality: v.quality })
          .toFile(out));
      if (made) console.log('  img/%s%s.webp (w%d q%d)', base, v.suffix, v.width, v.quality);
    }
  }
}

// The grain is featureless stationary noise. We sample a small native square and
// make it seamless with the OFFSET method (diagonal half-roll, then heal the
// resulting centre cross by blending the un-rolled sample over it). Unlike mirror
// tiling this leaves NO symmetry/kaleidoscope — just organic noise that wraps.
// Then we magnify it (nearest = crisp specks) and tile it at 1:1 (--tex-size = TILE).
//
// ── GRAIN KNOBS — tweak, then: rm public/img/Grain_texture_*.webp && npm run images
//   GRAIN_SCALE   grain size in px. Native specks are magnified by this factor.
//                 Higher = bigger/chunkier grain.
//   GRAIN_BLUR    softness. 0 = crisp specks; ~0.8 lightly soft; ~2 clearly fuzzy.
//   SAMPLE        native px sampled = the repeat period (= TILE / GRAIN_SCALE).
//                 Bigger = less visible repetition, larger file.
// On-screen speck size ≈ GRAIN_SCALE px. Changing GRAIN_SCALE or SAMPLE changes the
// tile size — set --tex-size to the px the script logs below.
const GRAIN_SCALE = 3;
const GRAIN_BLUR = 0;
const SAMPLE = 300;
const TILE = SAMPLE * GRAIN_SCALE; // seamless (no mirror), display at 1:1

// Diagonal half-roll: moves the wrap discontinuity from the tile edges to the
// centre, so the new edges are continuous (= seamless), leaving a centre cross.
async function rollDiag(buf, S) {
  const k = Math.floor(S / 2);
  const [hl, hr] = await Promise.all([
    sharp(buf).extract({ left: k, top: 0, width: S - k, height: S }).toBuffer(),
    sharp(buf).extract({ left: 0, top: 0, width: k, height: S }).toBuffer(),
  ]);
  const rx = await sharp({ create: { width: S, height: S, channels: 3, background: '#000' } })
    .composite([{ input: hl, left: 0, top: 0 }, { input: hr, left: S - k, top: 0 }])
    .png().toBuffer();
  const [vt, vb] = await Promise.all([
    sharp(rx).extract({ left: 0, top: k, width: S, height: S - k }).toBuffer(),
    sharp(rx).extract({ left: 0, top: 0, width: S, height: k }).toBuffer(),
  ]);
  return sharp({ create: { width: S, height: S, channels: 3, background: '#000' } })
    .composite([{ input: vt, left: 0, top: 0 }, { input: vb, left: 0, top: S - k }])
    .png().toBuffer();
}

// Feathered cross mask: opaque along the centre lines (where rollDiag's seam is),
// transparent at the edges (where we must keep the seamless rolled pixels).
function crossMask(S) {
  const c = S / 2, two = 2 * (S / 9) ** 2;
  const m = Buffer.alloc(S * S);
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const v = Math.max(Math.exp(-((x - c) ** 2) / two), Math.exp(-((y - c) ** 2) / two));
      m[y * S + x] = Math.round(v * 255);
    }
  }
  return m;
}

// Stable per-file 0/90/180/270 rotation so the colour variants don't share an
// orientation (and rebuilds stay deterministic).
function rot90(name) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (h % 4) * 90;
}

async function processTextures(dir) {
  const files = (await readdir(dir)).filter((f) => /\.png$/i.test(f));
  const S = SAMPLE;
  const mask = crossMask(S);
  for (const f of files) {
    const src = path.join(dir, f);
    const out = path.join(OUT, `${f.replace(/\.png$/i, '')}.webp`);
    const made = await emit(src, out, async () => {
      const sample = await sharp(src)
        .extract({ left: 200, top: 200, width: S, height: S })
        .removeAlpha()
        .png().toBuffer();
      // make seamless: heal the rolled centre cross with the un-rolled sample
      const rolled = await rollDiag(sample, S);
      const patch = await sharp(sample)
        .joinChannel(mask, { raw: { width: S, height: S, channels: 1 } })
        .png().toBuffer();
      const seamless = await sharp(rolled)
        .composite([{ input: patch, left: 0, top: 0 }])
        .png().toBuffer();
      // magnify (crisp specks) → soften → per-file rotate (still seamless)
      let pipe = sharp(seamless).resize({ width: TILE, height: TILE, kernel: 'nearest' });
      if (GRAIN_BLUR > 0) pipe = pipe.blur(GRAIN_BLUR);
      const rot = rot90(f);
      if (rot) pipe = pipe.rotate(rot);
      await pipe.webp({ quality: 72 }).toFile(out);
    });
    if (made) console.log('  img/%s.webp (seamless %dpx tile)', f.replace(/\.png$/i, ''), TILE);
  }
}

// Logos/stamps render at <=~260px; 600px keeps them crisp with alpha.
async function processLogos(dir) {
  const files = (await readdir(dir)).filter((f) => /\.png$/i.test(f));
  for (const f of files) {
    const src = path.join(dir, f);
    const out = path.join(OUT, `${f.replace(/\.png$/i, '')}.webp`);
    const made = await emit(src, out, () =>
      sharp(src)
        .resize({ width: 600, withoutEnlargement: true })
        .webp({ quality: 82 })
        .toFile(out));
    if (made) console.log('  img/%s.webp (logo)', f.replace(/\.png$/i, ''));
  }
}

async function main() {
  if (!existsSync(SRC)) {
    console.log('[optimize-images] no image-src/ — nothing to do');
    return;
  }
  await mkdir(OUT, { recursive: true });
  console.log('[optimize-images] generating WebP into public/img/ …');
  await processGallery(path.join(SRC, 'gallery'));
  await processTextures(path.join(SRC, 'assets'));
  await processLogos(path.join(SRC, 'logos'));
  console.log('[optimize-images] done');
}

main().catch((err) => {
  console.error('[optimize-images] failed:', err);
  process.exit(1);
});

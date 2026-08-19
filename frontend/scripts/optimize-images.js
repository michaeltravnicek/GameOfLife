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
// `height` matters as much as `width`. Capping only the width bounds nothing on
// a portrait photo: the gallery shoots 3:4, so a 1920-wide export came out
// 1920x2879 — 5.5 megapixels, 1.5 MB, the four heaviest files on the site. The
// cap below applies to whichever side is longer (`fit: 'inside'`), which takes
// that same file to 1280x1920 and 545 kB at *unchanged* quality. Dropping
// quality instead barely helped (q78→q62 saved 200 kB and looked worse) — the
// pixel count was the problem, not the compression.
const GALLERY_VARIANTS = [
  // Decorative full-screen page backgrounds — always behind dark overlays +
  // grain, so a small, heavily-compressed file is invisible-quality but light
  // enough to also serve to phones.
  { suffix: '', width: 1100, height: 1100, quality: 50 },
  { suffix: '-mobile', width: 768, height: 768, quality: 52 },
  { suffix: '-desktop', width: 1920, height: 1920, quality: 78 },
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
          .resize({
            width: v.width, height: v.height,
            // 'inside' = fit within the box, keep aspect ratio, never crop.
            fit: 'inside', withoutEnlargement: true,
          })
          .webp({ quality: v.quality })
          .toFile(out));
      if (made) console.log('  img/%s%s.webp (w%d q%d)', base, v.suffix, v.width, v.quality);
    }
  }
}

// The grain is featureless stationary noise. We sample a native square, FLATTEN it
// (see below), and make it seamless with the OFFSET method (diagonal half-roll, then
// heal the resulting centre cross by blending the un-rolled sample over it). Unlike
// mirror tiling this leaves NO symmetry/kaleidoscope — just organic noise that wraps.
//
// ── WHY THE TILE LOOKS LIKE A REPEATING PATTERN, AND WHAT FIXES IT
// A seamless tile still reads as a "pattern" on a large surface, because the eye does
// not match up individual specks — it matches up LANDMARKS: the slow light/dark
// blotches the source photo inherited from its lighting. There are two ways to fight
// that, and only one of them is free:
//   1. period — the old 240px tile covered a 1440x900 board with 24 copies of the
//      same landmark. At 1200px it is 2, which the eye does not pair up.
//   2. landmarks — high-passing the sample removes the blotches outright. It also
//      visibly changes the texture (it is the only step here that alters the source
//      pixels) and it wrecks the compression, so FLATTEN_SIGMA ships at 0. The knob
//      is kept for the case where period alone is not enough.
//
// ── THE ONE TRICK THAT MAKES THIS AFFORDABLE
// The tile is stored at native resolution and DISPLAYED SMALLER (TEX_SIZE < SAMPLE),
// so the browser does the downscale at paint time, for free. Doing that same
// downscale here instead costs 4-7x the bytes: resampling turns the source's
// quantised values into a continuum and the lossless predictors fall apart
// (1500px native = 144 kB; the same tile resampled to 1200px = 586-1061 kB).
// The downscale is not just for weight — it is what gives the grain its fineness.
// The source specks are soft and ~3px wide; shown 1:1 they read as coarse and
// gritty (sharpness metric 9.4 vs the 3.6 this site has always had).
//
// ── GRAIN KNOBS — tweak, then: rm public/img/Grain_texture_*.webp && npm run images
//   SAMPLE         native px sampled = the tile, stored as-is. Bigger = longer
//                  repeat, larger file: 1200 -> 87 kB, 1500 -> 144 kB, 1800 -> 209 kB.
//                  Capped by the source: 2000px minus the extract offset.
//   TEX_SIZE       px the tile is DISPLAYED at = the on-screen repeat period. Must
//                  match --tex-size in styles/colors_and_type.css — the script
//                  prints a reminder. TEX_SIZE/SAMPLE is the grain-fineness knob:
//                  0.8 is what this site has always rendered at.
//   FLATTEN_SIGMA  0 = ship the source pixels untouched. Above 0 it high-passes the
//                  sample (detail finer than this survives, coarser is flattened
//                  away), which hides the repeat further but flattens the texture's
//                  depth and multiplies the file size.
//   GRAIN_GAIN     contrast of the grain, 1 = untouched. Below 1 fades it toward
//                  flat; only meaningful together with FLATTEN_SIGMA.
//   GRAIN_BLUR     softness. 0 = as-is. Note blur() does not wrap — see below.
const SAMPLE = 1000;
const TEX_SIZE = 800;
const FLATTEN_SIGMA = 0;
const GRAIN_GAIN = 1;
const GRAIN_BLUR = 0;
const TILE = SAMPLE; // stored at native res; CSS shrinks it to TEX_SIZE

function channelMeans(raw) {
  return [0, 1, 2].map((c) => {
    let sum = 0;
    for (let i = c; i < raw.length; i += 3) sum += raw[i];
    return sum / (raw.length / 3);
  });
}

// High-pass: subtract the local mean and add the global mean back, per channel.
// Kills the slow lighting drift of the source photo (the landmarks that make tiling
// visible) while leaving the overall colour untouched. OFF by default — it is the
// only step that rewrites the source pixels, and it costs both the texture's depth
// and a multiple of the file size. heal() needs the means either way, so when it is
// off we still measure them and return the buffer unchanged.
async function flatten(buf, S, sigma, gain) {
  if (sigma <= 0 && gain === 1) {
    return { buf, mean: channelMeans(await sharp(buf).removeAlpha().raw().toBuffer()) };
  }
  const [hi, lo] = await Promise.all([
    sharp(buf).raw().toBuffer(),
    sharp(buf).blur(sigma > 0 ? sigma : 0.3).raw().toBuffer(),
  ]);
  const mean = channelMeans(hi);
  const out = Buffer.alloc(hi.length);
  for (let i = 0; i < hi.length; i++) {
    out[i] = Math.max(0, Math.min(255, Math.round((hi[i] - lo[i]) * gain + mean[i % 3])));
  }
  // mean is the flattened image's mean too (the residual is zero-mean), so heal()
  // can centre on it as well.
  return { buf: await sharp(out, { raw: { width: S, height: S, channels: 3 } }).png().toBuffer(), mean };
}

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

// Feathered cross mask: 1 along the centre lines (where rollDiag's seam is), 0 at
// the edges (where we must keep the seamless rolled pixels). Float, not a byte
// buffer, because heal() needs it in quadrature — see below.
//
// The profile is a raised cosine with COMPACT SUPPORT: exactly 0 beyond HEAL_BAND/2
// from a centre line. A Gaussian (what this used to be, sigma = S/9) never quite
// reaches 0, so heal() rewrote nearly every pixel in the tile with float arithmetic —
// which by itself took the lossless file from 144 kB to 377 kB. With a bounded band
// only the band is touched and the rest of the tile stays byte-identical to the
// source. Widen HEAL_BAND if a soft line ever shows down the middle of the tile;
// that is the trade being made here.
const HEAL_BAND = 160;
function crossMask(S) {
  const c = S / 2, h = HEAL_BAND / 2;
  const m = new Float32Array(S * S);
  const prof = (d) => (d >= h ? 0 : 0.5 * (1 + Math.cos((Math.PI * d) / h)));
  for (let y = 0; y < S; y++) {
    const py = prof(Math.abs(y - c));
    for (let x = 0; x < S; x++) {
      m[y * S + x] = Math.max(prof(Math.abs(x - c)), py);
    }
  }
  return m;
}

// Heal the rolled centre cross by mixing the un-rolled sample back in along it.
//
// The mix is in QUADRATURE (weights m and sqrt(1-m^2), not m and 1-m) and runs on
// the mean-centred residual. A plain alpha blend of two independent noise fields
// drops the variance where it is half-and-half — std falls to 0.71 of full — so the
// tile ends up with a soft low-contrast cross through it, ~S/9 wide. That cross is
// then repeated by every tile, which is precisely the "pattern" we are trying to
// get rid of. Quadrature weights satisfy m^2 + (1-m^2) = 1, which keeps the variance
// identical at every pixel, so the heal leaves no visible mark at all.
function heal(sampleRaw, rolledRaw, mask, mean) {
  const out = Buffer.alloc(sampleRaw.length);
  for (let i = 0; i < sampleRaw.length; i++) {
    const m = mask[(i / 3) | 0];
    if (m === 0) { out[i] = rolledRaw[i]; continue; } // outside the band: keep the byte
    const mu = mean[i % 3];
    const v = (sampleRaw[i] - mu) * m + (rolledRaw[i] - mu) * Math.sqrt(1 - m * m);
    out[i] = Math.max(0, Math.min(255, Math.round(v + mu)));
  }
  return out;
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
      const raw = await sharp(src)
        .extract({ left: 200, top: 200, width: S, height: S })
        .removeAlpha()
        .png().toBuffer();
      // flatten FIRST: the high-pass must not see the wrap seam we create below
      const { buf: sample, mean } = await flatten(raw, S, FLATTEN_SIGMA, GRAIN_GAIN);
      // make seamless: heal the rolled centre cross with the un-rolled sample
      const rolled = await rollDiag(sample, S);
      // removeAlpha is load-bearing: sharp's composite() hands back 4 channels, and
      // heal() indexes the buffer as RGB triples.
      const [sampleRaw, rolledRaw] = await Promise.all([
        sharp(sample).removeAlpha().raw().toBuffer(),
        sharp(rolled).removeAlpha().raw().toBuffer(),
      ]);
      const seamless = await sharp(heal(sampleRaw, rolledRaw, mask, mean),
        { raw: { width: S, height: S, channels: 3 } }).png().toBuffer();
      // soften → per-file rotate (still seamless)
      let pipe = sharp(seamless);
      // NB: blur() does not wrap, so any value here re-opens the seam. Left as a knob
      // only because 0 is the shipping value; soften with GRAIN_GAIN instead.
      if (GRAIN_BLUR > 0) pipe = pipe.blur(GRAIN_BLUR);
      const rot = rot90(f);
      if (rot) pipe = pipe.rotate(rot);
      // LOSSLESS, and for once that is also the CHEAP option: at 1500px this tile is
      // 144 kB lossless against 313 kB at q72 and 621 kB at q90. Grain is the lossy
      // encoder's worst case — it is all high-frequency detail, so every block spends
      // its bit budget and still comes out blotchy (the discarded detail leaves the
      // block DC behind, which reads as exactly the kind of landmark that gives the
      // tiling away). To cut page weight, lower SAMPLE, not the encoder.
      await pipe.webp({ lossless: true, effort: 6 }).toFile(out);
    });
    if (made) console.log('  img/%s.webp (seamless %dpx tile)', f.replace(/\.png$/i, ''), TILE);
  }
  if (files.length) {
    console.log('  → tiles are %dpx; CSS --tex-size must be %dpx (speck %spx, repeat %dpx)',
      TILE, TEX_SIZE, (TEX_SIZE / SAMPLE).toFixed(1), TEX_SIZE);
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

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

// Textures tile at --tex-size (400px), so 800px is plenty even on retina.
async function processTextures(dir) {
  const files = (await readdir(dir)).filter((f) => /\.png$/i.test(f));
  for (const f of files) {
    const src = path.join(dir, f);
    const out = path.join(OUT, `${f.replace(/\.png$/i, '')}.webp`);
    const made = await emit(src, out, () =>
      sharp(src)
        .resize({ width: 800, withoutEnlargement: true })
        .webp({ quality: 82 }) // keeps alpha automatically
        .toFile(out));
    if (made) console.log('  img/%s.webp (texture)', f.replace(/\.png$/i, ''));
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

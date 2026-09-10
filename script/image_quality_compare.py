"""Render the same image at several pipeline settings so the choice is made by eye.

The numbers in leaderboard/image_utils.py (max dimensions, WEBP_QUALITY, the
mobile variant's width and quality) trade file size against how the picture
actually looks. A size table tells you the first half; only looking at the
result tells you the second.

What makes this comparison honest is the last step: every candidate is scaled to
the SAME display width before cropping. That is what a browser does — a 1200 px
image filling a 1600 px column is upscaled, and the softness that follows is the
whole reason to consider larger dimensions. Comparing the renders at their own
native sizes would flatter the small ones and prove nothing.

Usage
-----
    python3 script/image_quality_compare.py                  # defaults, from prod
    python3 script/image_quality_compare.py --source path/to/photo.jpg
    python3 script/image_quality_compare.py --display 2400   # simulate a wider column

Writes into script/image_compare_out/ (gitignored):

    full/    every candidate at full size — open two and flip between them
    sheet_*.png  side-by-side 1:1 crops at a common display size, labelled
    report.txt   the size table, same as printed

Nothing here imports Django; it is a standalone measuring tool, deliberately
separate from the pipeline it is measuring.
"""
import argparse
import io
import os
import sys
import urllib.request

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    sys.exit("Pillow is required:  .venv/bin/python script/image_quality_compare.py")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "image_compare_out")
CACHE_DIR = os.path.join(OUT_DIR, ".source-cache")

# Two real files from the live site: a detailed landscape photo (the worst case
# for compression) and a flat logo with transparency (the best case). They behave
# so differently that a setting good for one can be wrong for the other.
DEFAULT_SOURCES = [
    ("photo", "https://www.gameofyolo.com/media/event_images/Lysa_hora-113.jpg"),
    ("logo",
     "https://www.gameofyolo.com/media/event_logos/GOL_Karaoke_transparent_jotap3a.png"),
]

# (label, max_side, quality). The first entry is what the pipeline does today, so
# every sheet has the current state as its reference point.
PHOTO_LADDER = [
    ("current 1200 q80", 1200, 80),
    ("1600 q80", 1600, 80),
    ("2000 q80", 2000, 80),
    ("2000 q85", 2000, 85),
    ("2400 q80", 2400, 80),
]
LOGO_LADDER = [
    ("current 512 q85", 512, 85),
    ("768 q85", 768, 85),
    ("1024 q85", 1024, 85),
    ("1400 q85", 1400, 85),
]
# The mobile sibling (image_utils.make_webp_variant). Phones get this, not the
# full render, so a desktop-only improvement is invisible to most visitors.
MOBILE_LADDER = [
    ("current 768 q55", 768, 55),
    ("768 q65", 768, 65),
    ("900 q60", 900, 60),
    ("1080 q60", 1080, 60),
    ("1080 q70", 1080, 70),
]

WEBP_METHOD = 4  # matches image_utils.WEBP_METHOD


def fetch(name, source):
    """Return raw bytes for a URL or path, caching downloads between runs."""
    if os.path.exists(source):
        with open(source, "rb") as fh:
            return fh.read()

    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = os.path.join(CACHE_DIR, name + os.path.splitext(source)[1])
    if os.path.exists(cached):
        with open(cached, "rb") as fh:
            return fh.read()

    print(f"  stahuji {source}")
    # Cloudflare's managed rules 403 the default "Python-urllib/x.y" agent, so
    # say who we are in a shape the edge does not treat as a scraper.
    req = urllib.request.Request(source, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(cached, "wb") as fh:
        fh.write(data)
    return data


def encode(img, max_side, quality, keep_alpha):
    """Resize + WebP-encode exactly the way process_upload would. Returns bytes."""
    out = img.copy()
    # Same call shape as image_utils: cap the long edge, let tall images stay tall.
    out.thumbnail((max_side, max_side * 6), Image.LANCZOS)
    buf = io.BytesIO()
    if not keep_alpha:
        out = out.convert("RGB")
    out.save(buf, "WEBP", quality=quality, method=WEBP_METHOD)
    return buf.getvalue()


def load_font(size):
    """A legible label font, falling back to PIL's bitmap default."""
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def crop_at_display_size(data, display_w, box_frac, keep_alpha):
    """Decode a candidate, scale it to the display width, crop the same region.

    box_frac is (left, top, right, bottom) as fractions of the image, so every
    candidate shows the *same part of the picture* regardless of its own
    resolution — and at the size a visitor would actually see it.
    """
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGBA" if keep_alpha else "RGB")

    scale = display_w / img.width
    img = img.resize(
        (display_w, max(1, round(img.height * scale))), Image.LANCZOS
    )

    left, top, right, bottom = box_frac
    return img.crop((
        round(left * img.width), round(top * img.height),
        round(right * img.width), round(bottom * img.height),
    ))


def build_sheet(title, entries, display_w, box_frac, keep_alpha, path):
    """Stitch labelled crops into one image, side by side."""
    crops = [(label, crop_at_display_size(data, display_w, box_frac, keep_alpha),
              len(data)) for label, data in entries]

    pad, bar = 12, 46
    tile_w = max(c.width for _, c, _ in crops)
    tile_h = max(c.height for _, c, _ in crops)
    sheet_w = len(crops) * tile_w + (len(crops) + 1) * pad
    sheet_h = tile_h + bar + 2 * pad

    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    font = load_font(19)
    small = load_font(15)

    for i, (label, crop, nbytes) in enumerate(crops):
        x = pad + i * (tile_w + pad)
        if crop.mode == "RGBA":
            # Flatten onto a mid grey so transparency is visible but not confusing.
            plate = Image.new("RGB", crop.size, (128, 128, 132))
            plate.paste(crop, mask=crop.split()[-1])
            crop = plate
        sheet.paste(crop, (x, pad))
        draw.text((x, pad + tile_h + 8), label, font=font, fill=(245, 241, 212))
        draw.text((x, pad + tile_h + 28), f"{nbytes / 1024:.0f} kB",
                  font=small, fill=(225, 84, 99))

    sheet.save(path, "PNG")
    print(f"  → {os.path.relpath(path)}  ({title})")


def run_ladder(name, raw, ladder, display_w, box_frac, keep_alpha, lines):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    src = src.convert("RGBA" if keep_alpha else "RGB")

    lines.append(f"\n{name}: {src.width}x{src.height}, zdroj {len(raw) / 1024:.0f} kB")
    lines.append(f"{'nastavení':<20}{'rozměr':>13}{'velikost':>12}{'vs dnes':>10}")

    entries, baseline = [], None
    full_dir = os.path.join(OUT_DIR, "full")
    os.makedirs(full_dir, exist_ok=True)

    for label, max_side, quality in ladder:
        data = encode(src, max_side, quality, keep_alpha)
        if baseline is None:
            baseline = len(data)
        with Image.open(io.BytesIO(data)) as probe:
            dims = f"{probe.width}x{probe.height}"

        ratio = len(data) / baseline
        lines.append(f"{label:<20}{dims:>13}{len(data) / 1024:>10.0f} kB"
                     f"{ratio:>9.1f}x")

        slug = label.replace(" ", "_")
        with open(os.path.join(full_dir, f"{name}__{slug}.webp"), "wb") as fh:
            fh.write(data)
        entries.append((label, data))

    build_sheet(name, entries, display_w, box_frac, keep_alpha,
                os.path.join(OUT_DIR, f"sheet_{name}.png"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", action="append", default=[],
                    help="Extra image (path or URL). Repeatable.")
    ap.add_argument("--display", type=int, default=1600,
                    help="Column width in CSS px to simulate (default 1600).")
    ap.add_argument("--zoom", type=float, default=0.30,
                    help="Fraction of the frame the crop covers (default 0.30).")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    # A centre-ish window, offset upward where photo subjects usually sit.
    z = max(0.05, min(1.0, args.zoom))
    box = (0.5 - z / 2, 0.38 - z / 2, 0.5 + z / 2, 0.38 + z / 2)
    box = (box[0], max(0.0, box[1]), box[2], max(z, box[3]))

    sources = list(DEFAULT_SOURCES) + [
        (f"custom{i}", s) for i, s in enumerate(args.source, 1)
    ]

    lines = [f"Zobrazeno v šířce {args.display} px "
             f"(každý kandidát přeškálován na stejnou velikost — jako v prohlížeči)"]

    for name, source in sources:
        print(f"\n{name}:")
        try:
            raw = fetch(name, source)
        except Exception as exc:  # noqa: BLE001 — a missing source is not fatal
            print(f"  ! přeskakuji ({exc})")
            continue

        is_logo = "logo" in name
        ladder = LOGO_LADDER if is_logo else PHOTO_LADDER
        run_ladder(name, raw, ladder, args.display, box, is_logo, lines)

        if not is_logo:
            # The mobile sibling, judged at a phone's real pixel width.
            run_ladder(f"{name}_mobile", raw, MOBILE_LADDER, 1170, box, False, lines)

    report = "\n".join(lines)
    print("\n" + report)
    with open(os.path.join(OUT_DIR, "report.txt"), "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(f"\nVše v {os.path.relpath(OUT_DIR)}/")


if __name__ == "__main__":
    main()

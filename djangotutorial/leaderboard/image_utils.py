"""Utilities for resizing uploaded images to save disk space and RAM.

Phone photos are often 5-20 MB. Resizing them to reasonable dimensions
with JPEG quality 85 typically drops them to <500 KB with no visible loss
at the display sizes we use (cards, hero, avatars).
"""
import os

from PIL import Image, ImageOps

# Pre-resize guard: reject obvious junk before PIL loads the file into memory.
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# PIL's own names for the same formats (Image.format), used for the real check —
# the browser-supplied content type is only a hint and is trivially forged.
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

# Decompression-bomb ceiling. Bytes on disk say nothing about memory cost: a
# ~1 MB PNG can declare 50000x50000 px, and PIL allocates the *decoded* bitmap
# (w * h * 4 bytes ≈ 10 GB) the moment resize_image() touches it — one request
# is enough to OOM the dyno. 60 MP leaves headroom above 48 MP phone cameras
# while capping a single decode at roughly a quarter gigabyte.
MAX_IMAGE_PIXELS = 60_000_000

# Belt and braces: make PIL itself raise instead of merely warning if anything
# slips past validate_upload (e.g. an image already on disk being re-processed
# by a backfill command).
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _too_many_pixels_message():
    return (
        "Rozlišení obrázku je příliš velké "
        f"(max {MAX_IMAGE_PIXELS // 1_000_000} megapixelů)."
    )


def validate_upload(field_file):
    """Reject non-images, oversized uploads and decompression bombs.

    Raises ValueError with a user-facing (Czech) message. The stored file is
    still downscaled by ``resize_image`` on the model's ``save()`` — this only
    stops a hostile or huge upload from reaching (and exhausting) PIL.

    Order matters: the cheap byte-count checks run before the header parse, so
    a large file is rejected without ever being handed to PIL.
    """
    content_type = (getattr(field_file, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError("Nepodporovaný formát. Povolené: JPEG, PNG, WebP, GIF.")
    if (getattr(field_file, "size", 0) or 0) > MAX_UPLOAD_BYTES:
        raise ValueError("Obrázek je příliš velký (max 15 MB).")

    # Parse the header only. Image.open() is lazy — it reads enough to fill in
    # .format and .size but does not decode pixel data, so a bomb is caught
    # before any large allocation happens.
    try:
        field_file.seek(0)
        with Image.open(field_file) as img:
            image_format = img.format
            width, height = img.size
    except Image.DecompressionBombError:
        # PIL's own guard (set below to MAX_IMAGE_PIXELS) fires during open()
        # for anything above 2x the limit, before our explicit check gets to
        # run. Same rejection, but keep the specific message.
        raise ValueError(_too_many_pixels_message())
    except Exception:
        # Unreadable, truncated, or not an image at all.
        raise ValueError("Soubor není platný obrázek.")
    finally:
        # Rewind whatever we consumed; the caller still has to save this file.
        try:
            field_file.seek(0)
        except (OSError, ValueError):
            pass

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValueError("Nepodporovaný formát. Povolené: JPEG, PNG, WebP, GIF.")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(_too_many_pixels_message())


def variant_name(name, suffix="mobile", ext=".webp"):
    """Sibling filename for a generated variant: 'a/b/foo.jpg' -> 'a/b/foo.mobile.webp'."""
    base, _ = os.path.splitext(name)
    return f"{base}.{suffix}{ext}"


def variant_url(field_file, request=None, suffix="mobile"):
    """URL of an image's generated variant, or None if it hasn't been produced yet.

    Existence-checked so legacy images (before a backfill) simply fall back to the
    original instead of serving a 404 in a srcset.
    """
    if not field_file:
        return None
    path = getattr(field_file, "path", None)
    if not path or not os.path.exists(variant_name(path, suffix)):
        return None
    url = variant_name(field_file.url, suffix)
    return request.build_absolute_uri(url) if request else url


def make_webp_variant(field_file, max_width=768, quality=55, suffix="mobile"):
    """Write a small WebP sibling next to an uploaded image (for mobile srcset).

    Produces ``<name>.<suffix>.webp`` alongside the (already resized) original.
    Idempotent and best-effort: a failure here must never break a save. Pair the
    output with ``variant_name`` to build the served URL.
    """
    if not field_file:
        return
    path = getattr(field_file, "path", None)
    if not path or not os.path.exists(path):
        return
    if os.path.splitext(path)[1].lower() in VECTOR_EXTENSIONS:
        return  # SVG is already tiny and PIL can't read it
    out = variant_name(path, suffix)
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode == "P":
                # Palette images (GIF logos) keep transparency in `info`; going
                # straight to RGB would paint the transparent parts black.
                img = img.convert("RGBA" if "transparency" in img.info else "RGB")
            elif img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            # Cap width; allow tall portraits to keep their aspect ratio.
            img.thumbnail((max_width, max_width * 6), Image.LANCZOS)
            img.save(out, "WEBP", quality=quality, method=6)
    except (OSError, IOError):
        # Not an image or file is corrupt — leave it alone.
        pass


# A correctly-dimensioned file under this size isn't worth re-encoding.
RESIZE_MIN_BYTES = 500 * 1024

# Extension -> PIL format that `resize_image` may rewrite the original as. The
# stored format is always preserved: writing a resized JPEG over a .png would
# destroy the alpha channel that event logos depend on, and would leave the file
# lying about its own type.
#
# Deliberately absent:
#   .svg  vector; PIL can't read it and there is nothing to downscale.
#   .gif  palette format. A naive resize wrecks the palette, and an animation
#         would be flattened to one frame. The variant below still gives the
#         frontend a small WebP, without touching the original.
RESIZABLE_FORMATS = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
}

# Never handed to PIL at all — not an image in the raster sense.
VECTOR_EXTENSIONS = {".svg"}


def is_animated(img):
    """True for multi-frame images (animated GIF/WebP)."""
    return getattr(img, "n_frames", 1) > 1


def needs_resize(path, max_width=1200, max_height=1200):
    """True when ``resize_image`` would actually rewrite the file at `path`.

    Split out of `resize_image` so a bulk backfill can report (or dry-run) what
    it would touch without writing. Both use this, so the two can't drift.
    """
    if not path or not os.path.exists(path):
        return False
    extension = os.path.splitext(path)[1].lower()
    if extension not in RESIZABLE_FORMATS:
        return False
    try:
        with Image.open(path) as img:
            # EXIF-rotated portraits report swapped dimensions until transposed.
            img = ImageOps.exif_transpose(img)
            oversized = img.width > max_width or img.height > max_height
    except (OSError, IOError):
        return False  # not an image or corrupt — leave it alone
    # Correct dimensions but heavy on disk still earns a re-encode.
    return oversized or os.path.getsize(path) >= RESIZE_MIN_BYTES


def resize_image(field_file, max_width=1200, max_height=1200, quality=85):
    """Resize an ImageFieldFile in place. Safe to call multiple times.

    - Respects EXIF orientation (phones save photos rotated).
    - Keeps the stored format, so transparency survives (event logos are PNGs
      with alpha and must stay that way).
    - Leaves alone anything it cannot rewrite safely: SVG, GIF, animations, and
      unknown extensions. See RESIZABLE_FORMATS.
    """
    if not field_file:
        return
    path = getattr(field_file, "path", None)
    if not path or not os.path.exists(path):
        return
    target_format = RESIZABLE_FORMATS.get(os.path.splitext(path)[1].lower())
    if target_format is None:
        return
    if not needs_resize(path, max_width, max_height):
        return

    try:
        with Image.open(path) as img:
            if is_animated(img):
                return  # a resize would flatten it to a single frame
            # Fix orientation from EXIF (phone photos)
            img = ImageOps.exif_transpose(img)

            img.thumbnail((max_width, max_height), Image.LANCZOS)

            if target_format == "JPEG":
                # JPEG has no alpha channel; flatten whatever mode we're in.
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(path, "JPEG", quality=quality, optimize=True)
            elif target_format == "PNG":
                img.save(path, "PNG", optimize=True)
            else:  # WEBP — keeps RGBA, so nothing to convert
                img.save(path, "WEBP", quality=quality, method=6)
    except (OSError, IOError):
        # Not an image or file is corrupt — leave it alone
        pass

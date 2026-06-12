"""Utilities for resizing uploaded images to save disk space and RAM.

Phone photos are often 5-20 MB. Resizing them to reasonable dimensions
with JPEG quality 85 typically drops them to <500 KB with no visible loss
at the display sizes we use (cards, hero, avatars).
"""
import os

from PIL import Image, ImageOps

# Pre-resize guard: reject obvious junk before PIL loads the file into memory.
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def validate_upload(field_file):
    """Reject non-images and oversized uploads before they're saved/resized.

    Raises ValueError with a user-facing message. The stored file is still
    downscaled by ``resize_image`` on the model's ``save()`` — this only stops
    a huge or wrong-type upload from reaching (and exhausting) PIL.
    """
    content_type = (getattr(field_file, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError("Nepodporovaný formát. Povolené: JPEG, PNG, WebP, GIF.")
    if (getattr(field_file, "size", 0) or 0) > MAX_UPLOAD_BYTES:
        raise ValueError("Obrázek je příliš velký (max 15 MB).")


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
    out = variant_name(path, suffix)
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            # Cap width; allow tall portraits to keep their aspect ratio.
            img.thumbnail((max_width, max_width * 6), Image.LANCZOS)
            img.save(out, "WEBP", quality=quality, method=6)
    except (OSError, IOError):
        # Not an image or file is corrupt — leave it alone.
        pass


def resize_image(field_file, max_width=1200, max_height=1200, quality=85):
    """Resize an ImageFieldFile in place. Safe to call multiple times.

    - Respects EXIF orientation (phones save photos rotated).
    - Converts to RGB if needed (PNG with alpha is converted to RGB for JPEG).
    - Skips if the file doesn't exist or isn't an image.
    """
    if not field_file:
        return
    path = getattr(field_file, "path", None)
    if not path or not os.path.exists(path):
        return

    try:
        with Image.open(path) as img:
            # Fix orientation from EXIF (phone photos)
            img = ImageOps.exif_transpose(img)

            # Skip if already small enough
            if img.width <= max_width and img.height <= max_height:
                # Still re-save as JPEG if original is large on disk
                if os.path.getsize(path) < 500 * 1024:
                    return

            img.thumbnail((max_width, max_height), Image.LANCZOS)

            # JPEG doesn't support alpha; convert if needed
            ext = os.path.splitext(path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(path, "JPEG", quality=quality, optimize=True)
            elif ext == ".png":
                img.save(path, "PNG", optimize=True)
            else:
                # Force everything else to JPEG to save space
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(path, "JPEG", quality=quality, optimize=True)
    except (OSError, IOError):
        # Not an image or file is corrupt — leave it alone
        pass

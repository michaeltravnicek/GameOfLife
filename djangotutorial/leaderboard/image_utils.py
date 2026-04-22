"""Utilities for resizing uploaded images to save disk space and RAM.

Phone photos are often 5-20 MB. Resizing them to reasonable dimensions
with JPEG quality 85 typically drops them to <500 KB with no visible loss
at the display sizes we use (cards, hero, avatars).
"""
import os

from PIL import Image, ImageOps


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

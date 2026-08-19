"""Validating, converting and downscaling uploaded images.

Every upload is stored as WebP, downscaled to the limits its model asks for and
squeezed under a byte cap. Phone photos arrive at 5-20 MB and leave at a few
hundred kB with no visible loss at the sizes the site displays them.

Two entry points matter:

    validate_upload(f)   -- reject junk before PIL ever decodes it (call at the
                            API boundary, on anything user-supplied)
    process_upload(f, w, h, cap)
                         -- re-encode what was stored; returns the new storage
                            key, which the caller MUST persist on the model

Everything is storage-abstracted (``.storage`` + ``.name``, never ``.path``), so
the same code serves the local filesystem and the R2 bucket.
"""
import errno
import io
import logging
import os
import tempfile
import threading
import time
from contextlib import contextmanager

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, ImageSequence

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # pragma: no cover — Windows; the in-process fallback covers it
    fcntl = None

# Pre-resize guard: reject obvious junk before PIL loads the file into memory.
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# PIL's own names for the same formats (Image.format), used for the real check —
# the browser-supplied content type is only a hint and is trivially forged.
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}

# One limit, every format, no exceptions -- a user should never have to know that
# their PNG is judged differently from their JPEG. Both knobs are settings, so
# they can be moved from Render's environment without a deploy:
#
#   IMAGE_MAX_UPLOAD_MB    file size accepted from the browser   (default 15)
#   IMAGE_MAX_MEGAPIXELS   declared resolution accepted          (default 30)
#
# They measure different dangers and you need both. Bytes bound the network and
# the disk; pixels bound RAM, and the two are barely related -- a 0.1 MB PNG can
# declare 28 MP and cost ~150 MB the moment it is decoded. Dropping the pixel
# limit because "15 MB is surely enough" is how the instance gets OOM-killed by
# a file that fits comfortably under the byte limit.
DEFAULT_MAX_UPLOAD_MB = 15
# 24 MP is where the memory budget lands, measured with imagelab/07_memory.py.
#
# The worst case is one decode of a PNG at the limit WITH AN ALPHA CHANNEL --
# the alpha matters and was missed at first: PNG cannot be decoded at reduced
# scale the way JPEG can, and dropping a useless alpha means both the RGBA and
# the RGB raster are live at once. That is +94 MB over the same image without
# alpha, and it is not an exotic file: it is every screenshot and every logo
# exported from Figma.
#
# Only one image decodes at a time on the whole instance (see the decode slot
# below), so the budget is peak + the other workers sitting at their ~60 MB
# floor. On 512 MB with three workers:
#
#   MP    peak     3 workers   spare over the 60 MB safety margin
#   30    ~350 MB   470 MB     none — do not
#   24    286 MB    406 MB     46 MB   ← default
#   20    242 MB    362 MB     90 MB
#   16    207 MB    327 MB     125 MB
#
# 24 MP is 6000x4000 — a full-frame camera's native resolution, and far above
# what a phone produces. The 15 MB byte limit turns away most bigger files
# anyway; this is the guard for the small-file-huge-canvas case that the byte
# limit cannot see.
DEFAULT_MAX_MEGAPIXELS = 24


def max_upload_bytes():
    """Largest file accepted from the browser, in bytes. Uniform across formats."""
    from django.conf import settings
    return int(getattr(settings, "IMAGE_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)) * 1024 * 1024


def max_image_pixels():
    """Largest declared resolution accepted, in pixels. Uniform across formats."""
    from django.conf import settings
    return int(getattr(settings, "IMAGE_MAX_MEGAPIXELS",
                       DEFAULT_MAX_MEGAPIXELS)) * 1_000_000


# Kept as module constants for the PIL guard below and for readable test fixtures;
# the functions above are what the checks actually consult.
MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_MB * 1024 * 1024

# Decompression-bomb ceiling. Bytes on disk say nothing about memory cost: a
# ~1 MB PNG can declare 50000x50000 px, and PIL allocates the *decoded* bitmap
# (w * h * 4 bytes) the moment process_upload() touches it — one request is enough
# to OOM the dyno.
#
# Sized against the 512 MB instance, measured rather than guessed: an idle worker
# sits at ~60 MB RSS, so the decode budget is what is left of 512 once the other
# workers are counted. Only one decode runs at a time instance-wide (decode slot
# below), so it is one peak, not one per worker -- see the table above.
#
# The cost of this number: a phone shooting at its full 48 MP sensor resolution
# is now rejected. Most phones bin down to 12 MP by default, and the 15 MB
# MAX_UPLOAD_BYTES already turns away most true 48 MP files, so this bites
# rarely.
#
# The same ceiling for every format, but the cost behind it is not the same.
# `_prepare_still` runs `Image.draft()`, which asks the JPEG decoder for a 1/2 to
# 1/8 scale image directly, so a 28 MP JPEG never materialises at full size and
# costs ~40 MB. PNG and WebP have no equivalent: every declared pixel becomes
# three bytes of RAM, and the same 28 MP costs ~150 MB.
#
# That gap is handled by the decode slot below rather than by a lower limit for PNG,
# so the rule stays one number the user can understand.
#
# Numbers from imagelab/07_memory.py — re-run it rather than reasoning about any
# change to them.
MAX_IMAGE_PIXELS = DEFAULT_MAX_MEGAPIXELS * 1_000_000

# Belt and braces: make PIL itself raise instead of merely warning if anything
# slips past validate_upload (e.g. an image already on disk being re-processed
# by a backfill command).
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _too_many_pixels_message():
    return (
        "Rozlišení obrázku je příliš velké "
        f"(max {max_image_pixels() // 1_000_000} megapixelů)."
    )


def validate_upload(field_file):
    """Reject non-images, oversized uploads and decompression bombs.

    Raises ValueError with a user-facing (Czech) message. The stored file is
    still re-encoded by ``process_upload`` on the model's ``save()`` — this only
    stops a hostile or huge upload from reaching (and exhausting) PIL.

    Order matters: the cheap byte-count checks run before the header parse, so
    a large file is rejected without ever being handed to PIL.
    """
    content_type = (getattr(field_file, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError("Nepodporovaný formát. Povolené: JPEG, PNG, WebP, GIF.")
    limit = max_upload_bytes()
    if (getattr(field_file, "size", 0) or 0) > limit:
        raise ValueError(f"Obrázek je příliš velký (max {limit // (1024 * 1024)} MB).")

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
    if width * height > max_image_pixels():
        raise ValueError(_too_many_pixels_message())


def variant_name(name, suffix="mobile", ext=".webp"):
    """Sibling filename for a generated variant: 'a/b/foo.jpg' -> 'a/b/foo.mobile.webp'."""
    base, _ = os.path.splitext(name)
    return f"{base}.{suffix}{ext}"


def _read_bytes(field_file):
    """Whole file as bytes via the storage API, or None if unreadable/missing.

    Storage-abstracted (``field_file.storage``) so this works identically for the
    local filesystem and remote object storage (S3/R2), neither of which is
    assumed to expose a local ``.path``.
    """
    if not field_file or not getattr(field_file, "name", None):
        return None
    try:
        with field_file.storage.open(field_file.name, "rb") as f:
            return f.read()
    except (OSError, IOError):
        return None


def _overwrite(field_file, name, data):
    """Replace the object stored at exactly ``name`` with ``data``.

    ``Storage.save`` picks a fresh, non-colliding name, so a plain save would not
    overwrite — delete first, then save the exact key. On the local filesystem
    this reproduces the previous in-place rewrite; on S3/R2 it replaces the key.
    """
    storage = field_file.storage
    if storage.exists(name):
        storage.delete(name)
    storage.save(name, ContentFile(data))


def variant_url(field_file, request=None, suffix="mobile"):
    """URL of an image's generated variant, or None if it hasn't been produced yet.

    Existence-checked so legacy images (before a backfill) simply fall back to the
    original instead of serving a 404 in a srcset. NOTE: on remote storage
    ``exists`` is a network round-trip (a HEAD) per call — fine for the single-
    object detail endpoint, and the Phase-2 backfill guarantees variants exist so
    the check can later be dropped for R2.
    """
    if not field_file or not getattr(field_file, "name", None):
        return None
    if not field_file.storage.exists(variant_name(field_file.name, suffix)):
        return None
    url = variant_name(field_file.url, suffix)
    return request.build_absolute_uri(url) if request else url


def make_webp_variant(field_file, max_width=768, quality=55, suffix="mobile"):
    """Write a small WebP sibling next to an uploaded image (for mobile srcset).

    Produces ``<name>.<suffix>.webp`` alongside the (already resized) original.
    Regenerated on every save and best-effort: a failure here must never break a
    save. Pair the output with ``variant_name`` to build the served URL.
    """
    name = getattr(field_file, "name", None)
    if not name:
        return
    if os.path.splitext(name)[1].lower() in VECTOR_EXTENSIONS:
        return  # SVG is already tiny and PIL can't read it
    data = _read_bytes(field_file)
    if data is None:
        return
    try:
        with decode_slot(), Image.open(io.BytesIO(data)) as img:
            img = _normalise_mode(ImageOps.exif_transpose(img))
            # Cap width; allow tall portraits to keep their aspect ratio.
            img.thumbnail((max_width, max_width * 6), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, "WEBP", quality=quality, method=WEBP_METHOD)
    except (OSError, IOError):
        # Not an image or file is corrupt — leave it alone.
        return
    _overwrite(field_file, variant_name(name, suffix), out.getvalue())


# ── Uploads are stored as WebP ────────────────────────────────────────────────
#
# One target format for every upload, whatever came in. Formats used to be
# preserved, which meant a PNG screenshot stayed a 3 MB PNG forever: PNG is
# lossless, so there was no quality knob to turn and `optimize=True` saved 0 %.
#
# WebP replaces the whole branchy mess with one path, and it is smaller at equal
# quality because it predicts each block from its already-decoded neighbours and
# stores only the residual. It also carries an alpha channel in lossy mode, which
# JPEG cannot do at all -- that is what makes a single format possible here:
# transparent logos and photos can share one encoder.
#
# The numbers below are measured, not guessed. imagelab/ in the repo root
# reproduces every one of them:
#   * imagelab/06_why_webp.py  -- where the saving comes from (+65 % on flat
#     artwork, +30 % on photos, +17 % on noise) and why blocking stays at the
#     level of the uncompressed original even at low quality.
#   * imagelab/01_ladder.py    -- the knee of the size/quality curve.
#   * imagelab/04_cap.py       -- what this does to the existing library.
WEBP_QUALITY = 80          # WebP q80 matches JPEG q85 perceptually (measured)
WEBP_QUALITY_FLOOR = 75    # below the knee: each step costs quality, saves ~5 kB
WEBP_QUALITY_STEP = 5
# method=6 searches ~3x longer for 10-15 % smaller output. That trade is wrong in
# the request path: encoding happens synchronously inside save(), so the user
# waits for it and one of four gunicorn workers is blocked meanwhile.
WEBP_METHOD = 4
SHRINK_FACTOR = 0.85       # -28 % pixels per round once quality hits the floor
# Enough rounds that the cap is a guarantee rather than an aspiration: 0.85^12
# takes 1600 px down to ~230 px, and pathological noise fits any sane cap long
# before that. Four rounds looked sufficient against real photos and was not --
# high-entropy input still landed 2.5x over a tight cap.
MAX_SHRINK_ROUNDS = 12
# ...but stop before the image becomes useless. Anything still over the cap at
# this size is so degenerate that storing it slightly oversized beats storing a
# thumbnail nobody can read.
MIN_DIMENSION = 200

# Animation budget. Unlike a still, every frame has to be in memory at once, so
# the cost is frames x width x height and the 15 MB upload limit does not bound
# it usefully -- a heavily-compressed GIF can hold hundreds of frames. Measured
# with imagelab/07_memory.py against the 512 MB instance.
MAX_ANIMATION_FRAMES = 120
MAX_ANIMATION_PIXELS = 12_000_000   # ~36 MB of RGB bitmap across all frames

# ── Only N images are decoded AT ONCE ON THE WHOLE INSTANCE ──────────────────
#
# This is the setting that decides how many gunicorn workers fit in RAM, so it
# is worth understanding rather than tuning by feel.
#
# Decoding is the only part of this app whose memory cost is chosen by the user
# rather than by us. A 24 MP PNG with an alpha channel peaks at 286 MB of RSS;
# an idle worker sits near 60 MB. So the budget is NOT "workers x peak" unless
# every worker can decode at the same time -- and stopping that is exactly what
# this lock does:
#
#     workers x peak             = 3 x 286      = 858 MB   OOM on a 512 MB box
#     (workers-1) x floor + peak = 2 x 60 + 286 = 406 MB   fits, 46 MB over the
#                                                          60 MB safety margin
#
# A per-process semaphore (what this used to be) cannot give the second line: it
# stops two threads of ONE worker decoding together, but three workers still
# decode three images at once. So the lock has to be host-wide, which means it
# cannot live in Python memory -- hence flock() on a file, which every process on
# the instance can see and which the kernel releases automatically if a worker is
# killed. (A Redis lock would also work, but it can go stale, costs a network
# round trip, and would make uploads fail whenever the cache is down.)
#
# The cost is that a second uploader waits. Uploads are rare here, the wait is
# seconds, and the slot is taken per IMAGE rather than per request -- so a bulk
# upload of 30 photos releases it 30 times instead of holding it throughout.
#
# Both knobs are settings, so the instance can be resized without a deploy:
#
#   IMAGE_DECODE_SLOTS         concurrent decodes per instance   (default 1)
#   IMAGE_DECODE_WAIT_SECONDS  how long an upload waits for one  (default 5)
#
# Raising SLOTS to 2 needs another whole peak (+226 MB over an idle worker) --
# i.e. a 1 GB instance. Verify with imagelab/07_memory.py, which measures the cross-process
# case explicitly.
DEFAULT_DECODE_SLOTS = 1
# Wait briefly, then refuse -- the middle of three options, and the reason for
# each bound is worth writing down.
#
# Refusing immediately (a bare LOCK_NB, which is what WAIT_SECONDS=0 gives you)
# turns the lock from a short queue into a pure capacity guard. It costs no
# latency but pays in errors, and the error lands on someone who has just picked
# a photo and pressed upload -- the worst possible moment to be told "no". Two
# uploads arriving a second apart is the NORMAL case, not an overload, and both
# should succeed.
#
# Waiting long is bounded by two things that have nothing to do with memory.
# A waiting request holds a gunicorn thread, and there are only
# WEB_CONCURRENCY x GUNICORN_THREADS = 6 of them: at 20 s, six queued uploads
# make the whole site unresponsive for 20 s. And the wait must finish well
# inside gunicorn's `timeout` (30 s, set explicitly in gunicorn.conf.py) plus
# the decode itself, so the refusal comes from this code as a clean 503 rather
# than from the arbiter killing a worker mid-request.
#
# 5 s covers a decode or two (1-3 s each) and leaves the timeout a wide margin.
DEFAULT_DECODE_WAIT_SECONDS = 5.0
# Sweep interval while waiting: short enough to pick up a freed slot promptly,
# long enough not to spin a core on a busy instance.
_DECODE_POLL_SECONDS = 0.05


class DecodeBusy(Exception):
    """Every decode slot stayed taken for longer than the caller would wait.

    Deliberately NOT "decode it anyway": proceeding is the exact thing the lock
    exists to prevent, and an OOM kill takes down every request the worker is
    serving, not just this upload. Turning one upload away is the smaller harm.

    `mysite.drf.api_exception_handler` renders it as 503 with a Czech message,
    and the write endpoints are transactional, so no half-saved row is left.
    """


def _decode_setting(name, default, cast):
    from django.conf import settings
    try:
        return cast(getattr(settings, name, default))
    except (TypeError, ValueError):
        logger.warning("%s is not a valid number; using %r.", name, default)
        return default


def _lock_dir():
    """Where the slot files live — one set per instance, so the temp dir fits."""
    from django.conf import settings
    return getattr(settings, "IMAGE_DECODE_LOCK_DIR", None) or tempfile.gettempdir()


# Flipped to False the first time flock() proves unavailable (exotic filesystem,
# non-POSIX host). Everything then falls back to the in-process semaphore, which
# is weaker -- it serialises only the threads of one worker -- but is exactly the
# behaviour this code had before, so nothing regresses.
_flock_usable = fcntl is not None
# Re-entry guard: a thread already holding a slot must not queue behind itself.
# Nothing nests today, but a future caller wrapping one of these functions in the
# other would deadlock, and that is a bad way to find out.
_holding = threading.local()
_in_process_slot = threading.BoundedSemaphore(1)


def _try_take(path):
    """Open `path` and grab its exclusive flock; None if someone else holds it."""
    global _flock_usable
    handle = None
    try:
        handle = open(path, "a+b")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError as exc:
        if handle is not None:
            handle.close()
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            return None  # just held by someone else — the normal busy case
        # Anything else (ENOTSUP, EPERM, a read-only temp dir) means flock is not
        # usable here at all. Say so once, then stop trying.
        logger.warning("flock unusable (%s); falling back to a per-process slot.", exc)
        _flock_usable = False
        return None


@contextmanager
def _fallback_slot():
    """Per-process serialisation, for when flock is not available."""
    with _in_process_slot:
        _holding.active = True
        try:
            yield
        finally:
            _holding.active = False


@contextmanager
def decode_slot():
    """Hold one instance-wide decode slot for the duration of the block.

    Raises `DecodeBusy` if none frees up within IMAGE_DECODE_WAIT_SECONDS.

    The acquire is a LOCK_NB sweep on a timer, not a blocking flock, and that is
    deliberate: a blocking flock cannot be given a deadline. (SIGALRM can
    interrupt one, but only on the main thread, and these run on gthread worker
    threads -- so it would work in testing and silently not in production.)
    Polling is duller and always works.

    IMAGE_DECODE_WAIT_SECONDS=0 degenerates to exactly one LOCK_NB attempt, i.e.
    refuse-immediately, if that is ever wanted.
    """
    if getattr(_holding, "active", False):
        yield                       # this thread is already inside a slot
        return

    if not _flock_usable:
        with _fallback_slot():
            yield
        return

    slots = max(1, _decode_setting("IMAGE_DECODE_SLOTS", DEFAULT_DECODE_SLOTS, int))
    wait = max(0.0, _decode_setting("IMAGE_DECODE_WAIT_SECONDS",
                                    DEFAULT_DECODE_WAIT_SECONDS, float))
    paths = [os.path.join(_lock_dir(), f"gol-image-decode-{i}.lock")
             for i in range(slots)]
    deadline = time.monotonic() + wait

    while True:
        for path in paths:
            handle = _try_take(path)
            if handle is None:
                continue
            _holding.active = True
            try:
                yield
                return
            finally:
                _holding.active = False
                try:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                finally:
                    handle.close()
        if not _flock_usable:
            # _try_take just discovered flock does not work here; take the
            # fallback rather than spinning until the deadline.
            with _fallback_slot():
                yield
            return
        if time.monotonic() >= deadline:
            raise DecodeBusy(
                f"No image-decode slot free after {wait:g}s ({slots} slot(s))."
            )
        time.sleep(_DECODE_POLL_SECONDS)

# Per-model ceilings on the stored file. Nothing but a pathological upload ever
# reaches them -- the biggest real photo in the library lands at ~330 kB -- so
# these are a guard rail, not a routine quality reduction.
CAP_EVENT_IMAGE = 1000 * 1024
CAP_GALLERY_PHOTO = 700 * 1024
CAP_ARTWORK = 700 * 1024

# Never handed to PIL at all — not an image in the raster sense.
VECTOR_EXTENSIONS = {".svg"}


def is_animated(img):
    """True for multi-frame images (animated GIF/WebP)."""
    return getattr(img, "n_frames", 1) > 1


def webp_name(name):
    """Storage key this upload gets once converted: 'a/foo.jpg' -> 'a/foo.webp'."""
    base, _ = os.path.splitext(name)
    return f"{base}.webp"


# ── The registry: every image field in the project, and how it is stored ──────
#
# THIS IS THE SINGLE SOURCE OF TRUTH. Model save(), the generate_image_variants
# backfill and the coverage test all read it, so the three cannot drift apart and
# a new image field cannot quietly skip processing:
# ImageFieldCoverageTests.test_every_image_field_is_registered fails until the
# field is listed here.
#
# Adding an image field to a model? Add one line below, and the upload gets
# converted, capped, backfilled and covered by tests automatically.
#
#   key   "<app_label>.<Model>.<field>"
#   value (max_width, max_height, cap_bytes, variant_kwargs)
#         variant_kwargs=None means "no .mobile.webp sibling" -- at small sizes
#         a variant saves nothing and only adds a file to store and serve.
UPLOAD_LIMITS = {
    "leaderboard.Event.image":        (1200, 1200, CAP_EVENT_IMAGE, {}),
    "leaderboard.ImageToEvent.image": (1024, 1024, CAP_GALLERY_PHOTO, {}),
    # The gallery grid serves the variant; this original is only fetched when
    # someone opens the lightbox to actually look at the photo, which is the
    # wrong place to economise. Hence the largest dimensions of the lot.
    "leaderboard.UserPhoto.image":    (1600, 1600, CAP_GALLERY_PHOTO, {}),
    "leaderboard.Badge.image":        (512, 512, CAP_ARTWORK, None),
    "accounts.Profile.photo":         (400, 400, CAP_ARTWORK,
                                       {"max_width": 200, "quality": 60}),
}

# Fields deliberately left unprocessed. Empty today; anything added here needs a
# comment saying why, because the coverage test treats it as a waiver.
UPLOAD_EXEMPT = set()


def field_key(instance_or_model, field_name):
    """'<app_label>.<Model>.<field>' — the key used throughout the registry."""
    meta = instance_or_model._meta
    return f"{meta.app_label}.{meta.object_name}.{field_name}"


def limits_for(instance_or_model, field_name):
    """Registry entry for this field, or a loud error if it was never registered."""
    key = field_key(instance_or_model, field_name)
    try:
        return UPLOAD_LIMITS[key]
    except KeyError:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            f"{key} is an image field with no entry in "
            f"image_utils.UPLOAD_LIMITS, so uploads to it would be stored at "
            f"full size. Add its limits there."
        )


def process_image_field(instance, field_name):
    """Convert this field's upload, persist the new key, refresh the mobile variant.

    The single call a model's ``save()`` needs to make -- everything specific to
    the field comes from UPLOAD_LIMITS.

    Two ordering rules are baked in here rather than repeated (and eventually got
    wrong) in five different models:

      * the new storage key is written back to the row, because process_upload
        renames the file and a row still pointing at 'foo.jpg' would 404;
      * the variant is generated afterwards, since its name derives from the
        original's -- doing it first strands it beside a key that no longer
        exists.

    Uses ``models.Model.save`` rather than ``instance.save()`` on purpose: the
    caller is already inside save(), so going through it again would recurse.
    """
    from django.db import models

    field = getattr(instance, field_name)
    if not field:
        return
    max_width, max_height, cap, variant_kwargs = limits_for(instance, field_name)

    stored = process_upload(field, max_width, max_height, cap)
    if stored:
        field.name = stored
        models.Model.save(instance, update_fields=[field_name])
    if variant_kwargs is not None:
        make_webp_variant(field, **variant_kwargs)


def _normalise_mode(img):
    """Put an image into RGB or RGBA, dropping an alpha channel that carries nothing.

    A surprising share of uploaded PNGs are RGBA with every pixel fully opaque --
    a quarter of the data spent on a channel holding no information. Dropping it
    is free. Note the check is on the actual pixel values, not the mode: mode
    alone says an alpha channel exists, not that anything is transparent.
    """
    if img.mode == "P":
        # Palette images (GIF logos) keep transparency in `info`; going straight
        # to RGB would paint the transparent parts black.
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.mode == "RGBA" and img.getchannel("A").getextrema()[0] == 255:
        img = img.convert("RGB")
    return img


def _webp_bytes(img, quality, frames=None, **extra):
    out = io.BytesIO()
    if frames:
        img.save(out, "WEBP", quality=quality, method=WEBP_METHOD,
                 save_all=True, append_images=frames, **extra)
    else:
        img.save(out, "WEBP", quality=quality, method=WEBP_METHOD, **extra)
    return out.getvalue()


def _shrink(img, factor=SHRINK_FACTOR):
    size = (max(int(img.width * factor), 1), max(int(img.height * factor), 1))
    return img.resize(size, Image.LANCZOS)


def _encode_under_cap(frames, max_bytes, quality=WEBP_QUALITY,
                      floor=WEBP_QUALITY_FLOOR, max_rounds=MAX_SHRINK_ROUNDS,
                      **extra):
    """Smallest WebP of `frames` that fits in `max_bytes`; drop quality, then size.

    Quality first because it is nearly free below the perceptual threshold; only
    once it hits the floor does the pixel count come down, since a smaller image
    is less objectionable than a mangled one at the same display size.

    Every attempt re-encodes from the same decoded frames, never from the
    previous attempt's output -- chaining them would stack one generation of
    loss per step.

    `floor` is clamped to `quality`: a floor above the starting quality makes the
    descending range empty and the function would return nothing at all. That is
    easy to trip the moment someone lowers WEBP_QUALITY without touching the
    floor, and it fails as a crash on an upload, not as a bad-looking image.
    """
    floor = min(floor, quality)
    work = list(frames)
    payload = None
    for round_no in range(max_rounds + 1):
        for q in range(quality, floor - 1, -WEBP_QUALITY_STEP):
            payload = _webp_bytes(work[0], q, frames=work[1:], **extra)
            if len(payload) <= max_bytes:
                return payload
        if round_no == max_rounds or min(work[0].size) <= MIN_DIMENSION:
            break
        work = [_shrink(f) for f in work]
    return payload  # best effort: over the cap, but far smaller than the input


def _prepare_still(img, max_width, max_height):
    """One frame, decoded as cheaply as the format allows.

    Memory is the constraint here, not speed: the instance has 512 MB and a
    28 MP photo is an 80 MB bitmap per copy. Two things keep that down.

    ``draft()`` asks the JPEG decoder for a 1/2, 1/4 or 1/8 scale image *while
    decoding*, so a 28 MP upload bound for 1200 px never materialises at full
    size at all. Pillow only reduces as far as it can while staying above the
    requested size, so the LANCZOS pass afterwards still has detail to work
    with. It is a no-op for formats that cannot do it.

    ``exif_transpose`` defaults to returning a full-size *copy* even when there
    is nothing to rotate -- another whole bitmap for nothing. in_place=True
    skips that.
    """
    try:
        img.draft("RGB", (max_width, max_height))
    except (AttributeError, ValueError, OSError):
        pass  # not a JPEG, or already loaded — nothing lost
    ImageOps.exif_transpose(img, in_place=True)
    out = _normalise_mode(img)
    if out.width > max_width or out.height > max_height:
        out.thumbnail((max_width, max_height), Image.LANCZOS)
    return [out]


def _prepare_animation(img, max_width, max_height):
    """Every frame, downscaled immediately so only small ones accumulate.

    Pillow needs the whole frame list in memory to write an animated WebP, so
    an animation costs frames x width x height all at once. A 60-frame 700x700
    GIF is already 88 MB of bitmap, and nothing stops someone uploading 500
    frames inside the 15 MB the validator allows -- so the budget is enforced
    by shrinking frames, which keeps the animation playing rather than
    rejecting the upload.

    The per-frame copy is unavoidable: ImageSequence.Iterator reuses one buffer,
    so keeping a reference without copying would hand back N views of the last
    frame. Shrinking each copy straight away means the peak is one full-size
    frame plus the small ones already collected.
    """
    count = min(getattr(img, "n_frames", 1), MAX_ANIMATION_FRAMES)
    side = int((MAX_ANIMATION_PIXELS / max(count, 1)) ** 0.5)
    cap = (min(max_width, side), min(max_height, side))

    frames = []
    for index, frame in enumerate(ImageSequence.Iterator(img)):
        if index >= MAX_ANIMATION_FRAMES:
            break
        prepared = _normalise_mode(frame.copy())
        prepared.thumbnail(cap, Image.LANCZOS)
        frames.append(prepared)
    return frames


def _inspect(data):
    """(format, width, height, animated) without decoding pixel data, or None."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.format, img.width, img.height, is_animated(img)
    except (OSError, IOError):
        return None


def needs_processing(field_file, max_width, max_height, max_bytes):
    """True when ``process_upload`` would actually rewrite this file.

    Split out so a bulk backfill can dry-run. Storage-abstracted, so it works
    the same against local disk and the R2 bucket.
    """
    name = getattr(field_file, "name", None)
    if not name or os.path.splitext(name)[1].lower() in VECTOR_EXTENSIONS:
        return False
    data = _read_bytes(field_file)
    if data is None:
        return False
    probe = _inspect(data)
    if probe is None:
        return False
    fmt, width, height, _animated = probe
    already_webp = fmt == "WEBP" and os.path.splitext(name)[1].lower() == ".webp"
    fits = width <= max_width and height <= max_height and len(data) <= max_bytes
    return not (already_webp and fits)


def process_upload(field_file, max_width, max_height, max_bytes):
    """Store this upload as WebP, downscaled and under `max_bytes`.

    Returns the new storage key when it changed (the caller must persist it on
    the model), or None when nothing was written.

    Safe to call on every save: an image that is already WebP, within bounds and
    under the cap is left untouched, so repeated saves cannot slowly degrade it
    by re-encoding it again and again.

    Animations survive as animated WebP. That closes a real hole -- GIF used to
    bypass processing entirely and could sit on disk at the full 15 MB the
    validator allows.

    SVG is passed over: PIL cannot read it and there is nothing to downscale.

    Storage-abstracted (reads and writes via ``field_file.storage``) so it never
    needs a local ``.path`` -- the same code serves local disk and S3/R2.
    """
    name = getattr(field_file, "name", None)
    if not name or os.path.splitext(name)[1].lower() in VECTOR_EXTENSIONS:
        return None
    data = _read_bytes(field_file)
    if data is None:
        return None
    probe = _inspect(data)
    if probe is None:
        return None  # unreadable or not an image — leave it alone
    fmt, width, height, animated = probe

    if (fmt == "WEBP" and os.path.splitext(name)[1].lower() == ".webp"
            and width <= max_width and height <= max_height
            and len(data) <= max_bytes):
        return None

    try:
        # Held across decode AND encode: both hold the full bitmap, so releasing
        # after the decode would let a second upload in while this one is still
        # at its peak.
        with decode_slot(), Image.open(io.BytesIO(data)) as img:
            if animated:
                # Keep the timing and looping the source declared, otherwise the
                # animation plays back at the WebP default speed.
                extra = {"duration": img.info.get("duration", 100),
                         "loop": img.info.get("loop", 0)}
                frames = _prepare_animation(img, max_width, max_height)
            else:
                extra = {}
                frames = _prepare_still(img, max_width, max_height)
            # Encoding stays inside the `with`: the still path deliberately does
            # not copy the decoded image, so `img` must still be open here.
            payload = _encode_under_cap(frames, max_bytes, **extra)
    except (OSError, IOError, ValueError):
        return None
    if payload is None:
        return None

    storage = field_file.storage
    target = webp_name(name)
    if target == name:
        _overwrite(field_file, name, payload)
        return None  # bytes changed, key did not — no model write needed

    # Two uploads in one directory can collide once extensions are normalised
    # ('logo.png' and 'logo.jpg' both want 'logo.webp'), and the second would
    # silently overwrite the first. Let the storage pick a free key instead.
    if storage.exists(target):
        target = storage.get_available_name(target)

    # Write the replacement before removing the source: an interrupted run then
    # leaves an orphan file rather than a row pointing at nothing.
    _overwrite(field_file, target, payload)
    try:
        if storage.exists(name):
            storage.delete(name)
    except (OSError, IOError):
        pass  # an orphan costs disk, a raised exception costs the upload
    return target

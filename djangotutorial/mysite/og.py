"""Server-rendered Open Graph / Twitter Card tags for the React SPA shell.

Link-preview crawlers -- Facebook (which also powers WhatsApp and Messenger),
Twitter/X, Discord, Slack, LinkedIn -- fetch a URL, read ``<head>``, and leave
WITHOUT executing JavaScript. A client-rendered SPA therefore cannot set its own
preview: by the time React mounts and could call `document.title`, the crawler is
long gone. This is why `react-helmet` and friends do nothing for link previews.

So the tags have to be in the HTML Django hands out. `mysite.views.react_index`
serves that HTML for every non-API route, which makes it the one place per-route
metadata can be attached without adding an SSR runtime.

Scope: events get real per-event previews (the pages people actually paste into
group chats); everything else gets a per-page title on top of the site defaults.
Player/profile pages deliberately fall through to the defaults -- see
`_PAGE_TITLES` -- so nobody's name and photo land in a preview card by accident.
"""
import os
import re

from django.utils.html import escape

SITE_NAME = "Game of Live"
DEFAULT_TITLE = "Game of Live — Život je hra, tak ho hrej"
DEFAULT_DESCRIPTION = (
    "Sbírej body za zážitky, ne za lajky. Přidej se k hráčům, "
    "kteří místo scrollování žijí."
)
# Served by WhiteNoise from the React build (WHITENOISE_ROOT = staticfiles/react).
# Swap for a purpose-made 1200x630 card if you ever cut one.
DEFAULT_IMAGE = "/img/home-onas-desktop.webp"

# Facebook rejects an og:image over 8 MB and WhatsApp is stricter still. Legacy
# event photos predate Event.save()'s resize_image() call and run to ~10 MB, so
# near the limit we hand over the small .mobile.webp sibling instead: a preview
# that renders beats a full-resolution one the crawler drops. Once the originals
# are downscaled this branch stops firing and everyone gets the original again.
_OG_IMAGE_MAX_BYTES = 5 * 1024 * 1024

_MAX_DESCRIPTION = 200

# Path (no leading/trailing slash) -> page title. Only pages worth naming in a
# preview; anything unlisted, including /profil/* and /hrac/*, uses the defaults.
_PAGE_TITLES = {
    "events": "Akce",
    "leaderboard": "Žebříček",
    "galerie": "Galerie",
    "o-bodech": "Jak se počítají body",
    "historie": "Historie",
}

# /events/<slug> only. `vytvorit` is the create form, and `<slug>/upravit` is the
# edit form -- neither is an event to preview.
_EVENT_DETAIL_RE = re.compile(r"^events/(?P<slug>[^/]+)/?$")
_RESERVED_EVENT_SLUGS = {"vytvorit"}


def _truncate(text, limit=_MAX_DESCRIPTION):
    """Collapse whitespace and cut to `limit` chars on a word boundary."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _absolute(request, url):
    """Crawlers reject relative og:image/og:url -- always send absolute."""
    return request.build_absolute_uri(url) if url else None


def _event_image_url(request, event):
    """Best previewable URL for an event photo, or None.

    Prefers the original (JPEG/PNG is the most broadly supported og:image
    format) and falls back to the generated .mobile.webp only when the original
    is too heavy for the crawlers to accept.
    """
    from leaderboard.image_utils import variant_name

    if not event.image:
        return None
    path = getattr(event.image, "path", None)
    if not path or not os.path.exists(path):
        return None

    if os.path.getsize(path) <= _OG_IMAGE_MAX_BYTES:
        return _absolute(request, event.image.url)

    if os.path.exists(variant_name(path)):
        return _absolute(request, variant_name(event.image.url))
    # Oversized with no variant yet: sending it is still better than sending
    # nothing -- some crawlers are more lenient than Facebook's documented cap.
    return _absolute(request, event.image.url)


def _event_description(event):
    """Event's own text, else a synthesised one-liner from place/date/points."""
    if event.description.strip():
        return _truncate(event.description)

    from django.utils import timezone

    bits = [b for b in (event.place, _format_date(event.date, timezone)) if b]
    if event.points:
        bits.append(f"{event.points} bodů")
    return " · ".join(bits) or DEFAULT_DESCRIPTION


def _format_date(value, timezone):
    if not value:
        return ""
    local = timezone.localtime(value)
    return f"{local.day}. {local.month}. {local.year}"


def _event_metadata(request, slug):
    """Per-event metadata, or None when there's no event to preview.

    Only `visible_to_users` events resolve: crawlers are anonymous, so a hidden
    or close-preview event must never leak its name and photo into a link card.
    """
    from leaderboard.models import Event

    event = (
        Event.objects
        .filter(slug=slug, visible_to_users=True)
        .only("name", "description", "place", "date", "points", "image", "slug")
        .first()
    )
    if event is None:
        return None
    return {
        "title": f"{event.name} — {SITE_NAME}",
        "description": _event_description(event),
        "image": _event_image_url(request, event) or _absolute(request, DEFAULT_IMAGE),
        "url": request.build_absolute_uri(),
    }


def metadata_for(request):
    """Resolve the request path to the metadata dict used for the tags."""
    path = request.path.strip("/")

    match = _EVENT_DETAIL_RE.match(path)
    if match:
        slug = match.group("slug")
        if slug not in _RESERVED_EVENT_SLUGS:
            event_meta = _event_metadata(request, slug)
            if event_meta:
                return event_meta

    title = DEFAULT_TITLE
    page_title = _PAGE_TITLES.get(path)
    if page_title:
        title = f"{page_title} — {SITE_NAME}"

    return {
        "title": title,
        "description": DEFAULT_DESCRIPTION,
        "image": _absolute(request, DEFAULT_IMAGE),
        "url": request.build_absolute_uri(),
    }


def render_tags(meta):
    """Metadata dict -> the ``<head>`` block, with every value HTML-escaped."""
    title = escape(meta["title"])
    description = escape(meta["description"])
    tags = [
        f"<title>{title}</title>",
        f'<meta name="description" content="{description}" />',
        f'<meta property="og:type" content="website" />',
        f'<meta property="og:site_name" content="{escape(SITE_NAME)}" />',
        f'<meta property="og:title" content="{title}" />',
        f'<meta property="og:description" content="{description}" />',
        f'<meta property="og:locale" content="cs_CZ" />',
        f'<meta name="twitter:title" content="{title}" />',
        f'<meta name="twitter:description" content="{description}" />',
    ]
    if meta.get("url"):
        tags.append(f'<meta property="og:url" content="{escape(meta["url"])}" />')
    if meta.get("image"):
        image = escape(meta["image"])
        tags.append(f'<meta property="og:image" content="{image}" />')
        tags.append(f'<meta name="twitter:image" content="{image}" />')
        tags.append('<meta name="twitter:card" content="summary_large_image" />')
    else:
        tags.append('<meta name="twitter:card" content="summary" />')
    return "\n    ".join(tags)


# The shell ships exactly one <title>; drop it so ours is the only one (crawlers
# take the first match, and a stale duplicate would win).
_TITLE_RE = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)


def inject(html, meta):
    """Return `html` with the shell's <title> replaced by the rendered tags."""
    tags = render_tags(meta)
    html, replaced = _TITLE_RE.subn(tags, html, count=1)
    if not replaced:
        # No <title> to swap (hand-edited shell) -- append instead of silently
        # serving a page with no metadata at all.
        html = html.replace("</head>", f"    {tags}\n  </head>", 1)
    return html

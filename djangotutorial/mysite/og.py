"""Server-rendered ``<head>`` metadata for the React SPA shell.

Link-preview crawlers -- Facebook (which also powers WhatsApp and Messenger),
Twitter/X, Discord, Slack, LinkedIn -- fetch a URL, read ``<head>``, and leave
WITHOUT executing JavaScript. A client-rendered SPA therefore cannot set its own
preview: by the time React mounts and could call `document.title`, the crawler is
long gone. This is why `react-helmet` and friends do nothing for link previews.

So the tags have to be in the HTML Django hands out. `mysite.views.react_index`
serves that HTML for every non-API route, which makes it the one place per-route
metadata can be attached without adding an SSR runtime.

Scope: events get real per-event previews (the pages people actually paste into
group chats). Player and profile pages get a title carrying the player's public
display name -- full name only where a matching consent is on file, otherwise
"Jan N.", the exact rule leaderboard/privacy.py applies everywhere else -- and
NO personal photo: the card falls back to the site's default image, so a name
may show but a face never does. Everything else gets a per-page title on top of
the site defaults.

Structure
---------
Three layers, deliberately kept apart:

1. **Resolvers** turn a matched URL into a `PageMeta` (or say they can't). One
   per content route, registered in `_ROUTES`.
2. **`metadata_for`** walks `_ROUTES`, falls back to the site defaults, and is
   the only public entry point for "what does this URL mean".
3. **`render_tags` / `inject`** turn a `PageMeta` into HTML. They know nothing
   about events, players or privacy.

Adding a route means writing a resolver and adding one line to `_ROUTES`.
"""
import json
import logging
import re
from dataclasses import dataclass, replace

from django.utils.html import escape

logger = logging.getLogger(__name__)

SITE_NAME = "Game of Life"
DEFAULT_TITLE = "👾 Život je hra."
DEFAULT_DESCRIPTION = (
    "✨ Žijeme naplno a děláme, co nás baví."
    "💖 Přidej se taky a vytvoř si nejkrásnější vzpomínky. 🙂‍↔️"
)
# Player/profile cards: a generic, non-identifying line. The name lives in the
# title (consent-gated); the description stays deliberately anonymous.
PLAYER_DESCRIPTION = "Profil hráče v leaderboardu Game of Life."
# Served by WhiteNoise from the React build (WHITENOISE_ROOT = staticfiles/react).
# Swap for a purpose-made 1200x630 card if you ever cut one.
DEFAULT_IMAGE = "/img/home-onas-desktop.webp"

# Facebook rejects an og:image over 8 MB and WhatsApp is stricter still. Legacy
# event photos predate Event.save()'s conversion call and run to ~10 MB, so
# near the limit we hand over the small .mobile.webp sibling instead: a preview
# that renders beats a full-resolution one the crawler drops. Once the originals
# are downscaled this branch stops firing and everyone gets the original again.
_OG_IMAGE_MAX_BYTES = 5 * 1024 * 1024

_MAX_DESCRIPTION = 200


@dataclass(frozen=True)
class PageMeta:
    """Everything the shell's ``<head>`` needs for one URL.

    Frozen so a resolver cannot mutate the shared defaults by accident; build
    variants with `dataclasses.replace`.

    `exists` is the one field that is not a tag: it records whether the URL
    names real content. `/events/<slug>` for a slug with no Event row is a
    page that does not exist, and the caller uses this to answer 404 instead
    of the 200-with-an-empty-shell that search engines file as a soft 404.
    Note it is about the *content*, not about the current viewer -- a page
    that is merely hidden from anonymous visitors still exists.
    """

    title: str
    description: str
    url: str
    image: str | None = None
    canonical: str | None = None
    robots: str | None = None
    jsonld: dict | None = None
    exists: bool = True


class _Missing:
    """Sentinel: the route matched, but there is no such object behind it."""

    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debugging aid
        return "MISSING"


MISSING = _Missing()

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

# /hrac/<id> (a leaderboard-user id, matching /api/v1/players/<id>/) and
# /profil/<username> (a linked account). Both resolve to the same player card.
_PLAYER_DETAIL_RE = re.compile(r"^hrac/(?P<user_id>\d+)/?$")
_PROFILE_DETAIL_RE = re.compile(r"^profil/(?P<username>[^/]+)/?$")


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

    Goes through the storage API rather than a filesystem path. `FieldFile.path`
    raises NotImplementedError on S3/R2 (object storage has no local path), and
    `getattr(..., None)` does not swallow that -- the default only covers
    AttributeError. Since react_index wraps OG injection in a blanket except, the
    failure would not surface as an error: link previews would simply stop having
    images the moment media moved to the bucket, with nothing in the logs.
    """
    from leaderboard.image_utils import variant_name

    if not event.image:
        return None

    storage = event.image.storage
    name = event.image.name
    try:
        if not name or not storage.exists(name):
            return None
        size = storage.size(name)
    except Exception:  # noqa: BLE001 -- a storage hiccup must not cost the preview
        logger.warning("OG image lookup failed for %r", name, exc_info=True)
        return _absolute(request, event.image.url)

    if size <= _OG_IMAGE_MAX_BYTES:
        return _absolute(request, event.image.url)

    if storage.exists(variant_name(name)):
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


def _defaults(request, **overrides):
    """The site-wide card, optionally with fields replaced."""
    base = PageMeta(
        title=DEFAULT_TITLE,
        description=DEFAULT_DESCRIPTION,
        url=request.build_absolute_uri(),
        image=_absolute(request, DEFAULT_IMAGE),
    )
    return replace(base, **overrides) if overrides else base


# --- Resolvers -------------------------------------------------------------
#
# Signature: (request, **named groups from the route regex).
# Three possible answers, and the difference between the last two is what makes
# a correct 404 possible:
#
#   PageMeta  -- here is the card for this page
#   None      -- no card, but the page is real (a form, or content deliberately
#                withheld from anonymous crawlers). Falls back to the defaults
#                with a 200.
#   MISSING   -- there is no such page at all. Falls back to the defaults, but
#                the caller answers 404.


def _event_metadata(request, slug):
    """Card for /events/<slug>.

    Looks the event up by slug ALONE and judges visibility afterwards, because
    the two failure modes need different HTTP answers: a slug nobody ever used
    is a 404, while an event that exists but is hidden from the public (a draft,
    or a `visible_to_close` preview) is a real page that the right signed-in
    user can open. Filtering `visible_to_users=True` in the query would collapse
    both into "not found" and hand that user a 404 for a page they can see.

    Either way the anonymous crawler learns nothing: a non-public event still
    gets the generic site card, never its name or photo.
    """
    from leaderboard.models import Event

    if slug in _RESERVED_EVENT_SLUGS:
        return None

    event = (
        Event.objects
        .filter(slug=slug)
        .only("name", "description", "place", "date", "points", "image", "slug",
              "visible_to_users")
        .first()
    )
    if event is None:
        return MISSING
    if not event.visible_to_users:
        return None

    return PageMeta(
        title=f"{event.name} — {SITE_NAME}",
        description=_event_description(event),
        image=_event_image_url(request, event) or _absolute(request, DEFAULT_IMAGE),
        url=request.build_absolute_uri(),
    )


def _public_player_name(lb_user, profile):
    """The name to show for a player, or None when it must not be shown.

    Two gates, both applied for anonymous viewers (a link-preview crawler is
    always anonymous):

    * ``members_only`` — a self-service "signed-in visitors only" flag. The
      profile page itself 404s for anonymous requests (visible_profile_user_or_404);
      the preview card has to withhold the name for the same reason, or the flag
      is bypassable by pasting the URL into a chat instead of a browser.
    * consent — full name only where a matching GDPR consent is on file,
      otherwise the shortened "Jan N." form, exactly as the site renders it.
    """
    from leaderboard.privacy import display_name, profile_has_consent

    if profile is not None and profile.members_only:
        return None
    return display_name(lb_user.name, consented=profile_has_consent(profile))


def _player_card(request, name):
    """A player/profile card: name in the title, default image (never a face)."""
    return PageMeta(
        title=f"{name} — {SITE_NAME}",
        description=PLAYER_DESCRIPTION,
        image=_absolute(request, DEFAULT_IMAGE),
        url=request.build_absolute_uri(),
    )


def _player_metadata(request, user_id):
    """Card for /hrac/<id>.

    MISSING when no such leaderboard user exists. A members_only player resolves
    to None instead: the row is there and the page works for signed-in visitors,
    so it must not become a 404 for them -- the name is simply withheld.
    """
    from leaderboard.models import User as LeaderboardUser
    from accounts.models import Profile

    lb_user = LeaderboardUser.objects.filter(pk=user_id).only("id", "name").first()
    if lb_user is None:
        return MISSING

    profile = (
        Profile.objects.filter(leaderboard_user=lb_user).select_related("user").first()
    )
    name = _public_player_name(lb_user, profile)
    return _player_card(request, name) if name else None


def _profile_metadata(request, username):
    """Card for /profil/<username>.

    The username in the URL identifies an account; the previewable name still
    comes from the linked leaderboard user through the consent gate. An account
    with no leaderboard link is a real profile page with nothing to preview
    (None), while a username belonging to nobody is MISSING.
    """
    from accounts.models import Profile

    profile = (
        Profile.objects
        .filter(user__username=username)
        .select_related("user", "leaderboard_user")
        .first()
    )
    if profile is None:
        return MISSING
    if profile.leaderboard_user is None:
        return None

    name = _public_player_name(profile.leaderboard_user, profile)
    return _player_card(request, name) if name else None


# Walked in order; first regex that matches the path wins.
_ROUTES = (
    (_EVENT_DETAIL_RE, _event_metadata),
    (_PLAYER_DETAIL_RE, _player_metadata),
    (_PROFILE_DETAIL_RE, _profile_metadata),
)


def metadata_for(request):
    """Resolve the request path to the `PageMeta` used for the tags."""
    path = request.path.strip("/")

    for pattern, resolve in _ROUTES:
        match = pattern.match(path)
        if match is None:
            continue
        result = resolve(request, **match.groupdict())
        if isinstance(result, PageMeta):
            return result
        if result is MISSING:
            return _defaults(request, exists=False)
        break  # resolver owns the path but has no card -- use the defaults

    page_title = _PAGE_TITLES.get(path)
    if page_title:
        return _defaults(request, title=f"{page_title} — {SITE_NAME}")
    return _defaults(request)


def _jsonld_tag(data):
    """Render a JSON-LD block.

    HTML escaping is WRONG inside <script>: the browser does not decode entities
    there, so `escape()` would turn a quote into a literal `&quot;` and break the
    JSON. The one real hazard is a `</script>` sequence in the data closing the
    tag early, so every `<` goes out as the `\\u003c` escape -- still valid JSON,
    and impossible to break out of.
    """
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")
    return f'<script type="application/ld+json">{payload}</script>'


def render_tags(meta):
    """`PageMeta` -> the ``<head>`` block, with every value escaped for its context."""
    title = escape(meta.title)
    description = escape(meta.description)
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
    if meta.url:
        tags.append(f'<meta property="og:url" content="{escape(meta.url)}" />')
    if meta.image:
        image = escape(meta.image)
        tags.append(f'<meta property="og:image" content="{image}" />')
        tags.append(f'<meta name="twitter:image" content="{image}" />')
        tags.append('<meta name="twitter:card" content="summary_large_image" />')
    else:
        tags.append('<meta name="twitter:card" content="summary" />')
    if meta.canonical:
        tags.append(f'<link rel="canonical" href="{escape(meta.canonical)}" />')
    if meta.robots:
        tags.append(f'<meta name="robots" content="{escape(meta.robots)}" />')
    if meta.jsonld:
        tags.append(_jsonld_tag(meta.jsonld))
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

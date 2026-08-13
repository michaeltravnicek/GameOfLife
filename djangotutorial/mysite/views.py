import logging
import os

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from . import og

logger = logging.getLogger(__name__)

# path -> (mtime, text). The shell is a handful of KB but it is read on every
# non-API request, so keep it in memory and re-read only when the build changes.
_shell_cache = {}


def _resolve_index_path():
    index_path = os.path.join(settings.STATIC_ROOT, "react", "index.html")
    if os.path.exists(index_path):
        return index_path
    # Dev fallback: try the source frontend dir
    alt = os.path.join(settings.BASE_DIR.parent, "frontend", "dist", "index.html")
    if os.path.exists(alt):
        return alt
    raise Http404(
        "React build not found. Run `cd frontend && npm run build` "
        "and ensure the output is collected into staticfiles/react/."
    )


def _shell_html(index_path):
    """Read the built index.html, memoised on the file's mtime."""
    mtime = os.path.getmtime(index_path)
    cached = _shell_cache.get(index_path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(index_path, encoding="utf-8") as fh:
        html = fh.read()
    _shell_cache[index_path] = (mtime, html)
    return html


@ensure_csrf_cookie
def react_index(request):
    """Serve the built React index.html for any non-API/non-admin route.

    The shell's <title> is swapped for per-route Open Graph tags on the way out
    (see `mysite.og`) so link previews work -- crawlers never run React, so this
    is the only chance to describe the page to them.

    Side effect: ensure_csrf_cookie sets the csrftoken cookie so React
    can include it in subsequent POST requests.
    """
    index_path = _resolve_index_path()
    html = _shell_html(index_path)
    try:
        html = og.inject(html, og.metadata_for(request))
    except Exception:  # noqa: BLE001 -- metadata is decoration; never 500 the SPA
        logger.warning("OG tag injection failed (serving plain shell).", exc_info=True)
    return HttpResponse(html, content_type="text/html")


@never_cache
def healthz(request):
    """Liveness probe for Render's health check, and for anything watching uptime.

    Why not just `/`: that serves the SPA shell from a memoised file read, so it
    answers 200 with the database face-down. A check that cannot fail is not a
    check — it means an outage looks healthy until a person notices.

    Touches both dependencies that make the site work at all: one trivial query
    (is Postgres reachable and accepting connections) and one cache round-trip
    (is Redis there). Nothing else — a probe that walks the whole app becomes a
    reason for restarts of its own.

    Never authenticated: the prober has no session, and the response says
    nothing an attacker doesn't already know from the site being up.
    """
    checks = {}
    ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — the point is to report, not raise
        logger.warning("healthz: database check failed: %s", exc)
        checks["database"] = "fail"
        ok = False

    try:
        cache.set("healthz", "1", 10)
        # Read it back: a cache that accepts writes and returns nothing is the
        # failure mode that silently doubles every page's query count.
        checks["cache"] = "ok" if cache.get("healthz") == "1" else "fail"
        ok = ok and checks["cache"] == "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("healthz: cache check failed: %s", exc)
        checks["cache"] = "fail"
        ok = False

    return JsonResponse({"ok": ok, **checks}, status=200 if ok else 503)


def api_not_found(request, exception=None):
    """JSON 404 for /api/ paths, plain 404 for everything else.

    Wired as the project-wide handler404. Without it a mistyped endpoint hands
    the SPA an HTML error page, axios tries to parse it as JSON, and the user
    sees a generic parse failure instead of "not found" — a wrong turn that
    looks like a broken app.

    Unknown *React* routes never arrive here: the SPA catch-all in urls.py
    matches them first and serves index.html, so the client-side NotFound page
    still renders. What reaches this handler is a real Django 404 — the admin,
    a missing media file, a view raising Http404 — and those must keep saying
    404. (An earlier version re-rendered the SPA shell here, which turned every
    one of them into a cheerful 200.)
    """
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Nenalezeno."}, status=404)
    return HttpResponse("Nenalezeno.", status=404, content_type="text/plain; charset=utf-8")


def robots_txt(request):
    """Serve /robots.txt.

    Tells well-behaved crawlers to skip everything that is either private or a
    functional dead end (the JSON API, auth screens, create/edit forms, the
    feedback console) so they spend their crawl budget on real content, and
    points them at the sitemap. This is guidance, not access control -- anything
    that must actually be protected is enforced server-side, not here.

    The admin path is listed ONLY while it sits at the default /admin/, which
    every crawler and scanner already probes anyway. Once ADMIN_URL moves it
    somewhere non-obvious, naming it here would broadcast the one thing the move
    was meant to keep quiet -- robots.txt is a world-readable file, so a
    "Disallow" line is a published address, not a hidden one. Use an
    `X-Robots-Tag: noindex` response header at the edge instead.
    """
    default_admin = settings.ADMIN_URL == "admin/"
    lines = [
        "User-agent: *",
        *(["Disallow: /admin/"] if default_admin else []),
        "Disallow: /api/",
        "Disallow: /prihlasit",
        "Disallow: /registrace",
        "Disallow: /zapomenute-heslo",
        "Disallow: /obnova-hesla/",
        "Disallow: /upravit-profil",
        "Disallow: /events/vytvorit",
        "Disallow: /events/*/upravit",
        "Disallow: /sprava/",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def sentry_debug(request):
    """Raise on purpose, to confirm errors actually reach Sentry.

    Superuser-only. Sentry's onboarding suggests an unauthenticated
    `sentry-debug/` route, but shipping one gives anyone on the internet a
    button that generates 500s — free quota exhaustion and log noise. Gating it
    still allows verifying the real production pipeline (log in to /admin/,
    then hit this URL), which a DEBUG-only route would not.
    """
    if not request.user.is_superuser:
        raise Http404
    raise RuntimeError("Sentry smoke test — this error is intentional.")


def whoami(request):
    """Show how the app sees the client's IP through the proxy chain.

    Superuser-only. PROXY_COUNT has to match the real number of hops
    (Cloudflare -> Render -> gunicorn); if it's wrong, the rate limiter and the
    axes lockout key on the wrong address and every visitor shares one bucket.
    That's invisible until it bites, so this makes it checkable in production:

        client_ip should equal your own public IP.

    If it shows a Cloudflare or Render address instead, adjust the PROXY_COUNT
    environment variable (no redeploy needed) until it doesn't.
    """
    from django.conf import settings as conf
    from django.http import JsonResponse

    if not request.user.is_superuser:
        raise Http404

    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    chain = [part.strip() for part in xff.split(",") if part.strip()]
    proxies = conf.PROXY_COUNT
    # Same indexing DRF's throttling uses.
    client_ip = chain[-proxies] if proxies and len(chain) >= proxies else (
        chain[0] if chain else request.META.get("REMOTE_ADDR")
    )

    return JsonResponse({
        "PROXY_COUNT": proxies,
        "x_forwarded_for": chain,
        "x_forwarded_for_length": len(chain),
        "remote_addr": request.META.get("REMOTE_ADDR"),
        "cf_connecting_ip": request.META.get("HTTP_CF_CONNECTING_IP"),
        "computed_client_ip": client_ip,
        "hint": "computed_client_ip must equal your own public IP address",
    })

"""Project-local middleware."""
import hmac

from django.conf import settings
from django.http import HttpResponseForbidden


class RequireCloudflareOriginMiddleware:
    """Reject traffic that did not arrive through the Cloudflare proxy.

    Render gives every web service a public ingress with no inbound IP firewall,
    so the usual "allow only Cloudflare's IP ranges at the origin" cannot be done
    here. Hiding the origin address is not a substitute: the A record pointed
    straight at Render before the Cloudflare migration, and historical-DNS
    services keep that forever.

    So instead of secrecy, this checks for something only Cloudflare can supply.
    A Transform Rule stamps ``X-Origin-Verify`` on every request it forwards; a
    request that arrives without it did not come through the edge, which means it
    also skipped the WAF, the rate limits and Access on the admin path. Those get
    403 before any view — and, importantly, before anything trusts their headers:
    a direct caller can forge X-Forwarded-For freely, which is what would
    otherwise make the per-IP throttle and the (ip, username) axes lockout
    evadable.

    Deliberately inert until ORIGIN_SHARED_SECRET is set, so the code can ship and
    be verified (see /whoami/) before enforcement is switched on. Turning it on is
    an env-var change, not a deploy — and turning it back off is too, which is the
    escape hatch if the Transform Rule ever stops firing.
    """

    #: Render's health check reaches the service on its internal network, never
    #: through the *site's* Cloudflare zone, so it can never carry the header.
    #: Everything here is unauthenticated and side-effect free.
    #:
    #: Note the missing trailing slash: the route is "healthz/", and APPEND_SLASH
    #: would redirect "/healthz" to it — but this middleware runs before
    #: CommonMiddleware, so a health check configured without the slash would be
    #: 403'd before the redirect could happen, and Render would kill the service.
    EXEMPT_PREFIXES = ("/healthz",)

    def __init__(self, get_response):
        self.get_response = get_response
        self.secret = getattr(settings, "ORIGIN_SHARED_SECRET", "")

    def __call__(self, request):
        if self.secret and not request.path.startswith(self.EXEMPT_PREFIXES):
            # compare_digest: the header is attacker-supplied, so keep the
            # comparison constant-time rather than leaking the prefix length.
            supplied = request.headers.get("X-Origin-Verify", "")
            if not hmac.compare_digest(supplied, self.secret):
                return HttpResponseForbidden("direct origin access denied")
        return self.get_response(request)


class AdminCSPExemptMiddleware:
    """Allow inline <script> on the Django admin only, keeping the site CSP strict.

    The site-wide Content-Security-Policy uses ``script-src 'self'`` — no inline
    JavaScript, which is where an XSS payload would actually run. The Django admin,
    though, ships inline <script> blocks (date/time widgets, inline formsets), and
    a strict script-src can silently break them — and unlike the SPA, nothing about
    that failure is visible server-side. So rather than weakening script-src for the
    whole site, we add ``'unsafe-inline'`` to script-src for admin paths only. The
    admin sits behind auth (and, in production, an obscured URL + edge auth), so the
    relaxation is contained to a small, privileged surface.

    Implementation: django-csp merges a per-response ``_csp_update`` dict into the
    policy — the same hook its ``csp_update`` view decorator sets. This middleware
    must be listed *after* ``csp.middleware.CSPMiddleware`` so that, on the response
    leg (which runs bottom-up), it sets the attribute before CSPMiddleware builds the
    header.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # ADMIN_URL already carries a trailing slash (see settings.py).
        self._admin_prefix = "/" + settings.ADMIN_URL

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self._admin_prefix):
            # Additive: script-src becomes "'self' 'unsafe-inline'" for admin only.
            response._csp_update = {"script-src": ["'unsafe-inline'"]}
        return response

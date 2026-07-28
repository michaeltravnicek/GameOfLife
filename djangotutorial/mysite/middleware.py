"""Project-local middleware."""
from django.conf import settings


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

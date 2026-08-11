# Security reference

## Six root causes

Nearly every web vulnerability traces to one of these. Reason from the cause rather than memorizing a checklist.

| Root cause | What it produces | Mitigations |
|---|---|---|
| Code and data share one string (HTML, SQL, shell can't tell them apart) | SQL injection, XSS, template injection, path traversal | ORM (no `.raw()`), autoescaping (no `mark_safe`/`\|safe`), JSX (no `dangerouslySetInnerHTML`), CSP |
| Browsers attach cookies automatically (ambient authority) | CSRF | `SameSite=Lax`, CSRF token |
| The client is under attacker control | IDOR, field tampering, bypassed validation | Filtered querysets, `read_only_fields`, server-side validation |
| The network is untrusted | interception, MITM, session theft | HTTPS, HSTS, `Secure` cookies |
| Resources are finite | brute force, DDoS, resource exhaustion | CDN rate limits, throttling, django-axes, upload limits |
| State is shared where it shouldn't be | cache poisoning, cross-user data leaks | `never_cache`, `Vary`, CDN bypass rules |

Quick code audit:

```bash
grep -rn "mark_safe\|\|safe\|\.raw(\|\.extra(\|dangerouslySetInnerHTML\|csrf_exempt" .
```

## Object-level authorization (highest risk)

DRF's `permission_classes` answers "may this user call this endpoint". It does **not** answer "may they touch this record". That second check is not automatic and is the most common real vulnerability in DRF projects.

```python
# WRONG — any authenticated user can delete anything
class RSVPViewSet(ModelViewSet):
    queryset = RSVP.objects.all()
    permission_classes = [IsAuthenticated]

# RIGHT
class RSVPViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = RSVPSerializer

    def get_queryset(self):
        return RSVP.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
```

Filtering the queryset beats `has_object_permission`: it applies to list, detail, update, and delete at once, can't be forgotten on one method, and returns 404 instead of 403 so it doesn't leak record existence.

Pair it with read-only fields, or a client will POST its own values:

```python
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        read_only_fields = ["user", "points", "is_staff", "created_at"]
```

Also cap pagination (`max_page_size`), or `?page_size=1000000` becomes a DoS.

**Verify:** with a second account, `curl` the first account's records by id/slug. Must return 404. Try PATCHing a privileged field. Must not change.

## Security settings baseline

```python
DEBUG = False
ALLOWED_HOSTS = ["example.com", "www.example.com"]
SECRET_KEY = os.environ["SECRET_KEY"]
CSRF_TRUSTED_ORIGINS = ["https://example.com"]

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600            # raise to 31536000 after verifying
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False          # the SPA must read this one

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
```

Notes that matter:

- `SECURE_PROXY_SSL_HEADER` is **required** behind Render/Fly/Heroku-style load balancers. TLS terminates at the balancer, Django sees HTTP, and without it `SECURE_SSL_REDIRECT` causes an infinite redirect loop.
- HSTS is a promise the browser remembers and cannot be revoked early. Start with a short TTL.
- `DEBUG = True` in production leaks variable values and settings in tracebacks.
- `ALLOWED_HOSTS` blocks Host header injection into password-reset emails.
- If the frontend is served from the same origin, CORS is unnecessary. `CORS_ALLOW_ALL_ORIGINS = True` should be removed.

Run `python manage.py check --deploy` against production settings.

## CSRF with a SPA

Session auth means CSRF protection is required. The SPA must echo the token:

```js
axios.defaults.xsrfCookieName = "csrftoken";
axios.defaults.xsrfHeaderName = "X-CSRFToken";
axios.defaults.withCredentials = true;
```

When it fails, the fix is always the header — never `@csrf_exempt`, never removing the middleware.

## Rate limiting

Two layers with different jobs:

- **CDN rate limiting rules** stop volume before it reaches the origin. This is the only thing that works against real DDoS.
- **Application throttling** is smarter but runs on your server.

```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "300/min"},
}
```

For login brute force, django-axes. Behind a proxy this is essential or you lock out the load balancer:

```python
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_IPWARE_PROXY_COUNT = 1
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR"]
```

## Admin hardening

Admin is full CRUD over every model including users, and it sits at a path every bot on the internet scans automatically. Layer defenses:

1. **Edge auth (Cloudflare Access or equivalent) on `/admin/*`** — highest value by far. Unauthenticated requests never reach Django. 15 minutes to set up.
2. **Move it off the default path** via env var. This is obscurity, not security — its real value is removing bot noise so a genuine attempt is visible in logs. Do not put the path in `robots.txt`; send `X-Robots-Tag: noindex` instead.
3. **Bypass CDN cache on `/admin/*`** — it returns fully personalized content including CSRF tokens.
4. **MFA** via django-otp `OTPAdminSite`, unless edge auth already provides it.
5. **Work as a staff user, not superuser.** A compromised staff session without `auth.User` permissions can't mint new access.

URL ordering matters — specific patterns above the SPA catch-all:

```python
urlpatterns = [
    path(os.environ["ADMIN_URL"], admin.site.urls),
    path("api/", include("api.urls")),
    re_path(r"^(?P<path>.*)$", spa_view),      # last
]
```

Link to admin with a plain `<a href>`, never a client-side router `<Link>` — the latter never reaches the server.

## CSP

Last line of defense: even if a script is injected, the browser refuses to run it.

```python
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "img-src": ["'self'", "https://media.example.com", "data:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
    }
}
```

`frame-ancestors: 'none'` supersedes `X-Frame-Options` and blocks clickjacking. Always deploy in report-only first — React and Tailwind commonly need inline styles, and enforcing blindly breaks the app.

## Upload safety

When uploads go to object storage via presigned URLs, three things still need handling server-side:

1. Generate the filename yourself (`uuid4()`). Never trust the client's — `../../settings.py` is the classic.
2. Constrain size and MIME type in the presigned policy, not after upload.
3. Serve media from a **different hostname** than the app. An uploaded SVG with an embedded script served from the app's origin runs with access to its cookies; from a separate host it's inert.

Reprocessing images (resize, re-encode) also strips metadata and any appended payload.

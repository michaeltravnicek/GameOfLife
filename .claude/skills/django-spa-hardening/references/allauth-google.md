# Social login with django-allauth

`django-allauth` is the only maintained option worth recommending in Django. `python-social-auth` is effectively dead.

Rough effort: **Google is about half a day.** Apple is one to two days plus $99/year — see the end of this file before agreeing to it.

## Setup

```bash
pip install "django-allauth[socialaccount]"
```

```python
INSTALLED_APPS = [
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
MIDDLEWARE += ["allauth.account.middleware.AccountMiddleware"]

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "secret": os.environ["GOOGLE_CLIENT_SECRET"],
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
```

Put credentials in settings from environment variables rather than the `SocialApp` admin model — otherwise anyone with admin access can read the client secret.

Google Cloud Console: new project → OAuth consent screen → Credentials → OAuth client ID (Web application) → redirect URI `https://example.com/accounts/google/login/callback/`.

Two common failures:

- **Redirect URI must match exactly**, including the trailing slash and the `www` variant. Google returns `redirect_uri_mismatch` with no further detail.
- **HTTPS behind a proxy.** allauth builds the callback from `request.build_absolute_uri()`. Without `SECURE_PROXY_SSL_HEADER` it sends `http://` and Google rejects it.

## Account takeover via email matching (critical)

The most important setting in this file.

A user has a password account with `user@example.com`. An attacker creates a provider account with the same address and signs in. If allauth auto-links social accounts to existing users by email, the attacker has taken over the account **without knowing the password**.

```python
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"     # Google already verified it
```

Linking should happen only when the user is already authenticated and explicitly connects the account in settings.

## Never grant is_staff automatically (critical)

If `is_staff = True` ever reaches the user-creation path, anyone with a Google account opens the admin. Django doesn't do this by default, but custom signals or adapters can. Make it explicit:

```python
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

class SocialAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])
        return user
```

```python
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SocialAdapter"
```

## Wiring to a React SPA

With session cookies on a shared origin, use the redirect flow. It's the least code and preserves the existing auth model:

```jsx
<a href="/accounts/google/login/?process=login">Sign in with Google</a>
```

A plain `<a href>`, not a router `<Link>` — this must be a full server navigation. Everything else happens outside React: Django redirects to Google, handles the callback, creates or finds the user, sets the session cookie, and redirects to `LOGIN_REDIRECT_URL`. React reboots already authenticated. No tokens, no `localStorage`.

allauth's headless mode (JSON API) is the alternative when a modal login without page transition is required. It's more work; don't reach for it by default.

Requests still need the CSRF header:

```js
axios.defaults.xsrfCookieName = "csrftoken";
axios.defaults.xsrfHeaderName = "X-CSRFToken";
axios.defaults.withCredentials = true;
```

## Don't route admin through social login

Technically trivial — allauth uses the standard Django session, so a staff user passes into admin with no changes. But it puts admin behind the same path ordinary users take, so any misconfiguration in the social flow becomes an admin exposure. Keep admin behind an independent edge auth layer and use allauth only for public users. Defenses should be layered, not shared.

## Apple: what makes it expensive

Recommend deferring unless there's an iOS wrapper or explicit demand. Sign in with Apple is only *required* for iOS apps that offer other social logins — a web app doesn't need it.

Three things differ from every other provider:

1. **The client secret is a JWT that expires.** Apple gives a `.p8` private key; you sign an ES256 JWT with a maximum lifetime of six months. It breaks by itself unless rotation is automated (a cron job, or let allauth compute it at runtime from the key, team id, and key id).
2. **The callback is a cross-site POST** (`response_mode=form_post`), which collides with `SameSite=Lax` — the state cookie isn't sent. allauth handles this with a separate `SameSite=None; Secure` cookie, but unexplained "state mismatch" errors trace here.
3. **User data arrives once.** The name is sent only on the very first sign-in. "Hide My Email" yields a relay address, and sending to it requires verifying your domain in the Apple developer portal.

Plus $99/year for the Apple Developer Program.

## Verification

- Signing up with Google from a private window creates a user with `is_staff = False`
- An existing password account with the same email does **not** get auto-linked
- The session cookie shows HttpOnly and Secure
- Login is rate-limited (see `security.md`)

"""allauth adapters — the security-critical half of social login.

The OAuth wiring in settings.py is boilerplate. These two classes are where the
actual decisions live, and both exist to stop a specific attack rather than to
make anything work.
"""
import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    """Local (password) accounts.

    Signup through allauth's own forms is closed: registration goes through
    `register_api` + CustomUserCreationForm, which records GDPR consent and
    enforces the username/e-mail rules. Leaving allauth's signup open would be a
    second, weaker door into account creation that bypasses both.
    """

    def is_open_for_signup(self, request):
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Google (and any future provider) sign-in."""

    def is_open_for_signup(self, request, sociallogin):
        """Google signup stays open even though allauth's own signup is closed.

        allauth's default delegates to the account adapter, which returns False
        above; without this every first-time Google user is bounced to an
        unstyled `signup_closed.html`. The password door stays shut so that
        registration goes through register_api (consent, username rules) —
        save_user() below applies the same to the Google path. This does not let
        a Google login attach to an existing local account: both
        SOCIALACCOUNT_EMAIL_AUTHENTICATION and _AUTO_CONNECT are off.
        """
        return True

    def on_authentication_error(self, request, provider, error=None, exception=None,
                                extra_context=None):
        """Record why a social login failed.

        allauth's own hook is a no-op, so every failure -- a client secret that
        no longer matches, an authorization code that arrived twice, a `state`
        that did not survive the round trip, a consent screen still in Testing
        that Google refused -- renders the same generic Czech error page and
        leaves nothing behind. This is the one leg of the flow no test can
        exercise (it needs a real Google account), which makes it the last place
        that should be silent.

        ERROR level on purpose: sentry_sdk's logging integration turns a record
        at this level into an event, so the reason reaches Sentry as well as the
        Render log. `error` is allauth's AuthError code; `exception` carries
        Google's own message (invalid_client, invalid_grant, …).
        """
        logger.error(
            "social login failed: provider=%s error=%s exception=%r",
            getattr(provider, "id", provider), error, exception,
        )
        return super().on_authentication_error(
            request, provider, error=error, exception=exception,
            extra_context=extra_context,
        )

    def is_auto_signup_allowed(self, request, sociallogin):
        # Skip allauth's intermediate "confirm your details" form. Google already
        # supplies a verified e-mail and a name, and the extra screen buys
        # nothing here.
        return True

    def save_user(self, request, sociallogin, form=None):
        """Create the local user for a social login.

        Two things are enforced here, and neither is allauth's default behaviour
        to be relied on:

        1. **Never staff.** If `is_staff=True` ever reached this path, anyone
           with a Google account would have an admin login. Django does not do
           this by itself, but a stray signal or a copied snippet could, and the
           blast radius is the whole site — so it is pinned explicitly rather
           than assumed.

        2. **A profile with a consent record.** Password signup records GDPR
           consent in CustomUserCreationForm.save(). Without the same thing here,
           a Google user would have no consent on file, which
           `leaderboard.privacy.profile_has_consent` reads as "never agreed" --
           so they would silently appear on the leaderboard as initials and never
           understand why. Recording it here keeps the two signup paths honest
           with each other.

           The consent is genuine only if the UI says so: the Google button must
           carry the same "by continuing you agree to the privacy policy" notice
           the registration form's checkbox does.
        """
        user = super().save_user(request, sociallogin, form=form)

        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["is_staff", "is_superuser"])

        # Imported here rather than at module level: adapters are imported during
        # app loading, before the app registry is ready for model imports.
        from accounts.models import Profile

        Profile.objects.get_or_create(
            user=user,
            defaults={
                # Server clock, not anything the client sent — same reasoning as
                # CustomUserCreationForm.save().
                "gdpr_consent_at": timezone.now(),
                "gdpr_consent_version": settings.PRIVACY_POLICY_VERSION,
            },
        )
        # Same as local registration: the account gets its own player straight
        # away, and adopts an archive row only on an exact e-mail match. Google
        # has verified this address, so here that match is as good a key as the
        # old phone number was. Name similarity still never links anything by
        # itself — that stays an admin merge (accounts.matching), because
        # claiming a namesake's points is the takeover this module exists to
        # prevent, just via the leaderboard instead of the login.
        from accounts.services import ensure_leaderboard_user
        ensure_leaderboard_user(user)
        return user

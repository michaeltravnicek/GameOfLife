"""Account-wide lockout layered on top of django-axes' per-(IP, username) lockout.

Axes counts failures per (IP, username) pair (``AXES_LOCKOUT_PARAMETERS``), which
stops one host hammering one account but does nothing about the distributed case:
200 hosts x 5 guesses each against the same account never trips a pair limit of 8.
The per-IP DRF throttles have exactly the same blind spot — they bound how fast a
single attacker can go, not how many guesses an account absorbs in total.

So this handler adds a second counter, over *all* IPs, for a single username. The
gap between the two limits is deliberate:

* the pair limit (``AXES_FAILURE_LIMIT``) is the everyday one — a human fumbling
  their password, or one host guessing;
* the account limit (``ACCOUNT_FAILURE_LIMIT``) is only reachable when many hosts
  cooperate, i.e. exactly the distributed case.

Any account-scoped counter is also a DoS lever: whoever can produce N failures for
a username can lock it. Two things keep that in check — the limit is high enough
that a real user never reaches it by accident, and an IP that has successfully
logged in as this user within ``ACCOUNT_TRUSTED_IP_DAYS`` is exempt, so the
victim's own device/network still gets in while a flood is running.

Wired up via ``AXES_HANDLER`` in settings, so it covers every path that goes
through ``authenticate()``: the DRF login endpoint, /admin/login/ and allauth.
"""
from datetime import timedelta
from logging import getLogger
from typing import Optional

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from axes.attempts import get_cool_off_threshold
from axes.handlers.database import AxesDatabaseHandler
from axes.helpers import get_client_username
from axes.models import AccessAttempt, AccessLog

log = getLogger(__name__)


class AccountAwareAxesHandler(AxesDatabaseHandler):
    """Axes' database handler plus a per-username failure counter."""

    def is_locked(self, request, credentials: Optional[dict] = None) -> bool:
        # Pair lockout first: it is the cheap check and the common one.
        if super().is_locked(request, credentials):
            return True
        return self.is_account_flooded(request, credentials)

    def is_account_flooded(self, request, credentials: Optional[dict] = None) -> bool:
        """True when one username collected too many failures across all IPs."""
        limit = getattr(settings, "ACCOUNT_FAILURE_LIMIT", 0)
        if not limit or not settings.AXES_LOCK_OUT_AT_FAILURE:
            return False
        if settings.AXES_COOLOFF_TIME is None:
            # Without a cool-off there is no window to count over, and a lockout
            # would be permanent. Refuse to guess.
            return False

        username = get_client_username(request, credentials)
        if not username:
            return False

        failures = AccessAttempt.objects.filter(
            username=username,
            attempt_time__gte=get_cool_off_threshold(request),
        ).aggregate(total=Sum("failures_since_start"))["total"] or 0
        if failures < limit:
            return False

        if self.is_trusted_ip(request, username):
            log.warning(
                "AXES: account %s is flooded (%d failures) but this IP has logged "
                "in successfully before — letting it through.", username, failures,
            )
            return False

        log.warning(
            "AXES: locking account %s after %d failed logins across all IPs.",
            username, failures,
        )
        return True

    @staticmethod
    def is_trusted_ip(request, username: str) -> bool:
        """Has this IP successfully logged in as this user recently?"""
        days = getattr(settings, "ACCOUNT_TRUSTED_IP_DAYS", 0)
        ip_address = getattr(request, "axes_ip_address", None)
        if not days or not ip_address:
            return False
        return AccessLog.objects.filter(
            username=username,
            ip_address=ip_address,
            attempt_time__gte=timezone.now() - timedelta(days=days),
        ).exists()

import logging

from allauth.socialaccount.internal.flows.signup import clear_pending_signup
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)


@never_cache
def social_signup_unavailable(request):
    """Stand-in for allauth's social signup form.

    allauth sends a Google sign-in here when it can neither log in nor sign up
    automatically: the address is not verified by Google, or it matches more
    than one account. That form is unstyled and creates accounts outside
    register_api, so the visitor goes back to the login page with a message.
    """
    logger.warning("social signup form reached; sending the visitor to /prihlasit")
    clear_pending_signup(request)
    return redirect("/prihlasit?google=nedokonceno")

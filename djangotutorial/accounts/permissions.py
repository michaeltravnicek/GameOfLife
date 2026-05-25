"""Role-based DRF permissions, keyed off ``accounts.Profile.role``."""
from rest_framework.permissions import BasePermission

from .models import Profile

_STAFF_ROLES = (Profile.ROLE_ADMIN, Profile.ROLE_PHOTOGRAPHER)


def role_of(user):
    """The user's profile role, or "" for anonymous / profileless users."""
    if not getattr(user, "is_authenticated", False):
        return ""
    profile = getattr(user, "profile", None)
    return profile.role if profile else ""


def is_staff_role(user):
    """True if the user is an admin or photographer."""
    return role_of(user) in _STAFF_ROLES


class IsAdmin(BasePermission):
    message = "Vyžaduje roli administrátora."

    def has_permission(self, request, view):
        return role_of(request.user) == Profile.ROLE_ADMIN


class IsAdminOrPhotographer(BasePermission):
    message = "Vyžaduje roli administrátora nebo fotografa."

    def has_permission(self, request, view):
        return is_staff_role(request.user)

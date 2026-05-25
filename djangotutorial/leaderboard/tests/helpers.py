"""Shared fixtures for the leaderboard test suite."""
from accounts.models import Profile
from leaderboard.models import User as LeaderboardUser

# Brno reference point used by all check-in tests.
BRNO_LAT = 49.1951
BRNO_LON = 16.6068


def make_profile_for(auth_user, *, number):
    """Link `auth_user` to a fresh LeaderboardUser via a Profile."""
    lb_user = LeaderboardUser.objects.create(number=number, name=f"Tester {number}")
    profile, _ = Profile.objects.get_or_create(user=auth_user)
    profile.leaderboard_user = lb_user
    profile.save()
    return lb_user

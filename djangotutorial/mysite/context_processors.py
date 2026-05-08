from datetime import date

from leaderboard.models import Season


def current_season(request):
    season = Season.objects.filter(is_active=True).first()
    if season is None:
        year = date.today().year
        season, _ = Season.objects.get_or_create(
            name=str(year),
            defaults={
                "start_date": date(year, 1, 1),
                "end_date": date(year, 12, 31),
                "is_active": True,
            },
        )
    return {"current_season": season}


def user_role(request):
    role = ""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, "profile", None)
        if profile is not None:
            role = profile.role or ""
    return {
        "user_role": role,
        "is_role_admin": role == "admin",
        "is_role_photographer": role == "photographer",
    }

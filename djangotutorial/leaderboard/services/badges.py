"""Serialize a player's earned badge collection for the API.

Badges hang off the leaderboard User (not the account), so a player synced from
Sheets already has a collection, and it follows them when an account links up.
"""


def badge_dict(user_badge, request=None):
    """One earned badge as the API shape. `request` makes the image URL absolute."""
    badge = user_badge.badge
    image = None
    if badge.image:
        image = (request.build_absolute_uri(badge.image.url)
                 if request else badge.image.url)
    return {
        "id": badge.id,
        "name": badge.name,
        "slug": badge.slug,
        "image": image,
        "description": badge.description,
        "awarded_at": user_badge.awarded_at.isoformat(),
    }


def badges_for(lb_user, request=None):
    """Earned badges for a leaderboard user, newest first. Empty list if none.

    One query with the badge joined in — this is called from profile and player
    detail, which already run several queries, so avoid a per-badge fetch.
    """
    if lb_user is None:
        return []
    earned = (
        lb_user.badges  # UserBadge rows (related_name on UserBadge.user)
        .select_related("badge")
        .order_by("-awarded_at")
    )
    return [badge_dict(ub, request) for ub in earned]

"""Business logic for the accounts app: auth resolution + profile payloads."""
import logging

from django.contrib.auth.models import User as AuthUser
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode

from leaderboard.image_utils import validate_upload
from leaderboard.models import Category, Season, User as LeaderboardUser, UserToEvent
from leaderboard.privacy import public_handle, visibility_for
from leaderboard.services import season_rank
from leaderboard.services.badges import badges_for

from .models import Profile

logger = logging.getLogger(__name__)


def _badge_logo_url(event, request=None):
    """Absolute URL of an event's logo, which lives on its badge. None if unset."""
    badge = event.badge
    if not badge or not badge.image:
        return None
    url = badge.image.url
    return request.build_absolute_uri(url) if request else url


# ── Auth ───────────────────────────────────────────────────────────────

def resolve_login_username(identifier):
    """Map a login identifier (username | email) to an auth username.

    Returns the matching `auth.User.username`, or None if nothing matches.
    """
    if AuthUser.objects.filter(username=identifier).exists():
        return identifier

    candidate = AuthUser.objects.filter(email__iexact=identifier).first()
    return candidate.username if candidate else None


# ── Account ↔ player ───────────────────────────────────────────────────

def ensure_leaderboard_user(user):
    """Give `user` a leaderboard player. Called by every signup path.

    An account without a player cannot check in at all (leaderboard/checkin.py),
    so the player is created up front rather than waited for. Registration is the
    only place a player appears automatically; everything else is an admin merge.

    The e-mail short-circuits that: if an archive player already carries this
    address, the account adopts that row instead of starting a second one, and
    the person's history is there from their first login.

    NOTE: this trusts an unverified e-mail. Local registration does not confirm
    the address, so someone who knows an archive player's e-mail can register
    with it and inherit that player's points. 

    Returns the LeaderboardUser. Reentrant.
    """
    from leaderboard.merging import resolve_player_id

    profile, _ = Profile.objects.get_or_create(user=user)

    # Already attached. If that player has since been merged away, follow the
    # chain -- otherwise the account points at a row that is off the leaderboard.
    if profile.leaderboard_user_id is not None:
        live = resolve_player_id(profile.leaderboard_user_id)
        if live is not None and live.pk != profile.leaderboard_user_id:
            profile.leaderboard_user = live
            profile.save(update_fields=["leaderboard_user"])
        return profile.leaderboard_user

    email = (user.email or "").strip().lower()
    name = user.get_full_name().strip() or user.username

    adopted = None
    if email:
        # all_objects + resolve: an archive row may already have been merged
        # into somebody, and the live target is what we would be adopting.
        existing = LeaderboardUser.all_objects.filter(email__iexact=email).first()
        candidate = resolve_player_id(existing.pk) if existing else None
        # Claimed by someone else -> not ours to take. Two accounts sharing one
        # address should be impossible (update_profile enforces it), but a stale
        # archive row can still collide, and silently handing over another
        # person's history is the one outcome worth writing code to prevent.
        if candidate is not None and not Profile.objects.filter(
            leaderboard_user=candidate
        ).exclude(user=user).exists():
            adopted = candidate

    if adopted is not None:
        profile.leaderboard_user = adopted
        profile.save(update_fields=["leaderboard_user"])
        logger.info(
            "Account %s adopted archive player #%s (%s) on e-mail match [automatic]",
            user.username, adopted.pk, adopted.name,
        )
        return adopted

    # None, never "": the column is unique and Postgres collapses empty strings
    # but not NULLs (see LeaderboardUser.email). Dropped entirely when the
    # address already sits on a player we may not adopt -- registration must not
    # die on a unique-constraint error because of an archive row.
    taken = bool(email) and LeaderboardUser.all_objects.filter(email__iexact=email).exists()
    lb_user = LeaderboardUser.objects.create(
        name=name,
        email=email if (email and not taken) else None,
    )
    profile.leaderboard_user = lb_user
    profile.save(update_fields=["leaderboard_user"])
    return lb_user


def reset_password(uid, token, new_password):
    """Verify a password-reset uid+token and set the new password.

    Returns ``(ok, error)`` — `error` is a user-facing message when `ok` is False.
    """
    if not (uid and token and new_password):
        return False, "Chybí údaje pro reset hesla."
    try:
        user = AuthUser.objects.get(pk=urlsafe_base64_decode(uid).decode())
    except (TypeError, ValueError, OverflowError, AuthUser.DoesNotExist):
        return False, "Neplatný odkaz pro reset."
    if not default_token_generator.check_token(user, token):
        return False, "Odkaz pro reset je neplatný nebo vypršel."
    try:
        validate_password(new_password, user)
    except ValidationError as exc:
        return False, " ".join(exc.messages)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return True, None


# ── Profile ────────────────────────────────────────────────────────────

def serialize_user(user, request=None):
    """Compact current-user payload for /me and post-login/register responses."""
    if user is None or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    photo_url = None
    if profile and profile.photo:
        photo_url = profile.photo.url
        if request is not None:
            photo_url = request.build_absolute_uri(photo_url)
    # Same single-name rule as profile_payload: linked leaderboard row wins.
    lb_name = ""
    if profile is not None and profile.leaderboard_user_id:
        lb_name = profile.leaderboard_user.name or ""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": lb_name or user.get_full_name() or user.username,
        "is_staff": user.is_staff,
        "role": profile.role if profile else "",
        "photo": photo_url,
        "instagram": profile.instagram if profile else "",
    }


def _since(profile_user, lb_user):
    """'Hraje od' month: the player's FIRST event, not the account signup.

    Many players attended events (via the Google Sheets leaderboard) long
    before registering on the web
    """
    first_event_date = None
    if lb_user:
        first_event_date = (
            UserToEvent.objects
            .filter(user=lb_user)
            .order_by("event__date")
            .values_list("event__date", flat=True)
            .first()
        )
    return (first_event_date or profile_user.date_joined).strftime("%Y-%m")


def visible_profile_user_or_404(username, request):
    """Resolve a username to a user the requester is allowed to see.

    A `members_only` profile 404s for anonymous visitors rather than 403s: a 403
    confirms the account exists, which is precisely what someone hiding their
    profile from the open internet is trying not to publish.
    """
    profile_user = get_object_or_404(AuthUser, username=username)
    if visibility_for(getattr(profile_user, "profile", None), request.user).members_only:
        raise Http404("Profile is members-only.")
    return profile_user


def profile_payload(profile_user, request):
    """Public profile dict: stats, rank, upcoming RSVPs, and per-season history.

    Honours the owner's privacy flags: hidden sections are *omitted* rather than
    zeroed, so the client can tell "hidden" from "has none" and say so, instead
    of rendering a real user as having zero points.
    """
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None
    gates = visibility_for(profile, request.user)

    total_points = 0
    total_events = 0
    rank = None
    if lb_user and not gates.hide_pts:
        agg = UserToEvent.objects.filter(user=lb_user).aggregate(
            total_points=Sum("points"),
            total_events=Count("id"),
        )
        total_points = agg["total_points"] or 0
        total_events = agg["total_events"] or 0
        if total_points > 0:
            rank = (
                LeaderboardUser.objects
                .annotate(tp=Coalesce(Sum("usertoevent__points"), 0))
                .filter(tp__gt=total_points).count()
            ) + 1

    upcoming_rsvps = []
    if profile and not gates.hide_events:
        rsvp_qs = (
            profile_user.rsvps.select_related("event")
            .filter(event__date__gte=timezone.now())
            .order_by("event__date")
        )
        upcoming_rsvps = [
            {
                "slug": r.event.slug,
                "name": r.event.name,
                "date": r.event.date,
                "place": r.event.place,
                "points": r.event.points,
                "survey_url": r.event.survey_url,
            }
            for r in rsvp_qs
        ]

    # Attended events, newest first — feeds the profile's "absolvované akce" list.
    past_events = []
    if lb_user and not gates.hide_events:
        past_qs = (
            UserToEvent.objects
            .filter(user=lb_user, event__date__lt=timezone.now())
            # badge too: the logo hangs off it, and 30 rows would otherwise be
            # 30 extra queries.
            .select_related("event", "event__badge")
            .order_by("-event__date")[:30]
        )
        past_events = [
            {
                "slug": u.event.slug,
                "name": u.event.name,
                "date": u.event.date,
                "place": u.event.place,
                # See player_payload: per-event points are the hidden total in
                # instalments, so hide_pts drops them here too.
                **({} if gates.hide_pts else {"points": u.points}),
                # The event's logo is its badge's artwork now.
                "logo": _badge_logo_url(u.event, request),
            }
            for u in past_qs
        ]

    photo_url = None
    if profile and profile.photo:
        photo_url = request.build_absolute_uri(profile.photo.url)

    fav_cats = []
    if profile:
        fav_cats = [{"id": c.id, "name": c.name} for c in profile.favourite_categories.all()]

    is_own_profile = request.user.is_authenticated and request.user == profile_user

    payload = {
        # public_handle withholds e-mail-shaped usernames (social logins default
        # the username to the e-mail): the frontend shows this as the "@handle"
        # on a public page, so a raw e-mail here would be published. None -> the
        # UI omits the handle line.
        "username":   public_handle(profile_user.username),
        "first_name": profile_user.first_name,
        # Single display name: the leaderboard row is the source of truth for
        # linked players (update_profile writes account name changes through).
        # Never fall back to the raw username — it's the e-mail for social logins.
        "full_name":  (lb_user.name if lb_user and lb_user.name
                       else (profile_user.get_full_name()
                             or public_handle(profile_user.username) or "Hráč")),
        "photo":      photo_url,
        "bio":        profile.bio if profile else "",
        "city":       profile.city if profile else "",
        "since":      _since(profile_user, lb_user),
        "instagram":  profile.instagram if profile else "",
        "strava":     profile.strava if profile else "",
        "spotify":    profile.spotify if profile else "",
        "tiktok":     profile.tiktok if profile else "",
        "favourite_categories": fav_cats,
        # Badges stay visible under both flags: they are awarded markers the user
        # chose to display, and they carry no point totals or event dates.
        "badges":         badges_for(lb_user, request),
        "is_own_profile": is_own_profile,
        # Tells the client which sections were withheld, so it can render
        # "skryto" instead of silently showing an incomplete profile.
        "hidden": [
            name for name, hidden in (
                ("points", gates.hide_pts),
                ("events", gates.hide_events),
            ) if hidden
        ],
    }
    if not gates.hide_pts:
        payload["total_points"] = total_points
        payload["total_events"] = total_events
        payload["rank"] = rank
    if not gates.hide_events:
        payload["upcoming_rsvps"] = upcoming_rsvps
        payload["past_events"] = past_events
        payload["seasons"] = (
            season_summaries(lb_user, hide_pts=gates.hide_pts) if lb_user else []
        )

    # Private account fields — only exposed to the owner so the edit form can
    # prefill them (and not blank them out on save). The privacy block belongs
    # here too: a visitor has no business reading which switches someone flipped.
    if is_own_profile:
        payload["last_name"] = profile_user.last_name
        payload["email"] = profile_user.email
        payload["privacy"] = {
            "hide_pts":     profile.hide_pts if profile else False,
            "hide_events":  profile.hide_events if profile else False,
            "members_only": profile.members_only if profile else False,
        }
    return payload


def set_profile_photo(user, photo):
    """Replace the user's avatar. Validated, then downscaled to 400×400 by Profile.save().

    Raises ValueError for a non-image / oversized upload.
    """
    validate_upload(photo)
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.photo = photo
    profile.save()
    return profile


def update_profile(user, data, files):
    """Apply account + profile updates. Raises ValueError if the username is taken."""
    profile, _ = Profile.objects.get_or_create(user=user)
    handle_changed = False

    for field in ("first_name", "last_name"):
        if field in data:
            setattr(user, field, data[field])
    # E-mail is a login identifier, so it has to stay unique and well-formed.
    # Without the uniqueness check two accounts could share an address, and
    # login-by-e-mail (resolve_login_username) would then resolve to an arbitrary
    # one of them. Case-insensitive, excluding self.
    if "email" in data:
        new_email = (data["email"] or "").strip()
        if new_email and new_email.casefold() != (user.email or "").casefold():
            if AuthUser.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                raise ValueError("Tento e-mail už používá jiný účet.")
        user.email = new_email
    new_handle = (data.get("username") or "").strip()
    if new_handle and new_handle != user.username:
        # Reject '@' in handles: usernames double as login identifiers, and
        # resolve_login_username matches a username before an e-mail. A handle
        # like "victim@example.com" would shadow that victim's e-mail login.
        if "@" in new_handle:
            raise ValueError("Přezdívka nesmí obsahovat znak @.")
        if AuthUser.objects.filter(username__iexact=new_handle).exclude(pk=user.pk).exists():
            raise ValueError("Přezdívka je obsazena.")
        user.username = new_handle
        handle_changed = True
    user.save()

    # The cached leaderboard row carries `profile_username`, so a rename that
    # skipped this would keep linking to the old handle until the TTL expired.
    if handle_changed:
        from leaderboard.cache_config import invalidate_points_dependent_caches
        invalidate_points_dependent_caches()

    # ONE display name: the linked leaderboard row mirrors the account name,
    # so profile and leaderboard can never drift apart. The board caches the
    # rendered name; LeaderboardUser.save() evicts it on a real rename.
    lb_user = profile.leaderboard_user
    if lb_user is not None:
        full_name = user.get_full_name().strip()
        if full_name and lb_user.name != full_name:
            lb_user.name = full_name
            lb_user.save(update_fields=["name"])

    for field in ("bio", "city", "instagram", "strava", "spotify", "tiktok"):
        if field in data:
            setattr(profile, field, data[field])
    for flag in ("hide_pts", "hide_events", "members_only"):
        if flag in data:
            setattr(profile, flag, str(data[flag]).lower() in ("1", "true"))
    if "photo" in files:
        profile.photo = files["photo"]
    elif data.get("remove_photo"):
        profile.photo = None
    profile.save()

    if "favourite_categories" in data:
        raw = data.getlist("favourite_categories") if hasattr(data, "getlist") else data["favourite_categories"]
        if not isinstance(raw, list):
            raw = [raw]
        ids = [int(x) for x in raw if str(x).isdigit()]
        profile.favourite_categories.set(list(Category.objects.filter(id__in=ids)[:3]))


def _season_base(season):
    return {
        "id": season.id,
        "label": season.name,
        "start": season.start_date,
        "end": season.end_date,
        "is_active": season.is_active,
    }


def season_summaries(lb_user, hide_pts=False):
    """Lightweight per-season points + rank for a user (no event lists).

    Feeds the profile's season selector; the heavy per-event data is fetched
    lazily per season via `season_detail`.

    Under `hide_pts` the season keeps its label and dates but loses its points
    and rank — a per-season total is still the total this flag withholds, only
    sliced by year.
    """
    result = []
    for season in Season.objects.all():
        if hide_pts:
            result.append(_season_base(season))
            continue
        season_pts = (
            UserToEvent.objects
            .filter(user=lb_user,
                    event__date__date__gte=season.start_date,
                    event__date__date__lte=season.end_date)
            .aggregate(s=Sum("points"))["s"] or 0
        )
        result.append({
            **_season_base(season),
            "season_pts": season_pts,
            "rank": season_rank(season, season_pts),
        })
    return result


def season_detail(lb_user, season, hide_pts=False):
    """Full breakdown for one season: points, rank, and the event list.

    `hide_pts` strips every number the events could be added up into — the
    season total, the rank, and the per-event points — while leaving the list of
    events itself, which is what the separate `hide_events` flag governs.
    """
    if lb_user is None:
        return {**_season_base(season), "season_pts": 0, "rank": None, "events": []}

    utes = (
        UserToEvent.objects
        .filter(user=lb_user,
                event__date__date__gte=season.start_date,
                event__date__date__lte=season.end_date)
        .select_related("event", "event__category")
        .order_by("event__date")
    )
    season_pts = sum(u.points for u in utes)
    payload = {
        **_season_base(season),
        "events": [
            {
                "slug":     u.event.slug,
                "name":     u.event.name,
                "place":    u.event.place,
                "date":     u.event.date,
                **({} if hide_pts else {"pts": u.points}),
                "category": {"id": u.event.category.id, "name": u.event.category.name}
                            if u.event.category else None,
            }
            for u in utes
        ],
    }
    if not hide_pts:
        payload["season_pts"] = season_pts
        payload["rank"] = season_rank(season, season_pts)
    return payload

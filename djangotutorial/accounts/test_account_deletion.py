"""Account deletion — the code behind PrivacyPage §6.

The policy promises a specific split: personal data goes, points and attendance
stay in anonymised form. These tests pin both halves, because getting either
one wrong is a problem — deleting the points breaks everyone else's standings,
and keeping the name means the promise was not kept.
"""
import tempfile

from django.contrib.auth.models import User as AuthUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from accounts.services import ensure_leaderboard_user
from leaderboard.models import (
    Event, EventFeedback, EventRSVP, PhotoLike, ProfileAnswer, ProfileQuestion,
    User as LeaderboardUser, UserPhoto, UserToEvent,
)
from leaderboard.privacy import short_name
from leaderboard.tests.helpers import make_image_upload


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AnonymizeAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.event = Event.objects.create(
            sheet_id="d1", sheet_list_id="x", name="Grilovačka", place="Brno",
            points=50, date=timezone.now(),
        )
        self.user = AuthUser.objects.create_user(
            username="odchazim", password="x",
            first_name="Jan", last_name="Novák", email="jan@example.com",
        )
        self.lb_user = LeaderboardUser.objects.create(name="Jan Novák", email="jan@example.com")
        self.profile = Profile.objects.create(
            user=self.user, leaderboard_user=self.lb_user,
            bio="Rád běhám.", city="Brno", instagram="jannovak",
            photo=make_image_upload("avatar.png"),
        )
        UserToEvent.objects.create(user=self.lb_user, event=self.event, points=50)
        EventFeedback.objects.create(
            user=self.lb_user, event=self.event, rating=9, comment="Bylo to super, díky!",
        )
        EventRSVP.objects.create(auth_user=self.user, event=self.event)
        self.photo = UserPhoto.objects.create(
            auth_user=self.user, event=self.event, image=make_image_upload("mine.png"),
        )
        self.url = reverse("api-delete-me")

    def _delete(self):
        self.client.force_authenticate(user=self.user)
        return self.client.delete(self.url)

    # ── what goes ────────────────────────────────────────────────────

    def test_account_and_profile_are_gone(self):
        self.assertEqual(self._delete().status_code, 200)
        self.assertFalse(AuthUser.objects.filter(username="odchazim").exists())
        self.assertFalse(Profile.objects.filter(pk=self.profile.pk).exists())

    def test_uploads_rsvps_and_likes_go_with_the_account(self):
        other = AuthUser.objects.create_user(username="fanousek", password="x")
        PhotoLike.objects.create(photo=self.photo, auth_user=other)

        self._delete()
        self.assertFalse(UserPhoto.objects.filter(pk=self.photo.pk).exists())
        self.assertFalse(EventRSVP.objects.filter(event=self.event).exists())
        # Someone else's like on the deleted photo goes too — the photo is gone.
        self.assertFalse(PhotoLike.objects.exists())

    def test_files_are_removed_from_storage_not_just_the_row(self):
        # Django drops the row and leaves the bytes; erasure has to mean the
        # image is actually gone.
        photo_storage, photo_name = self.photo.image.storage, self.photo.image.name
        avatar_storage, avatar_name = self.profile.photo.storage, self.profile.photo.name
        self.assertTrue(photo_storage.exists(photo_name))
        self.assertTrue(avatar_storage.exists(avatar_name))

        self._delete()
        self.assertFalse(photo_storage.exists(photo_name))
        self.assertFalse(avatar_storage.exists(avatar_name))

    def test_profile_answers_go_too(self):
        question = ProfileQuestion.objects.create(text="Co tě baví?", order=1)
        ProfileAnswer.objects.create(auth_user=self.user, question=question, answer="Běh.")
        self._delete()
        self.assertFalse(ProfileAnswer.objects.exists())

    # ── what stays ───────────────────────────────────────────────────

    def test_points_and_attendance_survive_untouched(self):
        self._delete()
        self.lb_user.refresh_from_db()
        self.assertEqual(
            UserToEvent.objects.filter(user=self.lb_user).count(), 1,
            "attendance must survive — everyone else's rank is relative to it",
        )
        self.assertEqual(UserToEvent.objects.get(user=self.lb_user).points, 50)

    def test_the_player_keeps_its_row_but_loses_its_identity(self):
        self._delete()
        self.lb_user.refresh_from_db()
        self.assertEqual(self.lb_user.name, "")
        self.assertIsNone(self.lb_user.email)
        # The board renders an empty name as "Hráč" already — no special case.
        self.assertEqual(short_name(self.lb_user.name), "Hráč")

    def test_feedback_keeps_its_rating_and_loses_its_comment(self):
        # The rating is about the event and is only read in aggregate; the
        # free text is the person talking.
        self._delete()
        feedback = EventFeedback.objects.get(event=self.event)
        self.assertEqual(feedback.rating, 9)
        self.assertEqual(feedback.comment, "")

    def test_it_is_not_a_merge(self):
        # merged_into hides a player and moves their points onto someone else.
        # Anonymising leaves them exactly where they are, still on the board.
        self._delete()
        self.lb_user.refresh_from_db()
        self.assertIsNone(self.lb_user.merged_into)
        self.assertTrue(LeaderboardUser.objects.filter(pk=self.lb_user.pk).exists())

    def test_the_anonymised_player_cannot_be_readopted(self):
        # ensure_leaderboard_user matches archive players on e-mail. If the
        # address stayed, the next person to register with it would inherit a
        # stranger's history.
        self._delete()
        newcomer = AuthUser.objects.create_user(
            username="jiny", password="x", email="jan@example.com",
        )
        adopted = ensure_leaderboard_user(newcomer)
        self.assertNotEqual(adopted.pk, self.lb_user.pk)
        self.assertEqual(UserToEvent.objects.filter(user=adopted).count(), 0)

    # ── access ───────────────────────────────────────────────────────

    def test_requires_auth(self):
        self.assertIn(self.client.delete(self.url).status_code, (401, 403))

    def test_you_can_only_delete_yourself(self):
        # There is no id in the URL at all — that is the point. Deleting is
        # scoped to request.user, so there is nothing to tamper with.
        other = AuthUser.objects.create_user(username="nekdo-jiny", password="x")
        Profile.objects.create(
            user=other, leaderboard_user=LeaderboardUser.objects.create(name="Někdo Jiný"),
        )
        self.client.force_authenticate(user=other)
        self.client.delete(self.url)

        self.assertTrue(AuthUser.objects.filter(username="odchazim").exists())
        self.lb_user.refresh_from_db()
        self.assertEqual(self.lb_user.name, "Jan Novák")

    def test_the_session_does_not_survive(self):
        self._delete()
        # A cookie pointing at a deleted row must read as a guest, not 500.
        resp = self.client.get(reverse("api-me"))
        self.assertEqual(resp.status_code, 200)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AnonymizeAccountCommandTests(TestCase):
    def setUp(self):
        self.user = AuthUser.objects.create_user(
            username="posta", password="x", email="posta@example.com",
        )
        self.lb_user = LeaderboardUser.objects.create(name="Poštovní Žádost")
        Profile.objects.create(user=self.user, leaderboard_user=self.lb_user)

    def test_command_finds_the_account_by_username(self):
        call_command("anonymize_account", "posta", "--yes")
        self.assertFalse(AuthUser.objects.filter(username="posta").exists())
        self.lb_user.refresh_from_db()
        self.assertEqual(self.lb_user.name, "")

    def test_command_finds_the_account_by_email(self):
        call_command("anonymize_account", "posta@example.com", "--yes")
        self.assertFalse(AuthUser.objects.filter(username="posta").exists())

    def test_unknown_identifier_is_an_error_not_a_silent_no_op(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("anonymize_account", "kdo-to-je", "--yes")
        self.assertTrue(AuthUser.objects.filter(username="posta").exists())


class PasswordChangeTests(TestCase):
    """Changing your own password while signed in.

    Until this existed the only route was logging out and mailing yourself a
    reset link — a strange thing to ask of someone already authenticated.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = AuthUser.objects.create_user(username="menic", password="stare-heslo-123")
        self.url = reverse("api-password-change")

    def _post(self, **body):
        self.client.force_authenticate(user=self.user)
        return self.client.post(self.url, body, format="json")

    def test_changes_the_password(self):
        resp = self._post(old_password="stare-heslo-123", new_password="nove-heslo-456")
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("nove-heslo-456"))

    def test_wrong_old_password_is_refused(self):
        # The session already proves who they are; the old password is what
        # stops a borrowed unlocked laptop becoming a permanent takeover.
        resp = self._post(old_password="uplne-jine", new_password="nove-heslo-456")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("stare-heslo-123"))

    def test_a_weak_new_password_is_refused(self):
        resp = self._post(old_password="stare-heslo-123", new_password="123")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("stare-heslo-123"))

    def test_reusing_the_same_password_is_refused(self):
        resp = self._post(old_password="stare-heslo-123", new_password="stare-heslo-123")
        self.assertEqual(resp.status_code, 400)

    def test_missing_fields_are_refused(self):
        self.assertEqual(self._post(old_password="stare-heslo-123").status_code, 400)
        self.assertEqual(self._post(new_password="nove-heslo-456").status_code, 400)

    def test_requires_auth(self):
        resp = self.client.post(
            self.url, {"old_password": "a", "new_password": "b"}, format="json",
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_you_stay_logged_in_afterwards(self):
        # Changing a password rotates the session auth hash. Without
        # update_session_auth_hash the user is logged out by their own
        # successful password change.
        self.client.force_authenticate(user=self.user)
        self.client.post(
            self.url,
            {"old_password": "stare-heslo-123", "new_password": "nove-heslo-456"},
            format="json",
        )
        self.assertEqual(self.client.get(reverse("api-me")).status_code, 200)

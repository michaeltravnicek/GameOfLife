"""Profile questions: the admin authors them, members answer them.

The models (ProfileQuestion / ProfileAnswer) shipped long ago with a Django
admin registration and nothing else — no endpoint, no serializer, no UI. These
tests cover the wiring that makes them reachable.
"""
from django.contrib.auth.models import User as AuthUser
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from accounts.models import Profile
from accounts.services import ANSWER_MAX_LENGTH
from leaderboard.models import ProfileAnswer, ProfileQuestion, User as LeaderboardUser


class ProfileQuestionListTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-profile-questions")

    def test_empty_until_someone_writes_one(self):
        # The normal state on a fresh install. The edit form renders no section
        # at all rather than an empty heading.
        self.assertEqual(self.client.get(self.url).json()["questions"], [])

    def test_returns_questions_in_admin_order(self):
        ProfileQuestion.objects.create(text="Druhá?", order=2)
        ProfileQuestion.objects.create(text="První?", order=1)
        rows = self.client.get(self.url).json()["questions"]
        self.assertEqual([r["text"] for r in rows], ["První?", "Druhá?"])

    def test_public_and_cached_but_an_edit_shows_up_at_once(self):
        ProfileQuestion.objects.create(text="Původní?", order=1)
        self.assertEqual(len(self.client.get(self.url).json()["questions"]), 1)

        # Saving through the model has to drop the cache; without that an admin
        # edit sits invisible for an hour and reads as "it didn't save".
        ProfileQuestion.objects.create(text="Nová?", order=2)
        self.assertEqual(len(self.client.get(self.url).json()["questions"]), 2)


class ProfileAnswerSaveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = AuthUser.objects.create_user(username="honza", password="x")
        Profile.objects.create(
            user=self.user, leaderboard_user=LeaderboardUser.objects.create(name="Honza"),
        )
        self.q1 = ProfileQuestion.objects.create(text="Nejlepší akce?", order=1)
        self.q2 = ProfileQuestion.objects.create(text="Co tě baví?", order=2)
        self.update_url = reverse("api-profile-update")
        self.client.force_authenticate(user=self.user)

    def _save(self, **fields):
        return self.client.post(self.update_url, fields, format="multipart")

    def test_answer_is_saved_and_appears_on_the_profile(self):
        resp = self._save(**{f"answer_{self.q1.id}": "Grilovačka."})
        self.assertEqual(resp.status_code, 200)

        profile = self.client.get(
            reverse("api-profile", kwargs={"username": "honza"})
        ).json()
        self.assertEqual(
            profile["answers"],
            [{"question_id": self.q1.id, "question": "Nejlepší akce?", "answer": "Grilovačka."}],
        )

    def test_unanswered_questions_are_omitted_not_blank(self):
        # An unanswered question is not a blank to render — it's a question this
        # person didn't take.
        self._save(**{f"answer_{self.q1.id}": "Ano.", f"answer_{self.q2.id}": ""})
        profile = self.client.get(
            reverse("api-profile", kwargs={"username": "honza"})
        ).json()
        self.assertEqual([a["question_id"] for a in profile["answers"]], [self.q1.id])

    def test_clearing_an_answer_deletes_the_row(self):
        self._save(**{f"answer_{self.q1.id}": "Něco."})
        self.assertTrue(ProfileAnswer.objects.filter(auth_user=self.user).exists())

        self._save(**{f"answer_{self.q1.id}": "   "})
        self.assertFalse(ProfileAnswer.objects.filter(auth_user=self.user).exists())

    def test_resaving_updates_in_place(self):
        self._save(**{f"answer_{self.q1.id}": "První verze."})
        self._save(**{f"answer_{self.q1.id}": "Druhá verze."})
        rows = ProfileAnswer.objects.filter(auth_user=self.user, question=self.q1)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().answer, "Druhá verze.")

    def test_unknown_question_id_is_ignored_not_fatal(self):
        # A member with the edit page open when a question is deleted in admin
        # must still be able to save the fields that are still valid.
        resp = self._save(**{
            "answer_999999": "Na neexistující otázku.",
            f"answer_{self.q1.id}": "Na existující.",
            "city": "Brno",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProfileAnswer.objects.filter(auth_user=self.user).count(), 1)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, "Brno")

    def test_answer_is_truncated_server_side(self):
        # The client's counter is a courtesy; the model field is a TextField
        # with no max_length of its own.
        self._save(**{f"answer_{self.q1.id}": "x" * (ANSWER_MAX_LENGTH + 250)})
        answer = ProfileAnswer.objects.get(auth_user=self.user, question=self.q1)
        self.assertEqual(len(answer.answer), ANSWER_MAX_LENGTH)

    def test_answers_are_per_account(self):
        other = AuthUser.objects.create_user(username="petra", password="x")
        Profile.objects.create(
            user=other, leaderboard_user=LeaderboardUser.objects.create(name="Petra"),
        )
        self._save(**{f"answer_{self.q1.id}": "Honzova odpověď."})

        self.client.force_authenticate(user=other)
        self._save(**{f"answer_{self.q1.id}": "Petřina odpověď."})

        self.assertEqual(
            ProfileAnswer.objects.get(auth_user=self.user, question=self.q1).answer,
            "Honzova odpověď.",
        )
        self.assertEqual(ProfileAnswer.objects.count(), 2)

    def test_saving_other_fields_leaves_answers_alone(self):
        # The privacy switches and the answers ride in the same multipart body;
        # a save from a form that never rendered the questions section (none
        # authored yet) must not wipe answers written earlier.
        self._save(**{f"answer_{self.q1.id}": "Zůstává."})
        self._save(city="Praha")
        self.assertEqual(
            ProfileAnswer.objects.get(auth_user=self.user, question=self.q1).answer,
            "Zůstává.",
        )

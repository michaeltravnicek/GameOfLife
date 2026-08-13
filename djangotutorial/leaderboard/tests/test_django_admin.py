"""Django admin surface: every page loads, and no model field is silently unreachable."""
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from leaderboard.models import Event

# Our apps only. Third-party admins (DRF's token proxy, django-axes' logs) hide
# fields on purpose and aren't ours to keep in sync.
OWN_APPS = {"leaderboard", "accounts"}

# Admins whose form deliberately omits editable model fields, as
# {"app_label.model_name": {"field", ...}}. Empty on purpose: an entry here is a
# decision to hide something from staff, so it should be argued for in review.
INTENTIONALLY_OMITTED = {}

# django-axes' log models are registered read-only (no add permission), so their
# add view answers 403 by design rather than 200.
NO_ADD_VIEW = {"axes.accessattempt", "axes.accesslog", "axes.accessfailurelog"}


def _superuser():
    return get_user_model().objects.create_superuser("admin_t", "a@t.cz", "pw12345!")


class AdminFieldCoverageTests(TestCase):
    """An explicit `fieldsets`/`fields` whitelist drifts as models grow.

    When a field is added to a model but not to the admin's whitelist, the admin
    keeps rendering happily and the field simply can't be edited -- no error,
    no warning. That is how Event.visible_to_close and Event.logo_scale became
    unreachable despite both existing to be set by hand.
    """

    def setUp(self):
        self.user = _superuser()
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user

    def _form_fields(self, model_admin):
        return set(model_admin.get_form(self.request)().fields)

    def _editable_fields(self, model, model_admin):
        declared = {f.name for f in model._meta.fields if f.editable and f.name != "id"}
        return declared - set(model_admin.get_readonly_fields(self.request))

    def test_every_editable_field_is_reachable(self):
        for model, model_admin in admin.site._registry.items():
            if model._meta.app_label not in OWN_APPS:
                continue
            label = f"{model._meta.app_label}.{model._meta.model_name}"
            with self.subTest(model=label):
                missing = (
                    self._editable_fields(model, model_admin)
                    - self._form_fields(model_admin)
                    - INTENTIONALLY_OMITTED.get(label, set())
                )
                self.assertEqual(
                    missing, set(),
                    f"{label}: fields exist on the model but not in the admin form: "
                    f"{sorted(missing)}. Add them to the admin, or list them in "
                    f"INTENTIONALLY_OMITTED with a reason.",
                )

    def test_event_visibility_and_badge_are_editable(self):
        """Named explicitly — visibility was once missing, and the badge is now
        the only way to give an event a logo."""
        form_fields = self._form_fields(admin.site._registry[Event])
        self.assertIn("visible_to_close", form_fields)
        self.assertIn("badge", form_fields)

    def test_badge_image_scale_is_editable(self):
        """The scale moved from Event to Badge; it must stay reachable somewhere."""
        from leaderboard.models import Badge
        self.assertIn("image_scale", self._form_fields(admin.site._registry[Badge]))


class AdminPagesLoadTests(TestCase):
    def setUp(self):
        self.client.force_login(_superuser())

    def test_index_loads(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_every_changelist_and_add_page_loads(self):
        for model in admin.site._registry:
            opts = model._meta
            label = f"{opts.app_label}.{opts.model_name}"
            with self.subTest(model=label):
                url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
                self.assertEqual(self.client.get(url).status_code, 200)
                if label in NO_ADD_VIEW:
                    continue
                url = reverse(f"admin:{opts.app_label}_{opts.model_name}_add")
                self.assertEqual(self.client.get(url).status_code, 200)


class EventAdminWriteTests(TestCase):
    def setUp(self):
        self.client.force_login(_superuser())

    def _payload(self, **overrides):
        start = timezone.now() + timedelta(days=14)
        data = {
            "name": "Admin akce", "description": "", "rules": "", "points": "10",
            "place": "Brno",
            "date_0": start.strftime("%Y-%m-%d"), "date_1": "18:00:00",
            "logo_scale": "1.0", "checkin_radius": "500",
            "sheet_id": "", "sheet_list_id": "", "slug": "",
            "survey_url": "", "whatsapp_url": "", "visible_to_users": "on",
        }
        data.update(overrides)
        return data

    def test_create_event_through_admin(self):
        response = self.client.post(
            reverse("admin:leaderboard_event_add"), self._payload())
        self.assertEqual(response.status_code, 302, getattr(response, "context", None)
                         and response.context["adminform"].form.errors)
        self.assertTrue(Event.objects.filter(name="Admin akce").exists())

    def test_close_preview_flag_can_be_set(self):
        """The API implements a close-preview tier; the admin has to be able to grant it."""
        self.client.post(reverse("admin:leaderboard_event_add"), self._payload(
            name="Close náhled", visible_to_users="", visible_to_close="on"))
        event = Event.objects.get(name="Close náhled")
        self.assertFalse(event.visible_to_users)
        self.assertTrue(event.visible_to_close)

    def test_badge_can_be_assigned(self):
        from leaderboard.models import Badge
        badge = Badge.objects.create(name="Karaoke", image_scale=2.5)
        self.client.post(reverse("admin:leaderboard_event_add"),
                         self._payload(name="S odznakem", badge=str(badge.id)))
        event = Event.objects.get(name="S odznakem")
        self.assertEqual(event.badge_id, badge.id)

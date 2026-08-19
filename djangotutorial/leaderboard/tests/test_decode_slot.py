"""The decode lock is what makes the worker count a free choice — so it is tested.

Decoding an image is the only thing this app does whose memory cost is chosen by
the user: a 24 MP PNG with alpha peaks at 286 MB against a ~60 MB idle worker.
If every worker could decode at once, three workers would need 858 MB and the
512 MB instance would be OOM-killed during a burst of uploads.

`decode_slot` stops that by serialising decodes across the whole instance with
`flock`, which is the part worth guarding: a per-process semaphore looks
identical in a single-process test suite and is silently useless in production,
where the contention is between separate gunicorn workers. So the test that
matters here is the one that spawns real subprocesses.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from rest_framework.test import APIClient

from leaderboard.image_utils import DecodeBusy, decode_slot
from accounts.models import Profile
from leaderboard.models import UserPhoto
from leaderboard.tests.helpers import make_image_upload


class DecodeSlotTests(SimpleTestCase):
    def test_a_single_caller_just_gets_the_slot(self):
        with decode_slot():
            pass  # no exception, no wait

    def test_re_entry_on_one_thread_does_not_deadlock(self):
        # Nothing nests today. If something ever does, it must not hang the
        # worker until gunicorn kills it.
        with decode_slot():
            with decode_slot():
                pass

    @override_settings(IMAGE_DECODE_SLOTS=1, IMAGE_DECODE_WAIT_SECONDS=0.3)
    def test_a_second_thread_waits_and_then_gives_up(self):
        holding = threading.Event()
        release = threading.Event()

        def hold():
            with decode_slot():
                holding.set()
                release.wait(timeout=5)

        keeper = threading.Thread(target=hold)
        keeper.start()
        try:
            self.assertTrue(holding.wait(timeout=5))
            with self.assertRaises(DecodeBusy):
                with decode_slot():
                    self.fail("took a slot that was already held")
        finally:
            release.set()
            keeper.join(timeout=5)

    @override_settings(IMAGE_DECODE_SLOTS=1, IMAGE_DECODE_WAIT_SECONDS=0)
    def test_zero_wait_refuses_at_once_instead_of_queueing(self):
        """WAIT_SECONDS=0 is the pure LOCK_NB case: one attempt, then give up.

        Worth pinning down because it is the setting to reach for if waiting
        ever turns out to be worse than refusing — and because "0" quietly
        meaning "wait forever" is exactly the kind of off-by-one that only
        shows up under load.
        """
        holding = threading.Event()
        release = threading.Event()

        def hold():
            with decode_slot():
                holding.set()
                release.wait(timeout=5)

        keeper = threading.Thread(target=hold)
        keeper.start()
        try:
            self.assertTrue(holding.wait(timeout=5))
            started = time.monotonic()
            with self.assertRaises(DecodeBusy):
                with decode_slot():
                    self.fail("took a held slot")
            self.assertLess(time.monotonic() - started, 0.5,
                            "zero wait still queued instead of refusing")
        finally:
            release.set()
            keeper.join(timeout=5)

    @override_settings(IMAGE_DECODE_SLOTS=2, IMAGE_DECODE_WAIT_SECONDS=0.3)
    def test_a_second_caller_fits_when_a_second_slot_exists(self):
        holding = threading.Event()
        release = threading.Event()

        def hold():
            with decode_slot():
                holding.set()
                release.wait(timeout=5)

        keeper = threading.Thread(target=hold)
        keeper.start()
        try:
            self.assertTrue(holding.wait(timeout=5))
            with decode_slot():
                pass  # the second slot is free
        finally:
            release.set()
            keeper.join(timeout=5)


class DecodeSlotIsHostWideTests(SimpleTestCase):
    """The claim the whole memory budget rests on: it holds ACROSS PROCESSES.

    An in-process semaphore passes every test above and still lets three
    gunicorn workers decode three images at once. Only a real subprocess can
    tell the two apart.
    """

    SCRIPT = textwrap.dedent("""
        import os, sys, time
        sys.path.insert(0, sys.argv[1])
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.test_settings")
        os.environ.setdefault("DJANGO_SECRET_KEY", "x")
        import django; django.setup()
        from leaderboard.image_utils import decode_slot
        hold = float(sys.argv[2])
        with decode_slot():
            print(f"IN {time.time():.3f}", flush=True)
            time.sleep(hold)
            print(f"OUT {time.time():.3f}", flush=True)
    """)

    def _spawn(self, hold):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return subprocess.Popen(
            [sys.executable, "-c", self.SCRIPT, base, str(hold)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )

    def test_two_processes_never_hold_the_slot_at_the_same_time(self):
        hold = 1.0
        first = self._spawn(hold)
        time.sleep(0.35)          # let the first one take the slot
        second = self._spawn(hold)

        windows = []
        for proc in (first, second):
            out, _ = proc.communicate(timeout=30)
            times = [float(line.split()[1]) for line in out.split("\n") if line.strip()]
            self.assertEqual(len(times), 2, f"subprocess produced: {out!r}")
            windows.append(tuple(times))

        (in1, out1), (in2, out2) = windows
        # The windows must not overlap. Whichever went second must have started
        # after the other finished — that is the entire guarantee.
        self.assertTrue(out1 <= in2 or out2 <= in1,
                        f"decodes overlapped: {windows} — the lock is not host-wide")


@override_settings(IMAGE_DECODE_SLOTS=1, IMAGE_DECODE_WAIT_SECONDS=0.2,
                   MEDIA_ROOT=tempfile.mkdtemp())
class BusySlotSurfacesAsServiceUnavailableTests(TestCase):
    """A refused upload has to look like "try again", not like a broken file.

    The status code carries the whole meaning here: 400 would tell the user
    (and any client retrying) that their image was wrong, when nothing was
    wrong with it and the same request will succeed in a moment.
    """

    def setUp(self):
        self.client = APIClient()
        # The upload endpoint gates on Profile.role, not on auth.User.is_staff.
        user = get_user_model().objects.create_user(username="fotograf", password="x")
        Profile.objects.create(user=user, role=Profile.ROLE_PHOTOGRAPHER)
        self.client.force_authenticate(user=user)

    def test_upload_returns_503_and_saves_nothing_while_the_slot_is_held(self):
        holding = threading.Event()
        release = threading.Event()

        def hold():
            with decode_slot():
                holding.set()
                release.wait(timeout=10)

        keeper = threading.Thread(target=hold)
        keeper.start()
        try:
            self.assertTrue(holding.wait(timeout=5))
            before = UserPhoto.objects.count()
            resp = self.client.post(
                reverse("api-photo-upload"),
                {"image": make_image_upload("busy.png")},
                format="multipart",
            )
            self.assertEqual(resp.status_code, 503, resp.content[:200])
            self.assertIn("za chvíli", resp.json()["error"])
            # Roughly one decode cycle — the header is what makes a client
            # retry sensibly rather than hammer or give up.
            self.assertEqual(resp.headers.get("Retry-After"), "3")
            # The write is inside transaction.atomic(), so the refused upload
            # must not leave a row behind pointing at an unprocessed file.
            self.assertEqual(UserPhoto.objects.count(), before)
        finally:
            release.set()
            keeper.join(timeout=10)

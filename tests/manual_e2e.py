"""Manual check of the editor buttons and the Python rating API.

    python tests/manual_e2e.py                              # stubbed Laya, instant
    python tests/manual_e2e.py --live                       # real Laya in this process (needs [local])
    python tests/manual_e2e.py --url http://127.0.0.1:8000  # a running `python -m laya.serve`
    python tests/manual_e2e.py --port 8766                  # serve the admin on another port (default 8765)

Prints the Ratings of the seeded page on every declared Quality, then serves the admin.
Log in at http://127.0.0.1:<port>/admin/ as admin / pw and edit "Django tips".
"""

import os
import sys
from pathlib import Path

sys.path[:0] = ["src", "."]
URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else None
LIVE = "--live" in sys.argv or URL is not None
PORT = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8765"
if URL:
    os.environ["WAGTAIL_LAYA_URL"] = URL

os.environ["DJANGO_SETTINGS_MODULE"] = "tests.e2e_settings"
import django  # noqa: E402

django.setup()

from django.core.management import call_command, execute_from_command_line  # noqa: E402

if not LIVE:
    import wagtail_laya.client as laya_client
    from tests.conftest import FakeBackend

    fake = FakeBackend(
        {"python": 0.93, "django": 0.71, "cooking": 0.05, "travel": 0.02,
         "finance": 0.1, "sport": 0.03, "calm": 0.9, "tense": 0.3, "joyful": 0.82,
         "nostalgic": 0.1},
        distributions={"readability": [0.6, 0.3, 0.1], "mood": [0.05, 0.75, 0.2]},
    )
    laya_client.get_backend = lambda: fake

db = Path("tests/test.db")
if db.exists():
    db.unlink()
call_command("migrate", verbosity=0)

from django.contrib.auth import get_user_model  # noqa: E402
from taggit.models import Tag  # noqa: E402
from wagtail.models import Page  # noqa: E402

from tests.testapp.models import ArticlePage, FeelingTag  # noqa: E402

get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
for name in ["python", "django", "cooking", "travel", "finance", "sport"]:
    Tag.objects.create(name=name)
for name in ["calm", "tense", "joyful", "nostalgic"]:
    FeelingTag.objects.create(name=name)
root = Page.objects.get(depth=1)
page = root.add_child(
    instance=ArticlePage(
        title="Django tips",
        slug="django-tips",
        intro="<p>Five ORM tricks that make Django queries faster: select_related, "
        "prefetch_related, only(), annotate() and database indexes.</p>",
    )
)
print("Mode:", f"Laya server at {URL}" if URL else "live Laya in this process" if LIVE else "stubbed Laya")
print("Ratings for", repr(page.title))
for rating in page.laya_rate():
    distribution = ", ".join(
        f"{level.label} {round(p * 100)}%" for level, p in zip(rating.levels, rating.probabilities)
    )
    print(
        f"  {rating.key}: {rating.top_label} ({rating.percent}%)  [{distribution}]"
    )
print(f"Edit page: http://127.0.0.1:{PORT}/admin/pages/{page.id}/edit/  (admin / pw)")
execute_from_command_line(["manage", "runserver", PORT, "--noreload"])

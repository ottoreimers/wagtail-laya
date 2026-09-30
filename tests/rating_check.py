"""Compare Laya's Ratings with levels set by hand.

    python tests/rating_check.py pages.json [--url http://127.0.0.1:8000]

pages.json is a list of {"title": ..., "body": ..., "expected": {"readability": "Easy", "mood": "Happy"}},
using the level labels of the test app's Qualities (readability: Easy/Medium/Hard, mood: Sad/Neutral/Happy).
Prints one line per page and Quality, then how many matched the expected level exactly (the pass
mark is 70%; "within one level" is shown too but means little on a 3-level rubric).
"""

import json
import os
import sys
from pathlib import Path

sys.path[:0] = ["src", "."]
os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
import django  # noqa: E402

django.setup()

from tests.testapp.models import ArticlePage  # noqa: E402
from wagtail_laya.article import Article  # noqa: E402
from wagtail_laya.backends import LocalBackend, ServiceBackend  # noqa: E402
from wagtail_laya.quality import rate  # noqa: E402

URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else None
backend = ServiceBackend(URL, timeout=120) if URL else LocalBackend()
pages = json.loads(Path(sys.argv[1]).read_text())

total = within_one = exact = 0
for page in pages:
    article = Article(title=page["title"], body=page["body"])
    keys = list(page["expected"])
    qualities = ArticlePage.laya_bound_qualities(*keys)
    for rating in rate(qualities, article, backend=backend):
        labels = [level.label for level in rating.levels]
        want = labels.index(page["expected"][rating.key])
        got = rating.top_index
        total += 1
        exact += got == want
        within_one += abs(got - want) <= 1
        flag = "ok " if got == want else "~  " if abs(got - want) <= 1 else "MISS"
        print(f"{flag} {page['title'][:40]:<40} {rating.key:<12} want {labels[want]:<8} got {rating.top_label:<8} "
              f"{rating.percent:3d}%")

print(f"\n{exact}/{total} ratings exact ({round(100 * exact / max(total, 1))}%, pass mark 70%); {within_one}/{total} within one level")

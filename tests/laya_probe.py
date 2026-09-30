"""Check wagtail-laya against the real Laya model: speed, language routing and the text limit.

    python tests/laya_probe.py                                 # Laya in this process
    python tests/laya_probe.py --url http://127.0.0.1:8000     # a running `python -m laya.serve`

Prints one line per check. Nothing here is asserted: read the numbers.
"""

import os
import sys
import time

sys.path[:0] = ["src", "."]
os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from tests.testapp.models import ArticlePage  # noqa: E402
from wagtail_laya.article import Article, Excerpt  # noqa: E402
from wagtail_laya.backends import LocalBackend, ServiceBackend  # noqa: E402
from wagtail_laya.models import LayaTagField  # noqa: E402

URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else None
backend = ServiceBackend(URL, timeout=120) if URL else LocalBackend()


def field(candidates):
    return LayaTagField(candidates=lambda: candidates).bind(ArticlePage, "tags")


def show(title, suggestions, seconds):
    tags = ", ".join(f"{s.name} {s.percent}%/c{s.confidence_percent}%" for s in suggestions)
    print(f"{title:<34} {seconds * 1000:7.0f} ms   {tags}")


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


print("Backend:", URL or "in-process")

english = Article(
    title="Five Django ORM tricks",
    body="select_related, prefetch_related, only(), annotate() and database indexes make Django queries faster.",
)
result, secs = timed(lambda: field(["python", "django", "cooking", "travel"]).score(english, backend=backend))
show("English, first call (includes load)", result, secs)
result, secs = timed(lambda: field(["python", "django", "cooking", "travel"]).score(english, backend=backend))
show("English, warm", result, secs)

swedish = Article(
    title="Så bakar du kanelbullar",
    body="Receptet på klassiska kanelbullar: degen, fyllningen med smör, socker och kanel, och gräddning i ugnen.",
)
result, secs = timed(lambda: field(["matlagning", "programmering", "resor", "ekonomi"]).score(swedish, backend=backend))
show("Swedish", result, secs)

many = [f"topic {i}" for i in range(38)] + ["django", "cooking"]
result, secs = timed(lambda: field(many).score(english, backend=backend))
show("40 questions in one request", result[:3], secs)

# Text limit: the only sentence about baking sits at the end of neutral filler. When Laya
# stops reading before it, the "baking" probability collapses.
settings.WAGTAIL_LAYA_MAX_CHARS = 60000
filler_sentence = "The committee met on Tuesday and approved the minutes of the previous meeting. "
decisive = "This article is entirely about baking sourdough bread at home, with a full recipe."
for size in (0, 500, 1000, 1500, 2000, 3000, 5000):
    filler = (filler_sentence * (size // len(filler_sentence) + 1))[:size]
    article = Article(title="Notes", body=filler + decisive)
    result, secs = timed(lambda: field(["baking", "politics"]).score(article, backend=backend))
    show(f"decisive sentence after {size} chars", result, secs)

readability = ArticlePage.laya_quality("readability")
for label, text in [
    ("easy text", "The cat sat on the mat. It was warm. The cat was happy."),
    ("hard text", "Notwithstanding the aforementioned epistemological caveats, the heteroskedastic "
                  "residuals preclude any unambiguous inference regarding the causal mechanism."),
]:
    rating, secs = timed(lambda: readability.rate(Excerpt(text=text), backend=backend))
    print(f"{'readability, ' + label:<34} {secs * 1000:7.0f} ms   {rating.top_label} "
          f"{rating.percent}% c{round(rating.confidence * 100)}%  {[round(p, 2) for p in rating.probabilities]}")

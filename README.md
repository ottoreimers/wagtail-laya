# wagtail-laya

wagtail-laya adds two buttons to the Wagtail page editor. Both send the text the editor
is writing to [Laya](https://huggingface.co/convaiinnovations/laya), an open-source
decision model that runs on your own servers, and show what it says.

- **Let Laya suggest tags** sits under a tag field. Laya looks at every tag your site
  already has and picks the ones that fit the page.
- **Rate with Laya** rates the page, or one field of it, on a scale you define, such as
  readability or mood. The result is shown to the editor and never saved. Rating is
  **experimental**: see "Qualities" below.

Laya runs on your own servers: no API key, no per-request cost, and page text never
leaves your infrastructure. One button press is one request, no matter how many tags or scales it
covers.

wagtail-laya is a fork of [wagtail-jev](https://github.com/rinti/wagtail-jev) by Andreas
Bernacca, which does the same with TypeSafe's hosted Jev model.

## Install

Run Laya as a separate server and point your sites at it. This is the setup for
production: one copy of the model in memory, on a GPU machine if you have one, shared
by every web worker and every site.

```sh
# on the Laya machine
pip install "laya[serve]"
LAYA_API_KEY=choose-a-secret python -m laya.serve     # listens on :8000
```

```sh
# on each Wagtail site
pip install wagtail-laya
```

```python
WAGTAIL_LAYA_URL = "http://laya.internal:8000"
WAGTAIL_LAYA_API_KEY = "choose-a-secret"   # or the LAYA_API_KEY environment variable
```

`laya.serve` reads `LAYA_HOST`, `LAYA_PORT`, `LAYA_DEVICE`, `LAYA_THREADS`,
`LAYA_PRELOAD` and `LAYA_API_KEY` from the environment. It accepts at most 64 questions
per request, which is why `WAGTAIL_LAYA_BATCH_SIZE` defaults to 40.

**For local development only**, Laya can run inside Django instead:

```sh
pip install "wagtail-laya[local]"
```

This installs Laya and PyTorch. The model downloads from Hugging Face on first use and
loads when the first button is pressed after a restart; that first press can take a
minute or more. Do not use this on a web server. Every worker process loads its own
copy of the model, and a site with pages in several languages can load both the English
and the multilingual checkpoint into one process. That is more memory than a typical
set of uWSGI or Gunicorn workers has.

Either way, add the app to your Django settings:

```python
INSTALLED_APPS = [
    "wagtail_laya",
    ...
]
```

## Use

Three changes to your page model: add `LayaTaggableMixin`, list the fields Laya should
read in `laya_text_fields`, and use `LayaTagFieldPanel` for the tag field:

```python
from modelcluster.contrib.taggit import ClusterTaggableManager
from wagtail.models import Page

from wagtail_laya.models import LayaTaggableMixin
from wagtail_laya.panels import LayaTagFieldPanel


class ArticlePage(LayaTaggableMixin, Page):
    intro = RichTextField(blank=True)
    body = StreamField([...], blank=True)
    tags = ClusterTaggableManager(through="blog.ArticleTag", blank=True)

    laya_text_fields = ("title", "intro", "body")  # what Laya reads
    # laya_tag_fields = {"tags": LayaTagField()}    # the default: tag the "tags" field

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
        LayaTagFieldPanel("tags"),  # instead of FieldPanel("tags")
    ]
```

`LayaTagFieldPanel` shows the normal tag widget with the button under it. The button
sends the current form contents to Laya, so unsaved edits count. Suggested tags are
added to the tag widget. Nothing is saved until the editor saves the page.

Laya reads the start of the page only: about the first 2,000 characters
(`WAGTAIL_LAYA_MAX_CHARS`). Put the fields that say what the page is about first in
`laya_text_fields`.

### Several tag fields

A page can have more than one tag field. Give each one its own `LayaTagField` in
`laya_tag_fields`. Each can have its own question, its own threshold, cap and margin, and
its own list of tags. By default, the list is every tag in that field's tag model.

Below, `tags` keeps the defaults. `feeling_tags` changes all three. `PromptTemplates`
holds the question, in the same three parts as the prompt settings:

```python
from wagtail_laya.models import LayaTagField, PromptTemplates


class ArticlePage(LayaTaggableMixin, Page):
    tags = ClusterTaggableManager(through="blog.ArticleTag", blank=True)
    feeling_tags = ClusterTaggableManager(through="blog.ArticleFeeling", blank=True)

    laya_tag_fields = {
        "tags": LayaTagField(),
        "feeling_tags": LayaTagField(
            templates=PromptTemplates(
                instructions="Does the mood of `state` match {tag}?",
                criteria_true="A reader would come away feeling {tag}.",
                criteria_false="{tag} does not describe the article's tone.",
            ),
            threshold=0.8,
            candidates=lambda: ["calm", "tense", "joyful"],
        ),
    }

    content_panels = Page.content_panels + [
        LayaTagFieldPanel("tags"),
        LayaTagFieldPanel("feeling_tags"),
    ]
```

Every `LayaTagField` argument is optional. Leave one out and the matching
`WAGTAIL_LAYA_*` setting from the table below is used.

### Bulk tagging

To tag many saved pages at once, use the `laya_tag_pages` management command:

```sh
manage.py laya_tag_pages blog.ArticlePage
manage.py laya_tag_pages blog.ArticlePage --apply
manage.py laya_tag_pages blog.ArticlePage --apply --publish --threshold 0.8 --ids 12 34
manage.py laya_tag_pages blog.ArticlePage --field feeling_tags
```

- With no options it only prints what Laya would suggest.
- `--apply` saves the tags as a new draft revision of each page. Add `--publish` to
  publish as well.
- `--threshold`, `--max-tags` and `--margin` override those settings. `--ids` limits
  the run to those pages.
- `--field` tags one tag field. The default is every field in `laya_tag_fields`.
- If Laya answers with an error for one page, the command prints it and goes on. If Laya
  cannot be reached or started at all, it stops at once.

### In code

Call `laya_suggest_tags()` on a saved page to get its tag suggestions:

```python
for s in page.laya_suggest_tags("tags"):
    print(s.name, s.probability, s.confidence)
```

You can also suggest tags for text that is not a saved page. First look up the tag
field with `laya_tag_field()`. Then call its `suggest()` method with an `Article`. An
Article is just a title and a body.

`suggest()` does the same work as the button. It skips tags the Article already has,
scores the rest, and keeps only the tags above the threshold and within the margin, up
to the cap.

```python
from wagtail_laya.article import Article

tag_field = ArticlePage.laya_tag_field("tags")
article = Article(title="Django ORM tips", body="select_related and friends")
for s in tag_field.suggest(article):
    print(s.name, s.probability, s.confidence)
```

If you want every tag's probability with no threshold, margin or cap, call
`tag_field.score(article)` instead.

## Qualities

**Rating is experimental.** Laya's ordinal scores are its weakest answer type. In our test
on 10 pages (7 English, 3 Swedish), 10 of 20 Ratings matched an editor's level exactly.
Mood was right on 6 of the 7 English pages, but readability came out "Medium" for 9 of
the 10 pages. Check a few Ratings against your own judgement before relying on them.

Tags say what a page is about. A **Quality** says how the text reads. Readability is
one example. Mood is another.

You define a Quality on the page model as a list of levels, from lowest to highest.
When an editor presses the button, Laya picks the level that fits the text best. It
also gives a probability for every level. This answer is called a **Rating**. Ratings
are shown to the editor and never saved. A Quality is not a tag.

### Writing a rubric

Here are two Qualities you can copy. The first rates how easy the text is to read. The
second rates its mood.

```python
from wagtail_laya.quality import Level, Quality

READABILITY = Quality(
    label="Readability",
    instructions="How easy is the text to understand?",
    levels=(
        Level("Easy", "A first-time reader follows every sentence without slowing down."),
        Level("Moderate", "A reader has to reread a few sentences or look up a term."),
        Level("Hard", "The text assumes expert knowledge or packs several ideas into each sentence."),
    ),
)

MOOD = Quality(
    label="Mood",
    instructions="What mood does the text leave the reader in?",
    levels=(
        Level("Sad", "The text dwells on loss, failure or disappointment."),
        Level("Neutral", "The text reports facts without emotional colour."),
        Level("Happy", "The text celebrates, reassures or looks forward to something."),
    ),
)
```

Each level has a short `label` and a longer `description`. The editor sees the label.
Laya judges the text against the description. Three rules for writing levels:

- **Use two to ten levels**, lowest first. Any other number raises an error when the
  panel is set up.
- **Describe a concrete situation**, not a degree. Laya judges each level on its own.
  "A reader has to reread a few sentences" works. "Moderately readable" does not.
- **Say "the text"**, never "the article" or "the field". Then the same Quality can
  rate the whole page or a single field.

The package ships no rubrics. Copy these two and adapt them to your site.

### In the editor

Add each Quality under a key in `laya_qualities`, then place the panels:

```python
from wagtail_laya.panels import LayaRatingFieldPanel, LayaRatingPanel


class ArticlePage(LayaTaggableMixin, Page):
    ...
    laya_qualities = {"readability": READABILITY, "mood": MOOD}

    content_panels = Page.content_panels + [
        LayaRatingFieldPanel("intro", keys=["readability"]),
        LayaRatingFieldPanel("body", keys=["readability", "mood"]),
        LayaTagFieldPanel("tags"),
        LayaRatingPanel(),
    ]
```

This gives the editor three buttons. One under the intro rates it on readability. One
under the body rates it on readability and mood. The last rates the whole page on
every Quality.

`LayaRatingPanel` adds a **Rate with Laya** button for the whole page. It rates the title
plus every field in `laya_text_fields`, on every Quality. It can go anywhere in a panel
list. Pass `keys` to rate only some Qualities:

```python
LayaRatingPanel(keys=["readability"], heading="Readability")
```

`LayaRatingFieldPanel` replaces `FieldPanel` for one text field. It works on a
`RichTextField`, `StreamField`, `CharField` or `TextField`. Its button rates only that
field's text, on the Qualities in `keys`. That text is called the **Excerpt**.

When a button covers exactly one Quality, it is named after it, for example **Rate
Readability with Laya**.

Both buttons work the same way:

- They send the current form contents, so unsaved edits count.
- Each Rating is shown as one line, such as `Readability: Easy (62%)`. Click it to see
  the probability of every level.
- One press is one request to Laya, however many Qualities it covers.
- Empty text makes no request.
- A misspelt key, or a field Laya cannot read, raises an error when the panel is set
  up, not when an editor presses the button.

### Rating in code

A saved page has a `laya_rate()` method. It returns one Rating per Quality, from one
request to Laya:

```python
for rating in page.laya_rate():
    print(rating.label, rating.top_label, rating.percent)  # Readability Easy 62
```

To rate only some Qualities, pass their keys: `page.laya_rate("readability")`.

Each Rating also lists the probability of every level:

```python
for level, probability in zip(rating.levels, rating.probabilities):
    print(level.label, probability)
```

You can also rate text that is not a page. First look up a Quality with
`laya_quality()`. Then call its `rate()` method with the text. The text can be an
`Article` (a title and a body) or an `Excerpt` (a single piece of text):

```python
from wagtail_laya.article import Article, Excerpt

readability = ArticlePage.laya_quality("readability")
readability.rate(Article(title="Django ORM tips", body="select_related and friends"))
readability.rate(Excerpt(text="One dense paragraph."))
readability.rate(Excerpt.from_page(page, "intro"))
```

The last line reads the `intro` field from a saved page. `rate()` returns `None` when
the text is empty.

To rate one text on several Qualities in one request, use
`wagtail_laya.quality.rate(qualities, subject)`. Every rating and scoring function also
takes a `backend=` argument, to reuse one backend across many calls; by default the
settings pick one per call.

Qualities have no threshold and no cap. They have no settings of their own. They use
the same backend, model, confidence and max chars settings as tagging. They need no
database migration.

## Settings

Put these in your Django settings. None are required. The tag settings can also be
set per tag field, as shown in "Several tag fields" above.

| Setting | Default | Meaning |
| --- | --- | --- |
| `WAGTAIL_LAYA_URL` | `None` | A Laya server's base URL. If unset, Laya runs inside Django (needs `wagtail-laya[local]`; for development only) |
| `WAGTAIL_LAYA_API_KEY` | `None` | The server's `LAYA_API_KEY`. If unset, the `LAYA_API_KEY` environment variable is used |
| `WAGTAIL_LAYA_MODEL` | `None` | Laya checkpoint: `"english"` or `"multilingual"`. If unset, Laya picks one per request by language |
| `WAGTAIL_LAYA_THRESHOLD` | `0.6` | A tag is suggested only if its probability is at least this |
| `WAGTAIL_LAYA_MAX_TAGS` | `5` | Suggest at most this many tags per page. `0` or `None` means no cap |
| `WAGTAIL_LAYA_MARGIN` | `None` | Suggest only tags at most this far below the best one, for example `0.1`. `None` means off |
| `WAGTAIL_LAYA_MAX_CHARS` | `2000` | Only the first this-many characters of the page text are sent. Laya cannot read much more |
| `WAGTAIL_LAYA_BATCH_SIZE` | `40` | How many tags to ask about in one request. Keep it at 64 or below with a Laya server |
| `WAGTAIL_LAYA_TAG_MODEL` | `"taggit.Tag"` | The model whose rows are the tags Laya can choose from |
| `WAGTAIL_LAYA_CANDIDATES` | `None` | Dotted path to a function that returns tag names. Replaces the tag model |
| `WAGTAIL_LAYA_TIMEOUT` | `30.0` | Give up on a Laya server request after this many seconds |
| `WAGTAIL_LAYA_INSTRUCTIONS` | see below | The question asked about each tag |
| `WAGTAIL_LAYA_CRITERIA_TRUE` | see below | What a "yes" answer means |
| `WAGTAIL_LAYA_CRITERIA_FALSE` | see below | What a "no" answer means |

### Prompts

Laya answers a yes/no question about each tag. Three settings hold the wording of that
question. These are the defaults:

```python
WAGTAIL_LAYA_INSTRUCTIONS = "Is `state` about {tag}?"
WAGTAIL_LAYA_CRITERIA_TRUE = "about {tag}"
WAGTAIL_LAYA_CRITERIA_FALSE = "not about {tag}"
```

`{tag}` stands for the tag name. `state` is what Laya reads: the page's title and text
as plain text.

Keep your own wording this short. On real Laya, these three short lines told relevant
from irrelevant tags far better than wagtail-jev's longer, more careful prompts, in both
English and Swedish.

To change the prompts for one tag field only, give its `LayaTagField` a
`templates=PromptTemplates(...)` argument. The "Several tag fields" section above shows
this.

## Tuning

Laya ranks tags well, but its probabilities run high. On one real site with 148 tags,
unrelated tags often scored 80–90%, and 15–30 tags per page passed the 0.6 threshold.
The best tags were still at the top of the list. So rely on the ranking more than on
the numbers:

- `WAGTAIL_LAYA_MAX_TAGS` (default 5) keeps the top few tags, however high the rest
  score.
- `WAGTAIL_LAYA_MARGIN` keeps only the tags close to the best one. With `0.1` and a best
  tag at 95%, only tags at 85% or higher are suggested. On a page that fits one tag
  clearly, that is fewer than the cap; on a page that fits many, up to the cap.
- The threshold is a floor. On a page where nothing fits, it keeps weak tags out.

Run `laya_tag_pages` without `--apply` on some pages, trying `--max-tags` and
`--margin`. Compare the output with the tags your editors would choose.

- If Laya suggests wrong tags, lower the cap or add a margin.
- If Laya misses good tags, raise the cap, widen the margin or change the prompt.

Each tag is one question to Laya, so a site with many tags waits longer for each
suggestion. On a CPU, 148 tags took about 35 seconds per page. If only some tags could
fit a page type, give its `LayaTagField` a shorter `candidates` list.

Other languages work: Laya switches to its multilingual checkpoint by itself. The tags
can stay in English. On the site above, German and Dutch pages ranked English tag names
well. English is still the most accurate. Test on your own content.

## Development

Install the package in a virtualenv and run the tests:

```sh
uv venv
uv pip install -e ".[test]"
pytest
```

To try the buttons in a browser, start a local site. By default it uses a fake Laya:

```sh
python tests/manual_e2e.py                               # fake Laya, instant
python tests/manual_e2e.py --live                        # real Laya in this process (needs [local])
python tests/manual_e2e.py --url http://127.0.0.1:8000   # a running python -m laya.serve
python tests/manual_e2e.py --port 8766                    # if port 8765 is taken
```

Log in at http://127.0.0.1:8765/admin/ with the username `admin` and the password
`pw`. Then open the "Django tips" page.

`python tests/laya_probe.py` checks the real model's speed, language routing and text
limit. `python tests/rating_check.py pages.json` compares Ratings with levels you set by
hand.

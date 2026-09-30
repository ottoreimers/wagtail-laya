# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- First release of wagtail-laya, forked from [wagtail-jev](https://github.com/rinti/wagtail-jev) (unreleased changes after 0.3.0).
- Laya backends: in-process (`pip install "wagtail-laya[local]"`, the default) or a `python -m laya.serve` server via `WAGTAIL_LAYA_URL` / `WAGTAIL_LAYA_API_KEY`.
- `TagSuggestion.confidence` and `Rating.confidence`: Laya's own confidence, reported but not filtered on. For a yes/no answer it is max(p, 1 − p) and for a score the top level's probability, so it adds nothing a threshold does not already cover.
- "Loading Laya…" message when the first request after a restart is slow.
- `WAGTAIL_LAYA_MARGIN`, `LayaTagField(margin=...)` and `laya_tag_pages --margin`: suggest only tags at most this far below the best one. Laya's ranking holds up better than its absolute probabilities.
- `LayaError`, raised for every failure to get an answer from Laya, and its subclass `LayaUnavailable` for when Laya is not installed, cannot start or cannot be reached. `laya_tag_pages` stops at once on `LayaUnavailable` instead of waiting out a timeout per page.

### Changed

- Every `Jev*` / `jev_*` / `WAGTAIL_JEV_*` name is now `Laya*` / `laya_*` / `WAGTAIL_LAYA_*`; the command is `laya_tag_pages`.
- The `client=` argument is now `backend=`.
- `WAGTAIL_LAYA_MAX_CHARS` defaults to 2000, since Laya reads at most 512 tokens per question.
- Rating is marked experimental.
- `WAGTAIL_LAYA_MAX_TAGS` defaults to 5 instead of no cap. On a real site with 148 tags, unrelated tags often scored 80–90% and 15–30 tags per page passed the 0.6 threshold. `0` (or `None`) still means no cap.
- The README recommends a `python -m laya.serve` server for production and `[local]` for development only, since each worker loads its own model (sometimes two: English and multilingual). It also notes that pages in other languages rank English tag names well.
- Tag questions are short and plain: the default prompt is "Is `state` about {tag}?" / "about {tag}" / "not about {tag}", the state is the page's title and text as plain text (no `article` or `existing_tags` keys), and tag names are no longer quoted. Measured on real Laya, wagtail-jev's longer prompt barely separated relevant from irrelevant tags.

### Removed

- The `typesafe-sdk` dependency and `WAGTAIL_JEV_API_KEY`'s TypeSafe meaning.

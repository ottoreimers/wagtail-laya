"""Flat ``WAGTAIL_LAYA_*`` Django settings with defaults."""

from django.conf import settings

DEFAULTS = {
    # Base URL of a Laya server (`python -m laya.serve`). Unset means Laya runs in this process.
    "WAGTAIL_LAYA_URL": None,
    # Bearer key for that server, matching its LAYA_API_KEY. Falls back to the LAYA_API_KEY environment variable.
    "WAGTAIL_LAYA_API_KEY": None,
    # Laya checkpoint, e.g. "english" or "multilingual". None lets Laya pick one per request by language.
    "WAGTAIL_LAYA_MODEL": None,
    # Minimum Noul probability for a tag to count as suggested.
    "WAGTAIL_LAYA_THRESHOLD": 0.6,
    # Upper bound on suggestions returned per page. None means no cap.
    "WAGTAIL_LAYA_MAX_TAGS": None,
    # Characters of page text sent as state. Laya reads at most 512 tokens per question and cuts the rest itself.
    "WAGTAIL_LAYA_MAX_CHARS": 2000,
    # Candidate tags per request. Each tag is one question; a Laya server accepts at most 64.
    "WAGTAIL_LAYA_BATCH_SIZE": 40,
    # Dotted path of the taggit model whose rows are the candidate tags.
    "WAGTAIL_LAYA_TAG_MODEL": "taggit.Tag",
    # Dotted path to a callable returning candidate tag names. Overrides the tag model.
    "WAGTAIL_LAYA_CANDIDATES": None,
    # Laya server request timeout in seconds.
    "WAGTAIL_LAYA_TIMEOUT": 30.0,
    # Prompt templates. ``{tag}`` is replaced with the candidate tag name. The state is the
    # page's title and text as plain text, which Laya calls `state`. Keep them short: on
    # real Laya, short wording separated tags far better than longer, more careful prompts.
    "WAGTAIL_LAYA_INSTRUCTIONS": "Is `state` about {tag}?",
    "WAGTAIL_LAYA_CRITERIA_TRUE": "about {tag}",
    "WAGTAIL_LAYA_CRITERIA_FALSE": "not about {tag}",
}



def get_setting(name):
    return getattr(settings, name, DEFAULTS[name])

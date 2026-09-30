"""The Tag field: one taggable manager on a page, with its own tag model, prompt
templates, threshold, margin and cap. The one place that turns an Article into Suggestions.

``LayaTagField`` is what a page declares in ``laya_tag_fields``; every attribute may be
``None`` meaning "use the ``WAGTAIL_LAYA_*`` setting". ``LayaTagField.bind`` resolves
those defaults against a model and field name once, producing a ``BoundTagField``.
Its ``score`` asks Laya one Noul question per candidate tag ("does this article belong
under tag X?") and returns every probability; ``suggest`` keeps those at or above the
threshold and within the margin of the best, capped. Questions in a request run in parallel and cannot see each other,
so each tag is judged independently and several may apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from django.apps import apps
from django.utils.module_loading import import_string

from wagtail_laya.backends import Backend
from wagtail_laya.client import ask, clip
from wagtail_laya.questions import noul
from wagtail_laya.article import Article
from wagtail_laya.settings import get_setting

@dataclass(frozen=True)
class TagSuggestion:
    """One candidate tag with Laya's probability that it applies and how sure Laya is."""

    name: str
    probability: float
    confidence: float = 1.0

    @property
    def percent(self) -> int:
        return round(self.probability * 100)

    @property
    def confidence_percent(self) -> int:
        return round(self.confidence * 100)


@dataclass(frozen=True)
class PromptTemplates:
    """Templates for the per-tag question. ``{tag}`` is replaced with the tag name."""

    instructions: str
    criteria_true: str
    criteria_false: str

    @classmethod
    def from_settings(cls) -> "PromptTemplates":
        return cls(
            instructions=get_setting("WAGTAIL_LAYA_INSTRUCTIONS"),
            criteria_true=get_setting("WAGTAIL_LAYA_CRITERIA_TRUE"),
            criteria_false=get_setting("WAGTAIL_LAYA_CRITERIA_FALSE"),
        )


@dataclass(frozen=True)
class LayaTagField:
    """Per-field configuration. Every attribute defaults to the ``WAGTAIL_LAYA_*`` settings.

    :param templates: prompt templates used for this field's tags.
    :param candidates: callable returning candidate tag names. Defaults to every
        row of the tag model behind the field.
    :param threshold: minimum probability for a suggestion.
    :param max_tags: cap on suggestions. ``0`` means no cap.
    :param margin: keep only suggestions at most this far below the best one.
    """

    templates: PromptTemplates | None = None
    candidates: Callable[[], Iterable[str]] | None = None
    threshold: float | None = None
    max_tags: int | None = None
    margin: float | None = None

    def bind(self, model, field_name: str) -> "BoundTagField":
        """Resolve every ``None`` against the settings for ``field_name`` on ``model``."""
        return BoundTagField(
            model=model,
            name=field_name,
            templates=self.templates or PromptTemplates.from_settings(),
            candidate_source=self.candidates or _default_candidate_source(model, field_name),
            threshold=get_setting("WAGTAIL_LAYA_THRESHOLD") if self.threshold is None else self.threshold,
            max_tags=get_setting("WAGTAIL_LAYA_MAX_TAGS") if self.max_tags is None else self.max_tags,
            margin=get_setting("WAGTAIL_LAYA_MARGIN") if self.margin is None else self.margin,
        )


@dataclass(frozen=True)
class BoundTagField:
    """A :class:`LayaTagField` resolved against a model and the settings. No ``None`` here."""

    model: type
    name: str
    templates: PromptTemplates
    candidate_source: Callable[[], Iterable[str]]
    threshold: float
    max_tags: int | None
    margin: float | None = None

    def candidates(self, article: Article) -> list[str]:
        """Candidate tag names for this field, minus the Article's existing tags."""
        return [c for c in self.candidate_source() if c not in article.existing_tags]

    def score(self, article: Article, *, backend: Backend | None = None) -> list[TagSuggestion]:
        """A probability for every candidate tag, unfiltered, sorted high to low.

        One Noul question per candidate, sent in batches of ``WAGTAIL_LAYA_BATCH_SIZE``.
        Blank and duplicate candidates are dropped; no candidates means no request.
        A ``backend`` you pass is used instead of the one the settings pick.
        """
        candidates = list(dict.fromkeys(c for c in self.candidates(article) if c and c.strip()))
        if not candidates:
            return []

        state = _state(article)
        results: list[TagSuggestion] = []
        for batch in _chunks(candidates, get_setting("WAGTAIL_LAYA_BATCH_SIZE")):
            questions = {f"tag_{i}": self._question(tag) for i, tag in enumerate(batch)}
            response = ask(state, questions, backend=backend)
            for i, tag in enumerate(batch):
                answer = response.nouls[f"tag_{i}"]
                results.append(TagSuggestion(tag, answer.noul, answer.confidence))
        results.sort(key=lambda s: s.probability, reverse=True)
        return results

    def suggest(self, article: Article, *, backend: Backend | None = None) -> list[TagSuggestion]:
        """:meth:`score`, keeping only suggestions at or above the threshold and at most
        ``margin`` below the best one, capped at ``max_tags``.

        Laya's probabilities run high across the board while its ranking holds up, so
        the margin and the cap, which only look at the ranking, do most of the work.

        There is no confidence gate here: for a yes/no answer Laya's confidence is
        max(p, 1 - p), so gating on it would quietly raise the threshold.
        """
        kept = [s for s in self.score(article, backend=backend) if s.probability >= self.threshold]
        if kept and self.margin is not None:
            kept = [s for s in kept if s.probability >= kept[0].probability - self.margin]
        return kept[: self.max_tags] if self.max_tags else kept

    def _question(self, tag: str) -> dict:
        # The tag goes in unquoted: on real Laya, quoting it added false positives in Swedish.
        return noul(
            self.templates.instructions.format(tag=tag),
            true=self.templates.criteria_true.format(tag=tag),
            false=self.templates.criteria_false.format(tag=tag),
        )


def _state(article: Article) -> str:
    """The page as plain text. Laya tells relevant from irrelevant tags far better with a
    plain-text state than with a nested dict; existing tags are already left out of the
    candidates, so they need not be in the state."""
    return f"{article.title}\n\n{clip(article.body)}"


def _chunks(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _default_candidate_source(model, field_name: str) -> Callable[[], Iterable[str]]:
    """``WAGTAIL_LAYA_CANDIDATES`` if set, else all rows of the field's tag model."""
    source = get_setting("WAGTAIL_LAYA_CANDIDATES")
    if isinstance(source, str):
        source = import_string(source)
    if callable(source):
        return source

    def from_tag_model():
        tag_model = _tag_model_for_field(model, field_name)
        return tag_model.objects.order_by("name").values_list("name", flat=True)

    return from_tag_model


def _tag_model_for_field(model, field_name: str):
    """The tag model behind a ``ClusterTaggableManager``/``TaggableManager``, falling back
    to ``WAGTAIL_LAYA_TAG_MODEL`` when the field has no ``through`` model."""
    try:
        return model._meta.get_field(field_name).through.tag_model()
    except Exception:
        return apps.get_model(get_setting("WAGTAIL_LAYA_TAG_MODEL"))

"""Mixin for pages that Laya can tag and rate."""

from __future__ import annotations

from typing import Mapping

from wagtail_laya.article import Article
from wagtail_laya.quality import BoundQuality, Level, Quality, Rating, rate
from wagtail_laya.tag_field import BoundTagField, LayaTagField, PromptTemplates, TagSuggestion

__all__ = ["LayaTagField", "LayaTaggableMixin", "Level", "PromptTemplates", "Quality", "TagSuggestion"]


class LayaTaggableMixin:
    """Add to a Page subclass that has one or more ``ClusterTaggableManager`` fields.

    Set ``laya_text_fields`` to the fields whose text makes up the Article,
    ``laya_tag_fields`` to a mapping of tag field name to :class:`LayaTagField`, and
    ``laya_qualities`` to a mapping of key to :class:`Quality` for Ratings.
    """

    laya_text_fields: tuple[str, ...] = ("title", "body")
    laya_tag_fields: Mapping[str, LayaTagField] = {"tags": LayaTagField()}
    laya_qualities: Mapping[str, Quality] = {}

    @classmethod
    def laya_tag_field(cls, field_name: str) -> BoundTagField:
        """The Tag field ``field_name``, with its settings defaults resolved.

        Raises :class:`LookupError` if the field is not in ``laya_tag_fields``.
        """
        try:
            config = cls.laya_tag_fields[field_name]
        except KeyError:
            raise LookupError(
                f"{cls.__name__} has no Laya tag field {field_name!r}; "
                f"configured: {', '.join(cls.laya_tag_fields) or 'none'}"
            ) from None
        return config.bind(cls, field_name)

    def laya_suggest_tags(self, field_name: str, *, backend=None) -> list[TagSuggestion]:
        """Score ``field_name`` against this page's saved content."""
        article = Article.from_page(self, field_name)
        return self.laya_tag_field(field_name).suggest(article, backend=backend)

    @classmethod
    def laya_quality(cls, key: str) -> BoundQuality:
        """The Quality declared under ``key``, checked and bound to this model.

        Raises :class:`LookupError` if the key is not in ``laya_qualities``.
        """
        try:
            quality = cls.laya_qualities[key]
        except KeyError:
            raise LookupError(
                f"{cls.__name__} has no Laya quality {key!r}; "
                f"configured: {', '.join(cls.laya_qualities) or 'none'}"
            ) from None
        return quality.bind(cls, key)

    @classmethod
    def laya_bound_qualities(cls, *keys: str) -> list[BoundQuality]:
        """The bound Qualities for ``keys``, or every declared Quality when none are given.

        Always in declaration order, whatever order the keys are given in.
        Raises :class:`LookupError` for an unknown key.
        """
        wanted = {key: cls.laya_quality(key) for key in keys or cls.laya_qualities}
        return [wanted[key] for key in cls.laya_qualities if key in wanted]

    def laya_rate(self, *keys: str, backend=None) -> list[Rating]:
        """Rate this page's saved Article on the Qualities ``keys``, or on every declared
        Quality when none are given, in one Laya request.

        Ratings come back in declaration order whatever order the keys are given in.
        Raises :class:`LookupError` for an unknown key before any request is made.
        """
        return rate(self.laya_bound_qualities(*keys), Article.from_page(self), backend=backend)

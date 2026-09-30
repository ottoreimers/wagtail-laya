from django.db import models
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import ItemBase, TagBase, TaggedItemBase
from wagtail import blocks
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page

from wagtail_laya.models import LayaTagField, LayaTaggableMixin, PromptTemplates
from wagtail_laya.quality import Level, Quality
from wagtail_laya.panels import LayaRatingFieldPanel, LayaRatingPanel, LayaTagFieldPanel


class ArticleTag(TaggedItemBase):
    content_object = ParentalKey("testapp.ArticlePage", related_name="tagged_items")


class FeelingTag(TagBase):
    class Meta:
        verbose_name = "feeling"


class ArticleFeeling(ItemBase):
    tag = models.ForeignKey(FeelingTag, on_delete=models.CASCADE, related_name="articles")
    content_object = ParentalKey("testapp.ArticlePage", related_name="feeling_items")


class ArticlePage(LayaTaggableMixin, Page):
    intro = RichTextField(blank=True)
    body = StreamField(
        [("paragraph", blocks.RichTextBlock()), ("heading", blocks.CharBlock())],
        blank=True,
    )
    tags = ClusterTaggableManager(through=ArticleTag, blank=True)
    feeling_tags = ClusterTaggableManager(
        through=ArticleFeeling, blank=True, related_name="feeling_tagged"
    )

    laya_text_fields = ("title", "intro", "body")
    laya_tag_fields = {
        "tags": LayaTagField(),
        "feeling_tags": LayaTagField(
            templates=PromptTemplates(
                instructions="Does the mood of `state` match {tag}?",
                criteria_true="A reader would come away feeling {tag}.",
                criteria_false="{tag} does not describe the article's tone.",
            ),
            threshold=0.8,
        ),
    }
    laya_qualities = {
        "readability": Quality(
            label="Readability",
            instructions="How easy is the text to understand?",
            levels=(
                Level("Easy", "A first-time reader follows every sentence."),
                Level("Medium", "A reader needs to reread some sentences."),
                Level("Hard", "The text assumes expert knowledge or is densely written."),
            ),
        ),
        "mood": Quality(
            instructions="What mood does the text leave the reader in?",
            levels=(
                Level("Sad", "The text dwells on loss or disappointment."),
                Level("Neutral", "The text reports without emotional colour."),
                Level("Happy", "The text celebrates or reassures."),
            ),
        ),
    }

    content_panels = Page.content_panels + [
        LayaRatingFieldPanel("intro", keys=["readability"]),
        LayaRatingFieldPanel("body", keys=["readability", "mood"]),
        LayaTagFieldPanel("tags"),
        LayaTagFieldPanel("feeling_tags"),
        LayaRatingPanel(),
    ]

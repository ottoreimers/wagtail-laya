import json

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, Panel

from wagtail_laya.article import text_field
from wagtail_laya.models import LayaTaggableMixin


class LayaTagFieldPanel(FieldPanel):
    """A ``FieldPanel`` for a tag field with a "Let Laya suggest tags" button beneath it.

    Use it in ``content_panels`` in place of ``FieldPanel("tags")`` on a page
    that mixes in :class:`wagtail_laya.models.LayaTaggableMixin`.
    """

    class BoundPanel(FieldPanel.BoundPanel):
        template_name = "wagtail_laya/panels/tag_field_panel.html"

        class Media:
            js = ["wagtail_laya/js/laya-suggest-controller.js"]

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            context["laya_url"] = reverse("wagtail_laya:suggest")
            context["laya_model"] = self.instance._meta.label
            context["laya_messages"] = json.dumps(
                {
                    "loading": str(_("Asking Laya…")),
                    "slow": str(_("Loading Laya… The first request after a restart can take up to a minute.")),
                    "empty": str(_("No tags passed the confidence threshold.")),
                    "added": str(_("Added: ")),
                    "error": str(_("Laya error: ")),
                }
            )
            return context


class LayaRatingPanel(Panel):
    """A panel with a "Rate with Laya" button that rates the whole Article on the page's Qualities.

    Place it anywhere in a panel list on a page that mixes in
    :class:`wagtail_laya.models.LayaTaggableMixin`. ``keys`` picks a subset of the declared
    Qualities; omit it to rate every one. Ratings are only displayed, never saved.
    """

    def __init__(self, keys=None, heading=_("Ratings"), **kwargs):
        super().__init__(heading=heading, **kwargs)
        self.keys = tuple(keys) if keys else ()

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["keys"] = self.keys
        return kwargs

    def on_model_bound(self):
        _check_rating_model(self)
        # Fail loudly here on a typo in ``keys``, not when an editor presses the button.
        self.model.laya_bound_qualities(*self.keys)

    class BoundPanel(Panel.BoundPanel):
        template_name = "wagtail_laya/panels/rating_panel.html"

        class Media:
            js = ["wagtail_laya/js/laya-rate-controller.js"]

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            context.update(
                _rating_context(
                    self.panel.model,
                    self.panel.keys,
                    empty=_("Nothing to rate yet: the page has no text."),
                )
            )
            return context


class LayaRatingFieldPanel(FieldPanel):
    """A ``FieldPanel`` for a text field with a "Rate with Laya" button beneath it that rates
    just that field's Excerpt on the Qualities ``keys``.

    Works on ``RichTextField``, ``StreamField``, ``CharField`` and ``TextField``. When one
    Quality is attached the button names it. Ratings are only displayed, never saved.
    """

    def __init__(self, field_name, *, keys, **kwargs):
        super().__init__(field_name, **kwargs)
        self.keys = tuple(keys)

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs["keys"] = self.keys
        return kwargs

    def on_model_bound(self):
        super().on_model_bound()
        _check_rating_model(self)
        # Fail loudly here on a typo in ``keys`` or a field Laya cannot read, not on button press.
        self.model.laya_bound_qualities(*self.keys)
        text_field(self.model, self.field_name)

    class BoundPanel(FieldPanel.BoundPanel):
        template_name = "wagtail_laya/panels/rating_field_panel.html"

        class Media:
            js = ["wagtail_laya/js/laya-rate-controller.js"]

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)
            context.update(
                _rating_context(
                    self.panel.model,
                    self.panel.keys,
                    field_name=self.panel.field_name,
                    empty=_("Nothing to rate yet: the field has no text."),
                )
            )
            return context


def _check_rating_model(panel):
    if not issubclass(panel.model, LayaTaggableMixin):
        raise ImproperlyConfigured(
            f"{type(panel).__name__} needs {panel.model.__name__} to mix in LayaTaggableMixin"
        )


def _rating_context(model, keys, *, empty, field_name="") -> dict:
    """Template context shared by both rating panels: the endpoint, the subject and the keys.

    ``keys`` is rendered as an explicit list so the "default to every Quality" choice is
    resolved at render time, not by the controller.
    """
    qualities = model.laya_bound_qualities(*keys)
    if len(qualities) == 1:
        button_label = _("Rate %(quality)s with Laya") % {"quality": qualities[0].label}
    else:
        button_label = _("Rate with Laya")
    return {
        "laya_url": reverse("wagtail_laya:rate"),
        "laya_model": model._meta.label,
        "laya_field": field_name,
        "laya_keys": ",".join(quality.key for quality in qualities),
        "laya_button_label": button_label,
        "laya_messages": json.dumps(
            {
                "loading": str(_("Asking Laya…")),
                "slow": str(_("Loading Laya… The first request after a restart can take up to a minute.")),
                "empty": str(empty),
                "error": str(_("Laya error: ")),
            }
        ),
    }

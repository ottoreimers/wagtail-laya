from django.apps import apps
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from wagtail.admin.auth import require_admin_access

from wagtail_laya.article import Article, Excerpt
from wagtail_laya.errors import LayaError
from wagtail_laya.models import LayaTaggableMixin
from wagtail_laya.quality import Rating, rate as rate_qualities


def _laya_model(request):
    """The LayaTaggable model named by ``laya_model``, or a 400 response."""
    try:
        model = apps.get_model(request.POST.get("laya_model", ""))
    except (LookupError, ValueError):
        return None, JsonResponse({"error": "Unknown model"}, status=400)
    if not issubclass(model, LayaTaggableMixin):
        return None, JsonResponse({"error": "Model is not LayaTaggable"}, status=400)
    return model, None


@require_admin_access
@require_POST
def suggest(request):
    """Score one tag field's candidates against the editor's current (unsaved) content.

    Expects the page edit form's data plus ``laya_model`` (``app_label.ModelName``)
    and ``laya_field`` (the tag field name). Returns
    ``{"tags": [{"name": ..., "probability": ..., "confidence": ...}]}``.
    """
    model, error = _laya_model(request)
    if error:
        return error

    field_name = request.POST.get("laya_field", "")
    try:
        tag_field = model.laya_tag_field(field_name)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    article = Article.from_form_data(model, request.POST, request.FILES, field_name=field_name)
    try:
        suggestions = tag_field.suggest(article)
    except LayaError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse(
        {"tags": [{"name": s.name, "probability": s.probability, "confidence": s.confidence} for s in suggestions]}
    )


@require_admin_access
@require_POST
def rate(request):
    """Rate the editor's current (unsaved) text on the model's Qualities in one Laya request.

    Expects the page edit form's data plus ``laya_model`` (``app_label.ModelName``) and
    zero or more ``laya_keys``; no keys means every declared Quality. With ``laya_field``
    the subject is that field's Excerpt, otherwise the whole Article. Returns
    ``{"ratings": [...]}`` in declaration order, each Rating with its key and label, the
    most likely level's label and probability, and every level's label and probability.
    Ratings are never written anywhere.
    """
    model, error = _laya_model(request)
    if error:
        return error

    try:
        qualities = model.laya_bound_qualities(*request.POST.getlist("laya_keys"))
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    field_name = request.POST.get("laya_field", "")
    try:
        if field_name:
            subject = Excerpt.from_form_data(model, field_name, request.POST, request.FILES)
        else:
            subject = Article.from_form_data(model, request.POST, request.FILES)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        ratings = rate_qualities(qualities, subject)
    except LayaError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse({"ratings": [_rating_json(r) for r in ratings]})


def _rating_json(rating: Rating) -> dict:
    return {
        "key": rating.key,
        "label": rating.label,
        "top_label": rating.top_label,
        "top_probability": rating.top_probability,
        "confidence": rating.confidence,
        "levels": [
            {"label": level.label, "probability": probability}
            for level, probability in zip(rating.levels, rating.probabilities)
        ],
    }

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from wagtail.models import Page

from tests.testapp.models import ArticlePage
from wagtail_laya.panels import LayaRatingFieldPanel, LayaRatingPanel


@pytest.mark.django_db
def test_edit_view_renders_one_suggest_button_per_tag_field(client):
    user = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
    client.force_login(user)
    root = Page.objects.get(depth=1)
    page = root.add_child(instance=ArticlePage(title="Hello", slug="hello"))

    response = client.get(reverse("wagtailadmin_pages:edit", args=[page.id]))

    assert response.status_code == 200
    html = response.content.decode()
    assert html.count("Let Laya suggest tags") == 2
    assert 'data-laya-suggest-field-value="tags"' in html
    assert 'data-laya-suggest-field-value="feeling_tags"' in html
    assert 'data-laya-suggest-model-value="testapp.ArticlePage"' in html
    assert html.count("wagtail_laya/js/laya-suggest-controller.js") == 1


@pytest.mark.django_db
def test_edit_view_renders_the_article_rating_button_once(client):
    user = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
    client.force_login(user)
    root = Page.objects.get(depth=1)
    page = root.add_child(instance=ArticlePage(title="Hello", slug="hello"))

    response = client.get(reverse("wagtailadmin_pages:edit", args=[page.id]))

    assert response.status_code == 200
    html = response.content.decode()
    assert html.count('data-laya-rate-field-value=""') == 1
    assert 'data-laya-rate-model-value="testapp.ArticlePage"' in html
    assert 'data-laya-rate-keys-value="readability,mood"' in html
    assert html.count("wagtail_laya/js/laya-rate-controller.js") == 1


@pytest.mark.django_db
def test_edit_view_renders_one_rating_button_per_wrapped_field(client):
    user = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
    client.force_login(user)
    root = Page.objects.get(depth=1)
    page = root.add_child(instance=ArticlePage(title="Hello", slug="hello"))

    response = client.get(reverse("wagtailadmin_pages:edit", args=[page.id]))

    assert response.status_code == 200
    html = response.content.decode()
    assert html.count('data-controller="laya-rate"') == 3
    intro = _controller_block(html, "intro")
    assert 'data-laya-rate-keys-value="readability"' in intro
    assert "Rate Readability with Laya" in intro
    body = _controller_block(html, "body")
    assert 'data-laya-rate-keys-value="readability,mood"' in body
    assert "Rate with Laya" in body
    # The normal widgets still render above the buttons.
    assert 'data-contentpath="intro"' in html and 'data-contentpath="body"' in html
    assert html.count("wagtail_laya/js/laya-rate-controller.js") == 1


def _controller_block(html, field_name):
    start = html.index(f'data-laya-rate-field-value="{field_name}"')
    return html[start : html.index("</button>", start)]


def test_rating_field_panel_with_an_unknown_key_fails_at_bind_time():
    with pytest.raises(LookupError, match="nope"):
        LayaRatingFieldPanel("intro", keys=["nope"]).bind_to_model(ArticlePage)


@pytest.mark.parametrize("field_name", ["live", "tags"])
def test_rating_field_panel_on_an_unsupported_field_fails_at_bind_time(field_name):
    with pytest.raises(LookupError, match=field_name):
        LayaRatingFieldPanel(field_name, keys=["mood"]).bind_to_model(ArticlePage)


def test_rating_field_panel_without_the_mixin_fails_at_bind_time():
    with pytest.raises(ImproperlyConfigured, match="LayaTaggableMixin"):
        LayaRatingFieldPanel("title", keys=["mood"]).bind_to_model(Page)


def test_rating_panel_with_an_unknown_key_fails_at_bind_time():
    with pytest.raises(LookupError, match="nope"):
        LayaRatingPanel(keys=["nope"]).bind_to_model(ArticlePage)


def test_rating_panel_without_the_mixin_fails_at_bind_time():
    with pytest.raises(ImproperlyConfigured, match="LayaTaggableMixin"):
        LayaRatingPanel().bind_to_model(Page)


@pytest.mark.django_db
def test_rating_panel_renders_only_its_key_subset(rf):
    panel = LayaRatingPanel(keys=["mood"]).bind_to_model(ArticlePage)
    page = ArticlePage(title="Hello")
    form = panel.get_form_class()(instance=page)

    html = panel.get_bound_panel(instance=page, request=rf.get("/"), form=form).render_html()

    assert 'data-laya-rate-keys-value="mood"' in html
    assert 'data-laya-rate-model-value="testapp.ArticlePage"' in html


@pytest.mark.django_db
def test_buttons_carry_the_slow_load_message_and_no_unsure_note(client):
    user = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
    client.force_login(user)
    root = Page.objects.get(depth=1)
    page = root.add_child(instance=ArticlePage(title="Hello", slug="hello"))

    response = client.get(reverse("wagtailadmin_pages:edit", args=[page.id]))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Let Laya suggest tags" in html
    assert "Rate with Laya" in html
    assert html.count("Loading Laya") >= 2  # tag panels and rating panels
    assert "Laya is unsure" not in html

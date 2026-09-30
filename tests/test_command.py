import pytest
from django.core.management import CommandError, call_command
from taggit.models import Tag
from wagtail.models import Page

from tests.testapp.models import ArticlePage, FeelingTag
from wagtail_laya.errors import LayaError, LayaUnavailable


@pytest.fixture
def page(db):
    Tag.objects.create(name="python")
    Tag.objects.create(name="cooking")
    FeelingTag.objects.create(name="calm")
    root = Page.objects.get(depth=1)
    return root.add_child(instance=ArticlePage(title="Py", slug="py", live=True))


def test_command_applies_all_fields_in_one_draft_revision(page, fake_backend):
    fake_backend({"python": 0.9, "cooking": 0.1, "calm": 0.95})

    call_command("laya_tag_pages", "testapp.ArticlePage", "--apply")

    page.refresh_from_db()
    latest = page.get_latest_revision_as_object()
    assert [t.name for t in latest.tags.all()] == ["python"]
    assert [t.name for t in latest.feeling_tags.all()] == ["calm"]
    assert page.revisions.count() == 1
    assert page.has_unpublished_changes
    assert list(ArticlePage.objects.get(id=page.id).tags.all()) == []


def test_command_field_option_limits_to_one_field(page, fake_backend):
    backend = fake_backend({"python": 0.9, "cooking": 0.1, "calm": 0.95})

    call_command("laya_tag_pages", "testapp.ArticlePage", "--field", "feeling_tags", "--apply")

    assert len(backend.calls) == 1
    latest = ArticlePage.objects.get(id=page.id).get_latest_revision_as_object()
    assert [t.name for t in latest.feeling_tags.all()] == ["calm"]
    assert list(latest.tags.all()) == []


def test_command_rejects_unknown_field(page):
    with pytest.raises(CommandError, match="nope"):
        call_command("laya_tag_pages", "testapp.ArticlePage", "--field", "nope")


def test_command_threshold_option_overrides_every_field(page, fake_backend):
    fake_backend({"python": 0.9, "cooking": 0.1, "calm": 0.95})

    call_command("laya_tag_pages", "testapp.ArticlePage", "--threshold", "0.92", "--apply")

    latest = ArticlePage.objects.get(id=page.id).get_latest_revision_as_object()
    assert list(latest.tags.all()) == []  # python at 0.9 no longer passes
    assert [t.name for t in latest.feeling_tags.all()] == ["calm"]


def test_command_reports_laya_errors_and_carries_on(page, monkeypatch, capsys):
    class Down:
        def predict(self, state, questions, *, model=None):
            raise LayaError("laya is down")

    monkeypatch.setattr("wagtail_laya.client.get_backend", lambda: Down())

    call_command("laya_tag_pages", "testapp.ArticlePage")

    err = capsys.readouterr().err
    assert err.count("laya is down") == 2  # one line per tag field, no crash


def test_command_does_not_hide_tags_on_confidence(page, fake_backend, capsys):
    fake_backend({"python": 0.9, "cooking": 0.1, "calm": 0.95}, confidences={"python": 0.5})

    call_command("laya_tag_pages", "testapp.ArticlePage", "--field", "tags")

    assert "tags: python (90%)" in capsys.readouterr().out


def test_command_stops_at_once_when_laya_is_unavailable(page, monkeypatch):
    # Waiting out a timeout for every page and field would take hours on a large site.
    calls = []

    class Unreachable:
        def predict(self, state, questions, *, model=None):
            calls.append(1)
            raise LayaUnavailable("Could not reach Laya at http://laya:8000/v1/systemone")

    monkeypatch.setattr("wagtail_laya.client.get_backend", lambda: Unreachable())

    with pytest.raises(CommandError, match="Could not reach Laya"):
        call_command("laya_tag_pages", "testapp.ArticlePage")
    assert len(calls) == 1

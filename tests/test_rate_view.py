import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail_laya.errors import LayaError

from tests.conftest import contentstate

DISTRIBUTIONS = {"readability": [0.55, 0.0, 0.45], "mood": [0.1, 0.1, 0.8]}


@pytest.fixture
def admin_client(client, db):
    user = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
    client.force_login(user)
    return client


def _form_data(**overrides):
    data = {
        "laya_model": "testapp.ArticlePage",
        "title": "Python packaging",
        "intro": contentstate("How to build wheels"),
        "body-count": "1",
        "body-0-type": "heading",
        "body-0-value": "Setup",
        "body-0-order": "0",
        "body-0-deleted": "",
        "tags": "django",
    }
    data.update(overrides)
    return data


def test_rate_sends_one_score_per_key_built_from_form_data(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)

    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data(laya_keys=["readability"]))

    assert response.status_code == 200
    assert response.json() == {
        "ratings": [
            {
                "key": "readability",
                "label": "Readability",
                "top_label": "Easy",
                "top_probability": 0.55,
                "confidence": 0.99,
                "levels": [
                    {"label": "Easy", "probability": 0.55},
                    {"label": "Medium", "probability": 0.0},
                    {"label": "Hard", "probability": 0.45},
                ],
            }
        ]
    }
    assert len(backend.calls) == 1
    state, questions = backend.calls[0]
    assert state == {"article": {"title": "Python packaging", "body": "How to build wheels\n\nSetup"}}
    assert list(questions) == ["readability"]
    assert questions["readability"]["type"] == "score"


def test_rate_with_no_keys_rates_every_declared_quality(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)

    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data())

    assert response.status_code == 200
    assert [(r["key"], r["label"], r["top_label"]) for r in response.json()["ratings"]] == [
        ("readability", "Readability", "Easy"),
        ("mood", "mood", "Happy"),
    ]
    assert len(backend.calls) == 1
    assert list(backend.calls[0][1]) == ["readability", "mood"]


def test_rate_returns_ratings_in_declaration_order_whatever_the_key_order(admin_client, fake_backend):
    fake_backend(distributions=DISTRIBUTIONS)
    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data(laya_keys=["mood", "readability"]))
    assert [r["key"] for r in response.json()["ratings"]] == ["readability", "mood"]


def test_rate_empty_article_makes_no_request_and_returns_no_ratings(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)

    response = admin_client.post(
        reverse("wagtail_laya:rate"), {"laya_model": "testapp.ArticlePage", "title": " ", "intro": ""}
    )

    assert response.status_code == 200
    assert response.json() == {"ratings": []}
    assert backend.calls == []


def test_rate_rejects_unknown_key_before_any_request(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)
    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data(laya_keys=["nope"]))
    assert response.status_code == 400
    assert "nope" in response.json()["error"]
    assert backend.calls == []


def test_rate_rejects_unknown_model(admin_client, db):
    response = admin_client.post(reverse("wagtail_laya:rate"), {"laya_model": "nope.Nope"})
    assert response.status_code == 400


def test_rate_rejects_non_laya_model(admin_client, db):
    response = admin_client.post(reverse("wagtail_laya:rate"), {"laya_model": "wagtailcore.Page"})
    assert response.status_code == 400


class DownBackend:
    def predict(self, state, questions, *, model=None):
        raise LayaError("laya is down")


def test_rate_returns_502_when_laya_fails(admin_client, monkeypatch, db):
    monkeypatch.setattr("wagtail_laya.client.get_backend", lambda: DownBackend())

    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data())

    assert response.status_code == 502
    assert "laya is down" in response.json()["error"]


def test_rate_requires_admin(client, db):
    response = client.post(reverse("wagtail_laya:rate"), {"laya_model": "testapp.ArticlePage"})
    assert response.status_code in (302, 403)


def test_rate_a_field_sends_only_that_fields_excerpt(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)

    response = admin_client.post(
        reverse("wagtail_laya:rate"), _form_data(laya_field="intro", laya_keys=["readability"])
    )

    assert response.status_code == 200
    assert [(r["key"], r["top_label"]) for r in response.json()["ratings"]] == [("readability", "Easy")]
    assert len(backend.calls) == 1
    state, questions = backend.calls[0]
    assert state == {"text": "How to build wheels"}
    assert list(questions) == ["readability"]
    assert questions["readability"]["type"] == "score"


def test_rate_a_stream_field_flattens_the_whole_stream(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)
    data = _form_data(
        laya_field="body",
        laya_keys=["readability", "mood"],
        **{
            "body-count": "2",
            "body-1-type": "paragraph",
            "body-1-value": contentstate("Run pip"),
            "body-1-order": "1",
            "body-1-deleted": "",
        },
    )

    response = admin_client.post(reverse("wagtail_laya:rate"), data)

    assert response.status_code == 200
    assert [r["key"] for r in response.json()["ratings"]] == ["readability", "mood"]
    assert backend.calls[0][0] == {"text": "Setup\nRun pip"}
    assert list(backend.calls[0][1]) == ["readability", "mood"]


def test_rate_a_blank_field_makes_no_request_and_returns_no_ratings(admin_client, fake_backend):
    backend = fake_backend(distributions=DISTRIBUTIONS)

    response = admin_client.post(
        reverse("wagtail_laya:rate"), _form_data(laya_field="intro", intro=contentstate(" "))
    )

    assert response.status_code == 200
    assert response.json() == {"ratings": []}
    assert backend.calls == []


@pytest.mark.parametrize("field_name", ["nope", "live", "tags"])
def test_rate_rejects_unknown_and_unsupported_fields(admin_client, fake_backend, field_name):
    backend = fake_backend(distributions=DISTRIBUTIONS)
    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data(laya_field=field_name))
    assert response.status_code == 400
    assert field_name in response.json()["error"]
    assert backend.calls == []


def test_rate_reports_confidence_without_an_unsure_flag(admin_client, fake_backend):
    # For a score, Laya's confidence is the top level's probability, so an "unsure" flag
    # would only repeat what the editor already sees.
    fake_backend(distributions=DISTRIBUTIONS, confidences={"readability": 0.3})
    response = admin_client.post(reverse("wagtail_laya:rate"), _form_data(laya_keys=["readability"]))
    rating = response.json()["ratings"][0]
    assert rating["confidence"] == 0.3
    assert "unsure" not in rating

from tests.conftest import FakeBackend
from wagtail_laya.backends import LocalBackend, ServiceBackend
from wagtail_laya.client import ask, clip, get_backend
from wagtail_laya.questions import noul

QUESTIONS = {"q": noul("about 'a'?", true="t", false="f")}


def test_ask_uses_get_backend_and_parses_the_payload(monkeypatch, settings):
    settings.WAGTAIL_LAYA_MODEL = "multilingual"
    backend = FakeBackend({"a": 0.5}, confidences={"a": 0.7})
    monkeypatch.setattr("wagtail_laya.client.get_backend", lambda: backend)

    response = ask({"x": 1}, QUESTIONS)

    assert response.nouls["q"].noul == 0.5
    assert response.nouls["q"].confidence == 0.7
    assert backend.calls == [({"x": 1}, QUESTIONS)]
    assert backend.models == ["multilingual"]


def test_ask_uses_a_given_backend_instead(monkeypatch):
    def must_not_be_called():
        raise AssertionError("get_backend must not be called when a backend is given")

    monkeypatch.setattr("wagtail_laya.client.get_backend", must_not_be_called)
    backend = FakeBackend({"a": 0.5})
    assert ask({}, QUESTIONS, backend=backend).nouls["q"].noul == 0.5


def test_get_backend_runs_laya_in_process_without_a_url(settings):
    settings.WAGTAIL_LAYA_URL = None
    assert isinstance(get_backend(), LocalBackend)


def test_get_backend_uses_the_server_when_a_url_is_set(settings, monkeypatch):
    settings.WAGTAIL_LAYA_URL = "http://laya:8000/"
    settings.WAGTAIL_LAYA_API_KEY = None
    settings.WAGTAIL_LAYA_TIMEOUT = 7.0
    monkeypatch.setenv("LAYA_API_KEY", "from-env")

    backend = get_backend()

    assert isinstance(backend, ServiceBackend)
    assert backend.url == "http://laya:8000/v1/systemone"
    assert backend.api_key == "from-env"
    assert backend.timeout == 7.0


def test_the_key_setting_wins_over_the_environment(settings, monkeypatch):
    settings.WAGTAIL_LAYA_URL = "http://laya:8000"
    settings.WAGTAIL_LAYA_API_KEY = "from-settings"
    monkeypatch.setenv("LAYA_API_KEY", "from-env")
    assert get_backend().api_key == "from-settings"


def test_clip_applies_max_chars(settings):
    settings.WAGTAIL_LAYA_MAX_CHARS = 5
    assert clip("0123456789") == "01234"

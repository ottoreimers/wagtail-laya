"""Where Laya runs: in this process, or behind a ``python -m laya.serve`` server.

Both backends take Laya-format question dicts and return Laya's ``/v1/systemone``
payload unchanged; :mod:`wagtail_laya.response` parses it. Every failure is raised as
:class:`LayaError`.

In-process, one ``laya.Router`` serves the whole process. It is built on first use, so
importing Django stays fast, and it picks the English or multilingual checkpoint per
request. Loading takes seconds and the model holds a lot of memory, so it is built
once and one prediction runs at a time, under the same lock.
"""

from __future__ import annotations

import http.client
import json
import threading
import urllib.error
import urllib.request
from typing import Any, Mapping, Protocol

from wagtail_laya.errors import LayaError, LayaUnavailable


class Backend(Protocol):
    def predict(self, state: Any, questions: Mapping[str, dict], *, model: str | None = None) -> dict: ...


_router = None
_lock = threading.Lock()


def _load_router():
    """The process-wide Router, built on first use. Call with ``_lock`` held."""
    global _router
    if _router is None:
        try:
            import laya

            _router = laya.Router()
        except ImportError as exc:
            raise LayaUnavailable(
                'Laya is not installed. Run pip install "wagtail-laya[local]", '
                "or set WAGTAIL_LAYA_URL to a Laya server."
            ) from exc
        except Exception as exc:  # e.g. a libtorch that fails to load, or a bad LAYA_* setting
            raise LayaUnavailable(f"Laya could not start: {exc}") from exc
    return _router


class LocalBackend:
    """Laya in this process."""

    def predict(self, state: Any, questions: Mapping[str, dict], *, model: str | None = None) -> dict:
        with _lock:
            router = _load_router()
            try:
                return router.predict(state, dict(questions), model=model)
            except Exception as exc:
                raise LayaError(f"Laya failed: {exc}") from exc


class ServiceBackend:
    """A Laya server speaking the ``/v1/systemone`` protocol, e.g. ``python -m laya.serve``."""

    def __init__(self, url: str, *, api_key: str | None = None, timeout: float = 30.0):
        self.url = url.rstrip("/") + "/v1/systemone"
        self.api_key = api_key
        self.timeout = timeout

    def predict(self, state: Any, questions: Mapping[str, dict], *, model: str | None = None) -> dict:
        body = {"state": state, "questions": dict(questions)}
        if model:
            body["model"] = model
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise LayaError(f"Laya server answered {exc.code}: {_detail(exc)}") from exc
        except OSError as exc:  # URLError, refused connections and timeouts
            raise LayaUnavailable(f"Could not reach Laya at {self.url}: {exc}") from exc
        except http.client.HTTPException as exc:  # not HTTP at all, or a connection cut mid-body
            raise LayaError(f"Laya server sent an invalid response: {exc!r}") from exc
        except ValueError as exc:
            raise LayaError(f"Laya server sent invalid JSON: {exc}") from exc


def _detail(exc: urllib.error.HTTPError) -> str:
    """The server's ``detail`` message (FastAPI's error shape), or the HTTP reason."""
    try:
        body = json.loads(exc.read())
        return str(body.get("detail", body))
    except Exception:
        return str(exc.reason)

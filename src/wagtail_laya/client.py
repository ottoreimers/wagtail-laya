"""The Laya connection: everything about talking to Laya that is not a domain question.

:func:`ask` puts questions to a backend and parses the answers into a
:class:`~wagtail_laya.response.Response`. :func:`get_backend` picks the backend from the
settings: the Laya server at ``WAGTAIL_LAYA_URL`` when it is set, otherwise Laya in this
process. :func:`clip` cuts text to ``WAGTAIL_LAYA_MAX_CHARS``. Tests replace
:func:`get_backend` to substitute a fake.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

from wagtail_laya.backends import Backend, LocalBackend, ServiceBackend
from wagtail_laya.errors import LayaError
from wagtail_laya.response import Response
from wagtail_laya.settings import get_setting

__all__ = ["LayaError", "Response", "ask", "clip", "get_backend"]

logger = logging.getLogger(__name__)


def get_backend() -> Backend:
    url = get_setting("WAGTAIL_LAYA_URL")
    if url:
        return ServiceBackend(
            url,
            api_key=get_setting("WAGTAIL_LAYA_API_KEY") or os.environ.get("LAYA_API_KEY"),
            timeout=get_setting("WAGTAIL_LAYA_TIMEOUT"),
        )
    return LocalBackend()


def ask(state: Any, questions: Mapping[str, dict], *, backend: Backend | None = None) -> Response:
    """Put ``questions`` about ``state`` to Laya in one request.

    Uses ``backend`` when given, otherwise the one :func:`get_backend` picks.
    Raises :class:`LayaError` when Laya cannot answer.
    """
    backend = backend or get_backend()
    payload = backend.predict(state, questions, model=get_setting("WAGTAIL_LAYA_MODEL"))
    response = Response.from_payload(payload)
    logger.info("laya answered %d questions with %s", len(questions), response.model or "laya")
    return response


def clip(text: str) -> str:
    """``text`` cut to ``WAGTAIL_LAYA_MAX_CHARS``."""
    return text[: get_setting("WAGTAIL_LAYA_MAX_CHARS")]

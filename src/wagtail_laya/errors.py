"""The one exception wagtail-laya raises when Laya cannot answer.

Whether Laya is missing, a server is unreachable, or an answer cannot be read, callers
catch ``LayaError`` alone: views turn it into a 502 and the bulk command logs it and
moves on.
"""


class LayaError(Exception):
    """Laya could not answer; the message says why, in words an editor can act on."""


class LayaUnavailable(LayaError):
    """Laya cannot answer anything right now: not installed, failing to start, or its server
    unreachable. Retrying the next page will fail the same way, so bulk runs stop."""

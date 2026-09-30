"""Laya's answers, parsed from the ``/v1/systemone`` payload both backends return.

``laya.Router.predict`` in this process and ``laya.serve`` over HTTP produce the same
JSON, so this is the only place that reads it. Each answer keeps Laya's calibrated
``answer_confidence``; payloads without it fall back to ``confidence``, then to 1.0, so
a server that omits it hides nothing rather than everything.
"""

from __future__ import annotations

from dataclasses import dataclass

from wagtail_laya.errors import LayaError


@dataclass(frozen=True)
class NoulResult:
    noul: float
    confidence: float


@dataclass(frozen=True)
class ScoreResult:
    probabilities: dict[int, float]
    confidence: float


@dataclass(frozen=True)
class Response:
    model: str
    nouls: dict[str, NoulResult]
    scores: dict[str, ScoreResult]

    @classmethod
    def from_payload(cls, payload: dict) -> "Response":
        """Parse a payload; raises :class:`LayaError` when it is not one Laya would send."""
        try:
            nouls, scores = {}, {}
            for qid, answer in payload["answers"].items():
                if answer["type"] == "noul":
                    nouls[qid] = NoulResult(float(answer["noul"]), _confidence(answer))
                elif answer["type"] == "score":
                    probabilities = {int(level): float(p) for level, p in answer["probabilities"].items()}
                    scores[qid] = ScoreResult(probabilities, _confidence(answer))
            return cls(model=str(payload.get("model") or ""), nouls=nouls, scores=scores)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise LayaError(f"Laya sent an answer wagtail-laya cannot read: {exc!r}") from exc


def _confidence(answer: dict) -> float:
    value = answer.get("answer_confidence", answer.get("confidence"))
    return 1.0 if value is None else float(value)

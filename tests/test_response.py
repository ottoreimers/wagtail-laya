import pytest

from wagtail_laya.errors import LayaError
from wagtail_laya.response import NoulResult, Response, ScoreResult


def test_parses_nouls_and_scores_with_calibrated_confidence():
    response = Response.from_payload(
        {
            "model": "english",
            "answers": {
                "tag_0": {"type": "noul", "noul": 0.91, "confidence": 0.91, "answer_confidence": 0.87},
                "mood": {
                    "type": "score",
                    "score": 1.2,
                    "probabilities": {"0": 0.1, "1": 0.6, "2": 0.3},
                    "confidence": 0.4,
                    "answer_confidence": 0.66,
                },
            },
        }
    )
    assert response.model == "english"
    assert response.nouls == {"tag_0": NoulResult(noul=0.91, confidence=0.87)}
    assert response.scores == {"mood": ScoreResult(probabilities={0: 0.1, 1: 0.6, 2: 0.3}, confidence=0.66)}


def test_confidence_falls_back_to_plain_confidence_then_one():
    response = Response.from_payload(
        {
            "answers": {
                "a": {"type": "noul", "noul": 0.2, "confidence": 0.8},
                "b": {"type": "noul", "noul": 0.2},
            }
        }
    )
    assert response.nouls["a"].confidence == 0.8
    assert response.nouls["b"].confidence == 1.0
    assert response.model == ""


def test_choice_answers_are_ignored():
    response = Response.from_payload({"answers": {"c": {"type": "choice", "choice": "x", "probabilities": {"x": 1.0}}}})
    assert response.nouls == {} and response.scores == {}


@pytest.mark.parametrize(
    "payload",
    [{}, {"answers": None}, {"answers": {"a": {"type": "noul"}}}, {"answers": {"a": {"type": "score", "probabilities": {"x": 1}}}}],
)
def test_malformed_payloads_raise_laya_error(payload):
    with pytest.raises(LayaError, match="cannot read"):
        Response.from_payload(payload)

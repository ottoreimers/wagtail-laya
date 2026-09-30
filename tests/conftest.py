import json

import pytest


def contentstate(text: str) -> str:
    """What the Draftail rich text editor posts for one paragraph: contentstate JSON, not HTML."""
    block = {"key": "a1b2c", "text": text, "type": "unstyled", "depth": 0, "inlineStyleRanges": [], "entityRanges": []}
    return json.dumps({"blocks": [block], "entityMap": {}})


class FakeBackend:
    """Answers each noul with a probability looked up from the tag name in its question,
    and each score with the per-level distribution configured under its question key.

    Confidences are looked up the same way (by tag name, or by score key) and default to
    0.99, so tests that do not care about confidence pass the 0.8 gate.
    """

    def __init__(self, probabilities, distributions=None, confidences=None):
        self.probabilities = probabilities
        self.distributions = distributions or {}
        self.confidences = confidences or {}
        self.calls = []
        self.models = []

    def predict(self, state, questions, *, model=None):
        self.calls.append((state, questions))
        self.models.append(model)
        answers = {}
        for key, question in questions.items():
            if question["type"] == "score":
                distribution = self.distributions[key]
                assert len(distribution) == len(question["criteria"])
                answers[key] = {
                    "type": "score",
                    "score": sum(i * p for i, p in enumerate(distribution)),
                    "probabilities": {str(i): p for i, p in enumerate(distribution)},
                    "answer_confidence": self.confidences.get(key, 0.99),
                }
            else:
                # Longest match, so a tag that is part of another tag's name ("py" in "python") is not picked by mistake.
                tag = max((t for t in self.probabilities if t in question["instructions"]), key=len)
                answers[key] = {
                    "type": "noul",
                    "noul": self.probabilities[tag],
                    "answer_confidence": self.confidences.get(tag, 0.99),
                }
        return {"model": "laya-test", "answers": answers}


@pytest.fixture
def fake_backend(monkeypatch):
    def make(probabilities=None, distributions=None, confidences=None):
        backend = FakeBackend(probabilities or {}, distributions, confidences)
        monkeypatch.setattr("wagtail_laya.client.get_backend", lambda: backend)
        return backend

    return make

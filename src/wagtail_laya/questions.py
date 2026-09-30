"""Laya questions, as the plain dicts both backends send.

Every noul gets neutral labels: without them Laya's English checkpoint leans on the
wording of the default labels instead of the criteria.
"""

from __future__ import annotations

from typing import Iterable

NEUTRAL_LABELS = {"true": "A", "false": "B"}


def noul(instructions: str, *, true: str, false: str) -> dict:
    """A yes/no question; Laya answers with the probability that ``true`` holds."""
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true, "false": false},
        "labels": dict(NEUTRAL_LABELS),
    }


def score(instructions: str, criteria: Iterable[str]) -> dict:
    """An ordinal question; ``criteria`` are the levels, lowest first."""
    return {"type": "score", "instructions": instructions, "criteria": list(criteria)}

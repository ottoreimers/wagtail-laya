from wagtail_laya.questions import noul, score


def test_noul_carries_criteria_and_neutral_labels():
    assert noul("Is it about 'x'?", true="yes x", false="no x") == {
        "type": "noul",
        "instructions": "Is it about 'x'?",
        "criteria": {"true": "yes x", "false": "no x"},
        "labels": {"true": "A", "false": "B"},
    }


def test_each_noul_gets_its_own_labels_dict():
    a, b = noul("a", true="t", false="f"), noul("b", true="t", false="f")
    a["labels"]["true"] = "changed"
    assert b["labels"] == {"true": "A", "false": "B"}


def test_score_lists_criteria_in_order():
    assert score("How easy?", (c for c in ["easy", "hard"])) == {
        "type": "score",
        "instructions": "How easy?",
        "criteria": ["easy", "hard"],
    }

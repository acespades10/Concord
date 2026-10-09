import pytest

from app.agreement import bio, cohen, consensus, fleiss, span_f1, tokenize, validate_spans
from app.imports import parse_import


def test_fleiss_reference_matrix():
    matrix = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    rows = [
        [str(category) for category, count in enumerate(row) for _ in range(count)]
        for row in matrix
    ]
    assert fleiss(rows, 14).value == pytest.approx(0.2099307)


@pytest.mark.parametrize(
    "rows,target,value,reason",
    [
        ([["a", "a", "a"], ["b", "b", "b"]], 3, 1.0, None),
        ([["a", "b"], ["a", "b"]], 2, -1.0, None),
        ([["a", "a", "a"]], 3, None, "zero_expected_disagreement"),
        ([["a", "b"]], 3, None, "no_fully_rated_items"),
        ([], 3, None, "no_fully_rated_items"),
    ],
)
def test_fleiss_edges(rows, target, value, reason):
    result = fleiss(rows, target)
    assert result.value == value
    assert result.reason == reason


@pytest.mark.parametrize(
    "a,b,value,reason",
    [
        (["a", "b"], ["a", "b"], 1.0, None),
        (["a", "b"], ["b", "a"], -1.0, None),
        (["a", "a"], ["a", "a"], None, "zero_expected_disagreement"),
        ([], [], None, "no_shared_labels"),
        (["a", "a", "b", "b"], ["a", "b", "a", "b"], 0.0, None),
    ],
)
def test_cohen_edges(a, b, value, reason):
    result = cohen(a, b)
    assert result.value == value
    assert result.reason == reason


def test_cohen_reference():
    left = ["yes"] * 50 + ["yes"] * 10 + ["no"] * 5 + ["no"] * 35
    right = ["yes"] * 50 + ["no"] * 10 + ["yes"] * 5 + ["no"] * 35
    assert cohen(left, right).value == pytest.approx(0.693877551)
    with pytest.raises(ValueError):
        cohen(["a"], [])


def test_tokenization_unicode_and_bio():
    text = "Hi 🌿 José in 台北.\nMaya Chen"
    tokens = tokenize(text)
    assert [t["text"] for t in tokens] == ["Hi", "🌿", "José", "in", "台北", ".", "Maya", "Chen"]
    assert tokens[2] == {"start": 5, "end": 9, "text": "José"}
    spans = [{"start": 17, "end": 26, "text": "Maya Chen", "label": "PERSON"}]
    validate_spans(text, tokens, spans, ["PERSON"])
    assert bio(tokens, spans)[-2:] == ["B-PERSON", "I-PERSON"]
    assert bio(tokens, []) == ["O"] * 8


@pytest.mark.parametrize(
    "spans",
    [
        [{"start": 1, "end": 4, "text": "aya", "label": "PERSON"}],
        [{"start": 0, "end": 4, "text": "Wrong", "label": "PERSON"}],
        [{"start": 0, "end": 4, "text": "Maya", "label": "UNKNOWN"}],
        [
            {"start": 0, "end": 9, "text": "Maya Chen", "label": "PERSON"},
            {"start": 5, "end": 9, "text": "Chen", "label": "PERSON"},
        ],
        [{"start": 5, "end": 4, "text": "", "label": "PERSON"}],
    ],
)
def test_invalid_ner(spans):
    with pytest.raises(ValueError):
        validate_spans("Maya Chen", tokenize("Maya Chen"), spans, ["PERSON"])


def test_span_f1():
    a = {"start": 0, "end": 4, "text": "Maya", "label": "PERSON"}
    b = {"start": 5, "end": 9, "text": "Chen", "label": "PERSON"}
    assert span_f1([], []) == 1
    assert span_f1([a], []) == 0
    assert span_f1([a], [a, b]) == pytest.approx(2 / 3)
    assert span_f1([a], [{**a, "label": "ORG"}]) == 0


def test_consensus_threshold_and_ties():
    assert (
        consensus("rating", [{"label": "a"}] * 2 + [{"label": "b"}], 3, 0.8, [])["reason"]
        == "below_threshold"
    )
    assert (
        consensus("rating", [{"label": "a"}, {"label": "b"}], 2, 0.5, [])["reason"]
        == "no_strict_majority"
    )
    assert consensus("ab", [{"choice": "TIE"}] * 3, 3, 0.8, [])["resolved"]
    assert consensus("rating", [{"label": "a"}], 3, 0.8, [])["reason"] == "awaiting_raters"


def test_ner_majority_and_empty():
    tokens = tokenize("Maya works")
    span = {"start": 0, "end": 4, "text": "Maya", "label": "PERSON"}
    payloads = [{"spans": [span]}, {"spans": [span]}, {"spans": []}]
    assert consensus("ner", payloads, 3, 0.6, tokens)["payload"] == {"spans": [span]}
    assert not consensus("ner", payloads, 3, 0.8, tokens)["resolved"]
    assert not consensus("ner", [{"spans": [span]}, {"spans": []}, {"spans": []}], 3, 0.8, tokens)[
        "resolved"
    ]
    assert consensus("ner", [{"spans": []}] * 3, 3, 0.8, tokens)["resolved"]
    assert (
        consensus("ner", [{"spans": [span]}, {"spans": []}], 2, 0.5, tokens)["reason"]
        == "no_strict_majority"
    )


def test_import_csv_and_errors():
    rows, errors = parse_import(
        'external_id,text,source\n1,"José\n台北",demo\n'.encode(), "data.csv", "ner", set()
    )
    assert not errors and rows[0]["content"]["text"] == "José\n台北"
    assert rows[0]["extra"] == {"source": "demo"}
    _, errors = parse_import(
        b'{"external_id":"ok","text":"Fine"}\n{bad}', "data.jsonl", "ner", set()
    )
    assert errors[0]["row"] == 2
    assert parse_import(b'{"external_id":"a","text":"Hi","x":NaN}', "data.jsonl", "ner", set())[1]

import importlib.util
import json
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agreement import calculate, cohen, fleiss

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_reference", ROOT / "benchmarks/reference.py"
)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
CASES = json.loads((ROOT / "benchmarks/reference-cases.json").read_text(encoding="utf-8"))


def assert_kappa(actual, expected):
    assert actual.n == expected["n"]
    assert actual.reason == expected["reason"]
    if expected["value"] is None:
        assert actual.value is None
    else:
        assert actual.value == pytest.approx(expected["value"], abs=1e-12)


def test_published_fleiss_worked_example():
    case = CASES["fleiss_published"]
    rows = [
        [str(category) for category, count in enumerate(row) for _ in range(count)]
        for row in case["counts"]
    ]
    result = reference.reference_fleiss(rows, 14)
    assert result["exact"] == case["expected_exact"]
    assert result["value"] == pytest.approx(
        case["expected_rounded"], abs=case["absolute_tolerance"]
    )
    assert_kappa(fleiss(rows, 14), result)


def test_published_cohen_worked_example():
    case = CASES["cohen_published"]
    pairs = [
        (str(a), str(b))
        for a, row in enumerate(case["counts"])
        for b, count in enumerate(row)
        for _ in range(count)
    ]
    left, right = [a for a, _ in pairs], [b for _, b in pairs]
    result = reference.reference_cohen(left, right)
    assert result["exact"] == case["expected_exact"]
    assert_kappa(cohen(left, right), result)


@pytest.mark.parametrize("case", CASES["fleiss_hand_checked"], ids=lambda case: case["name"])
def test_hand_checked_fleiss(case):
    result = reference.reference_fleiss(case["rows"], case["target"])
    assert result["exact"] == case["expected_exact"]
    assert_kappa(fleiss(case["rows"], case["target"]), result)


def test_all_binary_two_item_three_rater_matrices():
    for labels in product(["ham", "spam"], repeat=6):
        rows = [list(labels[:3]), list(labels[3:])]
        assert_kappa(fleiss(rows, 3), reference.reference_fleiss(rows, 3))
        for a, b in [(0, 1), (0, 2), (1, 2)]:
            left, right = [row[a] for row in rows], [row[b] for row in rows]
            assert_kappa(cohen(left, right), reference.reference_cohen(left, right))


@pytest.mark.parametrize(
    "rows,target,reason,n",
    [
        ([], 3, "no_fully_rated_items", 0),
        ([["ham", "spam"]], 3, "no_fully_rated_items", 0),
        ([["ham"]], 1, "no_fully_rated_items", 0),
        ([["ham", "ham", "ham"]], 3, "zero_expected_disagreement", 1),
    ],
)
def test_fleiss_undefined_cases(rows, target, reason, n):
    result = reference.reference_fleiss(rows, target)
    assert result == {"value": None, "reason": reason, "n": n, "exact": None}
    assert_kappa(fleiss(rows, target), result)


@pytest.mark.parametrize(
    "left,right,reason",
    [([], [], "no_shared_labels"), (["ham"], ["ham"], "zero_expected_disagreement")],
)
def test_cohen_undefined_cases(left, right, reason):
    result = reference.reference_cohen(left, right)
    assert result["value"] is None and result["reason"] == reason
    assert_kappa(cohen(left, right), result)


def test_mismatched_cohen_input_is_rejected():
    with pytest.raises(ValueError):
        reference.reference_cohen(["ham"], [])
    with pytest.raises(ValueError):
        cohen(["ham"], [])


@pytest.mark.parametrize(
    "votes",
    [
        {},
        {"empty": []},
        {"a": ["ham", "ham", "ham"], "b": ["spam", "spam", "spam"]},
        {"a": ["ham", "ham", "spam"], "b": ["spam", "spam", "ham"]},
        {"a": ["ham", None, "spam"], "b": [None, "spam", None], "c": []},
        {"a": ["x", "y", "z"], "b": ["x", "x", "y"]},
    ],
)
def test_summary_matches_application_with_missing_and_complete_votes(votes):
    expected = reference.calculate_reference(votes)
    project = SimpleNamespace(
        mode="rating", target_raters=3, review_threshold=0.8, metric_revision=1
    )
    items = [SimpleNamespace(id=key, external_id=key, tokens=[]) for key in votes]
    raters = ["rater1", "rater2", "rater3"]
    annotations = [
        SimpleNamespace(item_id=key, user_id=raters[index], payload={"label": label})
        for key, row in votes.items()
        for index, label in enumerate(row)
        if label is not None
    ]
    users = [SimpleNamespace(id=rater, name=rater) for rater in raters]
    actual = calculate(project, items, annotations, [], users)
    for key in [
        "total_items",
        "submissions",
        "expected_submissions",
        "fully_rated",
        "resolved",
        "unresolved",
        "coverage",
        "distribution",
    ]:
        assert actual[key] == expected[key], key
    assert_kappa(actual["fleiss"], expected["fleiss"])
    actual_pairs = {(pair["left"], pair["right"]): pair for pair in actual["pairs"]}
    assert len(actual_pairs) == len(expected["pairs"])
    for pair in expected["pairs"]:
        found = actual_pairs[pair["left"], pair["right"]]
        assert found["shared_items"] == pair["shared_items"]
        assert_kappa(found["kappa"], pair["kappa"])
    actual_items = {item["external_id"]: item for item in actual["items"]}
    for item in expected["items"]:
        found = actual_items[item["external_id"]]
        assert {key: found[key] for key in item} == item


def test_coverage_and_unresolved_exclude_awaiting_items():
    result = reference.calculate_reference(
        {"empty": [], "partial": ["ham"], "split": ["ham", "ham", "spam"]}
    )
    assert result["submissions"] == 4
    assert result["coverage"] == pytest.approx(4 / 9)
    assert result["unresolved"] == 1
    assert result["resolved"] == 0


@pytest.mark.parametrize(
    "votes,kwargs",
    [
        ({"a": ["ham"] * 4}, {}),
        ({"a": [7]}, {}),
        ({}, {"target": 0}),
        ({}, {"raters": ["a", "a"]}),
        ({}, {"threshold": 1.1}),
    ],
)
def test_reference_rejects_ambiguous_input(votes, kwargs):
    with pytest.raises(ValueError):
        reference.calculate_reference(votes, **kwargs)

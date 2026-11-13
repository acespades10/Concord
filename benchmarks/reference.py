"""Independent categorical benchmark calculations; Python standard library only."""

from collections import Counter
from fractions import Fraction
from itertools import combinations


def _result(observed: Fraction, expected: Fraction, n: int) -> dict:
    if expected == 1:
        return {"value": None, "reason": "zero_expected_disagreement", "n": n, "exact": None}
    value = (observed - expected) / (1 - expected)
    return {"value": float(value), "reason": None, "n": n, "exact": str(value)}


def reference_cohen(left: list[str], right: list[str]) -> dict:
    """Unweighted Cohen kappa from a contingency table and exact marginals."""
    if len(left) != len(right):
        raise ValueError("Paired labels must have equal lengths")
    n = len(left)
    if not n:
        return {"value": None, "reason": "no_shared_labels", "n": 0, "exact": None}
    table = Counter(zip(left, right, strict=True))
    categories = set(left) | set(right)
    diagonal = sum(table[label, label] for label in categories)
    marginal_products = sum(
        sum(count for (a, _), count in table.items() if a == label)
        * sum(count for (_, b), count in table.items() if b == label)
        for label in categories
    )
    return _result(Fraction(diagonal, n), Fraction(marginal_products, n * n), n)


def reference_fleiss(rows: list[list[str]], target: int) -> dict:
    """Fleiss kappa by enumerating agreeing rater pairs on complete items."""
    complete = [row for row in rows if len(row) == target]
    if target < 2 or not complete:
        return {"value": None, "reason": "no_fully_rated_items", "n": 0, "exact": None}
    agreeing_pairs = sum(a == b for row in complete for a, b in combinations(row, 2))
    possible_pairs = len(complete) * target * (target - 1) // 2
    counts = Counter(label for row in complete for label in row)
    total = len(complete) * target
    chance_pairs = sum(Fraction(count, total) ** 2 for count in counts.values())
    return _result(Fraction(agreeing_pairs, possible_pairs), chance_pairs, len(complete))


def calculate_reference(
    votes: dict[str, list[str | None]],
    raters: list[str] | None = None,
    target: int = 3,
    threshold: float = 0.8,
) -> dict:
    """Return app-shaped metrics without calling or importing application code.

    Each row follows the order in ``raters``; None marks a missing submission.
    A short row contains votes from the first raters only. Empty rows represent
    imported items without submissions. Adjudications are intentionally excluded.
    """
    raters = ["rater1", "rater2", "rater3"] if raters is None else list(raters)
    if target < 1 or len(set(raters)) != len(raters):
        raise ValueError("Target must be positive and rater names must be unique")
    cutoff = Fraction(str(threshold))
    if not 0 <= cutoff <= 1:
        raise ValueError("Threshold must be between zero and one")
    if any(len(row) > len(raters) for row in votes.values()):
        raise ValueError("Vote rows cannot exceed the named raters")
    if any(
        label is not None and not isinstance(label, str) for row in votes.values() for label in row
    ):
        raise ValueError("Labels must be strings or None for missing votes")

    items, rows = [], []
    distribution = Counter()
    active = set()
    for external_id, row in sorted(votes.items()):
        labels = [label for label in row if label is not None]
        rows.append(labels)
        distribution.update(labels)
        active.update(raters[index] for index, label in enumerate(row) if label is not None)
        count = len(labels)
        share, payload = Fraction(0), None
        if count < target:
            reason = "awaiting_raters"
        else:
            winner, support = Counter(labels).most_common(1)[0]
            share = Fraction(support, count)
            if support * 2 <= count:
                reason = "no_strict_majority"
            else:
                payload = {"label": winner}
                reason = "below_threshold" if share < cutoff else None
        items.append(
            {
                "external_id": external_id,
                "submitted": count,
                "resolved": reason is None,
                "reason": reason,
                "vote_share": float(share),
                "payload": payload,
            }
        )

    pairs = []
    for left_index, right_index in combinations(range(len(raters)), 2):
        left_name, right_name = raters[left_index], raters[right_index]
        if left_name not in active or right_name not in active:
            continue
        shared = [
            (row[left_index], row[right_index])
            for row in votes.values()
            if len(row) > right_index
            and row[left_index] is not None
            and row[right_index] is not None
        ]
        pairs.append(
            {
                "left": left_name,
                "right": right_name,
                "shared_items": len(shared),
                "kappa": reference_cohen([a for a, _ in shared], [b for _, b in shared]),
                "span_f1": None,
            }
        )

    total = len(votes)
    submissions = sum(distribution.values())
    return {
        "total_items": total,
        "submissions": submissions,
        "expected_submissions": total * target,
        "coverage": submissions / (total * target) if total else 0,
        "fully_rated": sum(len(row) == target for row in rows),
        "resolved": sum(item["resolved"] for item in items),
        "unresolved": sum(not item["resolved"] and item["submitted"] >= target for item in items),
        "distribution": dict(sorted(distribution.items())),
        "fleiss": reference_fleiss(rows, target),
        "pairs": pairs,
        "items": items,
    }

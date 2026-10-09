"""Pure agreement functions. Offsets are Unicode code points, never UTF-16 units."""

import re
from collections import Counter
from itertools import combinations

from app.schemas import Kappa


def tokenize(text: str) -> list[dict]:
    return [
        {"start": m.start(), "end": m.end(), "text": m.group()}
        for m in re.finditer(r"\w+|[^\w\s]", text, re.UNICODE)
    ]


def validate_spans(text: str, tokens: list[dict], spans: list[dict], labels: list[str]):
    starts = {t["start"] for t in tokens}
    ends = {t["end"] for t in tokens}
    previous_end = -1
    for span in sorted(spans, key=lambda x: (x["start"], x["end"])):
        start, end = span["start"], span["end"]
        if start not in starts or end not in ends or end <= start:
            raise ValueError("Spans must align with token boundaries")
        if start < previous_end:
            raise ValueError("Entity spans cannot overlap")
        if span["label"] not in labels:
            raise ValueError("Unknown entity type")
        if span["text"] != text[start:end]:
            raise ValueError("Span text does not match Unicode offsets")
        previous_end = end


def bio(tokens: list[dict], spans: list[dict]) -> list[str]:
    labels = ["O"] * len(tokens)
    for span in spans:
        covered = [
            i
            for i, token in enumerate(tokens)
            if token["start"] >= span["start"] and token["end"] <= span["end"]
        ]
        for pos, idx in enumerate(covered):
            labels[idx] = ("B-" if pos == 0 else "I-") + span["label"]
    return labels


def _kappa(observed: float, expected: float, n: int) -> Kappa:
    if abs(1 - expected) < 1e-12:
        return Kappa(value=None, reason="zero_expected_disagreement", n=n)
    return Kappa(value=(observed - expected) / (1 - expected), n=n)


def cohen(left: list[str], right: list[str]) -> Kappa:
    if len(left) != len(right):
        raise ValueError("Paired labels must have equal lengths")
    n = len(left)
    if not n:
        return Kappa(value=None, reason="no_shared_labels", n=0)
    a, b = Counter(left), Counter(right)
    expected = sum(a[x] * b[x] for x in a.keys() | b.keys()) / n**2
    return _kappa(sum(x == y for x, y in zip(left, right, strict=True)) / n, expected, n)


def fleiss(rows: list[list[str]], target: int) -> Kappa:
    complete = [row for row in rows if len(row) == target]
    if not complete or target < 2:
        return Kappa(value=None, reason="no_fully_rated_items", n=0)
    counts = [Counter(row) for row in complete]
    observed = sum(
        (sum(v * v for v in c.values()) - target) / (target * (target - 1)) for c in counts
    ) / len(counts)
    totals = Counter(x for row in complete for x in row)
    expected = sum((v / (len(complete) * target)) ** 2 for v in totals.values())
    return _kappa(observed, expected, len(complete))


def span_set(spans: list[dict]) -> set[tuple]:
    return {(s["start"], s["end"], s["label"]) for s in spans}


def span_f1(left: list[dict], right: list[dict]) -> float:
    a, b = span_set(left), span_set(right)
    return 2 * len(a & b) / (len(a) + len(b)) if a or b else 1.0


def consensus(
    mode: str, payloads: list[dict], target: int, threshold: float, tokens: list[dict]
) -> dict:
    n = len(payloads)
    if n < target:
        return {"resolved": False, "reason": "awaiting_raters", "vote_share": 0.0, "payload": None}
    if mode != "ner":
        key = "label" if mode == "rating" else "choice"
        votes = Counter(p[key] for p in payloads)
        value, count = votes.most_common(1)[0]
        share = count / n
        reason = (
            "no_strict_majority"
            if count <= n / 2
            else "below_threshold"
            if share < threshold
            else None
        )
        return {
            "resolved": reason is None,
            "reason": reason,
            "vote_share": share,
            "payload": {key: value} if count > n / 2 else None,
        }

    # Vote on exact spans; assess support for the resulting BIO sequence at every
    # token, including O. A minority entity never disappears into an unexamined O.
    votes = Counter(s for p in payloads for s in span_set(p["spans"]))
    majority = sorted(s for s, count in votes.items() if count > n / 2)
    spans = [
        {
            "start": a,
            "end": b,
            "label": label,
            "text": next(
                s["text"]
                for p in payloads
                for s in p["spans"]
                if (s["start"], s["end"], s["label"]) == (a, b, label)
            ),
        }
        for a, b, label in majority
    ]
    if any(a["end"] > b["start"] for a, b in zip(spans, spans[1:], strict=False)):
        return {
            "resolved": False,
            "reason": "overlapping_majority_spans",
            "vote_share": 0.0,
            "payload": None,
        }
    rows = [bio(tokens, p["spans"]) for p in payloads]
    proposed = bio(tokens, spans)
    shares = [sum(row[i] == label for row in rows) / n for i, label in enumerate(proposed)]
    shares.extend(votes[s] / n for s in majority)
    share = min(shares, default=1.0)
    reason = (
        "no_strict_majority" if share <= 0.5 else "below_threshold" if share < threshold else None
    )
    return {
        "resolved": reason is None,
        "reason": reason,
        "vote_share": share,
        "payload": {"spans": spans},
    }


def calculate(project, items, annotations, adjudications, users) -> dict:
    by_item = {item.id: [] for item in items}
    for annotation in annotations:
        by_item[annotation.item_id].append(annotation)
    decisions = {a.item_id: a for a in adjudications}
    item_metrics, rows = [], []
    distribution = Counter()
    for item in items:
        anns = by_item[item.id]
        payloads = [a.payload for a in anns]
        result = consensus(
            project.mode, payloads, project.target_raters, project.review_threshold, item.tokens
        )
        if item.id in decisions:
            result.update(resolved=True, reason=None, payload=decisions[item.id].payload)
        item_metrics.append(
            {
                "item_id": item.id,
                "external_id": item.external_id,
                "submitted": len(anns),
                "adjudicated": item.id in decisions,
                **result,
            }
        )
        if project.mode == "ner":
            sequences = [bio(item.tokens, p["spans"]) for p in payloads]
            if len(anns) == project.target_raters:
                rows.extend([list(x) for x in zip(*sequences, strict=True)])
            distribution.update(s["label"] for p in payloads for s in p["spans"])
        else:
            labels = [p["label" if project.mode == "rating" else "choice"] for p in payloads]
            rows.append(labels)
            distribution.update(labels)
    annotator_ids = sorted({a.user_id for a in annotations})
    pairs = []
    for left_id, right_id in combinations(annotator_ids, 2):
        left, right = [], []
        left_spans, right_spans = set(), set()
        shared = 0
        for item in items:
            lookup = {a.user_id: a.payload for a in by_item[item.id]}
            if left_id not in lookup or right_id not in lookup:
                continue
            shared += 1
            a, b = lookup[left_id], lookup[right_id]
            if project.mode == "ner":
                left.extend(bio(item.tokens, a["spans"]))
                right.extend(bio(item.tokens, b["spans"]))
                left_spans.update((item.id, *s) for s in span_set(a["spans"]))
                right_spans.update((item.id, *s) for s in span_set(b["spans"]))
            else:
                key = "label" if project.mode == "rating" else "choice"
                left.append(a[key])
                right.append(b[key])
        f1 = (
            (
                2 * len(left_spans & right_spans) / (len(left_spans) + len(right_spans))
                if left_spans or right_spans
                else 1.0
            )
            if shared and project.mode == "ner"
            else None
        )
        pairs.append(
            {
                "left": left_id,
                "right": right_id,
                "shared_items": shared,
                "kappa": cohen(left, right),
                "span_f1": f1,
            }
        )
    total, submitted = len(items), len(annotations)
    return {
        "revision": project.metric_revision,
        "total_items": total,
        "submissions": submitted,
        "expected_submissions": total * project.target_raters,
        "fully_rated": sum(len(a) == project.target_raters for a in by_item.values()),
        "resolved": sum(i["resolved"] for i in item_metrics),
        "unresolved": sum(
            not i["resolved"] and i["submitted"] >= project.target_raters for i in item_metrics
        ),
        "coverage": submitted / (total * project.target_raters) if total else 0,
        "fleiss": fleiss(rows, project.target_raters),
        "distribution": dict(distribution),
        "annotators": {u.id: u.name for u in users if u.id in annotator_ids},
        "pairs": pairs,
        "items": item_metrics,
    }

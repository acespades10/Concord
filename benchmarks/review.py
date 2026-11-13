"""Automatic source-reference adjudication for the controlled SMS simulation."""

from __future__ import annotations

import hashlib
import json

import httpx


def _annotations(items: list[dict]) -> dict:
    return {
        row["item"]["external_id"]: sorted(
            row["annotations"], key=lambda annotation: json.dumps(annotation, sort_keys=True)
        )
        for row in items
    }


def _digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


async def review_project(
    reviewer: httpx.AsyncClient, project_id: str, reference_labels: dict
) -> dict:
    """Inspect every item and explicitly adjudicate using supplied source labels.

    This is an automatic benchmark operation with access to the answers, not a
    human review or an estimate of annotator accuracy on unseen examples.
    """
    root = f"/api/v1/projects/{project_id}"

    async def read(path: str) -> list[dict]:
        response = await reviewer.get(root + path)
        response.raise_for_status()
        return response.json()

    queue_before = await read("/review")
    before = await read("/review?all_items=true")
    external_ids = [row["item"]["external_id"] for row in before]
    if len(external_ids) != len(set(external_ids)) or set(external_ids) != set(reference_labels):
        raise ValueError("Review items must uniquely and exactly match the source reference IDs")
    if not before:
        raise ValueError("Review requires at least one fully rated item")
    queued_ids = [row["item"]["external_id"] for row in queue_before]
    expected_queue = {
        row["item"]["external_id"]
        for row in before
        if not row["agreement"]["resolved"] and row["agreement"]["submitted"] >= 3
    }
    if len(set(queued_ids)) != len(queued_ids) or set(queued_ids) != expected_queue:
        raise RuntimeError("Disagreement queue differs from unresolved fully rated items")

    evidence = []
    for row in sorted(before, key=lambda item: item["item"]["external_id"]):
        external_id = row["item"]["external_id"]
        label = reference_labels[external_id]
        if not isinstance(label, str) or not label:
            raise ValueError(f"Invalid source reference label for {external_id}")
        annotations = row["annotations"]
        if len(annotations) != 3 or row["agreement"]["submitted"] != 3:
            raise ValueError(f"Review requires three submitted ratings for {external_id}")
        votes = [annotation["payload"]["label"] for annotation in annotations]
        unanimous = len(set(votes)) == 1
        evidence.append(
            {
                "external_id": external_id,
                "item_id": row["item"]["id"],
                "votes": sorted(votes),
                "disagreement": not unanimous,
                "unanimous_wrong": unanimous and votes[0] != label,
                "reference_label": label,
                "rationale": (
                    f"Simulated review of {external_id}: set label to {label!r} using the "
                    "source reference label. Automatic reference-based adjudication; "
                    "no human judgment was performed."
                ),
            }
        )

    raw_before = _annotations(before)
    for item in evidence:
        response = await reviewer.put(
            root + f"/items/{item['item_id']}/adjudication",
            json={
                "mode": "rating",
                "payload": {"label": item["reference_label"]},
                "rationale": item["rationale"],
            },
        )
        response.raise_for_status()

    after = await read("/review?all_items=true")
    queue_after = await read("/review")
    raw_after = _annotations(after)
    after_ids = [row["item"]["external_id"] for row in after]
    if len(after_ids) != len(external_ids) or set(after_ids) != set(external_ids):
        raise RuntimeError("Review item coverage changed during adjudication")
    if raw_before != raw_after:
        raise RuntimeError("Submitted annotation payloads changed during adjudication")
    for row in after:
        label = reference_labels[row["item"]["external_id"]]
        decision = row["adjudication"]
        if (
            not decision
            or decision["payload"].get("label") != label
            or not row["agreement"]["adjudicated"]
            or not row["agreement"]["resolved"]
            or (row["agreement"]["payload"] or {}).get("label") != label
        ):
            raise RuntimeError("Final adjudication does not match the source reference label")
    if queue_after:
        raise RuntimeError("Review queue is not empty after source-reference adjudication")

    return {
        "simulation": True,
        "method": "automatic source-reference adjudication of every item",
        "limitation": (
            "Source labels are supplied to the script. This demonstrates the review workflow, "
            "not human judgment or measured accuracy improvement. Concurrent reviewer writes "
            "remain last-write-wins; this sequential run does not test conflict protection."
        ),
        "inspected_items": len(evidence),
        "adjudicated_items": len(evidence),
        "queue_before": len(queue_before),
        "disagreement_items": sum(item["disagreement"] for item in evidence),
        "unanimous_wrong_items": sum(item["unanimous_wrong"] for item in evidence),
        "queue_after": len(queue_after),
        "raw_annotations_unchanged": True,
        "raw_annotations_sha256_before": _digest(raw_before),
        "raw_annotations_sha256_after": _digest(raw_after),
        "final_labels_match_reference": True,
        "items": evidence,
    }

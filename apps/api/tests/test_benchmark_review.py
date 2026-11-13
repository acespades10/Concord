import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Annotation

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("benchmark_review", ROOT / "benchmarks/review.py")
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


async def test_reviews_all_source_items_including_unanimously_wrong(clients, database):
    labels = json.loads((ROOT / "benchmarks/data/reference-labels.json").read_text("utf-8"))
    rows = [
        json.loads(line)
        for line in (ROOT / "benchmarks/data/dataset.jsonl").read_text("utf-8").splitlines()
    ]
    admin = await clients("admin")
    response = await admin.post(
        "/api/v1/projects",
        json={
            "name": "Source review test",
            "mode": "rating",
            "labels": ["ham", "spam"],
            "target_raters": 3,
            "review_threshold": 0.8,
        },
    )
    assert response.status_code == 201, response.text
    root = f"/api/v1/projects/{response.json()['id']}"
    pid = response.json()["id"]
    assert (
        await admin.put(root + "/members", json={"user_ids": ["rater1", "rater2", "rater3"]})
    ).status_code == 200
    imported = "\n".join(
        json.dumps({"external_id": row["id"], "prompt": row["text"], "response": "Classify SMS"})
        for row in rows
    ).encode("utf-8")
    response = await admin.post(
        root + "/imports", files={"file": ("sms.jsonl", imported, "application/x-ndjson")}
    )
    assert response.status_code == 200, response.text
    assert (await admin.post(root + "/state", json={"state": "active"})).status_code == 200

    positions = {external_id: index for index, external_id in enumerate(sorted(labels))}
    for rater_index in range(3):
        rater = await clients(f"rater{rater_index + 1}")
        for _ in rows:
            response = await rater.post(root + "/assignments/next")
            assert response.status_code == 200, response.text
            assignment = response.json()
            external_id = assignment["item"]["external_id"]
            residue = positions[external_id] % 6
            flipped = (
                residue == 2
                or (residue == 0 and rater_index == 2)
                or (residue == 1 and rater_index == 1)
            )
            source = labels[external_id]
            label = ({"ham": "spam", "spam": "ham"}[source]) if flipped else source
            response = await rater.post(
                f"/api/v1/assignments/{assignment['id']}/submit",
                json={
                    "mode": "rating",
                    "payload": {"label": label},
                    "version": assignment["version"],
                },
            )
            assert response.status_code == 200, response.text

    reviewer = await clients("reviewer")
    before_metrics = (await reviewer.get(root + "/metrics")).json()
    assert before_metrics["resolved"] == 20
    async with database() as session:
        before_annotations = [
            dict(row)
            for row in (
                await session.execute(select(Annotation.__table__).order_by(Annotation.id))
            ).mappings()
        ]

    result = await review.review_project(reviewer, pid, labels)
    assert result["inspected_items"] == result["adjudicated_items"] == 30
    assert result["disagreement_items"] == result["queue_before"] == 10
    assert result["unanimous_wrong_items"] == 5
    assert result["queue_after"] == 0
    assert result["raw_annotations_unchanged"]
    assert result["raw_annotations_sha256_before"] == result["raw_annotations_sha256_after"]
    assert result["final_labels_match_reference"]
    assert result["simulation"]
    json.dumps(result, allow_nan=False)
    inspected = (await reviewer.get(root + "/review?all_items=true")).json()
    assert len(inspected) == 30
    for row in inspected:
        assert row["adjudication"]["payload"]["label"] == labels[row["item"]["external_id"]]
        assert "Simulated review" in row["adjudication"]["rationale"]
        assert "source reference label" in row["adjudication"]["rationale"]
    assert (await reviewer.get(root + "/review")).json() == []
    after_metrics = (await reviewer.get(root + "/metrics")).json()
    assert after_metrics["resolved"] == 30
    for key in ["submissions", "distribution", "fleiss", "pairs"]:
        assert after_metrics[key] == before_metrics[key]
    async with database() as session:
        after_annotations = [
            dict(row)
            for row in (
                await session.execute(select(Annotation.__table__).order_by(Annotation.id))
            ).mappings()
        ]
    assert len(before_annotations) == 90
    assert after_annotations == before_annotations


@pytest.mark.parametrize(
    "labels,error",
    [({"unknown": "Good"}, "exactly match"), ({"item-1": "Good"}, "three submitted")],
)
async def test_rejects_incomplete_review_before_any_decision(
    project_factory, clients, labels, error
):
    pid, _ = await project_factory()
    reviewer = await clients("reviewer")
    with pytest.raises(ValueError, match=error):
        await review.review_project(reviewer, pid, labels)
    rows = (await reviewer.get(f"/api/v1/projects/{pid}/review?all_items=true")).json()
    assert all(row["adjudication"] is None for row in rows)

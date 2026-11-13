"""Checks for the scripted benchmark, using real HTTP workflow writes."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmarks.simulation import SIMULATION_NOTE, build_votes  # noqa: E402


def test_scripted_votes_include_disagreement_and_shared_errors():
    labels = {f"sms-{i:05}": "ham" if i < 15 else "spam" for i in range(30)}
    votes = build_votes(dict(reversed(list(labels.items()))))
    assert list(votes) == sorted(labels)
    assert sum(len(set(row)) > 1 for row in votes.values()) == 10
    assert sum(len(set(row)) == 1 and row[0] != labels[key] for key, row in votes.items()) == 5
    assert sum(len(set(row)) == 1 and row[0] == labels[key] for key, row in votes.items()) == 15
    assert sum(label != labels[key] for key, row in votes.items() for label in row) == 25
    with pytest.raises(ValueError, match="Unsupported reference label"):
        build_votes({"bad": "unknown"})


async def test_benchmark_real_api_roundtrip_and_database_isolation(tmp_path):
    from app.db import get_db
    from app.main import app
    from benchmarks.run import run_benchmark

    previous = app.dependency_overrides.get(get_db)
    output = tmp_path / "run"
    report = await run_benchmark(output, validate=False)
    assert app.dependency_overrides.get(get_db) is previous
    assert report["item_count"] == 30 and report["submission_count"] == 90
    assert report["reference_comparison"]["passed"]
    assert report["metrics_before"]["resolved"] == 20
    assert report["metrics_before"]["unresolved"] == 10
    assert report["metrics_after"]["resolved"] == 30
    assert report["metrics_after"]["unresolved"] == 0
    assert report["metrics_before"]["fleiss"] == report["metrics_after"]["fleiss"]
    assert report["metrics_before"]["pairs"] == report["metrics_after"]["pairs"]
    assert all(probe["passed"] for probe in report["permission_and_workflow_probes"])
    assert not report["passed"]  # A development run cannot claim export validation passed.
    submissions = json.loads((output / "simulated-submissions.json").read_text(encoding="utf-8"))
    assert len(submissions["submissions"]) == 90
    assert all(
        row["simulation"] and row["payload"]["note"] == SIMULATION_NOTE
        for row in submissions["submissions"]
    )
    assert (output / "benchmark.sqlite3").is_file()
    assert (output / "consensus.jsonl").is_file()
    assert (output / "annotations.jsonl").is_file()
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        await run_benchmark(output, validate=False)
    assert app.dependency_overrides.get(get_db) is previous

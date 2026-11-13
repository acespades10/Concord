"""Corrupt hand-built artifacts to exercise the independent export validator."""

import copy
import hashlib
import json
import subprocess
import sys
import unicodedata
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmarks.validate_export import validate_exports  # noqa: E402


def dump(path, value, *, jsonl=False):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in value) + "\n"
        if jsonl
        else json.dumps(value, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def artifacts():
    # Six hand-specified vote rows exercise every documented simulation phase.
    labels = dict(zip([f"sms-{i:05}" for i in range(6)], ["ham", "spam"] * 3, strict=True))
    source = [
        {
            "id": key,
            "text": f"  Café £🙂 {i}\t ",
            "metadata": {"source_row": i + 1, "dataset": "uci_sms_spam_collection"},
        }
        for i, key in enumerate(labels)
    ]
    vote_rows = [
        ["ham", "ham", "spam"],
        ["spam", "ham", "spam"],
        ["spam", "spam", "spam"],
        ["spam", "spam", "spam"],
        ["ham", "ham", "ham"],
        ["spam", "spam", "spam"],
    ]
    votes = dict(zip(labels, vote_rows, strict=True))
    note = "SIMULATED ANNOTATION: scripted benchmark vote; not a human judgment."
    raters = ["rater1", "rater2", "rater3"]
    people = {
        name: str(uuid.uuid5(uuid.NAMESPACE_URL, f"concord-benchmark/{name}"))
        for name in [*raters, "reviewer"]
    }
    project = {
        "id": str(uuid.uuid4()),
        "name": "UCI SMS controlled annotation benchmark",
        "description": "Local scripted simulation; not a human quality study. Gold labels stay outside the imported project.",
        "mode": "rating",
        "state": "completed",
        "labels": ["ham", "spam"],
        "ordered": False,
        "target_raters": 3,
        "review_threshold": 0.8,
        "metric_revision": 27,
    }

    def manifest(selection, count):
        return {
            "_manifest": {
                "schema_version": "1.0.0",
                "project": copy.deepcopy(project),
                "offset_unit": "unicode_code_points",
                "ab_identity": "canonical_response_a_and_response_b",
                "metadata_encoding": "metadata_json contains lossless JSON",
                "raw_status": "submitted_only",
                "include_unresolved": False,
                "datasets": {selection: count},
            }
        }

    consensus = [manifest("consensus", 6)]
    annotations = [manifest("annotations", 18)]
    submissions = {
        "simulation": True,
        "note": note,
        "policy": "Sort external IDs, then use zero-based index modulo 6: 0 flips rater3; 1 flips rater2; 2 flips all three; 3, 4 and 5 keep the reference label. The reference drives a controlled error simulation, not a blinded annotation study.",
        "raters": raters,
        "votes": votes,
        "submissions": [],
    }
    for i, row in enumerate(source):
        key, label = row["id"], labels[row["id"]]
        base = {
            "schema_version": "1.0.0",
            "project_id": project["id"],
            "item_id": str(uuid.uuid4()),
            "external_id": key,
            "mode": "rating",
            "tokens": [],
            "content": {"prompt": row["text"], "response": "Classify this message as ham or spam."},
            "metadata_json": json.dumps({"metadata": row["metadata"]}),
        }
        consensus.append(
            {
                **copy.deepcopy(base),
                "payload": {"label": label, "note": ""},
                "resolved": True,
                "vote_share": 2 / 3 if i < 2 else 1.0,
                "resolution": "adjudicated",
                "reviewer_id": people["reviewer"],
                "rationale": f"Simulated review of {key}: set label to {label!r} using the source reference label. Automatic reference-based adjudication; no human judgment was performed.",
            }
        )
        for rater_index, rater in enumerate(raters):
            payload = {"label": vote_rows[i][rater_index], "note": note}
            annotations.append(
                {
                    **copy.deepcopy(base),
                    "annotator_id": people[rater],
                    "payload": payload.copy(),
                    "submitted_at": 1700000000 + i,
                }
            )
            submissions["submissions"].append(
                {
                    "external_id": key,
                    "annotator": rater,
                    "annotator_id": people[rater],
                    "assignment_id": str(uuid.uuid4()),
                    "payload": payload.copy(),
                    "simulation": True,
                }
            )
    return dict(
        dataset=source,
        reference=labels,
        consensus=consensus,
        annotations=annotations,
        submissions=submissions,
    )


def write_artifacts(tmp_path, artifacts):
    paths = {}
    for name, value in artifacts.items():
        jsonl = name in {"dataset", "consensus", "annotations"}
        paths[name] = tmp_path / (name + (".jsonl" if jsonl else ".json"))
        dump(paths[name], value, jsonl=jsonl)
    return paths


def test_valid_hand_built_exports_preserve_source_text_and_hashes(tmp_path, artifacts):
    paths = write_artifacts(tmp_path, artifacts)
    report = validate_exports(**paths)
    assert report["passed"], report
    assert report["counts"] == {
        "dataset": 6,
        "reference": 6,
        "consensus": 6,
        "annotations": 18,
        "submissions": 18,
        "unique_items": 6,
        "raters": 3,
        "adjudicated": 6,
    }
    assert all(check["passed"] for check in report["checks"])
    for name, path in paths.items():
        assert report["files"][name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_unicode_line_separators_inside_sms_are_preserved(tmp_path, artifacts):
    text = "before\u0085middle\u2028after\u2029 "
    artifacts["dataset"][0]["text"] = text
    artifacts["consensus"][1]["content"]["prompt"] = text
    for row in artifacts["annotations"][1:4]:
        row["content"]["prompt"] = text
    report = validate_exports(**write_artifacts(tmp_path, artifacts))
    assert report["passed"], report


def corrupt(artifacts, mutation):
    con, raw, script = artifacts["consensus"], artifacts["annotations"], artifacts["submissions"]
    if mutation == "trimmed text":
        con[1]["content"]["prompt"] = con[1]["content"]["prompt"].strip()
    elif mutation == "normalized unicode":
        raw[1]["content"]["prompt"] = unicodedata.normalize("NFD", raw[1]["content"]["prompt"])
    elif mutation == "changed response":
        raw[1]["content"]["response"] += "!"
    elif mutation == "wrong consensus truth":
        con[1]["payload"]["label"] = "spam"
    elif mutation == "missing consensus note":
        con[1]["payload"].pop("note")
    elif mutation == "changed consensus note":
        con[1]["payload"]["note"] = "not the approved empty API default"
    elif mutation == "invalid label":
        raw[1]["payload"]["label"] = "maybe"
    elif mutation == "changed raw vote":
        raw[1]["payload"]["label"] = "spam"
    elif mutation == "coordinated scripted tampering":
        script["votes"]["sms-00000"][0] = "spam"
        script["submissions"][0]["payload"]["label"] = "spam"
        raw[1]["payload"]["label"] = "spam"
    elif mutation == "duplicate consensus":
        con[-1] = copy.deepcopy(con[1])
    elif mutation == "duplicate raw pair":
        raw[-1] = copy.deepcopy(raw[1])
    elif mutation == "duplicate script pair":
        script["submissions"][-1] = copy.deepcopy(script["submissions"][0])
        script["submissions"][-1]["assignment_id"] = str(uuid.uuid4())
    elif mutation == "duplicate assignment":
        script["submissions"][1]["assignment_id"] = script["submissions"][0]["assignment_id"]
    elif mutation == "unknown source":
        raw[1]["external_id"] = "unknown"
    elif mutation == "missing consensus":
        con.pop()
    elif mutation == "missing raw":
        raw.pop()
    elif mutation == "missing script":
        script["submissions"].pop()
    elif mutation == "missing reference":
        artifacts["reference"].pop("sms-00000")
    elif mutation == "duplicate source":
        artifacts["dataset"][-1] = copy.deepcopy(artifacts["dataset"][0])
    elif mutation == "email identity":
        raw[1]["annotator_id"] = "rater1@benchmark.invalid"
    elif mutation == "wrong reviewer":
        con[1]["reviewer_id"] = str(uuid.uuid4())
    elif mutation == "unresolved":
        con[1]["resolved"] = False
    elif mutation == "automatic consensus":
        con[1]["resolution"] = "consensus"
    elif mutation == "missing rationale":
        con[1]["rationale"] = None
    elif mutation == "changed vote share":
        con[1]["vote_share"] = 1.0
    elif mutation == "simulation concealed":
        raw[1]["payload"].pop("note")
    elif mutation == "simulation flag concealed":
        script["simulation"] = False
    elif mutation == "metadata injection":
        raw[1]["metadata_json"] = json.dumps(
            {"metadata": artifacts["dataset"][0]["metadata"], "gold_label": "ham"}
        )
    elif mutation == "shared leaked metadata":
        artifacts["dataset"][0]["metadata"]["gold_label"] = "ham"
        for row in [con[1], *raw[1:4]]:
            row["metadata_json"] = json.dumps({"metadata": artifacts["dataset"][0]["metadata"]})
    elif mutation == "shared email metadata":
        artifacts["dataset"][0]["metadata"]["contact"] = "person@example.com"
    elif mutation == "metadata numeric type":
        metadata = json.loads(raw[1]["metadata_json"])
        metadata["metadata"]["source_row"] = True
        raw[1]["metadata_json"] = json.dumps(metadata)
    elif mutation == "unknown row field":
        raw[1]["password_hash"] = "private"
    elif mutation == "unknown manifest field":
        con[0]["_manifest"]["auth"] = "private"
    elif mutation == "manifest count":
        con[0]["_manifest"]["datasets"]["consensus"] += 1
    elif mutation == "manifest selection":
        con[0]["_manifest"]["datasets"] = {"annotations": 6}
    elif mutation == "manifest schema":
        con[0]["_manifest"]["schema_version"] = "99.0.0"
    elif mutation == "manifest unresolved":
        con[0]["_manifest"]["include_unresolved"] = True
    elif mutation == "manifest config":
        con[0]["_manifest"]["project"]["review_threshold"] = 0.5
    elif mutation == "manifest different project":
        con[0]["_manifest"]["project"]["id"] = str(uuid.uuid4())
    elif mutation == "row different project":
        raw[1]["project_id"] = str(uuid.uuid4())
    elif mutation == "different item mapping":
        raw[1]["item_id"] = str(uuid.uuid4())
    elif mutation == "reused item ID":
        con[2]["item_id"] = con[1]["item_id"]
    elif mutation == "invalid timestamp":
        raw[1]["submitted_at"] = True
    elif mutation == "missing manifest":
        con.pop(0)
    else:
        raise AssertionError(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        "trimmed text",
        "normalized unicode",
        "changed response",
        "wrong consensus truth",
        "missing consensus note",
        "changed consensus note",
        "invalid label",
        "changed raw vote",
        "coordinated scripted tampering",
        "duplicate consensus",
        "duplicate raw pair",
        "duplicate script pair",
        "duplicate assignment",
        "unknown source",
        "missing consensus",
        "missing raw",
        "missing script",
        "missing reference",
        "duplicate source",
        "email identity",
        "wrong reviewer",
        "unresolved",
        "automatic consensus",
        "missing rationale",
        "changed vote share",
        "simulation concealed",
        "simulation flag concealed",
        "metadata injection",
        "shared leaked metadata",
        "shared email metadata",
        "metadata numeric type",
        "unknown row field",
        "unknown manifest field",
        "manifest count",
        "manifest selection",
        "manifest schema",
        "manifest unresolved",
        "manifest config",
        "manifest different project",
        "row different project",
        "different item mapping",
        "reused item ID",
        "invalid timestamp",
        "missing manifest",
    ],
)
def test_corruption_fails_closed(tmp_path, artifacts, mutation):
    corrupt(artifacts, mutation)
    report = validate_exports(**write_artifacts(tmp_path, artifacts))
    assert report["passed"] is False, mutation
    assert report["error"]
    assert any(check["passed"] is False for check in report["checks"])


@pytest.mark.parametrize(
    "mutation",
    ["duplicate json key", "nonfinite json", "blank record", "invalid json", "missing file"],
)
def test_malformed_and_missing_input(tmp_path, artifacts, mutation):
    paths = write_artifacts(tmp_path, artifacts)
    target = paths["annotations"]
    content = target.read_text(encoding="utf-8")
    if mutation == "duplicate json key":
        target.write_text(
            content.replace('"mode": "rating"', '"mode": "rating", "mode": "rating"', 1),
            encoding="utf-8",
        )
    elif mutation == "nonfinite json":
        target.write_text(
            content.replace('"submitted_at": 1700000000', '"submitted_at": NaN', 1),
            encoding="utf-8",
        )
    elif mutation == "blank record":
        target.write_text(content + "\n", encoding="utf-8")
    elif mutation == "invalid json":
        target.write_text(content + "broken\n", encoding="utf-8")
    else:
        target.unlink()
    report = validate_exports(**paths)
    assert report["passed"] is False
    assert report["error"]


def test_cli_without_site_packages_success_failure_and_output_protection(tmp_path, artifacts):
    paths = write_artifacts(tmp_path, artifacts)
    output = tmp_path / "validation.json"
    command = [sys.executable, "-S", "-m", "benchmarks.validate_export"]
    for name, path in paths.items():
        command.extend([f"--{name}", str(path)])
    command.extend(["--output", str(output)])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
    paths["annotations"].unlink()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is False
    protected = command[:-1] + [str(paths["dataset"])]
    original = paths["dataset"].read_bytes()
    result = subprocess.run(protected, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert paths["dataset"].read_bytes() == original


async def test_real_api_benchmark_exports_pass_independent_cli(tmp_path):
    # Unlike the hand-built corruption fixtures, this test checks the actual
    # API serialization contract, including RatingPayload's default empty note.
    from benchmarks.run import run_benchmark

    output = tmp_path / "real-api-benchmark"
    report = await run_benchmark(output, validate=True)
    assert report["passed"], report["independent_export_validation"]
    assert report["independent_export_validation"]["exit_code"] == 0
    validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
    assert validation["passed"]
    assert validation["counts"]["consensus"] == 30
    assert validation["counts"]["annotations"] == 90
    assert validation["counts"]["adjudicated"] == 30

"""Validate the controlled SMS benchmark exports without importing Concord code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import uuid
from collections import Counter
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
SIMULATION_NOTE = "SIMULATED ANNOTATION: scripted benchmark vote; not a human judgment."
POLICY = (
    "Sort external IDs, then use zero-based index modulo 6: 0 flips rater3; "
    "1 flips rater2; 2 flips all three; 3, 4 and 5 keep the reference label. "
    "The reference drives a controlled error simulation, not a blinded annotation study."
)
RATERS = ("rater1", "rater2", "rater3")
RESPONSE = "Classify this message as ham or spam."
BASE_FIELDS = {
    "schema_version",
    "project_id",
    "item_id",
    "external_id",
    "mode",
    "content",
    "metadata_json",
    "tokens",
}
RAW_FIELDS = BASE_FIELDS | {"annotator_id", "payload", "submitted_at"}
CONSENSUS_FIELDS = BASE_FIELDS | {
    "payload",
    "resolved",
    "vote_share",
    "resolution",
    "reviewer_id",
    "rationale",
}
MANIFEST_FIELDS = {
    "schema_version",
    "project",
    "offset_unit",
    "ab_identity",
    "metadata_encoding",
    "raw_status",
    "include_unresolved",
    "datasets",
}
PROJECT_FIELDS = {
    "id",
    "name",
    "description",
    "mode",
    "state",
    "labels",
    "ordered",
    "target_raters",
    "review_threshold",
    "metric_revision",
}
EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.IGNORECASE)
SECRET = re.compile(
    r"\bBearer\s+\S+|\$argon2\w*\$|-----BEGIN [A-Z ]*PRIVATE KEY-----|\beyJ[\w-]+\.[\w-]+\.[\w-]+",
    re.IGNORECASE,
)
PRIVATE_KEYS = {
    "email",
    "emails",
    "password",
    "passwordhash",
    "token",
    "tokenhash",
    "auth",
    "authorization",
    "cookie",
    "cookies",
    "session",
    "sessionid",
    "csrf",
    "secret",
    "apikey",
    "gold",
    "goldlabel",
    "goldlabels",
    "label",
    "labels",
    "truth",
    "groundtruth",
    "reference",
    "referencelabel",
    "referencelabels",
    "expectedlabel",
}


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def object_fields(value, fields: set[str], where: str) -> None:
    require(isinstance(value, dict), f"{where}: expected an object")
    require(set(value) == fields, f"{where}: missing or unknown fields")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValidationError(f"Non-finite JSON constant: {value}")


def parse_json(text: str):
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def parse_jsonl(data: bytes, name: str) -> list[dict]:
    # JSONL separates records with LF; Unicode line separators can be SMS text.
    lines = data.decode("utf-8").split("\n")
    if lines[-1] == "":
        lines.pop()
    require(bool(lines), f"{name}: empty file")
    result = []
    for number, line in enumerate(lines, 1):
        require(bool(line.strip()), f"{name}:{number}: blank record")
        value = parse_json(line)
        require(isinstance(value, dict), f"{name}:{number}: expected an object")
        result.append(value)
    return result


def canonical(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def pseudonym(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"concord-benchmark/{name}"))


def valid_uuid(value, where: str) -> None:
    require(isinstance(value, str), f"{where}: UUID must be a string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise ValidationError(f"{where}: invalid UUID") from error
    require(str(parsed) == value, f"{where}: UUID must use canonical spelling")


def privacy(value, where: str) -> None:
    """Check metadata and free text outside the preserved source SMS content."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            require(
                normalized not in PRIVATE_KEYS,
                f"{where}: private or reference-label metadata key",
            )
            privacy(child, where)
    elif isinstance(value, list):
        for child in value:
            privacy(child, where)
    elif isinstance(value, str):
        require(not EMAIL.search(value), f"{where}: email address found")
        require(not SECRET.search(value), f"{where}: authentication secret found")


def expected_votes(labels: dict[str, str]) -> dict[str, list[str]]:
    """Independent implementation of the documented six-item simulation cycle."""
    votes = {}
    for position, external_id in enumerate(sorted(labels)):
        truth = labels[external_id]
        opposite = {"ham": "spam", "spam": "ham"}[truth]
        phase = position % 6
        votes[external_id] = [
            opposite
            if phase == 2 or (phase == 0 and rater == 2) or (phase == 1 and rater == 1)
            else truth
            for rater in range(3)
        ]
    return votes


def validate_exports(
    dataset: Path,
    reference: Path,
    consensus: Path,
    annotations: Path,
    submissions: Path,
) -> dict:
    """Return a JSON-serializable report; invalid or missing input always fails."""
    paths = {
        "dataset": dataset,
        "reference": reference,
        "consensus": consensus,
        "annotations": annotations,
        "submissions": submissions,
    }
    report = {
        "validator_version": "1.0.0",
        "passed": False,
        "simulation": True,
        "note": "Scripted votes and automatic source-reference adjudication; no human agreement or quality claim.",
        "counts": {},
        "checks": [],
        "files": {},
    }
    data = {}

    def check(name, operation):
        entry = {"name": name, "passed": False}
        report["checks"].append(entry)
        result = operation()
        entry["passed"] = True
        return result

    try:

        def read_inputs():
            for name, value in paths.items():
                path = Path(value)
                info = {"path": str(path.resolve()), "sha256": None, "bytes": None}
                report["files"][name] = info
                content = path.read_bytes()
                info.update(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
                data[name] = content
            require(
                len({str(Path(p).resolve()) for p in paths.values()}) == len(paths),
                "Inputs must be distinct files",
            )

        check("read_all_inputs_and_hash_exact_bytes", read_inputs)

        def parse_inputs():
            source = parse_jsonl(data["dataset"], "dataset")
            labels = parse_json(data["reference"].decode("utf-8"))
            con = parse_jsonl(data["consensus"], "consensus")
            raw = parse_jsonl(data["annotations"], "annotations")
            scripted = parse_json(data["submissions"].decode("utf-8"))
            require(isinstance(labels, dict), "reference: expected an ID-to-label object")
            require(isinstance(scripted, dict), "submissions: expected an object")
            return source, labels, con, raw, scripted

        source, labels, con, raw, scripted = check("strict_json_and_jsonl", parse_inputs)
        report["counts"].update(
            dataset=len(source),
            reference=len(labels),
            consensus=len(con) - 1,
            annotations=len(raw) - 1,
        )

        def check_source():
            by_id = {}
            for row in source:
                object_fields(row, {"id", "text", "metadata"}, "dataset row")
                external_id = row["id"]
                require(
                    isinstance(external_id, str) and bool(external_id),
                    "dataset: invalid ID",
                )
                require(external_id not in by_id, "dataset: duplicate ID")
                require(
                    isinstance(row["text"], str) and bool(row["text"]),
                    "dataset: invalid text",
                )
                require(
                    isinstance(row["metadata"], dict),
                    "dataset: metadata must be an object",
                )
                privacy(row["metadata"], "source metadata")
                by_id[external_id] = row
            require(bool(by_id), "dataset: no records")
            require(set(labels) == set(by_id), "reference: IDs do not exactly match dataset")
            require(
                all(value in ("ham", "spam") for value in labels.values()),
                "reference: invalid label",
            )
            return by_id

        by_id = check("source_unique_ids_valid_labels_and_safe_metadata", check_source)
        votes = expected_votes(labels)

        def check_manifest(records, selection):
            object_fields(records[0], {"_manifest"}, f"{selection} leading record")
            manifest = records[0]["_manifest"]
            object_fields(manifest, MANIFEST_FIELDS, f"{selection} manifest")
            project = manifest["project"]
            object_fields(project, PROJECT_FIELDS, f"{selection} project")
            valid_uuid(project["id"], "project ID")
            require(
                project["name"] == "UCI SMS controlled annotation benchmark",
                "Unexpected benchmark project name",
            )
            require(
                project["description"]
                == "Local scripted simulation; not a human quality study. Gold labels stay outside the imported project.",
                "Unexpected benchmark project description",
            )
            require(
                project["mode"] == "rating" and project["state"] == "completed",
                "Project must be completed rating mode",
            )
            require(
                project["labels"] == ["ham", "spam"] and project["ordered"] is False,
                "Invalid project label configuration",
            )
            require(
                type(project["target_raters"]) is int and project["target_raters"] == 3,
                "Invalid target rater count",
            )
            require(
                type(project["review_threshold"]) in (int, float)
                and project["review_threshold"] == 0.8,
                "Invalid review threshold",
            )
            require(
                type(project["metric_revision"]) is int and project["metric_revision"] > 0,
                "Invalid metric revision",
            )
            require(
                manifest["schema_version"] == SCHEMA_VERSION,
                "Unsupported manifest schema version",
            )
            require(
                manifest["offset_unit"] == "unicode_code_points",
                "Wrong offset convention",
            )
            require(
                manifest["ab_identity"] == "canonical_response_a_and_response_b",
                "Wrong response identity convention",
            )
            require(
                manifest["metadata_encoding"] == "metadata_json contains lossless JSON",
                "Wrong metadata encoding",
            )
            require(
                manifest["raw_status"] == "submitted_only",
                "Raw export must contain submitted annotations only",
            )
            require(
                manifest["include_unresolved"] is False,
                "Unresolved exports are not approved",
            )
            require(
                isinstance(manifest["datasets"], dict) and set(manifest["datasets"]) == {selection},
                "Manifest selection mismatch",
            )
            count = manifest["datasets"][selection]
            expected = len(by_id) * (3 if selection == "annotations" else 1)
            require(
                type(count) is int and count == len(records) - 1 == expected,
                "Manifest or actual record count mismatch",
            )
            privacy(project["name"], "project name")
            privacy(project["description"], "project description")
            return project

        con_project = check(
            "consensus_manifest_schema_configuration_selection_counts",
            lambda: check_manifest(con, "consensus"),
        )
        raw_project = check(
            "annotations_manifest_schema_configuration_selection_counts",
            lambda: check_manifest(raw, "annotations"),
        )
        check(
            "same_project_and_metric_revision",
            lambda: require(
                canonical(con_project) == canonical(raw_project),
                "Export projects or configurations differ",
            ),
        )
        report["project_id"] = con_project["id"]

        def check_submissions():
            object_fields(
                scripted,
                {"simulation", "note", "policy", "raters", "votes", "submissions"},
                "submissions artifact",
            )
            require(
                scripted["simulation"] is True and scripted["note"] == SIMULATION_NOTE,
                "Missing simulation disclosure",
            )
            require(
                scripted["policy"] == POLICY and scripted["raters"] == list(RATERS),
                "Simulation policy or rater order mismatch",
            )
            require(
                canonical(scripted["votes"]) == canonical(votes),
                "Recorded votes differ from independently reconstructed simulation",
            )
            records = scripted["submissions"]
            require(
                isinstance(records, list) and len(records) == len(by_id) * 3,
                "Wrong number of scripted submissions",
            )
            report["counts"]["submissions"] = len(records)
            pairs, assignments = {}, set()
            for row in records:
                object_fields(
                    row,
                    {
                        "external_id",
                        "annotator",
                        "annotator_id",
                        "assignment_id",
                        "payload",
                        "simulation",
                    },
                    "scripted submission",
                )
                external_id, annotator = row["external_id"], row["annotator"]
                require(
                    isinstance(external_id, str) and external_id in by_id,
                    "Unknown scripted source ID",
                )
                require(annotator in RATERS, "Unknown scripted rater")
                require(
                    row["annotator_id"] == pseudonym(annotator),
                    "Scripted rater pseudonym mismatch",
                )
                valid_uuid(row["assignment_id"], "assignment ID")
                require(row["assignment_id"] not in assignments, "Duplicate assignment ID")
                assignments.add(row["assignment_id"])
                require(
                    row["simulation"] is True,
                    "Scripted submission missing simulation flag",
                )
                expected = {
                    "label": votes[external_id][RATERS.index(annotator)],
                    "note": SIMULATION_NOTE,
                }
                require(
                    canonical(row["payload"]) == canonical(expected),
                    "Scripted payload differs from policy",
                )
                pair = external_id, row["annotator_id"]
                require(pair not in pairs, "Duplicate scripted item/rater pair")
                pairs[pair] = row["payload"]
            expected_pairs = {
                (external_id, pseudonym(rater)) for external_id in by_id for rater in RATERS
            }
            require(set(pairs) == expected_pairs, "Scripted item/rater coverage incomplete")
            return pairs

        scripted_pairs = check(
            "scripted_votes_independent_policy_and_complete_unique_submissions",
            check_submissions,
        )

        item_ids, reverse_ids = {}, {}

        def check_base(row, fields):
            object_fields(row, fields, "export row")
            external_id = row["external_id"]
            require(
                isinstance(external_id, str) and external_id in by_id,
                "Unknown export external ID",
            )
            require(
                row["schema_version"] == SCHEMA_VERSION and row["mode"] == "rating",
                "Row schema or mode mismatch",
            )
            require(row["project_id"] == con_project["id"], "Row project ID mismatch")
            valid_uuid(row["item_id"], "item ID")
            require(
                item_ids.get(external_id, row["item_id"]) == row["item_id"],
                "Inconsistent item ID for source",
            )
            require(
                reverse_ids.get(row["item_id"], external_id) == external_id,
                "Item ID reused for different source IDs",
            )
            item_ids[external_id], reverse_ids[row["item_id"]] = (
                row["item_id"],
                external_id,
            )
            expected_content = {
                "prompt": by_id[external_id]["text"],
                "response": RESPONSE,
            }
            require(
                canonical(row["content"]) == canonical(expected_content),
                "Source text/content changed (including whitespace or Unicode)",
            )
            require(
                isinstance(row["metadata_json"], str),
                "metadata_json must be a JSON string",
            )
            metadata = parse_json(row["metadata_json"])
            require(
                canonical(metadata) == canonical({"metadata": by_id[external_id]["metadata"]}),
                "Metadata does not roundtrip exactly",
            )
            privacy(metadata, "export metadata")
            require(row["tokens"] == [], "Rating export unexpectedly contains tokens")
            return external_id

        def check_raw():
            observed = set()
            for row in raw[1:]:
                external_id = check_base(row, RAW_FIELDS)
                pair = external_id, row["annotator_id"]
                require(
                    isinstance(row["annotator_id"], str) and pair in scripted_pairs,
                    "Unknown export annotator/item pair",
                )
                require(pair not in observed, "Duplicate raw item/rater pair")
                observed.add(pair)
                require(
                    canonical(row["payload"]) == canonical(scripted_pairs[pair]),
                    "Raw annotation payload changed from scripted submission",
                )
                stamp = row["submitted_at"]
                require(
                    type(stamp) in (int, float) and math.isfinite(stamp) and stamp > 0,
                    "Invalid submitted timestamp",
                )
            require(observed == set(scripted_pairs), "Missing raw item/rater pairs")

        check(
            "raw_exact_source_roundtrip_pseudonyms_payloads_unique_complete_coverage",
            check_raw,
        )

        def check_consensus():
            seen = set()
            for row in con[1:]:
                external_id = check_base(row, CONSENSUS_FIELDS)
                require(external_id not in seen, "Duplicate consensus source ID")
                seen.add(external_id)
                require(
                    row["resolved"] is True and row["resolution"] == "adjudicated",
                    "Consensus row lacks approved adjudication",
                )
                require(
                    row["reviewer_id"] == pseudonym("reviewer"),
                    "Consensus reviewer pseudonym mismatch",
                )
                require(
                    canonical(row["payload"])
                    == canonical({"label": labels[external_id], "note": ""}),
                    "Consensus payload differs from source truth or approved empty note",
                )
                rationale = (
                    f"Simulated review of {external_id}: set label to {labels[external_id]!r} using the source reference label. "
                    "Automatic reference-based adjudication; no human judgment was performed."
                )
                require(
                    row["rationale"] == rationale,
                    "Missing or changed automatic-review rationale",
                )
                privacy(row["rationale"], "review rationale")
                expected_share = max(Counter(votes[external_id]).values()) / 3
                require(
                    type(row["vote_share"]) in (int, float)
                    and math.isclose(row["vote_share"], expected_share, rel_tol=0, abs_tol=1e-12),
                    "Consensus vote_share does not preserve raw-vote support",
                )
            require(seen == set(by_id), "Consensus source coverage incomplete")

        check(
            "consensus_exact_source_roundtrip_truth_adjudication_reviewer_and_raw_vote_support",
            check_consensus,
        )
        report["counts"].update(
            unique_items=len(item_ids), raters=len(RATERS), adjudicated=len(con) - 1
        )
        report["passed"] = True
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        report["error"] = str(error)
        if report["checks"]:
            report["checks"][-1]["error"] = str(error)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "dataset",
        "reference",
        "consensus",
        "annotations",
        "submissions",
        "output",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = {
        name: getattr(args, name)
        for name in ("dataset", "reference", "consensus", "annotations", "submissions")
    }
    if args.output.resolve() in {path.resolve() for path in inputs.values()}:
        parser.error("--output must not overwrite an input file")
    report = validate_exports(**inputs)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        print(f"Cannot write validation report: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "counts": report["counts"],
                "output": str(args.output.resolve()),
                **({"error": report["error"]} if "error" in report else {}),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

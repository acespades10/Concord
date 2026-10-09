import io
import json
import tempfile
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from datasets import Dataset, DatasetDict

from app.agreement import calculate

SCHEMA_VERSION = "1.0.0"
SPAN = pa.struct(
    [("start", pa.int64()), ("end", pa.int64()), ("label", pa.string()), ("text", pa.string())]
)
PAYLOAD = pa.struct(
    [
        ("label", pa.string()),
        ("choice", pa.string()),
        ("note", pa.string()),
        ("spans", pa.list_(SPAN)),
    ]
)
SCHEMA = pa.schema(
    [
        ("schema_version", pa.string()),
        ("project_id", pa.string()),
        ("item_id", pa.string()),
        ("external_id", pa.string()),
        ("mode", pa.string()),
        (
            "content",
            pa.struct(
                [
                    (k, pa.string())
                    for k in ["prompt", "response", "text", "response_a", "response_b"]
                ]
            ),
        ),
        ("metadata_json", pa.string()),
        (
            "tokens",
            pa.list_(
                pa.struct([("start", pa.int64()), ("end", pa.int64()), ("text", pa.string())])
            ),
        ),
        ("annotator_id", pa.string()),
        ("payload", PAYLOAD),
        ("submitted_at", pa.float64()),
        ("resolved", pa.bool_()),
        ("vote_share", pa.float64()),
        ("resolution", pa.string()),
        ("reviewer_id", pa.string()),
        ("rationale", pa.string()),
    ]
)


def json_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def build_rows(project, items, annotations, decisions, users, include_unresolved):
    people = {u.id: u.pseudonym for u in users}
    lookup = {i.id: i for i in items}

    def base(item):
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": project.id,
            "item_id": item.id,
            "external_id": item.external_id,
            "mode": project.mode,
            "content": item.content,
            "metadata_json": json_bytes(item.extra).decode(),
            "tokens": item.tokens,
        }

    raw = [
        {
            **base(lookup[a.item_id]),
            "annotator_id": people[a.user_id],
            "payload": a.payload,
            "submitted_at": a.submitted_at,
        }
        for a in annotations
    ]
    raw.sort(key=lambda x: (x["external_id"], x["annotator_id"]))
    decisions_by_item = {a.item_id: a for a in decisions}
    agreement = calculate(project, items, annotations, decisions, users)
    resolved = []
    for item in agreement["items"]:
        if not item["resolved"] and not include_unresolved:
            continue
        decision = decisions_by_item.get(item["item_id"])
        resolved.append(
            {
                **base(lookup[item["item_id"]]),
                "payload": item["payload"],
                "resolved": item["resolved"],
                "vote_share": item["vote_share"],
                "resolution": "adjudicated"
                if decision
                else "consensus"
                if item["resolved"]
                else item["reason"],
                "reviewer_id": people[decision.reviewer_id] if decision else None,
                "rationale": decision.rationale if decision else None,
            }
        )
    resolved.sort(key=lambda x: x["external_id"])
    return {"annotations": raw, "consensus": resolved}


def manifest_for(project, datasets, include_unresolved):
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            key: getattr(project, key)
            for key in [
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
            ]
        },
        "offset_unit": "unicode_code_points",
        "ab_identity": "canonical_response_a_and_response_b",
        "metadata_encoding": "metadata_json contains lossless JSON",
        "raw_status": "submitted_only",
        "include_unresolved": include_unresolved,
        "datasets": {name: len(rows) for name, rows in datasets.items()},
    }


def add_zip(archive, name, data):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def export_artifact(project, data, selection, fmt, include_unresolved):
    rows = build_rows(project, *data, include_unresolved)
    selected = rows if selection == "both" else {selection: rows[selection]}
    manifest = manifest_for(project, selected, include_unresolved)
    if fmt == "huggingface":
        with tempfile.TemporaryDirectory(prefix="concord-hf-") as folder:
            datasets = DatasetDict(
                {
                    name: Dataset(pa.Table.from_pylist(records, schema=SCHEMA))
                    for name, records in selected.items()
                }
            )
            root = Path(folder) / "dataset"
            # Force one shard even for an empty split. Some datasets releases
            # otherwise emit zero shards, which load_from_disk cannot reopen.
            datasets.save_to_disk(str(root), num_shards={name: 1 for name in selected})
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as archive:
                add_zip(archive, "manifest.json", json_bytes(manifest))
                for path in sorted(root.rglob("*")):
                    if path.is_file():
                        add_zip(
                            archive,
                            "dataset/" + path.relative_to(root).as_posix(),
                            path.read_bytes(),
                        )
            return out.getvalue(), "application/zip", "huggingface.zip"
    files = {}
    for name, records in selected.items():
        if fmt == "jsonl":
            # A leading manifest record makes a direct JSONL download self-describing.
            files[name + ".jsonl"] = (
                json_bytes({"_manifest": manifest})
                + b"\n"
                + b"".join(json_bytes(row) + b"\n" for row in records)
            )
        else:
            table = pa.Table.from_pylist(records, schema=SCHEMA)
            table = table.replace_schema_metadata({b"concord.manifest": json_bytes(manifest)})
            buffer = io.BytesIO()
            pq.write_table(table, buffer, compression="zstd")
            files[name + ".parquet"] = buffer.getvalue()
    if selection != "both":
        filename, content = next(iter(files.items()))
        return (
            content,
            "application/x-ndjson" if fmt == "jsonl" else "application/vnd.apache.parquet",
            filename,
        )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        add_zip(archive, "manifest.json", json_bytes(manifest))
        for name, content in sorted(files.items()):
            add_zip(archive, name, content)
    return out.getvalue(), "application/zip", f"{fmt}.zip"

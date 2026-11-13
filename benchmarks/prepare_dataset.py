#!/usr/bin/env python3
"""Rebuild the small SMS fixture from its committed, checksum-pinned source."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

DATA_DIR = Path(__file__).resolve().parent / "data"
DATASET = "uci_sms_spam_collection"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_verified(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if sha256(data) != expected:
        raise ValueError(f"Checksum mismatch: {path}")
    return data


def build_fixture(manifest: dict) -> dict[str, bytes]:
    source = manifest["source"]
    archive_path = DATA_DIR / source["archive"]
    read_verified(archive_path, source["archive_sha256"])
    with ZipFile(archive_path) as archive:
        raw = archive.read(source["member"])
    if sha256(raw) != source["member_sha256"]:
        raise ValueError("Source member checksum mismatch")

    # Remove only the final record separator, preserving SMS whitespace and spelling.
    lines = raw.decode("utf-8").split("\n")
    if lines[-1] == "":
        lines.pop()
    counts: Counter[str] = Counter()
    selected: Counter[str] = Counter()
    rows, labels = [], {}
    per_label = manifest["selection"]["per_label"]
    for number, line in enumerate(lines, 1):
        label, separator, text = line.partition("\t")
        if separator != "\t" or label not in {"ham", "spam"}:
            raise ValueError(f"Invalid source record {number}")
        counts[label] += 1
        if selected[label] >= per_label:
            continue
        external_id = f"sms-{number:05d}"
        rows.append(
            {
                "id": external_id,
                "text": text,
                "metadata": {"source_row": number, "dataset": DATASET},
            }
        )
        labels[external_id] = label
        selected[label] += 1
    if len(lines) != source["rows"] or dict(counts) != source["label_counts"]:
        raise ValueError("Unexpected source row counts")
    if dict(selected) != {"ham": per_label, "spam": per_label}:
        raise ValueError("Insufficient source rows for the sample")
    return {
        "dataset.jsonl": (
            "".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
            )
        ).encode("utf-8"),
        "reference-labels.json": (json.dumps(labels, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify files without writing them")
    parser.add_argument(
        "--fetch-source",
        action="store_true",
        help="Explicitly download the pinned official archive before rebuilding",
    )
    args = parser.parse_args()
    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    source = manifest["source"]
    if args.fetch_source:
        with urlopen(source["url"], timeout=60) as response:
            downloaded = response.read()
        if sha256(downloaded) != source["archive_sha256"]:
            raise ValueError("Downloaded archive differs from the pinned source")
        (DATA_DIR / source["archive"]).write_bytes(downloaded)
    for name, expected in manifest["files"].items():
        if name.startswith("source/"):
            read_verified(DATA_DIR / name, expected)
    for name, generated in build_fixture(manifest).items():
        if sha256(generated) != manifest["files"][name]:
            raise ValueError(f"Rebuilt fixture differs from the pinned checksum: {name}")
        path = DATA_DIR / name
        if args.check:
            if path.read_bytes() != generated:
                raise ValueError(f"Committed fixture differs from source: {path}")
        else:
            path.write_bytes(generated)
    print("Verified 30 source-derived SMS rows (15 ham, 15 spam).")


if __name__ == "__main__":
    main()

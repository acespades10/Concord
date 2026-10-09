import csv
import io
import json

from app.agreement import tokenize

FIELDS = {
    "rating": ["prompt", "response"],
    "ab": ["prompt", "response_a", "response_b"],
    "ner": ["text"],
}
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000


def parse_import(
    data: bytes, filename: str, mode: str, existing: set[str]
) -> tuple[list[dict], list[dict]]:
    errors, rows = [], []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [{"row": 0, "message": "File must use UTF-8 encoding"}]
    if filename.lower().endswith(".csv"):
        try:
            reader = csv.DictReader(io.StringIO(text), strict=True)
            required = ["external_id", *FIELDS[mode]]
            if not reader.fieldnames or any(key not in reader.fieldnames for key in required):
                return [], [{"row": 1, "message": f"Required columns: {', '.join(required)}"}]
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                return [], [{"row": 1, "message": "Duplicate column names"}]
            for row in reader:
                rows.append((reader.line_num, row))
                if len(rows) > MAX_ROWS:
                    return [], [
                        {"row": reader.line_num, "message": "Maximum 10,000 rows per import"}
                    ]
        except csv.Error as exc:
            return [], [{"row": reader.line_num, "message": str(exc)}]
    elif filename.lower().endswith(".jsonl"):
        for line_no, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(
                    (
                        line_no,
                        json.loads(
                            line,
                            parse_constant=lambda x: (_ for _ in ()).throw(
                                ValueError(f"Invalid JSON constant: {x}")
                            ),
                        ),
                    )
                )
            except ValueError as exc:
                errors.append({"row": line_no, "message": f"Invalid JSON: {exc}"})
            if len(rows) + len(errors) > MAX_ROWS:
                return [], [{"row": line_no, "message": "Maximum 10,000 rows per import"}]
    else:
        return [], [{"row": 0, "message": "Choose a .jsonl or .csv file"}]
    parsed, seen = [], set(existing)
    for number, row in rows:
        if not isinstance(row, dict):
            errors.append({"row": number, "message": "Each row must be an object"})
            continue
        required = ["external_id", *FIELDS[mode]]
        missing = [
            key for key in required if not isinstance(row.get(key), str) or not row[key].strip()
        ]
        if missing or None in row or any(v is None for v in row.values()):
            errors.append(
                {
                    "row": number,
                    "message": f"Missing or invalid fields: {', '.join(missing) or 'CSV columns'}",
                }
            )
            continue
        external_id = row["external_id"]
        if len(external_id) > 200 or external_id in seen:
            errors.append(
                {
                    "row": number,
                    "message": "Duplicate external_id or external_id longer than 200 characters",
                }
            )
            continue
        if any(len(row[k]) > 50000 for k in FIELDS[mode]):
            errors.append(
                {"row": number, "message": "Text fields must be at most 50,000 characters"}
            )
            continue
        seen.add(external_id)
        parsed.append(
            {
                "external_id": external_id,
                "content": {k: row[k] for k in FIELDS[mode]},
                "extra": {k: v for k, v in row.items() if k not in required},
                "tokens": tokenize(row["text"]) if mode == "ner" else [],
            }
        )
    if not rows and not errors:
        errors.append({"row": 0, "message": "File contains no data rows"})
    return ([] if errors else parsed), errors

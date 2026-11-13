"""Exercise the real API against a fresh, isolated local SQLite database."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from httpx import ASGITransport, AsyncClient, Response  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.auth import hasher  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from benchmarks.simulation import (  # noqa: E402
    IMPORT_RESPONSE,
    POLICY,
    RATERS,
    SIMULATION_NOTE,
    build_votes,
)

DATASET = ROOT / "benchmarks" / "data" / "dataset.jsonl"
REFERENCE = ROOT / "benchmarks" / "data" / "reference-labels.json"
PASSWORD = "local-benchmark-only-2026"


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def expect(response: Response, status: int = 200):
    if response.status_code != status:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path}: "
            f"expected {status}, received {response.status_code}: {response.text[:1000]}"
        )
    return response.json() if response.content else None


def compare_reference(actual: dict, expected: dict) -> dict:
    """Compare API metrics with the independent calculation, ignoring generated IDs."""
    checks = []

    def equal(name, left, right):
        matched = (
            math.isclose(left, right, rel_tol=0, abs_tol=1e-12)
            if isinstance(left, float) and isinstance(right, (float, int))
            else left == right
        )
        if not matched:
            raise RuntimeError(f"Independent metric mismatch {name}: {left!r} != {right!r}")
        checks.append(name)

    for key in [
        "total_items",
        "submissions",
        "expected_submissions",
        "coverage",
        "fully_rated",
        "resolved",
        "unresolved",
        "distribution",
    ]:
        equal(key, actual[key], expected[key])
    for key in ["value", "reason", "n"]:
        equal(f"fleiss.{key}", actual["fleiss"].get(key), expected["fleiss"].get(key))
    pairs = {(row["left"], row["right"]): row for row in actual["pairs"]}
    equal("pair_count", len(pairs), len(expected["pairs"]))
    for row in expected["pairs"]:
        pair = (row["left"], row["right"])
        equal(f"{pair}.shared_items", pairs[pair]["shared_items"], row["shared_items"])
        for key in ["value", "reason", "n"]:
            equal(f"{pair}.kappa.{key}", pairs[pair]["kappa"].get(key), row["kappa"].get(key))
    items = {row["external_id"]: row for row in actual["items"]}
    equal("item_count", len(items), len(expected["items"]))
    for row in expected["items"]:
        for key in ["submitted", "resolved", "reason", "vote_share"]:
            equal(f"{row['external_id']}.{key}", items[row["external_id"]][key], row[key])
        equal(
            f"{row['external_id']}.label",
            (items[row["external_id"]]["payload"] or {}).get("label"),
            (row["payload"] or {}).get("label"),
        )
    return {"passed": True, "checks": checks}


async def run_benchmark(
    output: Path,
    dataset: Path = DATASET,
    reference: Path = REFERENCE,
    *,
    validate: bool = True,
) -> dict:
    from benchmarks.reference import calculate_reference
    from benchmarks.review import review_project

    started = time.perf_counter()
    output = await asyncio.to_thread(Path(output).resolve)
    dataset = await asyncio.to_thread(Path(dataset).resolve)
    reference = await asyncio.to_thread(Path(reference).resolve)
    if dataset == DATASET and reference == REFERENCE:
        integrity = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(ROOT / "benchmarks" / "prepare_dataset.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if integrity.returncode:
            raise ValueError(f"Pinned dataset integrity check failed: {integrity.stderr}")
    rows = [
        json.loads(line) for line in dataset.read_text(encoding="utf-8").split("\n") if line.strip()
    ]
    labels = json.loads(reference.read_text(encoding="utf-8"))
    if len({row["id"] for row in rows}) != len(rows) or set(labels) != {row["id"] for row in rows}:
        raise ValueError("Dataset IDs must be unique and exactly match reference IDs")
    votes = build_votes(labels)
    output.mkdir(parents=True, exist_ok=True)
    database_path = output / "benchmark.sqlite3"
    if database_path.exists():
        raise FileExistsError(
            f"Refusing to replace an existing database: {database_path}. Choose a fresh --output directory."
        )
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def isolated_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = isolated_db
    timings = {}
    requests = []
    probes = []
    submissions = []
    pseudonyms = {
        name: str(uuid.uuid5(uuid.NAMESPACE_URL, f"concord-benchmark/{name}"))
        for name in ["admin", "reviewer", *RATERS, "outsider"]
    }

    async def on_request(request):
        request.extensions["benchmark_started"] = time.perf_counter()

    async def on_response(response):
        requests.append(
            {
                "method": response.request.method,
                "path": response.request.url.path,
                "status": response.status_code,
                "elapsed_ms": round(
                    (time.perf_counter() - response.request.extensions["benchmark_started"]) * 1000,
                    3,
                ),
            }
        )

    async def probe(name, response, status):
        expect(response, status)
        probes.append(
            {
                "name": name,
                "expected_status": status,
                "actual_status": response.status_code,
                "passed": True,
            }
        )

    try:
        stage = time.perf_counter()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        password_hash = hasher.hash(PASSWORD)
        async with factory() as session:
            for name in pseudonyms:
                session.add(
                    User(
                        id=name,
                        pseudonym=pseudonyms[name],
                        email=f"{name}@benchmark.invalid",
                        name=name,
                        role=name if name in {"admin", "reviewer"} else "annotator",
                        password_hash=password_hash,
                    )
                )
            await session.commit()
        timings["schema_and_accounts"] = time.perf_counter() - stage
        async with AsyncExitStack() as stack:
            clients = {}
            stage = time.perf_counter()
            for name in [*pseudonyms, "anonymous"]:
                client = await stack.enter_async_context(
                    AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="https://benchmark.invalid",
                        headers={"Origin": settings.app_origin},
                        event_hooks={"request": [on_request], "response": [on_response]},
                    )
                )
                clients[name] = client
                if name != "anonymous":
                    login = expect(
                        await client.post(
                            "/api/v1/auth/login",
                            json={"email": f"{name}@benchmark.invalid", "password": PASSWORD},
                        )
                    )
                    client.headers["X-CSRF-Token"] = login["csrf"]
                    if expect(await client.get("/api/v1/auth/session"))["user"]["id"] != name:
                        raise RuntimeError("Session identity mismatch")
            timings["authentication"] = time.perf_counter() - stage
            admin, reviewer = clients["admin"], clients["reviewer"]
            stage = time.perf_counter()
            project = expect(
                await admin.post(
                    "/api/v1/projects",
                    json={
                        "name": "UCI SMS controlled annotation benchmark",
                        "description": "Local scripted simulation; not a human quality study. Gold labels stay outside the imported project.",
                        "mode": "rating",
                        "labels": ["ham", "spam"],
                        "ordered": False,
                        "target_raters": 3,
                        "review_threshold": 0.8,
                    },
                ),
                201,
            )
            pid = project["id"]
            prefix = f"/api/v1/projects/{pid}"
            expect(await admin.put(prefix + "/members", json={"user_ids": RATERS}))
            imported = [
                {
                    "external_id": row["id"],
                    "prompt": row["text"],
                    "response": IMPORT_RESPONSE,
                    "metadata": row.get("metadata", {}),
                }
                for row in rows
            ]
            import_bytes = "\n".join(
                json.dumps(row, ensure_ascii=False) for row in imported
            ).encode("utf-8")
            imported_result = expect(
                await admin.post(
                    prefix + "/imports",
                    files={"file": ("sms.jsonl", import_bytes, "application/x-ndjson")},
                )
            )
            if imported_result["imported"] != len(rows):
                raise RuntimeError("Import count mismatch")
            expect(await admin.post(prefix + "/state", json={"state": "active"}))
            timings["project_import_activation"] = time.perf_counter() - stage
            stage = time.perf_counter()
            await probe(
                "anonymous cannot list projects",
                await clients["anonymous"].get("/api/v1/projects"),
                401,
            )
            outsider_projects = expect(await clients["outsider"].get("/api/v1/projects"))
            if outsider_projects:
                raise RuntimeError("Outsider saw a project")
            probes.append({"name": "outsider project list empty", "passed": True})
            for suffix in ["", "/review", "/exports?format=jsonl&selection=annotations"]:
                await probe(
                    f"outsider denied {suffix or 'project read'}",
                    await clients["outsider"].get(prefix + suffix),
                    403,
                )
            await probe(
                "outsider cannot claim",
                await clients["outsider"].post(prefix + "/assignments/next"),
                403,
            )
            for suffix in ["/metrics", "/review", "/exports?format=jsonl&selection=consensus"]:
                await probe(
                    f"annotator denied {suffix}", await clients["rater1"].get(prefix + suffix), 403
                )
            for name in ["rater1", "reviewer"]:
                await probe(
                    f"{name} cannot create project",
                    await clients[name].post(
                        "/api/v1/projects",
                        json={"name": "Forbidden", "mode": "rating", "labels": ["ham", "spam"]},
                    ),
                    403,
                )
            await probe(
                "mutation requires CSRF",
                await admin.post(
                    prefix + "/state",
                    headers={"X-CSRF-Token": "invalid"},
                    json={"state": "completed"},
                ),
                403,
            )
            await probe(
                "mutation requires trusted Origin",
                await admin.post(
                    prefix + "/state",
                    headers={"Origin": "https://untrusted.invalid"},
                    json={"state": "completed"},
                ),
                403,
            )
            await probe(
                "cannot complete before annotation",
                await admin.post(prefix + "/state", json={"state": "completed"}),
                409,
            )
            timings["permission_probes"] = time.perf_counter() - stage
            stage = time.perf_counter()
            first = True
            for rater_index, name in enumerate(RATERS):
                client = clients[name]
                seen = set()
                for _ in rows:
                    assignment = expect(await client.post(prefix + "/assignments/next"))
                    if assignment is None:
                        raise RuntimeError(f"Ran out of assignments for {name}")
                    external_id = assignment["item"]["external_id"]
                    if set(assignment["item"]) != {"id", "external_id", "content", "tokens"}:
                        raise RuntimeError("Annotator response exposed unexpected item fields")
                    if external_id in seen:
                        raise RuntimeError(f"Duplicate assignment for {name}: {external_id}")
                    seen.add(external_id)
                    payload = {"label": votes[external_id][rater_index], "note": SIMULATION_NOTE}
                    body = {"mode": "rating", "payload": payload, "version": assignment["version"]}
                    path = f"/api/v1/assignments/{assignment['id']}"
                    saved = expect(await client.put(path + "/draft", json=body))
                    if first:
                        await probe(
                            "stale draft rejected",
                            await client.put(path + "/draft", json=body),
                            409,
                        )
                        restored = expect(await client.get(prefix + "/assignments/current"))
                        reclaimed = expect(await client.post(prefix + "/assignments/next"))
                        if (
                            restored["draft"] != payload
                            or restored["version"] != saved["version"]
                            or reclaimed["id"] != assignment["id"]
                        ):
                            raise RuntimeError("Draft restoration or claim reuse failed")
                        probes.append(
                            {"name": "draft restored and active claim reused", "passed": True}
                        )
                        await probe(
                            "stale submit rejected",
                            await client.post(path + "/submit", json=body),
                            409,
                        )
                    body["version"] = saved["version"]
                    expect(await client.post(path + "/submit", json=body))
                    if first:
                        await probe(
                            "duplicate submit rejected",
                            await client.post(path + "/submit", json=body),
                            409,
                        )
                        await probe(
                            "submitted draft immutable",
                            await client.put(path + "/draft", json=body),
                            409,
                        )
                        first = False
                    submissions.append(
                        {
                            "external_id": external_id,
                            "annotator": name,
                            "annotator_id": pseudonyms[name],
                            "assignment_id": assignment["id"],
                            "payload": payload,
                            "simulation": True,
                        }
                    )
                if expect(await client.post(prefix + "/assignments/next")) is not None:
                    raise RuntimeError(f"Unexpected extra assignment for {name}")
            timings["claim_save_submit"] = time.perf_counter() - stage
            write_json(
                output / "simulated-submissions.json",
                {
                    "simulation": True,
                    "note": SIMULATION_NOTE,
                    "policy": POLICY,
                    "raters": RATERS,
                    "votes": votes,
                    "submissions": submissions,
                },
            )
            stage = time.perf_counter()
            before = expect(await reviewer.get(prefix + "/metrics"))
            expected = calculate_reference(votes, raters=RATERS)
            comparison = compare_reference(before, expected)
            write_json(output / "metrics-before.json", before)
            write_json(output / "reference-metrics.json", expected)
            timings["metrics_and_independent_comparison"] = time.perf_counter() - stage
            stage = time.perf_counter()
            review = await review_project(reviewer, pid, labels)
            reviewed_items = expect(await reviewer.get(prefix + "/review?all_items=true"))
            await probe(
                "annotator cannot alter approved label",
                await clients["rater1"].put(
                    prefix + f"/items/{reviewed_items[0]['item']['id']}/adjudication",
                    json={
                        "mode": "rating",
                        "payload": {"label": "ham"},
                        "rationale": "Unauthorized change probe",
                    },
                ),
                403,
            )
            after = expect(await reviewer.get(prefix + "/metrics"))
            write_json(output / "metrics-after.json", after)
            if (
                after["submissions"] != len(rows) * 3
                or after["distribution"] != before["distribution"]
                or after["fleiss"] != before["fleiss"]
                or after["pairs"] != before["pairs"]
            ):
                raise RuntimeError("Review changed raw-vote counts or agreement")
            timings["review_and_after_metrics"] = time.perf_counter() - stage
            stage = time.perf_counter()
            expect(await admin.post(prefix + "/state", json={"state": "completed"}))
            for selection in ["consensus", "annotations"]:
                response = await reviewer.get(
                    prefix + f"/exports?format=jsonl&selection={selection}"
                )
                if response.status_code != 200:
                    expect(response)
                (output / f"{selection}.jsonl").write_bytes(response.content)
            timings["completion_and_exports"] = time.perf_counter() - stage
        report = {
            "schema_version": "1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "simulation": True,
            "note": SIMULATION_NOTE,
            "policy": POLICY,
            "transport": "httpx ASGITransport in process; real HTTP API routes and isolated local SQLite; no browser or network latency measured",
            "database": str(database_path),
            "project_id": pid,
            "dataset": str(dataset),
            "reference": str(reference),
            "import_mapping": {
                "external_id": "dataset.id",
                "prompt": "dataset.text",
                "response": IMPORT_RESPONSE,
                "metadata": "dataset.metadata; reference labels excluded",
            },
            "item_count": len(rows),
            "submission_count": len(submissions),
            "reference_comparison": comparison,
            "permission_and_workflow_probes": probes,
            "review": review,
            "metrics_before": before,
            "metrics_after": after,
            "stage_seconds": timings,
            "requests": requests,
        }
        report["environment"] = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "packages": {
                name: package_version(name) for name in ["fastapi", "sqlalchemy", "httpx"]
            },
            "parallel_clients": False,
            "timing_clock": "time.perf_counter",
        }
        report["input_sha256"] = {
            "dataset": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "reference": hashlib.sha256(reference.read_bytes()).hexdigest(),
        }
        if validate:
            stage = time.perf_counter()
            command = [
                sys.executable,
                "-m",
                "benchmarks.validate_export",
                "--dataset",
                str(dataset),
                "--reference",
                str(reference),
                "--consensus",
                str(output / "consensus.jsonl"),
                "--annotations",
                str(output / "annotations.jsonl"),
                "--submissions",
                str(output / "simulated-submissions.json"),
                "--output",
                str(output / "validation.json"),
            ]
            result = await asyncio.to_thread(
                subprocess.run, command, cwd=ROOT, capture_output=True, text=True, check=False
            )
            report["independent_export_validation"] = {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
            timings["independent_export_validation"] = time.perf_counter() - stage
            report["passed"] = result.returncode == 0
        else:
            report["independent_export_validation"] = {"skipped": True}
            report["passed"] = False
        timings["total"] = time.perf_counter() - started
        write_json(output / "report.json", report)
        if validate and not report["passed"]:
            raise RuntimeError(
                f"Independent export validation failed; inspect {output / 'report.json'}"
            )
        return report
    except Exception as error:
        write_json(
            output / "failure.json",
            {"error": str(error), "stage_seconds": timings, "requests": requests},
        )
        raise
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local" / "benchmark")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Development only; report cannot pass when independent validation is skipped",
    )
    args = parser.parse_args()
    report = asyncio.run(
        run_benchmark(args.output, args.dataset, args.reference, validate=not args.skip_validation)
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "items": report["item_count"],
                "submissions": report["submission_count"],
                "passed": report["passed"],
                "seconds": report["stage_seconds"]["total"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

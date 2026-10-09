import asyncio
import io
import json
import time
import zipfile

import pyarrow.parquet as pq
import pytest
from datasets import load_from_disk
from sqlalchemy import select

from app.models import Annotation, Assignment, Item, Project, Session


async def claim(client, pid):
    response = await client.post(f"/api/v1/projects/{pid}/assignments/next")
    assert response.status_code == 200, response.text
    return response.json()


async def test_login_is_committed_before_response_headers(database):
    from http.cookies import SimpleCookie

    from httpx import ASGITransport, AsyncClient

    from app.auth import digest
    from app.main import app

    observed = []

    async def intercepted(scope, receive, send):
        async def inspect(message):
            if message["type"] == "http.response.start" and message["status"] == 200:
                cookie = SimpleCookie()
                for name, value in message["headers"]:
                    if name == b"set-cookie":
                        cookie.load(value.decode())
                if "concord_session" in cookie:
                    async with database() as other_request:
                        token = cookie["concord_session"].value
                        observed.append(await other_request.get(Session, digest(token)) is not None)
            await send(message)

        await app(scope, receive, inspect)

    async with AsyncClient(
        transport=ASGITransport(app=intercepted), base_url="http://localhost:8000"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"email": "admin@test.local", "password": "test-password-2026"},
        )
    assert response.status_code == 200
    assert observed == [True]


async def complete(clients, pid, mode="rating", choices=None):
    choices = choices or ["Good"] * 3
    for index in range(3):
        client = await clients(f"rater{index + 1}")
        assignment = await claim(client, pid)
        payload = (
            {"label": choices[index], "note": "Unicode 台北\nnew line"}
            if mode == "rating"
            else {"spans": [{"start": 0, "end": 4, "label": "PERSON", "text": "Maya"}]}
            if mode == "ner"
            else {"choice": choices[index]}
        )
        response = await client.post(
            f"/api/v1/assignments/{assignment['id']}/submit",
            json={"mode": mode, "payload": payload, "version": assignment["version"]},
        )
        assert response.status_code == 200, response.text


async def test_auth_sessions_csrf_and_rbac(clients, project_factory, database):
    pid, admin = await project_factory()
    anonymous = await clients()
    assert (await anonymous.get("/api/v1/projects")).status_code == 401
    assert (
        await anonymous.post(
            "/api/v1/auth/login", json={"email": "admin@test.local", "password": "wrong"}
        )
    ).status_code == 401
    response = await admin.get("/api/v1/auth/session")
    assert response.json()["user"]["role"] == "admin"
    assert "password_hash" not in response.text
    session_cookie = admin.cookies.get("concord_session")
    async with database() as db:
        stored = (await db.scalars(select(Session))).first()
        assert stored.token_hash != session_cookie
    rater = await clients("rater1")
    for path in ["metrics", "review", "events", "exports"]:
        assert (await rater.get(f"/api/v1/projects/{pid}/{path}")).status_code == 403
    assert (await rater.get("/api/v1/users")).status_code == 403
    assert (
        await rater.post(
            "/api/v1/projects", json={"name": "Oops", "mode": "rating", "labels": ["a"]}
        )
    ).status_code == 403
    assert (
        await admin.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "bad"})
    ).status_code == 403
    assert (
        await admin.post("/api/v1/auth/logout", headers={"Origin": "https://evil.test"})
    ).status_code == 403
    assert (await admin.post("/api/v1/auth/logout")).status_code == 200
    assert (await admin.get("/api/v1/auth/session")).status_code == 401


async def test_state_and_membership_rules(project_factory, clients):
    pid, admin = await project_factory(activate=False)
    cfg = {"name": "Updated", "mode": "rating", "labels": ["Bad", "Good"], "target_raters": 3}
    assert (await admin.put(f"/api/v1/projects/{pid}", json=cfg)).status_code == 200
    assert (
        await admin.put(f"/api/v1/projects/{pid}/members", json={"user_ids": ["rater1"]})
    ).status_code == 200
    assert (
        await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "active"})
    ).status_code == 422
    await admin.put(
        f"/api/v1/projects/{pid}/members", json={"user_ids": ["rater1", "rater2", "rater3"]}
    )
    await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "active"})
    assert (await admin.put(f"/api/v1/projects/{pid}", json=cfg)).status_code == 409
    assert (
        await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "completed"})
    ).status_code == 409
    outsider = await clients("rater4")
    assert (await outsider.post(f"/api/v1/projects/{pid}/assignments/next")).status_code == 403
    assert not (await outsider.get("/api/v1/projects")).json()
    await complete(clients, pid)
    assert (
        await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "completed"})
    ).status_code == 200
    assert (
        await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "archived"})
    ).status_code == 200
    assert (
        await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "active"})
    ).status_code == 409


async def test_atomic_import_rollback(project_factory, database):
    pid, admin = await project_factory(rows=[], activate=False)
    valid = json.dumps({"external_id": "one", "prompt": "a", "response": "b"})
    response = await admin.post(
        f"/api/v1/projects/{pid}/imports", files={"file": ("input.jsonl", valid + "\n{bad")}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["row"] == 2
    async with database() as db:
        assert not (await db.scalars(select(Item).where(Item.project_id == pid))).all()
    response = await admin.post(
        f"/api/v1/projects/{pid}/imports", files={"file": ("input.jsonl", valid + "\n" + valid)}
    )
    assert response.status_code == 422
    response = await admin.post(
        f"/api/v1/projects/{pid}/imports", files={"file": ("input.jsonl", valid)}
    )
    assert response.json()["imported"] == 1
    assert (
        await admin.post(f"/api/v1/projects/{pid}/imports", files={"file": ("input.jsonl", valid)})
    ).status_code == 422


async def test_concurrent_claims_do_not_overallocate(project_factory, clients, database):
    pid, _ = await project_factory(target=2)
    raters = [await clients(f"rater{i}") for i in range(1, 5)]
    results = await asyncio.gather(*(claim(rater, pid) for rater in raters))
    assert sum(result is not None for result in results) == 2
    first = next(i for i, result in enumerate(results) if result)
    same = await asyncio.gather(*(claim(raters[first], pid) for _ in range(3)))
    assert len({a["id"] for a in same}) == 1
    async with database() as db:
        assert (
            len((await db.scalars(select(Assignment).where(Assignment.project_id == pid))).all())
            == 2
        )


async def test_lease_autosave_conflict_and_immutable_submission(project_factory, clients, database):
    pid, admin = await project_factory()
    rater = await clients("rater1")
    assignment = await claim(rater, pid)
    body = {"mode": "rating", "payload": {"label": "Good"}, "version": 0}
    path = f"/api/v1/assignments/{assignment['id']}"
    saved = await rater.put(path + "/draft", json=body)
    assert saved.status_code == 200
    assert saved.json()["version"] == 1
    assert saved.json()["expires_at"] >= assignment["expires_at"]
    assert (await rater.put(path + "/draft", json=body)).status_code == 409
    current = (await rater.get(f"/api/v1/projects/{pid}/assignments/current")).json()
    assert current["draft"]["label"] == "Good"
    async with database() as db:
        lease = await db.get(Assignment, assignment["id"])
        lease.expires_at = time.time() - 1
        await db.commit()
    assert (await rater.post(path + "/submit", json={**body, "version": 1})).status_code == 409
    renewed = await claim(rater, pid)
    assert renewed["id"] == assignment["id"] and renewed["version"] == 2
    assert (await rater.post(path + "/submit", json={**body, "version": 2})).status_code == 200
    assert (await rater.put(path + "/draft", json={**body, "version": 3})).status_code == 409
    assert (await rater.post(path + "/skip")).status_code == 409
    metrics = (await admin.get(f"/api/v1/projects/{pid}/metrics")).json()
    assert metrics["revision"] == 2  # activation + submission
    assert metrics["submissions"] == 1 and metrics["fully_rated"] == 0


async def test_ab_blinding_and_canonical_identity(project_factory, clients, database):
    pid, admin = await project_factory(mode="ab")
    for i in range(1, 4):
        rater = await clients(f"rater{i}")
        assignment = await claim(rater, pid)
        assert "swapped" not in assignment and "extra" not in assignment["item"]
        choice = "A" if assignment["item"]["content"]["response_a"] == "Hello A" else "B"
        await rater.post(
            f"/api/v1/assignments/{assignment['id']}/submit",
            json={"mode": "ab", "payload": {"choice": choice}, "version": 0},
        )
    async with database() as db:
        annotations = (
            await db.scalars(select(Annotation).where(Annotation.project_id == pid))
        ).all()
        assert all(a.payload["choice"] == "A" for a in annotations)
    metrics = (await admin.get(f"/api/v1/projects/{pid}/metrics")).json()
    assert metrics["resolved"] == 1 and metrics["distribution"] == {"A": 3}


async def test_skip_and_revisit(project_factory, clients):
    pid, _ = await project_factory()
    rater = await clients("rater1")
    assignment = await claim(rater, pid)
    await rater.post(f"/api/v1/assignments/{assignment['id']}/skip")
    assert await claim(rater, pid) is None
    await rater.post(f"/api/v1/projects/{pid}/assignments/reset-skipped")
    assert (await claim(rater, pid))["id"] == assignment["id"]


@pytest.mark.parametrize("mode", ["rating", "ner", "ab"])
async def test_adjudication_overrides_consensus(project_factory, clients, mode):
    pid, admin = await project_factory(mode=mode)
    await complete(clients, pid, mode, ["Good", "Good", "Bad"] if mode == "rating" else ["TIE"] * 3)
    review = (await admin.get(f"/api/v1/projects/{pid}/review?all_items=true")).json()[0]
    payload = (
        {"label": "Bad"}
        if mode == "rating"
        else {"spans": []}
        if mode == "ner"
        else {"choice": "B"}
    )
    reviewer = await clients("reviewer")
    result = await reviewer.put(
        f"/api/v1/projects/{pid}/items/{review['item']['id']}/adjudication",
        json={
            "mode": mode,
            "payload": payload,
            "rationale": "Reviewed against the project guidelines.",
        },
    )
    assert result.status_code == 200, result.text
    metrics = (await admin.get(f"/api/v1/projects/{pid}/metrics")).json()
    assert metrics["resolved"] == 1 and metrics["unresolved"] == 0
    assert metrics["items"][0]["adjudicated"]
    assert all(metrics["items"][0]["payload"][k] == v for k, v in payload.items())


@pytest.mark.parametrize("mode", ["rating", "ner", "ab"])
async def test_export_roundtrips(project_factory, clients, tmp_path, mode):
    pid, admin = await project_factory(mode=mode)
    await complete(clients, pid, mode, ["TIE"] * 3 if mode == "ab" else None)
    root = f"/api/v1/projects/{pid}/exports"
    response = await admin.get(root + "?format=jsonl&selection=annotations")
    assert response.status_code == 200
    lines = [json.loads(line) for line in response.content.splitlines()]
    assert lines[0]["_manifest"]["schema_version"] == "1.0.0"
    rows = lines[1:]
    assert len(rows) == 3
    assert len(rows[0]["annotator_id"]) == 36
    assert (
        "email" not in response.text
        and "password" not in response.text
        and "token_hash" not in response.text
    )
    assert json.loads(rows[0]["metadata_json"])["source"]["unicode"] == "你好"
    assert (
        response.content == (await admin.get(root + "?format=jsonl&selection=annotations")).content
    )
    parquet = await admin.get(root + "?format=parquet&selection=annotations")
    table = pq.read_table(io.BytesIO(parquet.content))
    assert len(table) == 3 and b"concord.manifest" in table.schema.metadata
    assert table.to_pylist()[0]["annotator_id"] == rows[0]["annotator_id"]
    assert (
        parquet.content == (await admin.get(root + "?format=parquet&selection=annotations")).content
    )
    if mode == "ner":
        assert table.to_pylist()[0]["payload"]["spans"][0]["text"] == "Maya"
        assert table.to_pylist()[0]["tokens"][1]["text"] == "🌿"
    archive = await admin.get(root + "?format=jsonl&selection=both")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zip_file:
        assert sorted(zip_file.namelist()) == [
            "annotations.jsonl",
            "consensus.jsonl",
            "manifest.json",
        ]
    hf = await admin.get(root + "?format=huggingface&selection=both")
    assert hf.status_code == 200, hf.text[:100]
    with zipfile.ZipFile(io.BytesIO(hf.content)) as zip_file:
        zip_file.extractall(tmp_path / "hf")
    dataset = load_from_disk(str(tmp_path / "hf" / "dataset"))
    assert set(dataset) == {"annotations", "consensus"}
    assert len(dataset["annotations"]) == 3 and len(dataset["consensus"]) == 1
    assert dataset["annotations"][0]["payload"] == table.to_pylist()[0]["payload"]
    assert hf.content == (await admin.get(root + "?format=huggingface&selection=both")).content


async def test_demo_seed_is_idempotent(database):
    from sqlalchemy import func

    from app.models import User
    from app.seed import seed

    async with database() as db:
        await seed(db)
        before = [
            await db.scalar(select(func.count()).select_from(model))
            for model in [User, Project, Item, Annotation]
        ]
        password = (
            await db.scalar(select(User).where(User.email == "admin@concord.demo"))
        ).password_hash
        await seed(db)
        after = [
            await db.scalar(select(func.count()).select_from(model))
            for model in [User, Project, Item, Annotation]
        ]
        assert before == after
        assert (
            await db.scalar(select(User).where(User.email == "admin@concord.demo"))
        ).password_hash == password


async def test_export_unresolved_defaults_and_empty_hf(project_factory, clients, tmp_path):
    pid, admin = await project_factory()
    await complete(clients, pid, choices=["Good", "Good", "Bad"])
    root = f"/api/v1/projects/{pid}/exports"
    resolved = await admin.get(root + "?format=jsonl&selection=consensus")
    assert len(resolved.content.splitlines()) == 1
    unresolved = await admin.get(root + "?format=jsonl&selection=consensus&include_unresolved=true")
    assert len(unresolved.content.splitlines()) == 2
    assert json.loads(unresolved.content.splitlines()[1])["resolved"] is False
    hf = await admin.get(root + "?format=huggingface&selection=consensus")
    with zipfile.ZipFile(io.BytesIO(hf.content)) as archive:
        archive.extractall(tmp_path / "empty")
    assert len(load_from_disk(str(tmp_path / "empty" / "dataset"))["consensus"]) == 0


async def test_sse_database_revisions_and_expiry(project_factory, database):
    # Exercise the actual stream iterator without an ASGI client buffering an
    # infinite response. A second transaction emulates a different API process.
    from app.auth import digest
    from app.models import User
    from app.routes import events

    pid, admin = await project_factory()
    token = admin.cookies.get("concord_session")

    class Request:
        cookies = {"concord_session": token}

        async def is_disconnected(self):
            return False

    async with database() as db:
        user = await db.get(User, "admin")
        response = await events(pid, Request(), user, db)
        iterator = response.body_iterator
        assert '"revision": 1' in await anext(iterator)
        async with database() as other:
            project = await other.get(Project, pid)
            project.metric_revision += 1
            await other.commit()
        assert '"revision": 2' in await asyncio.wait_for(anext(iterator), 4)
        async with database() as other:
            session = await other.get(Session, digest(token))
            session.expires_at = 0
            await other.commit()
        assert "event: expired" in await asyncio.wait_for(anext(iterator), 4)
        await iterator.aclose()

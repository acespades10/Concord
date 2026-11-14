import os
from contextlib import AsyncExitStack

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import hasher
from app.db import Base, get_db
from app.main import app
from app.models import User

PASSWORD = "test-password-2026"
PASSWORD_HASH = hasher.hash(PASSWORD)


@pytest.fixture
async def database(tmp_path, monkeypatch):
    url = os.environ.get(
        "TEST_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    )
    engine = create_async_engine(url)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def config(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def dependency():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr("app.routes.SessionLocal", factory)
    monkeypatch.setattr("app.login_limits.SessionLocal", factory)
    async with factory() as session:
        for role, name in [
            ("admin", "admin"),
            ("reviewer", "reviewer"),
            *[("annotator", f"rater{i}") for i in range(1, 5)],
        ]:
            session.add(
                User(
                    id=name,
                    email=f"{name}@test.local",
                    name=name,
                    role=role,
                    password_hash=PASSWORD_HASH,
                )
            )
        await session.commit()
    yield factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def clients(database):
    async with AsyncExitStack() as stack:

        async def client(name=None):
            http = await stack.enter_async_context(
                AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://localhost:8000",
                    headers={"Origin": "http://localhost:3000"},
                )
            )
            if name:
                response = await http.post(
                    "/api/v1/auth/login", json={"email": f"{name}@test.local", "password": PASSWORD}
                )
                assert response.status_code == 200, response.text
                http.headers["X-CSRF-Token"] = response.json()["csrf"]
            return http

        yield client


@pytest.fixture
async def project_factory(clients):
    admin = await clients("admin")

    async def create(
        mode="rating", rows=None, target=3, threshold=0.8, activate=True, members=None
    ):
        import json

        labels = (
            ["Bad", "Good"]
            if mode == "rating"
            else ["PERSON", "ORG", "LOCATION"]
            if mode == "ner"
            else []
        )
        response = await admin.post(
            "/api/v1/projects",
            json={
                "name": f"Test {mode}",
                "mode": mode,
                "labels": labels,
                "target_raters": target,
                "review_threshold": threshold,
            },
        )
        assert response.status_code == 201, response.text
        project = response.json()
        pid = project["id"]
        response = await admin.put(
            f"/api/v1/projects/{pid}/members",
            json={"user_ids": members or ["rater1", "rater2", "rater3", "rater4"]},
        )
        assert response.status_code == 200, response.text
        if rows is None:
            content = (
                {"prompt": "Say hello", "response": "Hello 🌏!\nWelcome"}
                if mode == "rating"
                else {"text": "Maya 🌿 met José in Taipei."}
                if mode == "ner"
                else {"prompt": "Greet me", "response_a": "Hello A", "response_b": "Hello B"}
            )
            rows = [{"external_id": "item-1", **content, "source": {"unicode": "你好", "score": 3}}]
        if rows:
            response = await admin.post(
                f"/api/v1/projects/{pid}/imports",
                files={
                    "file": (
                        "items.jsonl",
                        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode(
                            "utf-8"
                        ),
                        "application/x-ndjson",
                    )
                },
            )
            assert response.status_code == 200, response.text
        if activate:
            response = await admin.post(f"/api/v1/projects/{pid}/state", json={"state": "active"})
            assert response.status_code == 200, response.text
        return pid, admin

    return create

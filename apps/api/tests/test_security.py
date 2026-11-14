import asyncio
import time

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.accounts import create_account, reset_password
from app.auth import hasher
from app.bootstrap import bootstrap_owner
from app.config import Settings
from app.login_limits import consume_login_budget
from app.models import LoginBudget, Session, User


def production(**overrides):
    values = {
        "app_env": "production",
        "app_origin": "https://concord.example.com",
        "cookie_secure": True,
        "database_url": "postgresql+asyncpg://concord:" + "a" * 40 + "@db/concord",
    }
    return Settings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"app_origin": "http://concord.example.com"},
        {"app_origin": "https://concord.example.com/"},
        {"app_origin": "https://user@concord.example.com"},
        {"cookie_secure": False},
        {"database_url": "sqlite+aiosqlite:///./test.db"},
        {"database_url": "postgresql+asyncpg://concord:weak@db/concord"},
    ],
)
def test_production_rejects_unsafe_configuration(overrides):
    with pytest.raises(ValidationError):
        production(**overrides)


def test_valid_production_configuration():
    assert production().cookie_secure


async def test_first_owner_bootstrap_never_replaces_a_password_or_adds_another_admin(database):
    password_hash = hasher.hash("initial-owner-password-12345")
    async with database.begin() as db:
        await db.execute(delete(User))
        await bootstrap_owner(db, "owner@example.com", password_hash)
    async with database.begin() as db:
        await bootstrap_owner(db, "owner@example.com", hasher.hash("a-different-password-12345"))
        with pytest.raises(ValueError, match="empty workspace"):
            await bootstrap_owner(db, "another@example.com", password_hash)
    async with database() as db:
        owner = await db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner.role == "admin"
        assert owner.password_hash == password_hash


async def test_first_owner_bootstrap_cannot_promote_existing_non_admin(database):
    async with database() as db:
        with pytest.raises(ValueError, match="non-admin"):
            await bootstrap_owner(
                db, "rater1@test.local", hasher.hash("strong-initial-password-12345")
            )


async def test_seed_is_disabled_in_production(database, monkeypatch):
    from app.config import settings
    from app.seed import seed

    monkeypatch.setattr(settings, "app_env", "production")
    async with database() as db:
        with pytest.raises(RuntimeError, match="disabled"):
            await seed(db)


async def test_account_creation_and_password_rotation(database, clients):
    async with database.begin() as db:
        user = await create_account(
            db, "Owner@Example.com", "Owner", "admin", "unique-password-12345"
        )
        uid = user.id
    async with database.begin() as db:
        with pytest.raises(ValueError, match="already exists"):
            await create_account(db, "owner@example.com", "Owner", "admin", "unique-password-12345")
        db.add(
            Session(token_hash="test-token", user_id=uid, csrf="test", expires_at=time.time() + 60)
        )
    async with database.begin() as db:
        await reset_password(db, "owner@example.com", "replacement-password-12345")
    async with database() as db:
        user = await db.get(User, uid)
        assert hasher.verify(user.password_hash, "replacement-password-12345")
        assert await db.get(Session, "test-token") is None


@pytest.mark.parametrize(
    "email,password",
    [
        ("bad", "long-enough-password"),
        ("admin@concord.demo", "long-enough-password"),
        ("real@example.com", "short"),
    ],
)
async def test_accounts_reject_invalid_identity_or_password(database, email, password):
    async with database() as db:
        with pytest.raises(ValueError):
            await create_account(db, email, "Name", "admin", password)


async def test_failed_logins_persist_budget_and_return_retry_after(clients, database, monkeypatch):
    monkeypatch.setattr("app.login_limits.ACCOUNT_LIMIT", 2)
    client = await clients()
    for _ in range(2):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "incorrect"}
        )
        assert response.status_code == 401
    response = await client.post(
        "/api/v1/auth/login", json={"email": "NOBODY@example.com", "password": "incorrect"}
    )
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 600
    async with database() as db:
        budgets = (await db.scalars(select(LoginBudget))).all()
        assert len(budgets) == 2
        assert all("@" not in row.key for row in budgets)


async def test_workspace_limit_cannot_be_bypassed_by_changing_email(database, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr("app.login_limits.WORKSPACE_LIMIT", 2)
    results = await asyncio.gather(
        *(consume_login_budget(f"person{i}@example.com") for i in range(6)),
        return_exceptions=True,
    )
    assert sum(value is None for value in results) == 2
    assert (
        sum(isinstance(value, HTTPException) and value.status_code == 429 for value in results) == 4
    )


async def test_login_budget_recovers_after_window(database, monkeypatch):
    monkeypatch.setattr("app.login_limits.ACCOUNT_LIMIT", 1)
    monkeypatch.setattr("app.login_limits.time.time", lambda: 10000)
    await consume_login_budget("person@example.com")
    monkeypatch.setattr("app.login_limits.time.time", lambda: 10601)
    await consume_login_budget("person@example.com")


async def test_demo_login_rejected_in_production_and_real_cookie_is_secure(
    database, clients, monkeypatch
):
    from app.config import settings

    async with database.begin() as db:
        db.add(
            User(
                email="admin@concord.demo",
                name="Demo",
                role="admin",
                password_hash=hasher.hash("test-password-2026"),
            )
        )
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "app_origin", "https://concord.example.com")
    client = await clients()
    client.headers["Origin"] = "https://concord.example.com"
    demo = await client.post(
        "/api/v1/auth/login", json={"email": "admin@concord.demo", "password": "test-password-2026"}
    )
    assert demo.status_code == 401
    real = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "test-password-2026"}
    )
    assert real.status_code == 200
    assert "Secure" in real.headers["set-cookie"]
    assert "HttpOnly" in real.headers["set-cookie"]

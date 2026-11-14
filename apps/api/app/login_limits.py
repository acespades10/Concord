"""Database-backed budgets shared by workers, including rejected login attempts."""

import hashlib
import math
import time

from fastapi import HTTPException
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db import SessionLocal
from app.models import LoginBudget

ACCOUNT_LIMIT = 10
ACCOUNT_WINDOW = 600
WORKSPACE_LIMIT = 30
WORKSPACE_WINDOW = 60


async def consume_login_budget(email: str, factory=None):
    now = time.time()
    blocked_for = 0
    async with (factory or SessionLocal).begin() as db:
        await db.execute(delete(LoginBudget).where(LoginBudget.started_at <= now - ACCOUNT_WINDOW))
        insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
        # Always acquire the workspace budget first so concurrent workers use the
        # same row-lock order. Do not trust forwarded IPs or store email addresses.
        for identity, limit, window in [
            ("workspace", WORKSPACE_LIMIT, WORKSPACE_WINDOW),
            ("account:" + email.strip().lower(), ACCOUNT_LIMIT, ACCOUNT_WINDOW),
        ]:
            key = hashlib.sha256(identity.encode()).hexdigest()
            expired = LoginBudget.started_at <= now - window
            statement = insert(LoginBudget).values(key=key, started_at=now, attempts=1)
            statement = statement.on_conflict_do_update(
                index_elements=[LoginBudget.key],
                set_={
                    "started_at": case((expired, now), else_=LoginBudget.started_at),
                    "attempts": case((expired, 1), else_=LoginBudget.attempts + 1),
                },
            ).returning(LoginBudget.started_at, LoginBudget.attempts)
            started, attempts = (await db.execute(statement)).one()
            if attempts > limit:
                blocked_for = max(1, math.ceil(started + window - now))
                break
    # Raising inside the transaction would roll back failed-attempt accounting.
    if blocked_for:
        raise HTTPException(
            429,
            "Too many sign-in attempts. Please try again later.",
            headers={"Retry-After": str(blocked_for)},
        )

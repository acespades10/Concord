"""Optional first-owner bootstrap for hosts without an interactive shell."""

import asyncio
import os

from argon2 import Type, extract_parameters
from sqlalchemy import select

from app.accounts import validate_account
from app.db import SessionLocal
from app.models import User


async def bootstrap_owner(db, email: str, password_hash: str):
    email = validate_account(email, "Workspace owner", "admin", "hash-supplied-out-of-band")
    parameters = extract_parameters(password_hash)
    if (
        parameters.type != Type.ID
        or parameters.memory_cost < 19456
        or parameters.time_cost < 2
        or parameters.hash_len < 32
        or parameters.salt_len < 16
    ):
        raise ValueError("Initial admin hash must use Argon2id with strong parameters")
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        if existing.role != "admin":
            raise ValueError("Initial admin address already belongs to a non-admin account")
        return
    if await db.scalar(select(User.id).limit(1)):
        raise ValueError("First-owner bootstrap requires an empty workspace; use the account CLI")
    db.add(User(email=email, name="Workspace owner", role="admin", password_hash=password_hash))
    await db.flush()


async def main():
    email = os.environ.get("INITIAL_ADMIN_EMAIL", "")
    password_hash = os.environ.get("INITIAL_ADMIN_PASSWORD_HASH", "")
    if not email and not password_hash:
        return
    if not email or not password_hash:
        raise ValueError("Set both INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD_HASH")
    async with SessionLocal.begin() as db:
        await bootstrap_owner(db, email, password_hash)
    print("Initial admin available; existing passwords are never replaced")


if __name__ == "__main__":
    asyncio.run(main())

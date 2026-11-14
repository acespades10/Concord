"""Provision workspace accounts without public registration or password arguments."""

import argparse
import asyncio
import getpass
import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hasher
from app.db import SessionLocal
from app.models import Session, User


def validate_account(email: str, name: str, role: str, password: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Provide a valid email address")
    if email.endswith("@concord.demo"):
        raise ValueError("Use a real account address, not a demo address")
    if not name.strip() or len(name.strip()) > 100:
        raise ValueError("Name must contain 1–100 characters")
    if role not in {"admin", "reviewer", "annotator"}:
        raise ValueError("Invalid role")
    if len(password) < 16 or password == "concord-demo-2026":
        raise ValueError("Use a unique password of at least 16 characters")
    return email


async def create_account(db: AsyncSession, email: str, name: str, role: str, password: str):
    email = validate_account(email, name, role, password)
    if await db.scalar(select(User).where(User.email == email)):
        raise ValueError("Account already exists; use reset-password to rotate its password")
    user = User(email=email, name=name.strip(), role=role, password_hash=hasher.hash(password))
    db.add(user)
    await db.flush()
    return user


async def reset_password(db: AsyncSession, email: str, password: str):
    user = await db.scalar(
        select(User).where(User.email == email.strip().lower()).with_for_update()
    )
    if not user:
        raise ValueError("Account does not exist")
    validate_account(user.email, user.name, user.role, password)
    user.password_hash = hasher.hash(password)
    await db.execute(delete(Session).where(Session.user_id == user.id))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "reset-password"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name")
    parser.add_argument("--role", choices=["admin", "reviewer", "annotator"], default="annotator")
    args = parser.parse_args()
    if args.action == "create" and not args.name:
        parser.error("create requires --name")
    password = getpass.getpass("New password (at least 16 characters): ")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        async with SessionLocal.begin() as db:
            if args.action == "create":
                await create_account(db, args.email, args.name, args.role, password)
            else:
                await reset_password(db, args.email, password)
    except ValueError as error:
        parser.error(str(error))
    print(
        "Account created"
        if args.action == "create"
        else "Password rotated; existing sessions revoked"
    )


if __name__ == "__main__":
    asyncio.run(main())

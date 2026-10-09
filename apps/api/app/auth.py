import hashlib
import hmac
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import get_db
from app.models import Session, User
from app.schemas import Login, Message, SessionOut

router = APIRouter(prefix="/auth", tags=["Authentication"])
hasher = PasswordHasher()  # Argon2id
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_origin(request: Request):
    # All browser mutations, including login, require the configured origin.
    if request.headers.get("origin") != settings.app_origin:
        raise HTTPException(403, "Untrusted request origin")


async def current_session(
    request: Request, db: AsyncSession = Depends(get_db, scope="function")
) -> Session:
    raw = request.cookies.get("concord_session", "")
    session = await db.get(Session, digest(raw)) if raw else None
    if not session or session.expires_at <= time.time():
        raise HTTPException(401, "Please sign in to continue")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            raise HTTPException(403, "Invalid CSRF token")
    return session


async def current_user(
    session: Session = Depends(current_session),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> User:
    user = await db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Session user is no longer available")
    return user


def roles(*allowed: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, "This action requires a different role")
        return user

    return dependency


@router.post("/login", response_model=SessionOut)
async def login(
    body: Login,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db, scope="function"),
):
    check_origin(request)
    user = await db.scalar(select(User).where(User.email == body.email.strip().lower()))
    try:
        await run_in_threadpool(
            hasher.verify, user.password_hash if user else DUMMY_HASH, body.password
        )
    except (VerificationError, InvalidHashError):
        raise HTTPException(401, "Email or password is incorrect") from None
    if not user:
        raise HTTPException(401, "Email or password is incorrect")
    old = request.cookies.get("concord_session")
    if old:
        await db.execute(delete(Session).where(Session.token_hash == digest(old)))
    await db.execute(delete(Session).where(Session.expires_at < time.time()))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires_at=time.time() + settings.session_hours * 3600,
        )
    )
    response.set_cookie(
        "concord_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "csrf": csrf}


@router.get("/session", response_model=SessionOut)
async def session_info(
    response: Response,
    session: Session = Depends(current_session),
    user: User = Depends(current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "csrf": session.csrf}


@router.post("/logout", response_model=Message)
async def logout(
    response: Response,
    session: Session = Depends(current_session),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    await db.delete(session)
    response.delete_cookie(
        "concord_session", path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
    return {"message": "Signed out"}

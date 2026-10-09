from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.config import settings
from app.db import engine
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="Concord Annotation API",
    version="1.0.0",
    description="Collaborative annotation and quality control. Session-cookie authentication; mutations require Origin and X-CSRF-Token. See /api/v1/auth/session for the CSRF token.",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    redoc_url="/api/v1/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    return response


@app.get("/api/v1/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")

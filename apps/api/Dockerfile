FROM ghcr.io/astral-sh/uv:0.11.29 AS uv
FROM python:3.12-slim AS builder
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 concord
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=concord:concord apps/api/ ./
USER concord
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

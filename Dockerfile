FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/ packages/

RUN uv sync --frozen --no-dev

# `uv run` reads/writes a cache at $UV_CACHE_DIR (defaults to $HOME/.cache/uv).
# appuser has no home, so point uv at a writable location and pre-create it with
# the right ownership so the first `uv run` in the container doesn't fail.
ENV UV_CACHE_DIR=/tmp/uv-cache
RUN mkdir -p /tmp/uv-cache && \
    groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --no-create-home appuser && \
    chown -R appuser:appuser /tmp/uv-cache /app
USER appuser

EXPOSE 8000

WORKDIR /app/packages/api

CMD ["uv", "run", "uvicorn", "agentaudit_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

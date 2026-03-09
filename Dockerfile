FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/ packages/

RUN uv sync --frozen --no-dev

EXPOSE 8000

WORKDIR /app/packages/api

CMD ["uv", "run", "uvicorn", "agentaudit_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

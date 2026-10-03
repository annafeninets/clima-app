# syntax=docker/dockerfile:1

# ---------- stage 1: сборка виртуального окружения ----------
FROM ghcr.io/astral-sh/uv:0.12 AS uv

FROM python:3.14-slim AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Сначала зависимости: слой кэшируется, пока не меняются pyproject.toml / uv.lock.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Затем сам проект (не editable, чтобы в runtime хватило одной папки .venv).
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------- stage 2: минимальный runtime ----------
FROM python:3.14-slim AS runtime

# tzdata нужен zoneinfo: утренние уведомления считаются по часовому поясу пользователя.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 clima \
 && useradd --system --uid 10001 --gid clima --no-create-home --home-dir /nonexistent clima \
 && mkdir -p /data/uploads \
 && chown -R clima:clima /data

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CLIMA_HOST=0.0.0.0 \
    CLIMA_PORT=8000 \
    CLIMA_DB_PATH=/data/clima.sqlite3 \
    CLIMA_UPLOADS_PATH=/data/uploads

# Сборка падает сразу, если SQL-схема не попала в пакет.
RUN python -c "from clima.database.database import Database; assert Database._schema_path.is_file()"

USER clima
VOLUME ["/data"]
EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["clima"]

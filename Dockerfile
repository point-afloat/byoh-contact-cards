# syntax=docker/dockerfile:1

# ---- Stage 1: build the React app ------------------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the runtime image --------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/data

# uv installs the locked dependencies; it is only needed at build time.
RUN pip install --no-cache-dir uv==0.10.12

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY --from=frontend /build/dist ./frontend/dist

# Non-root user; /data is where persistent data (user accounts) lives. Mount a volume there.
RUN groupadd --system --gid 10001 app \
 && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 && mkdir /data \
 && chown app:app /data
VOLUME ["/data"]

USER app
EXPOSE 8080

# 200 only when configured and /data is writable (see /api/health); the platform has its own check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/health', timeout=4)"]

# exec form: python is PID 1, so SIGTERM reaches uvicorn, which shuts down gracefully.
# One worker only: review sessions live in memory.
CMD ["python", "-m", "app.server"]

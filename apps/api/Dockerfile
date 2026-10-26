# Solar forecast API — production image (Azure Container Apps / docker compose).
FROM python:3.12-slim

# Pinned uv binary; keep in step with the version in .github/workflows/ci.yml.
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/srv/.venv/bin:$PATH" \
    PORT=8000

WORKDIR /srv

# Unprivileged runtime user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

# Install locked runtime dependencies first so this layer is cached across code changes.
# The app runs from /srv, so the project itself does not need installing.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=2)" || exit 1

# Shell form via sh -c so ${PORT} is expanded at runtime; exec keeps uvicorn as PID 1.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]

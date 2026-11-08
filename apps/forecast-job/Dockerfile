# Daily forecast job image (Azure Container Apps Job / docker run). See README.md here.
# Build: docker build -t solar-forecast-job apps/forecast-job
FROM python:3.12-slim

# Pinned uv binary; keep in step with the version in .github/workflows/ci.yml.
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH" \
    SOLAR_MODEL_DIR=/models \
    FORECAST_DIR=/forecasts

WORKDIR /app

# Unprivileged runtime user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

# Install locked runtime dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# The script finds ml/src from its own path, so keep the ML repo's layout. Model files are mounted at
# /models, never built in. ml/src/S01 is test-only and stays out.
COPY ml/configs/plants.yaml ml/configs/
COPY ml/src/solar ml/src/solar
COPY ml/scripts/run_forecast_job.py ml/scripts/

USER app

CMD ["python", "ml/scripts/run_forecast_job.py"]

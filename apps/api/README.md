# Solar Forecast API (`apps/api`)

FastAPI service that serves **day-ahead, 15-minute PV power forecasts (P10/P50/P90, kW)** for the four
PEA plants. It does **not** train or run the ML model. The model runs as a batch job in the ML repo and writes JSON
files, which this API reads and serves. Until those files exist, the `demo` provider returns a synthetic curve
(a clear-sky-shaped curve with seeded random clouds). It uses no real plant data.

```
app/
  main.py            create_app() factory, CORS, /health
  config.py          settings from env vars (pydantic-settings)
  schemas.py         API contract (Plant, Forecast, ForecastPoint, Health)
  plants.py          plant registry (S01–S04)
  providers/
    base.py          ForecastProvider protocol + errors
    demo.py          synthetic deterministic forecasts
    file.py          reads {FORECAST_DIR}/{plant_id}/{YYYY-MM-DD}.json
  routers/forecast.py  /api/v1/plants, /api/v1/forecast
tests/               pytest + TestClient
```

## Run locally

Uses [uv](https://docs.astral.sh/uv/getting-started/installation/). uv installs Python 3.12 for you if it is missing.

```bash
cd apps/api
uv sync                                # creates .venv from uv.lock, including dev tools
uv run uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Managing dependencies:

```bash
uv add <package>             # runtime dependency (updates pyproject.toml and uv.lock)
uv add --dev <package>       # dev-only tool
uv lock --upgrade            # bump everything within the allowed ranges
```

Always commit `uv.lock` together with `pyproject.toml`. CI runs `uv sync --locked`, which fails if they disagree.

With Docker (from the repo root):

```bash
docker build -t solar-api apps/api
docker run --rm -p 8000:8000 solar-api
# or the full stack: docker compose up --build
```

## Test and lint (same commands as CI)

```bash
uv run ruff check .
uv run ruff format --check .      # `uv run ruff format .` to fix
uv run pytest -q
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `local` | Free-text environment name, echoed by `/health` (`local`, `dev`, `prod`, ...) |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS origins, e.g. `http://localhost:3000,https://<web-app>.azurestaticapps.net` |
| `FORECAST_PROVIDER` | `demo` | `demo` = synthetic curves, `file` = read JSON files written by the ML job |
| `FORECAST_DIR` | `./forecasts` | Root folder for `file` provider (in Azure: a mounted Azure Files share) |
| `PORT` | `8000` | Container listen port (Docker image only) |

The API also reads a local `.env` file if one exists. `.env` is gitignored, so never commit it.

## Endpoints

Interactive docs: `/docs` (Swagger UI) and `/openapi.json`.

### `GET /health`

```json
{"status": "ok", "env": "local", "provider": "demo"}
```

### `GET /api/v1/plants`

```json
[
  {"id": "S01", "name": "S01 Sa Kaeo", "capacity_kw": 6000, "lat": 13.867, "lon": 102.6434},
  {"id": "S02", "name": "S02 Prachuap Khiri Khan", "capacity_kw": 5950, "lat": 12.0017, "lon": 99.7959},
  {"id": "S03", "name": "S03 Aranyaprathet", "capacity_kw": 8000, "lat": null, "lon": null},
  {"id": "S04", "name": "S04 Phichit", "capacity_kw": 8000, "lat": null, "lon": null}
]
```

S03/S04 coordinates are TBD. Update `app/plants.py` once PEA confirms them.

### `GET /api/v1/forecast?plant_id=S01&date=2026-10-17`

```json
{
  "plant_id": "S01",
  "date": "2026-10-17",
  "issued_at": "2026-10-16T23:55:00+07:00",
  "model_version": "demo-0.1",
  "forecast_mode": "primary",
  "unit": "kW",
  "resolution_minutes": 15,
  "timezone": "Asia/Bangkok",
  "points": [
    {"timestamp": "2026-10-17T00:00:00+07:00", "p10": 0.0, "p50": 0.0, "p90": 0.0},
    "... 96 points total, 00:00 to 23:45 ..."
  ]
}
```

| Status | When |
|---|---|
| 200 | Forecast found |
| 404 | Unknown `plant_id`, or (`file` provider) no file for that plant/date |
| 422 | Missing parameter or `date` not a valid `YYYY-MM-DD` |
| 500 | Forecast file exists but is invalid (the error is logged) |

## Forecast files written by the ML batch job

When `FORECAST_PROVIDER=file`, the API serves the file at:

```
{FORECAST_DIR}/{plant_id}/{YYYY-MM-DD}.json      e.g. forecasts/S01/2026-10-17.json
```

The file has **the exact same JSON as the `/api/v1/forecast` response** above. Rules (the API validates these
and returns 500 if they fail):

- `plant_id` and `date` must match the folder and file name.
- `points` has exactly **96** entries, one per 15-min interval of the **local** day (Asia/Bangkok, UTC+7).
  `timestamp` is the **interval start** with an explicit `+07:00` offset (`...T00:00:00+07:00` to `...T23:45:00+07:00`).
- `p10`, `p50`, `p90` are in kW, `>= 0`, and `p10 <= p50 <= p90`. Clip to `[0, capacity_kw]` in the ML job.
  Use `0.0` at night.
- `issued_at` is when the model ran (ISO 8601 with `+07:00`). It must be at or before the forecast's issue
  deadline on D-1.
- `model_version` identifies the model, e.g. `lgbm-nwp-2026.10.1`. It is shown in the dashboard.
- `forecast_mode` says how the forecast was made. Optional in the file; a missing value is served as `primary`.

  | Value | Meaning |
  |---|---|
  | `primary` | The model selected for this plant, using a fresh weather forecast |
  | `cached_weather` | The selected model, using the last weather forecast fetched before the cutoff |
  | `climatology` | Training-only monthly time-slot climatology, because no weather forecast was available |
  | `baseline` | Another baseline, because the selected model could not run |

  Anything other than `primary` shows the fallback badge in the dashboard. Any other value is rejected (500).
- `unit` = `"kW"`, `resolution_minutes` = `15`, `timezone` = `"Asia/Bangkok"`.

Write each file atomically: write `2026-10-17.json.tmp`, then rename it. This way the API never reads a half-written
file. Forecast files contain model output, not raw PEA measurements. Keep them out of git anyway
(`forecasts/` and `data/` are gitignored).

Minimal writer (ML side):

```python
import json, os
from pathlib import Path


def write_forecast(root: Path, payload: dict) -> None:
    out = root / payload["plant_id"] / f"{payload['date']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, out)
```

To validate a file against the contract, install this package and run
`app.schemas.Forecast.model_validate_json(path.read_text())`.

# Solar Forecast App

Web app and API that serve **day-ahead 15-min solar PV power forecasts** for four PEA (Thailand) plants,
deployed on **Azure** with **GitHub Actions** CI/CD. The ML model is trained in a separate repository,
[Solar_Power_Prediction](https://github.com/pcismyname/Solar_Power_Prediction).

```
solar-forecast-app/
├── apps/
│   ├── api/            FastAPI service (Python 3.12, Docker)   → Azure Container Apps
│   └── web/            Next.js dashboard (static export)       → Azure Static Web Apps
├── infra/azure/        one-time Azure setup commands
├── docs/architecture.md   architecture + stack decision
├── .github/workflows/  ci.yml · deploy-api.yml · deploy-web.yml
├── docker-compose.yml  run both locally
├── AGENTS.md           rules for contributors & AI agents
└── CLAUDE.md
```

## Quick start

```bash
# Option A: Docker (both services)
docker compose up --build            # web → http://localhost:3000, API → http://localhost:8000/docs

# Option B: run each app directly
cd apps/api && python -m venv .venv && source .venv/Scripts/activate && pip install -e ".[dev]" && uvicorn app.main:app --reload
cd apps/web && npm ci && npm run dev
```

The API starts in **demo mode** (`FORECAST_PROVIDER=demo`). It returns synthetic clear-sky-shaped forecasts, so
the app works without any real data. Set `FORECAST_PROVIDER=file` to serve JSON written by the ML job.

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | status, environment, provider |
| GET | `/api/v1/plants` | the 4 plants (id, name, capacity, coordinates) |
| GET | `/api/v1/forecast?plant_id=S01&date=YYYY-MM-DD` | 96 × {timestamp, p10, p50, p90} in kW, Asia/Bangkok |

Interactive docs are at `/docs`.

## CI/CD

- **CI** (`ci.yml`) runs on every PR and on `main`:
  - API: ruff, pytest and a Docker build.
  - Web: lint, typecheck and build.
- **Deploy** runs on merge to `main`, once Azure is configured (see [infra/azure/README.md](infra/azure/README.md)):
  - `deploy-api.yml`: build the image → Azure Container Registry → Container App → smoke test.
  - `deploy-web.yml`: static build → Static Web App.

## Working agreement

Branch per task, then a PR with one review and green CI before merging. Never commit secrets or real plant data.
See [AGENTS.md](AGENTS.md).

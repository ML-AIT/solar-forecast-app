# Daily forecast job

Runs `ml/scripts/run_forecast_job.py` once and exits. Each run writes tomorrow's forecast (final, issued at the
23:55 D-1 cutoff) and the day after (early version, D-2 23:55) for S01 and S02. The output is
`{FORECAST_DIR}/{plant_id}/{YYYY-MM-DD}.json`, in the format described in `apps/api/README.md`. The logic is in
`ml/src/solar/forecast_job.py`, and its settings are the environment variables listed in the run script's docstring.

## Where the code comes from

The job forecasts with the ML repo's feature and model code, **copied unchanged**, so it serves exactly what was
evaluated. The `ml/` layout is the ML repo's, so the paths match between the two repos.

| Files | Owner |
|---|---|
| `ml/src/solar/{issue_time,nwp,nwp_features,plants,pvlib_baseline,solar_geometry,weather_only,__init__}.py`, `ml/configs/plants.yaml`, `ml/tests/conftest.py`, `ml/tests/test_{issue_time,nwp,nwp_features,pvlib_baseline,weather_only}.py` | ML repo (copies) |
| `ml/src/S01/` | ML repo (copy, tests only: `test_issue_time.py` checks the job's features against the notebooks' builder; not in the image) |
| `ml/src/solar/forecast_job.py`, `ml/scripts/run_forecast_job.py`, `ml/tests/test_forecast_job.py`, everything else here | This repo |

Copied from the ML repo at **`cabd66b`**, plus the `PvlibBaseline.from_dict` fix, which is still waiting to be merged in the ML repo.

When the ML repo changes one of the copied files, update the copies from a clone of it and record its commit above.
Run this from the repo root:

```bash
python -I apps/forecast-job/sync_ml_copies.py --ml-repo <ML repo clone>          # copy
python -I apps/forecast-job/sync_ml_copies.py --ml-repo <ML repo clone> --check  # exit 1 if a copy is stale
```

The ML repo is private, so CI cannot run this check. Run it before every PR that touches the job.

Lint uses the ML repo's settings (`ruff check`, line length 100, no `ruff format`), so the copies stay byte for byte
the same as the ML repo's files.

## Develop

```bash
cd apps/forecast-job
uv sync
uv run ruff check .
uv run pytest -q
```

## Run the image

The image holds code only. **Model files are mounted, never built in**, because they are made from PEA data:

| Mount | Holds | Access |
|---|---|---|
| `/models` | `pvlib_baseline_{plant}.json`, `{plant}_climatology.csv`, `climatology_meta.json` | read only |
| `/forecasts` | Forecast JSON, the folder the API reads, and `weather_cache/` | read and write |

```bash
docker build -t solar-forecast-job apps/forecast-job
docker run --rm -v <models>:/models:ro -v <forecasts>:/forecasts solar-forecast-job
```

## In Azure

The image runs as the Container Apps Job `solar-forecast-daily` on cron `0 16 * * *` (23:00 Bangkok; Azure reads cron
in UTC). Every weather run the 23:55 issue may use is out by 23:00. If a run exits with an error, the job retries once.
A rerun never makes a day's forecast worse, so the retry keeps any good file the first try wrote.

Two Azure Files shares back the mounts, so the API has no route to the model files:

| Share | Job | API |
|---|---|---|
| `solar-models` | `/models`, read only | not mounted |
| `solar-forecasts` | `/forecasts`, read and write | `/forecasts`, read only |

Both images run as uid 10001, and Azure Files mounts belong to root by default, so each volume sets
`uid=10001,gid=10001` in `mountOptions`.

`.github/workflows/deploy-job.yml` deploys after CI passes on `main`. It skips the deploy when `apps/forecast-job/` and
the workflow have not changed since the commit the running image was built from. It needs the repository variable
`DEPLOY_JOB=true`, and the `production` environment variables from `infra/azure/README.md` plus `FORECAST_JOB_NAME`.

# Forecast job: operation check

The proposal's prototype-operation criteria (§1.3), measured on a replay of past days and on the live nightly runs. Made by `apps/forecast-job/ml/scripts/replay_forecast_job.py`; see its docstring for how it works and how to rerun it.

## Replay: 2026-10-10 to 2026-11-08 (30 target days, S01, S02)

| Criterion | Result | Target |
| --- | --- | --- |
| Complete files (96 finite values in 15-min order, P10 <= P50 <= P90, issue time, model version, mode) | 60 / 60 (100 %) | 100 % |
| Days with every plant complete | 30 / 30 | all |
| `primary` | 60 | counted |
| `cached_weather` | 0 | counted |
| `climatology` | 0 | counted |
| Failed (no complete file) | 0 | counted |
| Run time per day, all plants, container start to exit | median 8 s, max 9 s | under 300 s |

Image built from commit `7c6d2b0`; models pvlib-S01-2024.08.07, pvlib-S02-2024.07.19. Each day is the final forecast (`d1_2355`). Per-day rows: `replay_runs.csv`.

## Live scheduled runs on Azure

| Started (Bangkok) | Finished | Status | Run time | Files | Modes | Before target day |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-08 23:00 | 23:00:42 | Succeeded | 42 s | 4 written | 4 primary | yes |

Scheduled runs: 1; succeeded: 1; published before the target day: 1; longest run: 42 s. Each run writes tomorrow's final forecast (`d1_2355`) and the early version for the day after (`d2_2355`). Per-file rows: `live_runs.csv`.

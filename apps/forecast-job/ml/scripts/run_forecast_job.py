"""Write tomorrow's forecast JSON for each plant (see solar.forecast_job).

Settings come from environment variables, so the same image runs locally and in Azure:
    SOLAR_MODEL_DIR    required: folder with the model files (confidential, never in git)
    FORECAST_DIR       where forecasts go, the same folder the API reads (default: forecasts)
    WEATHER_CACHE_DIR  last good weather fetch (default: $FORECAST_DIR/weather_cache)
    ISSUE_SCENARIO     d1_2355 (default) or d1_1000; move the job's schedule with it
    WEATHER_API_URL    Open-Meteo Previous Runs URL; a broken one forces the fallback chain

Without --date it writes tomorrow at ISSUE_SCENARIO and the day after at d2_2355 (the early version).
A rerun never makes a day's forecast worse (see solar.forecast_job); --force replaces it anyway.
Prints one JSON line per plant and day and exits 1 if any wrote no file. A failed plant or day does
not stop the others, and a fallback is not a failure: the file says which mode it used.

Usage (from the repo root):
    SOLAR_MODEL_DIR=<folder> python ml/scripts/run_forecast_job.py
    SOLAR_MODEL_DIR=<folder> python ml/scripts/run_forecast_job.py --date 2026-11-06 --plants S01
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "ml" / "src"))

import pandas as pd

from solar import forecast_job as job
from solar import nwp as nw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", help="forecast day, YYYY-MM-DD (default: tomorrow in Bangkok)")
    parser.add_argument("--plants", nargs="+", default=list(job.PLANTS))
    parser.add_argument("--force", action="store_true", help="replace an existing forecast")
    args = parser.parse_args()

    forecast_dir = Path(os.environ.get("FORECAST_DIR", "forecasts"))
    paths = job.JobPaths(
        model_dir=Path(os.environ["SOLAR_MODEL_DIR"]),
        forecast_dir=forecast_dir,
        cache_dir=Path(os.environ.get("WEATHER_CACHE_DIR", forecast_dir / "weather_cache")),
    )
    scenario = job.get_scenario(os.environ.get("ISSUE_SCENARIO", job.DEFAULT_SCENARIO))
    api_url = os.environ.get("WEATHER_API_URL", nw.API_URL)
    fetch = job.fetch_once_per_plant(functools.partial(job.fetch_weather, api_url=api_url))
    now = pd.Timestamp.now(tz=job.TIMEZONE)
    targets = ([(pd.Timestamp(args.date), scenario)] if args.date
               else job.nightly_targets(now, scenario))

    failed = False
    for plant_id in args.plants:
        for day, day_scenario in targets:
            started = pd.Timestamp.now(tz=job.TIMEZONE)
            try:
                summary = job.run_plant(plant_id, day, day_scenario, paths, now, fetch, args.force)
            except Exception as err:  # noqa: BLE001  one plant or day must not stop the others
                failed = True
                summary = {"plant_id": plant_id, "date": f"{day:%Y-%m-%d}",
                           "scenario": day_scenario.key, "forecast_mode": None,
                           "reason": f"{type(err).__name__}: {err}"}
            seconds = (pd.Timestamp.now(tz=job.TIMEZONE) - started).total_seconds()
            print(json.dumps({**summary, "seconds": round(seconds, 1)}), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

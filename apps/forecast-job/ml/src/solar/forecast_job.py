"""Daily forecast job: 96 x 15-min P10/P50/P90 (kW) for one plant and day, as forecast JSON.

The file format is the contract in solar-forecast-app's `apps/api/README.md`. The job has no live
plant data, so it serves what passed with weather alone: the pvlib baseline (final proposal §3.3).

Fallback chain, each step used only if the one before fails:
1. `primary`: pvlib with weather fetched now.
2. `cached_weather`: pvlib with the last complete weather fetch.
3. `climatology`: the training-only monthly slot table.

Weather comes from the Previous Runs API, the source of the archive the model was scored on, and
goes through the same `build_weather_features`, so serving and evaluation use the same inputs. The
API also fills offsets with runs newer than the cutoff, so the job must never use an offset other
than the one `allowed_offset` picks for a slot. Running after the cutoff is therefore safe.

Each night writes two days: tomorrow at the issue time (the final forecast) and the day after at
D-2 23:55 (an early version), so the dashboard always has tomorrow. One fetch per plant covers both.

A rerun for the same day never makes the forecast worse: it replaces the file only with a better
mode, or the same mode from a later cutoff (the final replacing the early version), and leaves a
`primary` file alone otherwise, unless forced. The file records its `issue_scenario`, which the API
serves. The summary logs what it did (proposal §3.3).

The issue time is one setting, `scenario`. Each model file holds a P10/P90 band per issue time, so
switching needs no rebuild: only the job's schedule has to move with it.

The model folder holds confidential derivatives of PEA data, so it stays out of git:
    pvlib_baseline_{plant}.json, {plant}_climatology.csv, climatology_meta.json

Timestamps are Asia/Bangkok slot starts. Slots are naive inside the job, like the PEA data, and get
their +07:00 offset only in the JSON.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import issue_time as it
from . import nwp as nw
from . import nwp_features as nf
from .plants import Plant, load_plants
from .pvlib_baseline import PvlibBaseline
from .solar_geometry import slot_geometry, zero_at_night
from .weather_only import build_weather_features

TIMEZONE = "Asia/Bangkok"
SLOTS_PER_DAY = 96
PLANTS = ("S01", "S02")  # S03 and S04 wait for confirmed coordinates (decision 0003)
DEFAULT_SCENARIO = it.D1_2355.key
EARLY_SCENARIO = it.D2_2355

PRIMARY = "primary"
CACHED_WEATHER = "cached_weather"
CLIMATOLOGY = "climatology"
MODE_ORDER = (PRIMARY, CACHED_WEATHER, CLIMATOLOGY)  # best first

WEATHER_VARIABLES = ("shortwave_radiation", "temperature_2m", "cloud_cover")
# A fetch reaches past the target day so that its cache can stand in on the next days too.
FETCH_DAYS_BEHIND, FETCH_DAYS_AHEAD = 1, 3
REQUEST_TIMEOUT_S = 30
# About 1 request in 9 was dropped in a test on 2026-11-05, cause unknown. Three tries were too few.
RETRIES, RETRY_WAIT_S = 4, 5  # waits 5, 10, 20 and 40 s
# What a failed fetch or a bad cache file raises. Anything else is a bug and should fail loudly.
WEATHER_ERRORS = (OSError, ValueError, KeyError)


class WeatherError(ValueError):
    """The weather forecast does not cover every slot from all three models."""


@dataclass(frozen=True)
class JobPaths:
    """`model_dir` is read only, the other two are written."""

    model_dir: Path
    forecast_dir: Path
    cache_dir: Path


@dataclass(frozen=True)
class ServedModel:
    """The fitted pvlib baseline and its band for one issue time."""

    model: PvlibBaseline
    hour_error_kw: dict[str, dict[str, float]]  # {hour: {"q10": kW, "q90": kW}}
    version: str


def get_scenario(key: str) -> it.IssueScenario:
    """The issue scenario with this key, e.g. `d1_2355`."""
    scenarios = {s.key: s for s in it.SCENARIOS}
    if key not in scenarios:
        raise ValueError(f"unknown issue scenario {key!r}; expected one of {sorted(scenarios)}")
    return scenarios[key]


def target_day(now: pd.Timestamp) -> pd.Timestamp:
    """Tomorrow in Bangkok, as naive midnight, for an aware `now`."""
    return now.tz_convert(TIMEZONE).normalize().tz_localize(None) + pd.Timedelta(days=1)


def nightly_targets(now: pd.Timestamp, scenario: it.IssueScenario):
    """[(day, scenario)]: tomorrow at `scenario`, then the day after as the early version."""
    tomorrow = target_day(now)
    return [(tomorrow, scenario), (tomorrow + pd.Timedelta(days=1), EARLY_SCENARIO)]


def day_slots(day: pd.Timestamp) -> pd.DatetimeIndex:
    """The 96 naive slot starts of `day`."""
    return pd.date_range(day, periods=SLOTS_PER_DAY, freq=nf.SLOT)


# ---------------------------------------------------------------- weather --------------------
def _get_json(url: str) -> dict:
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_S) as response:
                return json.load(response)
        except (OSError, ValueError):
            if attempt == RETRIES:
                raise
            time.sleep(RETRY_WAIT_S * 2**attempt)
    raise RuntimeError("unreachable")


def fetch_weather(plant: Plant, day: pd.Timestamp, api_url: str = nw.API_URL) -> pd.DataFrame:
    """Open-Meteo rows for all three models, in the shape of the archive table."""
    first = day - pd.Timedelta(days=FETCH_DAYS_BEHIND)
    last = day + pd.Timedelta(days=FETCH_DAYS_AHEAD)
    frames = []
    for model in nw.MODELS:
        params = nw.build_params(plant.lat, plant.lon, model, f"{first:%Y-%m-%d}",
                                 f"{last:%Y-%m-%d}", variables=WEATHER_VARIABLES)
        payload = _get_json(f"{api_url}?{urllib.parse.urlencode(params)}")
        frames.append(nw.parse_response(payload, plant.plant_id, model))
    return pd.concat(frames, ignore_index=True)


def fetch_once_per_plant(fetch: Callable[[Plant, pd.Timestamp], pd.DataFrame]):
    """Reuse a plant's first good fetch for its other days; tomorrow's window covers the day after."""
    fetched: dict[str, pd.DataFrame] = {}

    def shared(plant: Plant, day: pd.Timestamp) -> pd.DataFrame:
        if plant.plant_id not in fetched:
            fetched[plant.plant_id] = fetch(plant, day)
        return fetched[plant.plant_id]

    return shared


def usable_weather(nwp: pd.DataFrame, slots: pd.DatetimeIndex, scenario: it.IssueScenario,
                   plant: Plant) -> pd.DataFrame:
    """Weather features for `slots`. Raises WeatherError unless all three models cover them all.

    The model mean was scored on rows with all three models. A mean of fewer would shift it,
    because the models differ in bias.
    """
    rows = nf.load_plant_nwp(nwp, plant.plant_id)
    features = build_weather_features(slots, rows, scenario, plant)
    needed = [f"nwp_{v}_{s}" for v in ("ghi", "temp") for s in nf.SHORT_NAME.values()]
    missing = features[needed].isna().sum()
    if missing.any():
        raise WeatherError(f"missing slots: {missing[missing > 0].to_dict()}")
    return features


def _cache_path(paths: JobPaths, plant_id: str) -> Path:
    return paths.cache_dir / f"{plant_id}.csv"


def write_cache(paths: JobPaths, plant_id: str, nwp: pd.DataFrame) -> None:
    """Keep this fetch for the fallback, replacing the last one atomically."""
    out = _cache_path(paths, plant_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".csv.tmp")
    nwp.to_csv(tmp, index=False)
    os.replace(tmp, out)


def choose_weather(
    plant: Plant,
    day: pd.Timestamp,
    scenario: it.IssueScenario,
    paths: JobPaths,
    fetch: Callable[[Plant, pd.Timestamp], pd.DataFrame],
) -> tuple[str, pd.DataFrame | None, str]:
    """(forecast mode, weather features or None, why it is not the mode above it)."""
    slots = day_slots(day)
    try:
        nwp = fetch(plant, day)
        features = usable_weather(nwp, slots, scenario, plant)
    except WEATHER_ERRORS as err:
        reason = f"fetch failed: {type(err).__name__}: {err}"
    else:
        try:
            write_cache(paths, plant.plant_id, nwp)
        except OSError as err:  # the forecast is still good; the cost comes only on a later failure
            return PRIMARY, features, f"cache not written: {err}"
        return PRIMARY, features, ""
    try:
        cached = pd.read_csv(_cache_path(paths, plant.plant_id))
        return CACHED_WEATHER, usable_weather(cached, slots, scenario, plant), reason
    except WEATHER_ERRORS as err:
        return CLIMATOLOGY, None, f"{reason}; cache unusable: {type(err).__name__}: {err}"


# ---------------------------------------------------------------- models ---------------------
def load_model(model_dir: Path, plant_id: str, scenario: it.IssueScenario) -> ServedModel:
    """The saved baseline with its band for `scenario`."""
    path = model_dir / f"pvlib_baseline_{plant_id}.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    if scenario.key not in saved["intervals"]:
        raise ValueError(f"{path.name} has no band for {scenario.key}: {sorted(saved['intervals'])}")
    version = f"pvlib-{plant_id}-{saved['train_end'].replace('-', '.')}"
    return ServedModel(PvlibBaseline.from_dict(saved),
                       saved["intervals"][scenario.key]["hour_error_kw"], version)


def _quantiles(p10, p50, p90, capacity_kw: float, sun_down) -> dict[str, np.ndarray]:
    """Contract rules: within [0, capacity], p10 <= p50 <= p90, 0 kW when the sun is down all slot.

    Same order as the evaluation: clip, then widen to include p50, then zero the night.
    """
    p50 = np.clip(p50, 0, capacity_kw)
    return {"p10": zero_at_night(np.minimum(p50, np.clip(p10, 0, capacity_kw)), sun_down),
            "p50": zero_at_night(p50, sun_down),
            "p90": zero_at_night(np.maximum(p50, np.clip(p90, 0, capacity_kw)), sun_down)}


def pvlib_quantiles(served: ServedModel, features: pd.DataFrame, sun_down) -> dict[str, np.ndarray]:
    """P50 from pvlib, P10 and P90 from the error band of the slot's hour of day.

    An hour with no daylight training row has no band, and P10 = P90 = P50 there.
    """
    model = served.model
    raw = model.predict(features.index, features["nwp_ghi_mean"], features["nwp_temp_mean"])
    p50 = zero_at_night(np.clip(raw, 0, model.capacity_kw), sun_down)
    hours = [served.hour_error_kw.get(str(h), {}) for h in features.index.hour]
    q10 = np.array([h.get("q10", 0.0) for h in hours])
    q90 = np.array([h.get("q90", 0.0) for h in hours])
    return _quantiles(p50 + q10, p50, p50 + q90, model.capacity_kw, sun_down)


def climatology_quantiles(model_dir: Path, plant: Plant, day: pd.Timestamp,
                          sun_down) -> tuple[dict[str, np.ndarray], str]:
    """(quantiles, model version) for `day`'s month. The table's values are raw."""
    table = pd.read_csv(model_dir / f"{plant.plant_id}_climatology.csv")
    rows = table[table["month"] == day.month].sort_values("slot")
    if len(rows) != SLOTS_PER_DAY:
        raise ValueError(f"{plant.plant_id} climatology has {len(rows)} rows for month {day.month}")
    meta = json.loads((model_dir / "climatology_meta.json").read_text(encoding="utf-8"))
    quantiles = _quantiles(rows["p10_kw"].to_numpy(), rows["mean_kw"].to_numpy(),
                           rows["p90_kw"].to_numpy(), plant.capacity_kw, sun_down)
    return quantiles, meta["plants"][plant.plant_id]["model_version"]


# ---------------------------------------------------------------- output ---------------------
def forecast_payload(plant_id: str, day: pd.Timestamp, issued_at: pd.Timestamp, version: str,
                     mode: str, quantiles: dict[str, np.ndarray],
                     scenario: str = DEFAULT_SCENARIO) -> dict:
    """The contract's JSON. Raises ValueError rather than let a bad forecast reach the API."""
    if any(len(q) != SLOTS_PER_DAY or not np.isfinite(q).all() for q in quantiles.values()):
        raise ValueError(f"{plant_id} {day:%Y-%m-%d}: need {SLOTS_PER_DAY} finite values")
    rounded = {name: np.round(q, 2) for name, q in quantiles.items()}
    stamps = day_slots(day).tz_localize(TIMEZONE)
    return {
        "plant_id": plant_id,
        "date": f"{day:%Y-%m-%d}",
        "issued_at": issued_at.tz_convert(TIMEZONE).isoformat(timespec="seconds"),
        "model_version": version,
        "forecast_mode": mode,
        "issue_scenario": scenario,
        "unit": "kW",
        "resolution_minutes": 15,
        "timezone": TIMEZONE,
        "points": [{"timestamp": stamp.isoformat(), "p10": float(rounded["p10"][i]),
                    "p50": float(rounded["p50"][i]), "p90": float(rounded["p90"][i])}
                   for i, stamp in enumerate(stamps)],
    }


def forecast_path(root: Path, plant_id: str, day: pd.Timestamp) -> Path:
    return root / plant_id / f"{day:%Y-%m-%d}.json"


def read_forecast(path: Path) -> dict | None:
    """The forecast already written, or None. An unreadable file counts as none."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _scenario_of(payload: dict) -> it.IssueScenario:
    """The issue scenario a file was made with. Files from before the field count as the default."""
    scenarios = {s.key: s for s in it.SCENARIOS}
    return scenarios.get(payload.get("issue_scenario"), scenarios[DEFAULT_SCENARIO])


def write_forecast(out: Path, payload: dict) -> None:
    """Write atomically, so the API never reads a half-written file."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, out)


def run_plant(
    plant_id: str,
    day: pd.Timestamp,
    scenario: it.IssueScenario,
    paths: JobPaths,
    now: pd.Timestamp,
    fetch: Callable[[Plant, pd.Timestamp], pd.DataFrame] = fetch_weather,
    force: bool = False,
) -> dict:
    """Forecast one plant and day, write the file and return a summary for the logs.

    The summary's `action` is `written`, `replaced` or `kept`. `force` replaces whatever is there.
    """
    out = forecast_path(paths.forecast_dir, plant_id, day)
    previous = read_forecast(out)
    previous_mode = None if previous is None else previous.get("forecast_mode", PRIMARY)
    later_cutoff = previous is not None and (
        nf.issue_time(day, scenario) > nf.issue_time(day, _scenario_of(previous)))
    summary = {"plant_id": plant_id, "date": f"{day:%Y-%m-%d}", "scenario": scenario.key,
               "path": str(out)}

    def kept(reason: str) -> dict:
        return {**summary, "action": "kept", "forecast_mode": previous_mode,
                "model_version": previous.get("model_version"), "reason": reason}

    if previous_mode == PRIMARY and not force and not later_cutoff:
        return kept("primary forecast already written")

    plant = load_plants()[plant_id]
    served = load_model(paths.model_dir, plant_id, scenario)
    sun_down = slot_geometry(day_slots(day), plant.lat, plant.lon)["sun_down"].to_numpy()
    mode, features, reason = choose_weather(plant, day, scenario, paths, fetch)
    if features is None:
        quantiles, version = climatology_quantiles(paths.model_dir, plant, day, sun_down)
    else:
        quantiles, version = pvlib_quantiles(served, features, sun_down), served.version
    payload = forecast_payload(plant_id, day, now, version, mode, quantiles, scenario.key)
    if previous_mode in MODE_ORDER and not force:
        rank, previous_rank = MODE_ORDER.index(mode), MODE_ORDER.index(previous_mode)
        if rank > previous_rank or (rank == previous_rank and not later_cutoff):
            return kept(f"this run got {mode}, not better than {previous_mode}: {reason}")
    write_forecast(out, payload)
    return {**summary, "action": "written" if previous is None else "replaced",
            "forecast_mode": mode, "model_version": version, "reason": reason}

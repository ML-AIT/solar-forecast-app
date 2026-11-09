"""Archived day-ahead weather forecasts (NWP) from the Open-Meteo Previous Runs API.

Previous Runs keeps forecasts as they were issued: `<variable>_previous_dayN` at valid time t
comes from a model run about N days (N x 24 h plus the run's delay) before t, so different hours
of one forecast day can come from different runs. Exact lead times and publication delays are
[UNVERIFIED] (RESEARCH_NOTES §8: lead 24 to ~29 h for previous_day1). These are the only
weather-forecast inputs allowed for day D (AGENTS.md §3). The stitched Historical Forecast API must not be used as features.

Conventions (docs/RESEARCH_NOTES.md §8):
- Times are Asia/Bangkok. Radiation is the mean over the hour *ending* at the stamp
  (07:00 = mean 06:00-07:00). Temperature, humidity, cloud cover and wind are instantaneous.
- Wind is requested in m/s (the API defaults to km/h).
- Models are named explicitly (`best_match` switches models by location).
- Each model snaps the plant to its own grid cell; grid_lat/grid_lon/grid_elevation keep it.

What `offset_day` does *not* prove: the exact run and when it was published. Which offset an
issue time may use depends on the hour of day (e.g. 23:55 D-1 needs offset 2 for bins after
18:00, RESEARCH_NOTES §8) and is decided when features are built (solar.issue_time); this module
only downloads and reshapes.

Time labels: `valid_time` is Open-Meteo's stamp. For radiation it is the END of the averaged hour,
while PEA stamps appear to be interval-start (AGENTS.md §3.8): shift before joining.

Sources: https://open-meteo.com/en/docs/previous-runs-api ·
https://openmeteo.substack.com/p/weather-forecasts-from-previous-model-runs
"""

from __future__ import annotations

import pandas as pd

API_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
TIMEZONE = "Asia/Bangkok"

MODELS = ("ecmwf_ifs025", "gfs_seamless", "icon_global")
# First date with *radiation* in the archive (RESEARCH_NOTES §8; confirmed by the 2026-10-27
# download). ECMWF non-radiation variables start earlier (2024-02-04, RH 2024-03-01).
ARCHIVE_START = {
    "ecmwf_ifs025": "2024-03-07",
    "gfs_seamless": "2024-01-19",
    "icon_global": "2024-01-19",
}
VARIABLES = (
    "shortwave_radiation",  # GHI, W/m2, backward hourly mean
    "direct_radiation",  # W/m2 on horizontal plane, backward hourly mean
    "diffuse_radiation",  # W/m2, backward hourly mean
    "direct_normal_irradiance",  # W/m2, backward hourly mean
    "cloud_cover",  # %, instantaneous
    "temperature_2m",  # degC, instantaneous
    "relative_humidity_2m",  # %, instantaneous
    "wind_speed_10m",  # m/s (requested), instantaneous
)
# Days between the run and the valid time. Offsets 1-3 cover the issue-time scenarios (D-1 23:55,
# D-1 12:00 Grid Code, D-2 23:55); the allowed offset per hour is chosen in solar.issue_time.
OFFSETS = (1, 2, 3)
EXPECTED_UNITS = {
    "shortwave_radiation": "W/m²",
    "direct_radiation": "W/m²",
    "diffuse_radiation": "W/m²",
    "direct_normal_irradiance": "W/m²",
    "cloud_cover": "%",
    "temperature_2m": "°C",
    "relative_humidity_2m": "%",
    "wind_speed_10m": "m/s",
}
# Physical range per variable; values outside are counted in the audit (not changed here).
VALID_RANGE = {
    "shortwave_radiation": (0, 1500),
    "direct_radiation": (0, 1500),
    "diffuse_radiation": (0, 1500),
    "direct_normal_irradiance": (0, 1500),
    "cloud_cover": (0, 100),
    "relative_humidity_2m": (0, 100),
    "temperature_2m": (-10, 55),
    "wind_speed_10m": (0, 60),
}

ID_COLUMNS = ["plant", "model", "offset_day", "valid_time"]
GRID_COLUMNS = ["grid_lat", "grid_lon", "grid_elevation"]


def build_params(
    lat: float,
    lon: float,
    model: str,
    start_date: str,
    end_date: str,
    variables: tuple[str, ...] = VARIABLES,
    offsets: tuple[int, ...] = OFFSETS,
) -> dict[str, str]:
    """Query parameters for one location, one model and one date range (inclusive)."""
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}; expected one of {MODELS}")
    hourly = [f"{v}_previous_day{n}" for n in offsets for v in variables]
    return {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "hourly": ",".join(hourly),
        "models": model,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": TIMEZONE,
        "wind_speed_unit": "ms",
    }


def parse_response(payload: dict, plant: str, model: str) -> pd.DataFrame:
    """Reshape one API response into rows of (plant, model, offset_day, valid_time) + variables.

    Column names in the response may or may not carry a `_<model>` suffix (they do when several
    models are requested); both forms are accepted.
    """
    if payload.get("error"):
        raise ValueError(f"Open-Meteo error for {plant}/{model}: {payload.get('reason')}")
    hourly = payload["hourly"]
    units = payload.get("hourly_units", {})
    times = pd.to_datetime(hourly["time"]).tz_localize(TIMEZONE)

    by_offset: dict[int, dict[str, pd.Series]] = {}
    for key, values in hourly.items():
        if key == "time":
            continue
        variable, offset, suffix = _split_key(key)
        if suffix not in ("", model):
            raise ValueError(f"{plant}: column {key!r} is for model {suffix!r}, not {model!r}")
        expected_unit = EXPECTED_UNITS.get(variable)
        if expected_unit and key in units and units[key] != expected_unit:
            raise ValueError(f"{plant}/{model}: {key} in {units[key]!r}, expected {expected_unit!r}")
        columns = by_offset.setdefault(offset, {})
        if variable in columns:
            raise ValueError(f"{plant}/{model}: duplicate column for {variable} offset {offset}")
        columns[variable] = pd.to_numeric(pd.Series(values), errors="coerce")

    frames = []
    for offset in sorted(by_offset):
        frame = pd.DataFrame(by_offset[offset])
        frame.insert(0, "valid_time", times)
        frame.insert(0, "offset_day", offset)
        frames.append(frame)

    out = pd.concat(frames, ignore_index=True)
    out.insert(0, "model", model)
    out.insert(0, "plant", plant)
    out["grid_lat"] = payload.get("latitude")
    out["grid_lon"] = payload.get("longitude")
    out["grid_elevation"] = payload.get("elevation")
    return out


def _split_key(key: str) -> tuple[str, int, str]:
    """'shortwave_radiation_previous_day1_gfs_seamless' -> ('shortwave_radiation', 1, 'gfs_seamless').

    The model suffix is '' when the response holds a single model without suffixes.
    """
    variable, sep, rest = key.partition("_previous_day")
    digits, _, suffix = rest.partition("_")
    if not sep or not digits.isdigit():
        raise ValueError(f"not a Previous Runs column: {key!r}")
    return variable, int(digits), suffix


def expected_rows(params: dict[str, str]) -> int:
    """Rows parse_response should return for a request: hours in the date range x offsets."""
    days = (pd.Timestamp(params["end_date"]) - pd.Timestamp(params["start_date"])).days + 1
    offsets = {_split_key(k)[1] for k in params["hourly"].split(",")}
    return 24 * days * len(offsets)


def availability_audit(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate coverage per plant, model, offset and variable (safe to commit: no PEA data).

    first_valid/last_valid are local dates of the first and last non-missing value;
    pct_present is measured from first_valid to the last requested hour. n_out_of_range counts
    values outside VALID_RANGE (e.g. cloud cover -1 or 101); they are left as downloaded.
    """
    variables = [c for c in df.columns if c not in ID_COLUMNS + GRID_COLUMNS]
    long = df.melt(id_vars=ID_COLUMNS, value_vars=variables, var_name="variable")
    rows = []
    for (plant, model, offset, variable), g in long.groupby(
        ["plant", "model", "offset_day", "variable"], sort=True
    ):
        present = g["value"].notna()
        lo, hi = VALID_RANGE.get(variable, (float("-inf"), float("inf")))
        out_of_range = int(((g["value"] < lo) | (g["value"] > hi)).sum())
        if present.any():
            first = g.loc[present, "valid_time"].min()
            last = g.loc[present, "valid_time"].max()
            after_first = g[g["valid_time"] >= first]
            pct = 100.0 * after_first["value"].notna().mean()
            first_s, last_s = f"{first:%Y-%m-%d}", f"{last:%Y-%m-%d}"
        else:
            first_s = last_s = None
            pct = 0.0
        rows.append(
            {
                "plant": plant,
                "model": model,
                "offset_day": offset,
                "variable": variable,
                "first_valid": first_s,
                "last_valid": last_s,
                "hours_requested": len(g),
                "hours_present": int(present.sum()),
                "pct_present_after_first": round(pct, 2),
                "n_out_of_range": out_of_range,
            }
        )
    return pd.DataFrame(rows)

"""Features for the cloud weather-only model: no plant power and no on-site sensor data.

The cloud job has no live PEA feed (final proposal §3.2), so its model may use only what it can
fetch or compute at issue time: archived/live NWP forecasts (runs chosen by decision 0004), sun
position, clear-sky GHI, calendar terms and fixed plant metadata. It is trained on PEA history
offline but must be evaluated under the same restriction.

`build_weather_features` takes a timestamp index, not the plant frame, so plant data cannot slip
in. `assert_weather_only` is an allowlist check to run on any feature list before training.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .issue_time import IssueScenario, calendar_features
from .nwp_features import clear_sky_features, nwp_slot_features
from .plants import Plant
from .pvlib_baseline import physical_power
from .solar_geometry import slot_geometry

PHYSICAL = "pv_physical_kw"  # uncalibrated pvlib power from the model-mean forecast
CALENDAR = ["interval_sin", "interval_cos", "doy_sin", "doy_cos", "month_sin", "month_cos", "dow"]
ASTRONOMY = ["cs_ghi", "sun_elevation"]


def build_weather_features(index, nwp: pd.DataFrame, scenario: IssueScenario, plant: Plant,
                           tilt: float | None = None) -> pd.DataFrame:
    """Weather-only features for each 15-min slot (naive Asia/Bangkok slot starts).

    `nwp`: one plant's Open-Meteo rows (solar.nwp_features.load_plant_nwp).
    """
    index = pd.DatetimeIndex(index)
    out = calendar_features(index)
    out = out.join(clear_sky_features(index, plant.lat, plant.lon))
    out["sun_elevation"] = slot_geometry(index, plant.lat, plant.lon)["elevation_mid"].to_numpy()
    out = out.join(nwp_slot_features(nwp, index, scenario, plant.lat, plant.lon))
    out["nwp_temp_mean"] = out.filter(regex=r"^nwp_temp_(?!mean)").mean(axis=1)
    out[PHYSICAL] = physical_power(index, out["nwp_ghi_mean"], out["nwp_temp_mean"],
                                   plant.lat, plant.lon, plant.capacity_kw, tilt)
    return out


def assert_weather_only(columns: Iterable[str]) -> None:
    """Raise ValueError if any column is not a known weather-only feature."""
    allowed = set(CALENDAR) | set(ASTRONOMY) | {PHYSICAL}
    bad = [c for c in columns if c not in allowed and not c.startswith("nwp_")]
    if bad:
        raise ValueError(f"not allowed in the weather-only model: {bad}")

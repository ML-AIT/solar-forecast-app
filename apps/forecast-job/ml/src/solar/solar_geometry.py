"""Sun position for 15-min slots: daylight scoring mask and night zeroing.

The final proposal (§2.4) defines "daytime" as solar elevation > 0, not a fixed 06:00-18:00
window. Sun position is pure astronomy, so it is known for any future slot (allowed at issue time).

Timestamps are local Asia/Bangkok (UTC+7) slot starts, as in the processed PEA data. The
interval-start convention is still to be verified against solar noon (AGENTS.md §3 rule 8).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TIMEZONE = "Asia/Bangkok"
SLOT = pd.Timedelta(minutes=15)


def _localize(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(index)
    return index.tz_localize(TIMEZONE) if index.tz is None else index


def apparent_elevation(times: pd.DatetimeIndex, lat: float, lon: float) -> np.ndarray:
    """Apparent solar elevation in degrees (refraction-corrected) at the given instants."""
    from pvlib.solarposition import get_solarposition

    position = get_solarposition(_localize(times), lat, lon, method="nrel_numpy")
    return position["apparent_elevation"].to_numpy()


def slot_geometry(index: pd.DatetimeIndex, lat: float, lon: float) -> pd.DataFrame:
    """Elevation at slot start, middle and end, plus the two masks used for scoring.

    `daylight`: elevation at the slot middle > 0 (proposal definition of daytime).
    `sun_down`: the sun is below the horizon for the whole slot, so PV power must be 0.
    """
    index = pd.DatetimeIndex(index)
    start = apparent_elevation(index, lat, lon)
    middle = apparent_elevation(index + SLOT / 2, lat, lon)
    end = apparent_elevation(index + SLOT, lat, lon)
    return pd.DataFrame(
        {
            "elevation_start": start,
            "elevation_mid": middle,
            "elevation_end": end,
            "daylight": middle > 0,
            "sun_down": (start <= 0) & (middle <= 0) & (end <= 0),
        },
        index=index,
    )


def zero_at_night(predictions, sun_down) -> np.ndarray:
    """Set predictions to 0 kW where the sun is down for the whole slot."""
    out = np.asarray(predictions, dtype=float).copy()
    out[np.asarray(sun_down, dtype=bool)] = 0.0
    return out

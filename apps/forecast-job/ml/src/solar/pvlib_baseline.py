"""Simplified, calibrated pvlib baseline: forecast weather -> plant AC power (kW).

Required baseline (final proposal §2.3) and the weather-only fallback for the cloud job. PEA gives
no panel geometry or inverter data, so decision 0002 fixes the assumptions and labels the result
"pvlib (simplified, calibrated)". It is not a physical model of any one plant.

Chain for each 15-min slot (sun position at the slot middle, Asia/Bangkok slot starts):
1. Forecast GHI -> DNI + DHI with the Erbs decomposition.
2. Transpose to the panel plane (Hay-Davies), fixed tilt ≈ latitude, facing south (azimuth 180).
3. Cell temperature: Faiman model with forecast 2 m air temperature and a fixed wind speed
   (the 15-min NWP features carry no wind). Missing temperature -> no temperature correction.
4. DC power: PVWatts, sized at nameplate, temperature coefficient GAMMA_PDC.
5. Calibration, fitted on training rows only: one scale factor (weighted median of P / step-4
   power, the MAE-optimal scale, so outage days barely move it) and an AC cap = highest
   training P (AGENTS.md §4: models learn the observed maximum).

Steps 1-4 learn nothing from data, so `physical_power` is also safe as an ML feature.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

import numpy as np
import pandas as pd

TIMEZONE = "Asia/Bangkok"
SLOT = pd.Timedelta(minutes=15)
LABEL = "pvlib (simplified, calibrated)"

# Assumptions (decision 0002). Typical crystalline-silicon values, not plant data.
GAMMA_PDC = -0.004  # 1/°C, PVWatts temperature coefficient
WIND_SPEED = 1.0  # m/s, fixed for the Faiman cell-temperature model
STC_CELL_TEMP = 25.0
# Calibration rows: enough physical output to give a stable ratio, and below the AC cap.
MIN_PHYSICAL_FRACTION = 0.05  # of nameplate
CLIPPED_FRACTION = 0.97  # of the highest training P


def physical_power(index, ghi, temp_air, lat: float, lon: float, capacity_kw: float,
                   tilt: float | None = None, azimuth: float = 180.0) -> np.ndarray:
    """Uncalibrated DC power (kW) from slot-mean GHI (W/m²) and air temperature (°C).

    `tilt=None` means tilt = |latitude|. NaN GHI gives NaN; the sun below the horizon gives 0.
    """
    from pvlib import irradiance, pvsystem, solarposition, temperature

    index = pd.DatetimeIndex(index)
    ghi = np.asarray(ghi, dtype=float)
    temp_air = np.asarray(temp_air, dtype=float)
    if not len(index) == len(ghi) == len(temp_air):
        raise ValueError("index, ghi and temp_air must have the same length")
    tilt = abs(lat) if tilt is None else float(tilt)

    middle = (index + SLOT / 2).tz_localize(TIMEZONE)
    sun = solarposition.get_solarposition(middle, lat, lon, method="nrel_numpy")
    zenith = sun["apparent_zenith"].to_numpy()
    ghi_safe = np.clip(np.nan_to_num(ghi), 0, None)
    parts = irradiance.erbs(ghi_safe, zenith, middle)
    poa = irradiance.get_total_irradiance(
        tilt, azimuth, zenith, sun["azimuth"].to_numpy(), np.asarray(parts["dni"]), ghi_safe,
        np.asarray(parts["dhi"]), dni_extra=np.asarray(irradiance.get_extra_radiation(middle)),
        model="haydavies")
    poa_global = np.nan_to_num(np.asarray(poa["poa_global"], dtype=float))
    poa_global = np.where(zenith >= 90, 0.0, np.clip(poa_global, 0, None))

    cell = np.asarray(temperature.faiman(poa_global, temp_air, WIND_SPEED), dtype=float)
    cell = np.where(np.isnan(cell), STC_CELL_TEMP, cell)
    dc = np.asarray(pvsystem.pvwatts_dc(poa_global, cell, capacity_kw, GAMMA_PDC), dtype=float)
    dc = np.clip(dc, 0, None)
    return np.where(np.isnan(ghi), np.nan, dc)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, 0.5 * cumulative[-1])])


def calibrate(physical, power, capacity_kw: float) -> tuple[float, float]:
    """(scale, AC cap) from uncalibrated `physical_power` and observed P on training rows.

    Scale = weighted median of P / physical on rows with enough physical output and below the
    cap; AC cap = highest observed P. NaN rows are skipped, so the cap comes only from rows
    that also have a forecast.
    """
    physical = np.asarray(physical, dtype=float)
    observed = np.asarray(power, dtype=float)
    finite = np.isfinite(physical) & np.isfinite(observed)
    if not finite.any():
        raise ValueError("no training rows with both forecast GHI and observed P")
    ac_limit = float(observed[finite].max())
    use = (finite & (physical > MIN_PHYSICAL_FRACTION * capacity_kw)
           & (observed < CLIPPED_FRACTION * ac_limit))
    if use.sum() < 10:
        raise ValueError("need at least 10 daylight training rows to calibrate the scale")
    ratio = np.clip(observed[use], 0, None) / physical[use]
    return _weighted_median(ratio, physical[use]), ac_limit


@dataclass(frozen=True)
class PvlibBaseline:
    """Fitted baseline. Save with `to_dict` (JSON) for the cloud job; load with `from_dict`."""

    lat: float
    lon: float
    capacity_kw: float
    tilt: float
    azimuth: float
    scale: float
    ac_limit_kw: float
    gamma_pdc: float = GAMMA_PDC
    wind_speed: float = WIND_SPEED

    @classmethod
    def fit(cls, index, ghi, temp_air, power, lat: float, lon: float, capacity_kw: float,
            tilt: float | None = None, azimuth: float = 180.0) -> PvlibBaseline:
        """Calibrate on training rows only. `power` = observed P (kW); NaN rows are skipped."""
        tilt = abs(lat) if tilt is None else float(tilt)
        physical = physical_power(index, ghi, temp_air, lat, lon, capacity_kw, tilt, azimuth)
        scale, ac_limit = calibrate(physical, power, capacity_kw)
        return cls(lat=float(lat), lon=float(lon), capacity_kw=float(capacity_kw), tilt=tilt,
                   azimuth=float(azimuth), scale=scale, ac_limit_kw=ac_limit)

    def predict(self, index, ghi, temp_air) -> np.ndarray:
        """AC power forecast (kW), clipped to [0, ac_limit_kw]. NaN where GHI is missing."""
        if self.gamma_pdc != GAMMA_PDC or self.wind_speed != WIND_SPEED:
            raise ValueError("saved baseline used other physics constants; refit it")
        physical = physical_power(index, ghi, temp_air, self.lat, self.lon, self.capacity_kw,
                                  self.tilt, self.azimuth)
        return np.clip(self.scale * physical, 0, self.ac_limit_kw)

    def to_dict(self) -> dict:
        return {"model": LABEL, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> PvlibBaseline:
        """Load a saved baseline. Other keys in the file (plant, train_end, ...) are ignored."""
        return cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})

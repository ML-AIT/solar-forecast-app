"""Forecast issue-time scenarios and the features that are allowed under each one.

An issue-time scenario says which plant observations exist when the day-D forecast is made.
The current S01 notebook assumes all of D-1 is known (issue at 23:55 D-1). PEA Grid Code 2569
needs the forecast by 12:00 D-1, so a compliant run can only use data up to the morning of D-1.
See docs/RESEARCH_NOTES.md §10.6.

Availability rule: a 15-min slot is available once it has ended, i.e. slot start + 15 min must
be at or before the scenario's data cutoff. "24:00" means the whole cutoff day is available.

Feature names stay the same in every scenario so models and baselines can be compared, but
their meaning follows the scenario: `P_lag1` is the same time slot on the most recent day that
is available for that slot. With a 10:00 D-1 cutoff, a 08:00 slot comes from D-1 and a 14:00
slot from D-2. With full-day cutoffs, `build_features` gives the same values as
`S01.data_quality.build_forecast_features`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

SLOT = pd.Timedelta(minutes=15)
FULL_DAY = pd.Timedelta(hours=24)
MORNING_START = pd.Timedelta(hours=6)
WEATHER_LAGS = {
    "irr_lag1": "irradiance",
    "pv_temp_lag1": "pv_temp",
    "amb_lag1": "AMBTEMP",
    "wind_lag1": "WINDSPEED",
}
POWER_HISTORY = ["P_lag1", "P_lag2", "P_lag7", "P_roll7", "energy_roll7_mean", "energy_roll7_std"]
MORNING_FEATURES = ["P_morning_mean", "P_morning_ratio", "irr_morning_mean"]


@dataclass(frozen=True)
class IssueScenario:
    """When the day-D forecast is issued, expressed as a data cutoff.

    cutoff_day:  latest day with plant data, counted back from D (1 = D-1, 2 = D-2).
    cutoff_time: "HH:MM" on that day; slots that end by then are available. "24:00" = whole day.
    """

    key: str
    label: str
    cutoff_day: int
    cutoff_time: str
    grid_code_compliant: bool
    morning_features: bool = False

    def __post_init__(self):
        if self.cutoff_day < 1:
            raise ValueError("cutoff_day must be 1 (D-1) or earlier")
        offset = self.cutoff_offset
        if offset <= pd.Timedelta(0) or offset > FULL_DAY or offset % SLOT:
            raise ValueError("cutoff_time must be a 15-min boundary in (00:00, 24:00]")
        if self.morning_features and offset <= MORNING_START:
            raise ValueError("morning features need a cutoff after 06:00")

    @property
    def cutoff_offset(self) -> pd.Timedelta:
        hours, minutes = (int(part) for part in self.cutoff_time.split(":"))
        return pd.Timedelta(hours=hours, minutes=minutes)

    @property
    def full_day(self) -> bool:
        return self.cutoff_offset == FULL_DAY

    @property
    def last_complete_day(self) -> int:
        """Days back from D to the latest day whose 96 slots are all available."""
        return self.cutoff_day + (0 if self.full_day else 1)

    def data_cutoff(self, target_day) -> pd.Timestamp:
        """Latest moment whose observations may be used for `target_day`."""
        day = pd.Timestamp(target_day).normalize()
        return day - pd.Timedelta(days=self.cutoff_day) + self.cutoff_offset

    def params(self) -> dict[str, str | int | bool]:
        """Scenario settings to log with an experiment run."""
        return {
            "issue_scenario": self.key,
            "issue_label": self.label,
            "data_cutoff": f"D-{self.cutoff_day} {self.cutoff_time}",
            "grid_code_compliant": self.grid_code_compliant,
            "morning_features": self.morning_features,
        }


# 23:55 D-1 is the current notebook setting: it uses all of D-1 but misses the Grid Code deadline.
D1_2355 = IssueScenario("d1_2355", "D-1 23:55 (current)", 1, "24:00", grid_code_compliant=False)
# Grid Code: data up to 10:00 D-1 (last slot 09:45), forecast sent well before 12:00 D-1.
D1_1000 = IssueScenario("d1_1000", "D-1 10:00", 1, "10:00", grid_code_compliant=True)
D1_1000_MORNING = IssueScenario(
    "d1_1000_morning", "D-1 10:00 + morning", 1, "10:00",
    grid_code_compliant=True, morning_features=True,
)
# Compliant with a 12 h margin: whole days only, latest is D-2.
D2_2355 = IssueScenario("d2_2355", "D-2 23:55", 2, "24:00", grid_code_compliant=True)
SCENARIOS = [D1_2355, D1_1000, D1_1000_MORNING, D2_2355]


def _slot_end_offset(index: pd.DatetimeIndex) -> pd.TimedeltaIndex:
    return (index - index.normalize()) + SLOT


def latest_day_offset(index: pd.DatetimeIndex, scenario: IssueScenario) -> np.ndarray:
    """For each target slot, days back to the latest day where that slot is available."""
    late = np.asarray(_slot_end_offset(index) > scenario.cutoff_offset)
    return scenario.cutoff_day + late.astype(int)


def _lookup(series: pd.Series, index: pd.DatetimeIndex, days_back: np.ndarray) -> pd.Series:
    source = index - pd.to_timedelta(days_back, unit="D")
    return pd.Series(series.reindex(source).to_numpy(), index=index)


def _mean_std_min_count(frame: pd.DataFrame, min_count: int = 3) -> tuple[pd.Series, pd.Series]:
    enough = frame.notna().sum(axis=1) >= min_count
    return (frame.mean(axis=1, skipna=True).where(enough),
            frame.std(axis=1, skipna=True).where(enough))


def daily_energy_kwh(power: pd.Series) -> pd.Series:
    """kWh per day for days with all 96 slots; other days stay missing."""
    power = power.replace([np.inf, -np.inf], np.nan)
    groups = power.groupby(power.index.normalize())
    return (groups.sum(min_count=96) * 0.25).where(groups.count().eq(96))


def _daily_to_rows(daily: pd.Series, index: pd.DatetimeIndex, days_back: int) -> pd.Series:
    source = index.normalize() - pd.Timedelta(days=days_back)
    return pd.Series(daily.reindex(source).to_numpy(), index=index)


def _morning_window_mean(series: pd.Series, cutoff: pd.Timedelta) -> pd.Series:
    """Daily mean over slots from 06:00 that end by `cutoff`; needs half the slots valid."""
    slot_start = series.index - series.index.normalize()
    in_window = (slot_start >= MORNING_START) & (slot_start + SLOT <= cutoff)
    window = series[in_window]
    n_slots = int((cutoff - MORNING_START) / SLOT)
    groups = window.groupby(window.index.normalize())
    return groups.mean().where(groups.count() >= max(1, n_slots // 2))


def calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Cyclic slot / day-of-year / month encodings and day of week (known for any future day)."""
    idx = pd.DatetimeIndex(index)
    out = pd.DataFrame(index=idx)
    slot = idx.hour * 4 + idx.minute // 15
    for prefix, value, period in [("interval", slot, 96), ("doy", idx.dayofyear, 365.25),
                                  ("month", idx.month, 12)]:
        out[prefix + "_sin"] = np.sin(2 * np.pi * value / period)
        out[prefix + "_cos"] = np.cos(2 * np.pi * value / period)
    out["dow"] = idx.dayofweek
    return out


def build_features(
    frame: pd.DataFrame,
    scenario: IssueScenario,
    *,
    nwp: pd.DataFrame | None = None,
    location: tuple[float, float] | None = None,
    clear_sky: bool = False,
) -> pd.DataFrame:
    """Target `P` plus features that are known at the scenario's data cutoff.

    `frame` is the cleaned 15-min series (P, irradiance, pv_temp, AMBTEMP, WINDSPEED) on a
    DatetimeIndex. Missing days may be absent or NaN; lags to them become NaN.

    Optional (both need `location=(lat, lon)`):
    - `nwp`: one plant's Open-Meteo rows (solar.nwp_features.load_plant_nwp); adds weather-forecast
      features from runs published by the issue time (decision 0004).
    - `clear_sky=True`: adds slot-mean clear-sky GHI `cs_ghi` (astronomy only).
    """
    if (nwp is not None or clear_sky) and location is None:
        raise ValueError("NWP and clear-sky features need location=(lat, lon)")
    df = frame.sort_index()
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.has_duplicates:
        raise ValueError("Feature timestamps must be a unique DatetimeIndex")
    idx = df.index
    base = latest_day_offset(idx, scenario)

    out = df[["P"]].copy()
    lags = {k: _lookup(df["P"], idx, base + k - 1) for k in range(1, 8)}
    for k in (1, 2, 7):
        out[f"P_lag{k}"] = lags[k]
    out["P_roll7"], _ = _mean_std_min_count(pd.concat(lags.values(), axis=1))
    for name, column in WEATHER_LAGS.items():
        out[name] = _lookup(df[column], idx, base)

    out = out.join(calendar_features(idx))

    energy = daily_energy_kwh(df["P"])
    first = scenario.last_complete_day
    history = pd.concat([_daily_to_rows(energy, idx, first + d) for d in range(7)], axis=1)
    out["energy_roll7_mean"], out["energy_roll7_std"] = _mean_std_min_count(history)

    if scenario.morning_features:
        cutoff = scenario.cutoff_offset
        p_morning = _morning_window_mean(df["P"], cutoff)
        days = p_morning.index
        past = pd.concat([p_morning.reindex(days - pd.Timedelta(days=d)).set_axis(days)
                          for d in range(1, 8)], axis=1)
        past_mean, _ = _mean_std_min_count(past)
        # Today's morning vs the past week's mornings: a rough "sky today" signal.
        ratio = (p_morning / past_mean.where(past_mean > 1.0)).clip(0, 3)
        out["P_morning_mean"] = _daily_to_rows(p_morning, idx, scenario.cutoff_day)
        out["P_morning_ratio"] = _daily_to_rows(ratio, idx, scenario.cutoff_day)
        irr_morning = _morning_window_mean(df["irradiance"], cutoff)
        out["irr_morning_mean"] = _daily_to_rows(irr_morning, idx, scenario.cutoff_day)

    if nwp is not None or clear_sky:
        from .nwp_features import clear_sky_features, nwp_slot_features

        lat, lon = location
        if clear_sky:
            out = out.join(clear_sky_features(idx, lat, lon))
        if nwp is not None:
            out = out.join(nwp_slot_features(nwp, idx, scenario, lat, lon))
    return out


def check_no_future_data(
    frame: pd.DataFrame,
    scenario: IssueScenario,
    target_days: Iterable,
    *,
    window_days: int = 21,
    builder=None,
) -> pd.DataFrame:
    """Leakage test: scramble every observation after the cutoff and confirm features stay put.

    For each target day D, all slots that end after `scenario.data_cutoff(D)` are replaced with
    different values. Every feature for day D must be unchanged; only the target `P` may change.
    `builder(frame)` defaults to `build_features(frame, scenario)`.
    Returns one row per day and raises AssertionError if any feature moved.
    """
    if builder is None:
        def builder(data):
            return build_features(data, scenario)
    numeric = frame.select_dtypes("number").columns
    rows = []
    for day in pd.DatetimeIndex(pd.to_datetime(list(target_days))).normalize():
        start, end = day - pd.Timedelta(days=window_days), day + pd.Timedelta(days=1)
        window = frame.loc[(frame.index >= start) & (frame.index < end)]
        if window.empty:
            continue
        scrambled = window.copy()
        after = (scrambled.index + SLOT) > scenario.data_cutoff(day)
        # Change values and also fill gaps, so leaks through "is the data there?" are caught too.
        scrambled.loc[after, numeric] = scrambled.loc[after, numeric].fillna(0.0) * -3.0 + 777.0
        on_day = window.index.normalize() == day
        clean = builder(window).loc[on_day].drop(columns="P")
        dirty = builder(scrambled).loc[on_day].drop(columns="P")
        changed = [c for c in clean if not np.allclose(clean[c], dirty[c], equal_nan=True)]
        rows.append({"target_day": day.date(), "data_cutoff": scenario.data_cutoff(day),
                     "scrambled_slots": int(after.sum()), "features_changed": ", ".join(changed),
                     "pass": not changed})
    report = pd.DataFrame(rows)
    failed = [f"{r['target_day']}: {r['features_changed']}" for r in rows if not r["pass"]]
    assert not failed, f"{scenario.key}: features use data after the cutoff: " + "; ".join(failed)
    return report


def common_rows(feature_frames: Mapping[str, pd.DataFrame], required: Iterable[str]) -> pd.Index:
    """Timestamps where every scenario has all `required` columns, so scores are comparable."""
    required = list(required)
    common = None
    for frame in feature_frames.values():
        valid = frame.dropna(subset=[c for c in required if c in frame]).index
        common = valid if common is None else common.intersection(valid)
    return common.sort_values()

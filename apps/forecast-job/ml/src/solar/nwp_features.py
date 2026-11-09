"""15-min weather-forecast (NWP) features for day D, using only model runs published by issue time.

Input: the hourly Open-Meteo Previous Runs table (ml/scripts/download_open_meteo.py) for one
plant. Output: one row per 15-min slot (naive Asia/Bangkok slot starts, like the PEA data).

Which run a value comes from (Open-Meteo docs + blog, see decision 0004):
`<var>_previous_dayN` at valid time t is taken from the latest run whose lead time is at least
N x 24 h. Global models start a run every 6 h (00/06/12/18 UTC), so the run started at
floor_6h(t - N x 24 h) UTC. That run may be used only if run start + publication delay is at or
before the issue time. Delays are Open-Meteo availability times measured on 2026-10-27 plus a
safety margin (PUBLICATION_DELAY). For each slot the smallest allowed N is used.

Hourly -> 15 min (RESEARCH_NOTES §8):
- Radiation is the mean over the hour ending at the stamp. It is turned into a clear-sky index
  k = GHI / clear-sky GHI (both hourly means), k is interpolated linearly between hour centres,
  and multiplied by the slot's clear-sky GHI. At low sun (clear-sky hourly GHI below
  MIN_CLEAR_SKY_GHI) GHI itself is interpolated instead.
- Instantaneous variables (temperature, cloud cover) are interpolated between stamps.
Each slot uses two hourly stamps; the later one decides which run, so a slot never mixes in a
value from a run that was not yet published.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .issue_time import IssueScenario

TIMEZONE = "Asia/Bangkok"
SLOT = pd.Timedelta(minutes=15)
HOUR = pd.Timedelta(hours=1)
RUN_INTERVAL = pd.Timedelta(hours=6)
OFFSETS = (1, 2, 3)

# Run start -> usable on Open-Meteo. Measured 2026-10-27 from the metadata API
# (https://api.open-meteo.com/data/<model>/static/meta.json, last_run_availability_time):
# ECMWF IFS 0.25 7.6 h, GFS 0.25 7.1 h, ICON 3.6 h. Historical 2024-25 delays are not
# published, so a margin of about 2.5 h is added. See decision 0004.
PUBLICATION_DELAY = {
    "ecmwf_ifs025": pd.Timedelta(hours=10),
    "gfs_seamless": pd.Timedelta(hours=10),
    "icon_global": pd.Timedelta(hours=6),
}
SHORT_NAME = {"ecmwf_ifs025": "ecmwf", "gfs_seamless": "gfs", "icon_global": "icon"}
CLEAR_SKY_STEP = pd.Timedelta(minutes=5)  # averaging step for slot/hour clear-sky means
MIN_CLEAR_SKY_GHI = 20.0  # W/m2; below this the clear-sky index is too noisy
MAX_CLEAR_SKY_INDEX = 1.5


# ---------------------------------------------------------------- timing ---------------------
def issue_time(target_day, scenario: IssueScenario) -> pd.Timestamp:
    """Moment the day-D forecast is made (naive Bangkok time). "24:00" scenarios issue at 23:55."""
    cutoff = scenario.data_cutoff(target_day)
    return cutoff - pd.Timedelta(minutes=5) if scenario.full_day else cutoff


def run_start(valid_time: pd.DatetimeIndex, offset_day: int) -> pd.DatetimeIndex:
    """Start of the run behind `<var>_previous_day<offset_day>` at each valid time (naive local)."""
    utc = pd.DatetimeIndex(valid_time).tz_localize(TIMEZONE).tz_convert("UTC")
    start = (utc - pd.Timedelta(days=offset_day)).floor(RUN_INTERVAL)
    return start.tz_convert(TIMEZONE).tz_localize(None)


def latest_stamp(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Latest hourly stamp a 15-min slot's interpolated values depend on."""
    middle = pd.DatetimeIndex(index) + SLOT / 2
    return (middle + HOUR / 2).floor(HOUR) + HOUR


def allowed_offset(index: pd.DatetimeIndex, scenario: IssueScenario, model: str) -> np.ndarray:
    """Smallest offset_day whose run was published by the issue time, per slot (NaN if none)."""
    index = pd.DatetimeIndex(index)
    issue = pd.DatetimeIndex([issue_time(d, scenario) for d in index.normalize()])
    stamp = latest_stamp(index)
    out = np.full(len(index), np.nan)
    for offset in sorted(OFFSETS, reverse=True):
        ok = (run_start(stamp, offset) + PUBLICATION_DELAY[model]) <= issue
        out[np.asarray(ok)] = offset
    return out


def offset_table(scenarios: Iterable[IssueScenario], models: Iterable[str] = tuple(SHORT_NAME),
                 day: str = "2024-06-15") -> pd.DataFrame:
    """Allowed offset per scenario, model and hour of day D (for the decision record)."""
    slots = pd.date_range(day, periods=96, freq=SLOT)
    rows = []
    for scenario in scenarios:
        for model in models:
            offsets = pd.Series(allowed_offset(slots, scenario, model), index=slots)
            rows.append(offsets.groupby(offsets.index.hour).max().rename(
                (scenario.key, SHORT_NAME[model])))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- physics --------------------
def clear_sky_ghi(times: pd.DatetimeIndex, lat: float, lon: float) -> pd.Series:
    """Ineichen clear-sky GHI (W/m2) at naive Bangkok instants."""
    from pvlib.location import Location

    local = pd.DatetimeIndex(times).tz_localize(TIMEZONE)
    cs = Location(lat, lon, tz=TIMEZONE).get_clearsky(local, model="ineichen")
    return pd.Series(cs["ghi"].to_numpy(), index=pd.DatetimeIndex(times))


def _period_mean_clear_sky(starts: pd.DatetimeIndex, length: pd.Timedelta, lat: float,
                           lon: float, step: pd.Timedelta = CLEAR_SKY_STEP) -> np.ndarray:
    """Mean clear-sky GHI over [start, start + length) for each start (5-min midpoint rule)."""
    n = int(length / step)
    shifts = pd.to_timedelta(np.arange(n) * step + step / 2).to_numpy()
    grid = pd.DatetimeIndex(starts).to_numpy()[:, None] + shifts[None, :]
    cs = clear_sky_ghi(pd.DatetimeIndex(grid.ravel()), lat, lon).to_numpy()
    return cs.reshape(len(starts), n).mean(axis=1)


def clear_sky_features(index: pd.DatetimeIndex, lat: float, lon: float) -> pd.DataFrame:
    """Slot-mean clear-sky GHI: pure astronomy, allowed at any issue time (E3 '+clear-sky')."""
    index = pd.DatetimeIndex(index)
    return pd.DataFrame({"cs_ghi": _period_mean_clear_sky(index, SLOT, lat, lon)}, index=index)


# ---------------------------------------------------------------- hourly -> 15 min -----------
def _two_point(hourly: pd.Series, knots_a: pd.DatetimeIndex, weight: np.ndarray) -> np.ndarray:
    va = hourly.reindex(knots_a).to_numpy(dtype=float)
    vb = hourly.reindex(knots_a + HOUR).to_numpy(dtype=float)
    return (1 - weight) * va + weight * vb


def hourly_to_slots(hourly: pd.DataFrame, index: pd.DatetimeIndex, lat: float, lon: float,
                    cs_slot: np.ndarray | None = None) -> pd.DataFrame:
    """One model and one offset: hourly frame (naive local stamps) -> 15-min slot values.

    Returns columns ghi, k (clear-sky index), temp, cloud.
    """
    index = pd.DatetimeIndex(index)
    hourly = hourly.sort_index()
    if len(index):  # only the stamps these slots can touch (clear-sky means are the slow part)
        hourly = hourly.loc[index.min() - 2 * HOUR: index.max() + 2 * HOUR]
    middle = index + SLOT / 2
    if cs_slot is None:
        cs_slot = clear_sky_features(index, lat, lon)["cs_ghi"].to_numpy()

    # Radiation: values are hour means, centred 30 min before the stamp.
    rad_a = (middle + HOUR / 2).floor(HOUR)
    rad_w = np.asarray((middle - (rad_a - HOUR / 2)) / HOUR, dtype=float)
    ghi_h = hourly["shortwave_radiation"]
    cs_h = pd.Series(_period_mean_clear_sky(ghi_h.index - HOUR, HOUR, lat, lon), index=ghi_h.index)
    k_h = (ghi_h / cs_h.where(cs_h >= MIN_CLEAR_SKY_GHI)).clip(0, MAX_CLEAR_SKY_INDEX)
    k = _two_point(k_h, rad_a, rad_w)
    ghi_lin = _two_point(ghi_h, rad_a, rad_w)
    ghi = np.clip(np.where(np.isnan(k), ghi_lin, k * cs_slot), 0, None)
    ghi = np.where(cs_slot <= 0, 0.0, ghi)  # sun down for the whole slot: no radiation

    # Instantaneous variables: values at the stamp.
    ins_a = middle.floor(HOUR)
    ins_w = np.asarray((middle - ins_a) / HOUR, dtype=float)
    out = pd.DataFrame({"ghi": ghi, "k": k}, index=index)
    out["temp"] = _two_point(hourly["temperature_2m"], ins_a, ins_w)
    out["cloud"] = np.clip(_two_point(hourly["cloud_cover"], ins_a, ins_w), 0, 100)
    return out


def load_plant_nwp(nwp: pd.DataFrame, plant: str) -> pd.DataFrame:
    """Rows of the downloaded table for one plant, with naive Bangkok `valid_time`."""
    rows = nwp[nwp["plant"] == plant].copy()
    times = pd.to_datetime(rows["valid_time"])
    if getattr(times.dt, "tz", None) is not None:
        times = times.dt.tz_convert(TIMEZONE).dt.tz_localize(None)
    rows["valid_time"] = times
    return rows


def nwp_slot_features(nwp: pd.DataFrame, index: pd.DatetimeIndex, scenario: IssueScenario,
                      lat: float, lon: float) -> pd.DataFrame:
    """NWP features for each slot, from the freshest run published by the issue time.

    `nwp`: one plant's rows (load_plant_nwp). Per model: nwp_ghi_*, nwp_k_*, nwp_temp_*,
    nwp_cloud_*; across models: nwp_ghi_mean, nwp_ghi_std (needs 2 models), nwp_cloud_mean.

    If the freshest allowed offset is missing for a slot (archive gap, or ECMWF radiation before
    2024-03-07), the next older offset is used; older runs were published earlier, so this stays
    leak-safe. nwp_k_* is NaN at night and low sun (clear-sky GHI < MIN_CLEAR_SKY_GHI): impute or
    mask it for models that cannot handle NaN.
    """
    index = pd.DatetimeIndex(index)
    cs_slot = clear_sky_features(index, lat, lon)["cs_ghi"].to_numpy()
    out = pd.DataFrame(index=index)
    columns = ["ghi", "temp", "cloud"]  # k is legitimately NaN at low sun; not a reason to fall back
    for model, short in SHORT_NAME.items():
        rows = nwp[nwp["model"] == model]
        offsets = allowed_offset(index, scenario, model)
        chosen = pd.DataFrame(np.nan, index=index, columns=["ghi", "k", "temp", "cloud"])
        for offset in OFFSETS:
            use = (offsets <= offset) & chosen[columns].isna().any(axis=1).to_numpy()
            hourly = rows[rows["offset_day"] == offset].set_index("valid_time")
            if not use.any() or hourly.empty:
                continue
            slots = hourly_to_slots(hourly, index[use], lat, lon, cs_slot[use])
            chosen.loc[index[use]] = chosen.loc[index[use]].fillna(slots)
        for column in chosen:
            out[f"nwp_{column}_{short}"] = chosen[column]
    ghi = out[[f"nwp_ghi_{s}" for s in SHORT_NAME.values()]]
    out["nwp_ghi_mean"] = ghi.mean(axis=1)
    out["nwp_ghi_std"] = ghi.std(axis=1).where(ghi.notna().sum(axis=1) >= 2)
    out["nwp_cloud_mean"] = out[[f"nwp_cloud_{s}" for s in SHORT_NAME.values()]].mean(axis=1)
    return out


# ---------------------------------------------------------------- leakage test ---------------
def check_nwp_no_future_runs(nwp: pd.DataFrame, scenario: IssueScenario, target_days: Iterable,
                             lat: float, lon: float, builder=None) -> pd.DataFrame:
    """Scramble every forecast value from a run not published by the issue time of day D and
    confirm day D's NWP features do not change. Raises AssertionError on any leak.

    `builder(nwp, slots)` returns the features to check; default `nwp_slot_features`. Pass a
    wider builder (e.g. solar.weather_only) to check everything derived from the forecasts.

    This proves the code obeys the timing rule (run_start + PUBLICATION_DELAY). It cannot prove
    the rule's inputs: Open-Meteo's lead-time semantics and the historical delays (decision 0004).
    """
    if builder is None:
        def builder(data, slots):
            return nwp_slot_features(data, slots, scenario, lat, lon)
    unknown = set(nwp["model"]) - set(PUBLICATION_DELAY)
    if unknown:
        raise KeyError(f"no publication delay for models {sorted(unknown)}")
    starts = pd.Series(pd.NaT, index=nwp.index, dtype="datetime64[ns]")
    for offset in OFFSETS:
        sel = nwp["offset_day"] == offset
        starts[sel] = run_start(pd.DatetimeIndex(nwp.loc[sel, "valid_time"]), offset)
    delay = nwp["model"].map(PUBLICATION_DELAY)
    published = starts + delay
    value_cols = [c for c in nwp.select_dtypes("number").columns
                  if c not in ("offset_day", "grid_lat", "grid_lon", "grid_elevation")]
    rows = []
    for day in pd.DatetimeIndex(pd.to_datetime(list(target_days))).normalize():
        slots = pd.date_range(day, periods=96, freq=SLOT)
        late = (published > issue_time(day, scenario)).to_numpy()
        scrambled = nwp.copy()
        scrambled.loc[late, value_cols] = scrambled.loc[late, value_cols].fillna(0.0) * -3 + 777
        clean = builder(nwp, slots)
        dirty = builder(scrambled, slots)
        changed = [c for c in clean if not np.allclose(clean[c], dirty[c], equal_nan=True)]
        rows.append({"target_day": day.date(), "issue_time": issue_time(day, scenario),
                     "late_values": int(late.sum()), "features_changed": ", ".join(changed),
                     "pass": not changed})
    report = pd.DataFrame(rows)
    failed = [f"{r['target_day']}: {r['features_changed']}" for r in rows if not r["pass"]]
    assert not failed, f"{scenario.key}: NWP features use unpublished runs: " + "; ".join(failed)
    return report

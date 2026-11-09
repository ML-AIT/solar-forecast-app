"""Tests for solar.nwp_features: run timing, hourly -> 15-min conversion, leakage check.

Synthetic forecasts only (no network, no PEA data).
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pvlib")

import solar.nwp_features as nf
from solar.issue_time import D1_1000, D1_2355, D2_2355, build_features

LAT, LON = 13.867, 102.6434


def _synthetic_nwp(start="2024-06-08", end="2024-06-20", seed=0) -> pd.DataFrame:
    """Hourly rows for all models and offsets; values differ per offset so mix-ups show."""
    rng = np.random.default_rng(seed)
    stamps = pd.date_range(start, end, freq="h")
    cs = nf._period_mean_clear_sky(stamps - nf.HOUR, nf.HOUR, LAT, LON)
    frames = []
    for model in nf.SHORT_NAME:
        for offset in nf.OFFSETS:
            frames.append(pd.DataFrame({
                "plant": "S01", "model": model, "offset_day": offset, "valid_time": stamps,
                "shortwave_radiation": cs * rng.uniform(0.3, 1.0, len(stamps)),
                "temperature_2m": 28 + 4 * np.sin(np.arange(len(stamps)) / 4) + offset,
                "cloud_cover": rng.uniform(0, 100, len(stamps)),
            }))
    return pd.concat(frames, ignore_index=True)


def test_run_start_floors_to_six_hourly_utc_run():
    valid = pd.DatetimeIndex(["2024-06-15 18:00"])  # 11 UTC
    assert nf.run_start(valid, 1)[0] == pd.Timestamp("2024-06-14 13:00")  # 06 UTC D-1
    assert nf.run_start(valid, 2)[0] == pd.Timestamp("2024-06-13 13:00")


def test_allowed_offset_at_2355_switches_after_late_afternoon():
    slots = pd.DatetimeIndex(["2024-06-15 12:00", "2024-06-15 16:45", "2024-06-15 17:30"])
    np.testing.assert_array_equal(nf.allowed_offset(slots, D1_2355, "ecmwf_ifs025"), [1, 1, 2])


def test_allowed_offset_never_uses_a_run_published_after_issue():
    slots = pd.date_range("2024-06-15", periods=96, freq="15min")
    for scenario in (D1_2355, D1_1000, D2_2355):
        for model, delay in nf.PUBLICATION_DELAY.items():
            offsets = nf.allowed_offset(slots, scenario, model)
            assert not np.isnan(offsets).any()
            for slot, offset in zip(slots, offsets, strict=True):
                stamp = nf.latest_stamp(pd.DatetimeIndex([slot]))
                published = nf.run_start(stamp, int(offset))[0] + delay
                assert published <= nf.issue_time(slot.normalize(), scenario)
                if offset > 1:  # and the next-fresher run was really not available
                    fresher = nf.run_start(stamp, int(offset) - 1)[0] + delay
                    assert fresher > nf.issue_time(slot.normalize(), scenario)


def test_hourly_to_slots_keeps_a_constant_clear_sky_index():
    stamps = pd.date_range("2024-06-14", "2024-06-16", freq="h")
    cs_h = nf._period_mean_clear_sky(stamps - nf.HOUR, nf.HOUR, LAT, LON)
    hourly = pd.DataFrame({"shortwave_radiation": 0.8 * cs_h, "temperature_2m": 30.0,
                           "cloud_cover": 50.0}, index=stamps)
    slots = pd.date_range("2024-06-15", periods=96, freq="15min")
    out = nf.hourly_to_slots(hourly, slots, LAT, LON)
    cs_slot = nf.clear_sky_features(slots, LAT, LON)["cs_ghi"]
    day = cs_slot > 100
    np.testing.assert_allclose(out.loc[day, "k"], 0.8, atol=1e-6)
    np.testing.assert_allclose(out.loc[day, "ghi"], 0.8 * cs_slot[day], rtol=1e-6)
    assert (out.loc[cs_slot <= 0, "ghi"] == 0).all()


def test_hourly_to_slots_interpolates_instantaneous_values_between_stamps():
    stamps = pd.date_range("2024-06-15 08:00", periods=4, freq="h")
    hourly = pd.DataFrame({"shortwave_radiation": 300.0, "temperature_2m": [28.0, 32.0, 32.0, 32.0],
                           "cloud_cover": 0.0}, index=stamps)
    out = nf.hourly_to_slots(hourly, pd.DatetimeIndex(["2024-06-15 08:00"]), LAT, LON)
    assert out["temp"].iloc[0] == pytest.approx(28 + 4 * 0.125)  # slot middle 08:07:30


@pytest.mark.parametrize("scenario", [D1_2355, D1_1000, D2_2355])
def test_nwp_features_pass_the_unpublished_run_check(scenario):
    nwp = _synthetic_nwp()
    report = nf.check_nwp_no_future_runs(nwp, scenario, ["2024-06-15", "2024-06-16"], LAT, LON)
    assert report["pass"].all() and (report["late_values"] > 0).all()


def test_unpublished_run_check_catches_a_leak(monkeypatch):
    nwp = _synthetic_nwp()
    monkeypatch.setattr(nf, "allowed_offset", lambda index, scenario, model: np.ones(len(index)))
    with pytest.raises(AssertionError, match="unpublished"):
        nf.check_nwp_no_future_runs(nwp, D1_2355, ["2024-06-15"], LAT, LON)


def test_build_features_adds_nwp_and_clear_sky_columns():
    idx = pd.date_range("2024-06-10", "2024-06-17", freq="15min", inclusive="left")
    frame = pd.DataFrame({"P": 1.0, "irradiance": 1.0, "pv_temp": 1.0, "AMBTEMP": 1.0,
                          "WINDSPEED": 1.0}, index=idx)
    out = build_features(frame, D1_2355, nwp=_synthetic_nwp(), location=(LAT, LON),
                         clear_sky=True)
    assert {"nwp_ghi_ecmwf", "nwp_k_icon", "nwp_ghi_std", "cs_ghi"} <= set(out.columns)
    assert out.loc["2024-06-15 12:00", "nwp_ghi_mean"] > 0
    with pytest.raises(ValueError, match="location"):
        build_features(frame, D1_2355, nwp=_synthetic_nwp())


def test_late_evening_slots_depend_on_the_next_day():
    slots = pd.DatetimeIndex(["2024-06-15 23:15", "2024-06-15 23:30", "2024-06-15 23:45"])
    assert list(nf.latest_stamp(slots)) == [pd.Timestamp("2024-06-16 00:00"),
                                            pd.Timestamp("2024-06-16 01:00"),
                                            pd.Timestamp("2024-06-16 01:00")]
    np.testing.assert_array_equal(nf.allowed_offset(slots, D1_1000, "ecmwf_ifs025"), [2, 3, 3])


@pytest.mark.parametrize("too_early", [
    lambda index: (pd.DatetimeIndex(index) + nf.SLOT / 2 + nf.HOUR / 2).floor(nf.HOUR),
    lambda index: pd.DatetimeIndex(index).floor(nf.HOUR) + nf.HOUR,
])
def test_unpublished_run_check_catches_a_wrong_latest_stamp(monkeypatch, too_early):
    nwp = _synthetic_nwp()
    monkeypatch.setattr(nf, "latest_stamp", too_early)
    with pytest.raises(AssertionError, match="unpublished"):
        nf.check_nwp_no_future_runs(nwp, D1_2355, ["2024-06-15"], LAT, LON)


def test_missing_freshest_offset_falls_back_to_an_older_one():
    nwp = _synthetic_nwp()
    gap = (nwp["model"] == "icon_global") & (nwp["offset_day"] == 1)
    nwp.loc[gap, ["shortwave_radiation", "temperature_2m", "cloud_cover"]] = np.nan
    slots = pd.date_range("2024-06-15", periods=96, freq="15min")
    out = nf.nwp_slot_features(nwp, slots, D1_2355, LAT, LON)
    assert out["nwp_temp_icon"].notna().all()
    only_day2 = nwp[(nwp["model"] == "icon_global") & (nwp["offset_day"] == 2)]
    expected = nf.hourly_to_slots(only_day2.set_index("valid_time"), slots, LAT, LON)["temp"]
    np.testing.assert_allclose(out["nwp_temp_icon"], expected)
    nf.check_nwp_no_future_runs(nwp, D1_2355, ["2024-06-15"], LAT, LON)


def test_unpublished_run_check_rejects_unknown_models():
    nwp = _synthetic_nwp()
    nwp.loc[nwp.index[:5], "model"] = "best_match"
    with pytest.raises(KeyError):
        nf.check_nwp_no_future_runs(nwp, D1_2355, ["2024-06-15"], LAT, LON)

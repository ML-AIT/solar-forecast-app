"""Tests for solar.issue_time on synthetic data (no PEA data)."""

import numpy as np
import pandas as pd
import pytest

from S01.data_quality import build_forecast_features
from solar import issue_time as it

N_DAYS = 30


@pytest.fixture
def frame():
    """30 days of 15-min data where each value encodes its own timestamp.

    P = day_number * 1000 + slot, so a lookup tells us exactly which day/slot it came from.
    """
    index = pd.date_range("2024-01-01", periods=N_DAYS * 96, freq="15min")
    day = np.asarray((index.normalize() - index[0]).days)
    slot = np.asarray(index.hour * 4 + index.minute // 15)
    code = day * 1000.0 + slot
    return pd.DataFrame(
        {"P": code, "irradiance": code + 0.1, "pv_temp": code + 0.2,
         "AMBTEMP": code + 0.3, "WINDSPEED": code + 0.4},
        index=index,
    )


def code(day, hour, minute=0):
    return day * 1000.0 + hour * 4 + minute // 15


def at(features, day, hour, minute=0):
    return features.loc[pd.Timestamp("2024-01-01") + pd.Timedelta(days=day, hours=hour,
                                                                   minutes=minute)]


def test_current_scenario_matches_existing_s01_features(frame):
    expected = build_forecast_features(frame)
    actual = it.build_features(frame, it.D1_2355)
    pd.testing.assert_frame_equal(actual, expected, check_freq=False)


def test_full_day_cutoff_keeps_existing_values_with_gaps(frame):
    gappy = frame.drop(frame.index[frame.index.normalize() == "2024-01-10"])
    gappy.loc["2024-01-12 10:00", "P"] = np.nan
    expected = build_forecast_features(gappy)
    actual = it.build_features(gappy, it.D1_2355)
    pd.testing.assert_frame_equal(actual, expected, check_freq=False)


def test_ten_oclock_cutoff_uses_d1_morning_and_d2_afternoon(frame):
    feats = it.build_features(frame, it.D1_1000)
    day = 20
    # 09:45 slot ends at 10:00 -> still from D-1; 10:00 slot ends 10:15 -> from D-2.
    assert at(feats, day, 9, 45)["P_lag1"] == code(day - 1, 9, 45)
    assert at(feats, day, 10, 0)["P_lag1"] == code(day - 2, 10, 0)
    assert at(feats, day, 14)["P_lag1"] == code(day - 2, 14)
    assert at(feats, day, 14)["P_lag2"] == code(day - 3, 14)
    assert at(feats, day, 14)["P_lag7"] == code(day - 8, 14)
    assert at(feats, day, 8)["P_lag7"] == code(day - 7, 8)
    assert at(feats, day, 14)["irr_lag1"] == code(day - 2, 14) + 0.1


def test_ten_oclock_cutoff_daily_energy_starts_at_d2(frame):
    feats = it.build_features(frame, it.D1_1000)
    energy = it.daily_energy_kwh(frame["P"])
    days = pd.Timestamp("2024-01-21") - pd.to_timedelta(range(2, 9), unit="D")
    assert at(feats, 20, 12)["energy_roll7_mean"] == pytest.approx(energy.loc[days].mean())


def test_d2_scenario_uses_whole_days_from_d2(frame):
    feats = it.build_features(frame, it.D2_2355)
    assert at(feats, 20, 8)["P_lag1"] == code(18, 8)
    assert at(feats, 20, 23, 45)["P_lag1"] == code(18, 23, 45)
    assert at(feats, 20, 8)["P_lag7"] == code(12, 8)


def test_morning_features_come_from_d1_before_cutoff(frame):
    feats = it.build_features(frame, it.D1_1000_MORNING)
    morning_slots = [code(19, 6, 0) + k for k in range(16)]  # 06:00 ... 09:45 on D-1
    day20 = feats.loc[feats.index.normalize() == "2024-01-21"]
    assert day20["P_morning_mean"].nunique() == 1
    assert day20["P_morning_mean"].iloc[0] == pytest.approx(np.mean(morning_slots))
    assert set(it.MORNING_FEATURES) <= set(feats)
    assert not set(it.MORNING_FEATURES) & set(it.build_features(frame, it.D1_1000))


@pytest.mark.parametrize("scenario", it.SCENARIOS, ids=lambda s: s.key)
def test_no_feature_uses_data_after_the_cutoff(frame, scenario):
    days = pd.date_range("2024-01-15", periods=5, freq="D")
    report = it.check_no_future_data(frame, scenario, days)
    assert report["pass"].all() and len(report) == 5
    assert (report["scrambled_slots"] > 0).all()


def test_leakage_check_catches_full_d1_features_under_a_morning_cutoff(frame):
    with pytest.raises(AssertionError, match="P_lag1"):
        it.check_no_future_data(frame, it.D1_1000, ["2024-01-20"],
                                builder=build_forecast_features)


def test_data_cutoff_timestamps():
    day = "2024-05-10"
    assert it.D1_2355.data_cutoff(day) == pd.Timestamp("2024-05-10 00:00")
    assert it.D1_1000.data_cutoff(day) == pd.Timestamp("2024-05-09 10:00")
    assert it.D2_2355.data_cutoff(day) == pd.Timestamp("2024-05-09 00:00")


@pytest.mark.parametrize("kwargs", [
    {"cutoff_day": 0, "cutoff_time": "10:00"},
    {"cutoff_day": 1, "cutoff_time": "10:05"},
    {"cutoff_day": 1, "cutoff_time": "24:15"},
    {"cutoff_day": 1, "cutoff_time": "05:00", "morning_features": True},
])
def test_invalid_scenarios_are_rejected(kwargs):
    with pytest.raises(ValueError):
        it.IssueScenario("x", "x", grid_code_compliant=True, **kwargs)


def test_only_current_scenario_is_not_grid_code_compliant():
    assert [s.key for s in it.SCENARIOS if not s.grid_code_compliant] == ["d1_2355"]


def test_common_rows_is_the_intersection_of_valid_rows(frame):
    a = frame.assign(x=1.0)
    b = frame.assign(x=1.0)
    b.iloc[:96, b.columns.get_loc("x")] = np.nan
    rows = it.common_rows({"a": a, "b": b}, ["x", "P", "missing_column"])
    assert len(rows) == len(frame) - 96
    assert rows[0] == frame.index[96]


def test_leakage_check_catches_features_that_only_count_missing_data(frame):
    gappy = frame.copy()
    gappy.loc["2024-01-19 14:00":"2024-01-19 15:00", "P"] = np.nan  # D-1 afternoon gap

    def builder(data):
        out = it.build_features(data, it.D1_1000)
        valid_d1 = data["P"].notna().groupby(data.index.normalize()).sum()
        out["leaky_count"] = it._daily_to_rows(valid_d1, out.index, 1)
        return out

    with pytest.raises(AssertionError, match="leaky_count"):
        it.check_no_future_data(gappy, it.D1_1000, ["2024-01-20"], builder=builder)

"""Tests for solar.pvlib_baseline: physics chain, training-only calibration, JSON round trip.

Synthetic weather only (no network, no PEA data).
"""

import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pvlib")

import solar.nwp_features as nf
import solar.pvlib_baseline as pb

LAT, LON, CAPACITY = 13.867, 102.6434, 6000.0


def _days(start="2024-06-10", days=6):
    return pd.date_range(start, periods=96 * days, freq="15min")


def _clear_ghi(index):
    return nf.clear_sky_features(index, LAT, LON)["cs_ghi"].to_numpy()


def test_physical_power_is_zero_at_night_and_positive_at_noon():
    index = _days(days=1)
    power = pb.physical_power(index, _clear_ghi(index), np.full(len(index), 30.0),
                              LAT, LON, CAPACITY)
    night = (index.hour < 5) | (index.hour >= 20)
    assert np.all(power[night] == 0)
    noon = power[(index.hour == 12)]
    assert np.all(noon > 0.5 * CAPACITY)
    assert np.all(noon < 1.2 * CAPACITY)


def test_physical_power_rises_with_ghi_and_falls_with_heat():
    index = pd.DatetimeIndex(["2024-06-10 12:00"] * 3)
    power = pb.physical_power(index, np.array([300.0, 600.0, 600.0]),
                              np.array([30.0, 30.0, 40.0]), LAT, LON, CAPACITY)
    assert power[1] > power[0]
    assert power[2] < power[1]


def test_missing_ghi_gives_nan_and_missing_temperature_does_not():
    index = pd.DatetimeIndex(["2024-06-10 12:00", "2024-06-10 12:15"])
    power = pb.physical_power(index, np.array([np.nan, 600.0]), np.array([30.0, np.nan]),
                              LAT, LON, CAPACITY)
    assert np.isnan(power[0])
    assert np.isfinite(power[1]) and power[1] > 0


def test_default_tilt_is_latitude_facing_south():
    index = pd.DatetimeIndex(["2024-12-15 12:00"])
    ghi, temp = np.array([700.0]), np.array([25.0])
    default = pb.physical_power(index, ghi, temp, LAT, LON, CAPACITY)
    explicit = pb.physical_power(index, ghi, temp, LAT, LON, CAPACITY, tilt=LAT, azimuth=180)
    flat = pb.physical_power(index, ghi, temp, LAT, LON, CAPACITY, tilt=0)
    np.testing.assert_allclose(default, explicit)
    assert default[0] > flat[0]  # December sun is low in the south: tilted panels get more


def _synthetic_training(scale=0.8, ac_limit=4500.0, seed=0):
    rng = np.random.default_rng(seed)
    index = _days(days=8)
    ghi = _clear_ghi(index) * rng.uniform(0.4, 1.0, len(index))
    temp = 28 + 5 * rng.random(len(index))
    physical = pb.physical_power(index, ghi, temp, LAT, LON, CAPACITY)
    power = np.minimum(scale * physical, ac_limit)
    return index, ghi, temp, pd.Series(power, index=index)


def test_fit_recovers_scale_and_ac_limit():
    index, ghi, temp, power = _synthetic_training()
    model = pb.PvlibBaseline.fit(index, ghi, temp, power, LAT, LON, CAPACITY)
    assert model.scale == pytest.approx(0.8, rel=1e-3)
    assert model.ac_limit_kw == pytest.approx(power.max())
    np.testing.assert_allclose(model.predict(index, ghi, temp), power.to_numpy(), atol=1e-6)


def test_fit_is_robust_to_outage_days():
    index, ghi, temp, power = _synthetic_training()
    outage = index.normalize() == index.normalize()[0]  # one day of zero output among eight
    power[outage] = 0.0
    model = pb.PvlibBaseline.fit(index, ghi, temp, power, LAT, LON, CAPACITY)
    assert model.scale == pytest.approx(0.8, rel=0.02)


def test_fit_ignores_missing_targets():
    index, ghi, temp, power = _synthetic_training()
    power[::5] = np.nan
    model = pb.PvlibBaseline.fit(index, ghi, temp, power, LAT, LON, CAPACITY)
    assert model.scale == pytest.approx(0.8, rel=1e-3)


def test_fit_needs_daylight_rows():
    index = pd.date_range("2024-06-10 00:00", periods=8, freq="15min")
    with pytest.raises(ValueError, match="daylight"):
        pb.PvlibBaseline.fit(index, np.zeros(8), np.full(8, 25.0), pd.Series(0.0, index=index),
                             LAT, LON, CAPACITY)


def test_predict_is_clipped_to_zero_and_ac_limit():
    model = pb.PvlibBaseline(lat=LAT, lon=LON, capacity_kw=CAPACITY, tilt=LAT, azimuth=180.0,
                             scale=2.0, ac_limit_kw=3000.0)
    index = _days(days=1)
    prediction = model.predict(index, _clear_ghi(index), np.full(len(index), 30.0))
    assert prediction.min() >= 0
    assert prediction.max() == pytest.approx(3000.0)


def test_json_round_trip_gives_identical_forecasts():
    index, ghi, temp, power = _synthetic_training()
    model = pb.PvlibBaseline.fit(index, ghi, temp, power, LAT, LON, CAPACITY)
    restored = pb.PvlibBaseline.from_dict(json.loads(json.dumps(model.to_dict())))
    assert restored == model
    np.testing.assert_array_equal(restored.predict(index, ghi, temp), model.predict(index, ghi, temp))


def test_saved_file_with_extra_keys_loads():
    index, ghi, temp, power = _synthetic_training()
    model = pb.PvlibBaseline.fit(index, ghi, temp, power, LAT, LON, CAPACITY)
    saved = {**model.to_dict(), "plant": "S01", "train_end": "2024-08-07", "intervals": {}}
    assert pb.PvlibBaseline.from_dict(saved) == model

"""Tests for solar.weather_only: cloud-model features built without any plant data.

Synthetic forecasts only (no network, no PEA data).
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pvlib")

from test_nwp_features import _synthetic_nwp

import solar.nwp_features as nf
import solar.pvlib_baseline as pb
import solar.weather_only as wo
from solar.issue_time import D1_1000, D1_2355, POWER_HISTORY
from solar.plants import Plant

PLANT = Plant("S01", "test", 6000.0, 13.867, 102.6434, "exact", "test")
SLOTS = pd.date_range("2024-06-15", periods=96, freq="15min")


def test_features_need_only_an_index_and_forecasts():
    out = wo.build_weather_features(SLOTS, _synthetic_nwp(), D1_2355, PLANT)
    assert out.index.equals(SLOTS)
    assert {"interval_sin", "doy_cos", "cs_ghi", "sun_elevation", "nwp_ghi_mean",
            "nwp_temp_mean", wo.PHYSICAL} <= set(out.columns)
    assert "P" not in out and not set(POWER_HISTORY) & set(out.columns)
    wo.assert_weather_only(out.columns)


def test_physical_feature_is_the_uncalibrated_pvlib_chain():
    out = wo.build_weather_features(SLOTS, _synthetic_nwp(), D1_2355, PLANT)
    expected = pb.physical_power(SLOTS, out["nwp_ghi_mean"], out["nwp_temp_mean"],
                                 PLANT.lat, PLANT.lon, PLANT.capacity_kw)
    np.testing.assert_allclose(out[wo.PHYSICAL], expected)
    night = out["sun_elevation"] < -1
    assert (out.loc[night, wo.PHYSICAL] == 0).all()
    assert out[wo.PHYSICAL].max() > 0


@pytest.mark.parametrize("scenario", [D1_2355, D1_1000])
def test_weather_features_use_only_published_runs(scenario):
    nwp = _synthetic_nwp()

    def builder(data, slots):
        return wo.build_weather_features(slots, data, scenario, PLANT)

    report = nf.check_nwp_no_future_runs(nwp, scenario, ["2024-06-15", "2024-06-16"],
                                         PLANT.lat, PLANT.lon, builder=builder)
    assert report["pass"].all()


@pytest.mark.parametrize("column", ["P", "P_lag1", "energy_roll7_mean", "irr_lag1",
                                    "P_morning_mean", "aod_3h"])
def test_guard_rejects_plant_and_unvetted_inputs(column):
    with pytest.raises(ValueError, match=column):
        wo.assert_weather_only(["nwp_ghi_mean", column])

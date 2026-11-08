"""Tests for solar.nwp (Open-Meteo Previous Runs reshaping). No network access."""

import pandas as pd
import pytest

from solar.nwp import (
    _split_key,
    availability_audit,
    build_params,
    expected_rows,
    parse_response,
)


def _payload(suffix: str = "") -> dict:
    times = ["2024-03-07T06:00", "2024-03-07T07:00", "2024-03-07T08:00"]
    return {
        "latitude": 13.75,
        "longitude": 102.75,
        "elevation": 80.0,
        "hourly": {
            "time": times,
            f"shortwave_radiation_previous_day1{suffix}": [0.0, 120.0, 400.0],
            f"temperature_2m_previous_day1{suffix}": [25.0, 26.0, 28.0],
            f"shortwave_radiation_previous_day2{suffix}": [None, 110.0, 390.0],
            f"temperature_2m_previous_day2{suffix}": [None, None, 27.5],
        },
    }


def test_build_params_requests_every_variable_and_offset_in_ms_and_bangkok_time():
    params = build_params(13.867, 102.6434, "gfs_seamless", "2024-01-01", "2024-12-31",
                          variables=("shortwave_radiation", "wind_speed_10m"), offsets=(1, 2))
    assert params["hourly"].split(",") == [
        "shortwave_radiation_previous_day1",
        "wind_speed_10m_previous_day1",
        "shortwave_radiation_previous_day2",
        "wind_speed_10m_previous_day2",
    ]
    assert params["models"] == "gfs_seamless"
    assert params["timezone"] == "Asia/Bangkok"
    assert params["wind_speed_unit"] == "ms"


def test_build_params_rejects_best_match():
    with pytest.raises(ValueError):
        build_params(13.0, 102.0, "best_match", "2024-01-01", "2024-01-02")


@pytest.mark.parametrize("suffix", ["", "_ecmwf_ifs025"])
def test_parse_response_one_row_per_offset_and_hour(suffix):
    df = parse_response(_payload(suffix), "S01", "ecmwf_ifs025")
    assert len(df) == 6
    assert sorted(df["offset_day"].unique()) == [1, 2]
    assert {"shortwave_radiation", "temperature_2m"} <= set(df.columns)
    assert str(df["valid_time"].dt.tz) == "Asia/Bangkok"
    day2 = df[df["offset_day"] == 2].set_index("valid_time")
    assert pd.isna(day2["shortwave_radiation"].iloc[0])
    assert day2["shortwave_radiation"].iloc[2] == 390.0
    assert (df["grid_lat"] == 13.75).all() and (df["plant"] == "S01").all()


def test_parse_response_raises_on_api_error():
    with pytest.raises(ValueError):
        parse_response({"error": True, "reason": "bad"}, "S01", "gfs_seamless")


def test_availability_audit_counts_from_first_valid_hour():
    df = parse_response(_payload(), "S01", "ecmwf_ifs025")
    audit = availability_audit(df).set_index(["offset_day", "variable"])
    t2 = audit.loc[(2, "temperature_2m")]
    assert t2["first_valid"] == "2024-03-07"
    assert t2["hours_present"] == 1
    assert t2["pct_present_after_first"] == 100.0
    assert audit.loc[(1, "shortwave_radiation")]["hours_present"] == 3


def test_split_key_handles_two_digit_offsets_and_suffix():
    assert _split_key("cloud_cover_previous_day10_icon_global") == ("cloud_cover", 10, "icon_global")
    assert _split_key("temperature_2m_previous_day1") == ("temperature_2m", 1, "")
    with pytest.raises(ValueError):
        _split_key("temperature_2m")


def test_parse_response_rejects_other_model_columns():
    with pytest.raises(ValueError, match="model"):
        parse_response(_payload("_gfs_seamless"), "S01", "ecmwf_ifs025")


def test_parse_response_rejects_wrong_units():
    payload = _payload()
    payload["hourly"]["wind_speed_10m_previous_day1"] = [1.0, 2.0, 3.0]
    payload["hourly_units"] = {"wind_speed_10m_previous_day1": "km/h"}
    with pytest.raises(ValueError, match="km/h"):
        parse_response(payload, "S01", "ecmwf_ifs025")


def test_expected_rows_matches_parsed_length():
    params = build_params(13.0, 102.0, "icon_global", "2024-03-07", "2024-03-07",
                          variables=("shortwave_radiation", "temperature_2m"), offsets=(1, 2))
    assert expected_rows(params) == 48


def test_availability_audit_counts_out_of_range_values():
    payload = _payload()
    payload["hourly"]["cloud_cover_previous_day1"] = [-1, 50, 101]
    audit = availability_audit(parse_response(payload, "S01", "ecmwf_ifs025"))
    row = audit.set_index(["offset_day", "variable"]).loc[(1, "cloud_cover")]
    assert row["n_out_of_range"] == 2

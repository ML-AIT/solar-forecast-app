"""Tests for solar.forecast_job: contract, fallback chain, issue-time switch, no future runs.

Synthetic weather and model files only (no network, no PEA data).
"""

import io
import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pvlib")

import solar.forecast_job as job
import solar.issue_time as it
import solar.nwp as nw
import solar.nwp_features as nf
from solar.plants import load_plants

PLANT = load_plants()["S01"]
DAY = pd.Timestamp("2026-11-06")
NOW = pd.Timestamp("2026-11-05 23:30", tz="Asia/Bangkok")
SCENARIO = it.D1_2355


def _band(q10, q90):
    return {"hour_error_kw": {str(h): {"q10": q10, "q90": q90} for h in range(6, 19)}}


def _weather(day=DAY):
    """Hourly rows for all three models and offsets, like fetch_weather returns."""
    times = pd.date_range(day - pd.Timedelta(days=1), day + pd.Timedelta(days=4), freq="h",
                          inclusive="left", tz="Asia/Bangkok")
    frames = []
    for model in nw.MODELS:
        for offset in nw.OFFSETS:
            sun = np.clip(np.sin((times.hour - 6) / 12 * np.pi), 0, None)
            frames.append(pd.DataFrame({
                "plant": PLANT.plant_id, "model": model, "offset_day": offset, "valid_time": times,
                "shortwave_radiation": 800.0 * sun, "temperature_2m": 30.0, "cloud_cover": 20.0}))
    return pd.concat(frames, ignore_index=True)


def _fail(plant, day):
    raise OSError("network down")


@pytest.fixture
def paths(tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    saved = {"model": "pvlib", "plant": PLANT.plant_id, "train_end": "2024-08-07",
             "lat": PLANT.lat, "lon": PLANT.lon, "capacity_kw": PLANT.capacity_kw,
             "tilt": PLANT.lat, "azimuth": 180.0, "scale": 0.9, "ac_limit_kw": 5000.0,
             "gamma_pdc": -0.004, "wind_speed": 1.0,
             "intervals": {"d1_2355": _band(-500.0, 400.0), "d1_1000": _band(-900.0, 800.0),
                           "d2_2355": _band(-950.0, 850.0)}}
    (model_dir / "pvlib_baseline_S01.json").write_text(json.dumps(saved))
    months, slots = np.meshgrid(np.arange(1, 13), np.arange(96), indexing="ij")
    power = 3000.0 * np.clip(np.sin((slots.ravel() / 4 - 6) / 12 * np.pi), 0, None)
    pd.DataFrame({"month": months.ravel(), "slot": slots.ravel(), "mean_kw": power,
                  "p10_kw": 0.7 * power, "p90_kw": 1.2 * power}).to_csv(
        model_dir / "S01_climatology.csv", index=False)
    (model_dir / "climatology_meta.json").write_text(
        json.dumps({"plants": {"S01": {"model_version": "climatology-S01-2024.08.07"}}}))
    return job.JobPaths(model_dir, tmp_path / "forecasts", tmp_path / "cache")


def _run(paths, fetch=lambda plant, day: _weather(day), day=DAY, scenario=SCENARIO, now=NOW,
         force=False):
    summary = job.run_plant("S01", day, scenario, paths, now, fetch, force)
    return summary, json.loads((paths.forecast_dir / "S01" / f"{day:%Y-%m-%d}.json").read_text())


def _values(payload, name):
    return np.array([p[name] for p in payload["points"]])


def test_target_day_is_tomorrow_in_bangkok():
    assert job.target_day(pd.Timestamp("2026-11-05 16:30", tz="UTC")) == DAY  # 23:30 Bangkok
    assert job.target_day(pd.Timestamp("2026-11-05 17:30", tz="UTC")) == DAY + pd.Timedelta(days=1)


def test_dropped_requests_are_retried_with_growing_waits(monkeypatch):
    waits, calls = [], []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(url, timeout):
        calls.append(url)
        if len(calls) <= job.RETRIES:
            raise ConnectionResetError("dropped")
        return Response(b'{"ok": true}')

    monkeypatch.setattr(job.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(job.time, "sleep", waits.append)
    assert job._get_json("https://example.test") == {"ok": True}
    assert waits == [5, 10, 20, 40]


def test_retries_give_up_and_raise(monkeypatch):
    def urlopen(url, timeout):
        raise ConnectionResetError("dropped")

    monkeypatch.setattr(job.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(job.time, "sleep", lambda seconds: None)
    with pytest.raises(ConnectionResetError):
        job._get_json("https://example.test")


def test_primary_forecast_follows_the_contract(paths):
    summary, payload = _run(paths)
    assert summary["forecast_mode"] == payload["forecast_mode"] == "primary"
    assert payload["plant_id"] == "S01" and payload["date"] == "2026-11-06"
    assert payload["model_version"] == "pvlib-S01-2024.08.07"
    assert payload["issue_scenario"] == "d1_2355"
    assert payload["issued_at"] == "2026-11-05T23:30:00+07:00"
    stamps = [p["timestamp"] for p in payload["points"]]
    assert len(stamps) == 96 and stamps == sorted(stamps)
    assert stamps[0] == "2026-11-06T00:00:00+07:00" and stamps[-1] == "2026-11-06T23:45:00+07:00"
    p10, p50, p90 = (_values(payload, n) for n in ("p10", "p50", "p90"))
    assert np.isfinite([p10, p50, p90]).all()
    assert (p10 >= 0).all() and (p10 <= p50).all() and (p50 <= p90).all()
    assert p90.max() <= PLANT.capacity_kw and p50.max() > 1000
    assert p50[:16].sum() == 0 and p90[-16:].sum() == 0  # night
    assert not list(paths.forecast_dir.rglob("*.tmp"))


def test_failed_fetch_falls_back_to_the_last_good_weather(paths):
    _, fresh = _run(paths)
    summary, cached = _run(paths, fetch=_fail, force=True)
    assert summary["forecast_mode"] == cached["forecast_mode"] == "cached_weather"
    assert "network down" in summary["reason"]
    assert cached["model_version"] == fresh["model_version"]
    np.testing.assert_allclose(_values(cached, "p50"), _values(fresh, "p50"))


def test_yesterdays_cache_covers_the_next_day(paths):
    _run(paths)
    summary, _ = _run(paths, fetch=_fail, day=DAY + pd.Timedelta(days=1))
    assert summary["forecast_mode"] == "cached_weather"


def test_no_weather_and_no_cache_falls_back_to_climatology(paths):
    summary, payload = _run(paths, fetch=_fail)
    assert summary["forecast_mode"] == payload["forecast_mode"] == "climatology"
    assert payload["model_version"] == "climatology-S01-2024.08.07"
    p10, p50, p90 = (_values(payload, n) for n in ("p10", "p50", "p90"))
    assert (p10 <= p50).all() and (p50 <= p90).all() and p50[:16].sum() == 0 and p50.max() > 1000


@pytest.mark.parametrize("broken", ["one model missing", "one model has a gap"])
def test_incomplete_weather_is_not_served_or_cached(paths, broken):
    def partial(plant, day):
        rows = _weather(day)
        if broken == "one model missing":
            return rows[rows["model"] != "icon_global"]
        rows.loc[rows["model"] == "icon_global", "shortwave_radiation"] = np.nan
        return rows

    summary, _ = _run(paths, fetch=partial)
    assert summary["forecast_mode"] == "climatology"
    assert not (paths.cache_dir / "S01.csv").exists()


def test_bad_cache_file_falls_back_to_climatology(paths):
    paths.cache_dir.mkdir()
    (paths.cache_dir / "S01.csv").write_text("not,a,forecast\n")
    summary, _ = _run(paths, fetch=_fail)
    assert summary["forecast_mode"] == "climatology"


def test_issue_time_switch_picks_that_band(paths):
    _, late = _run(paths, scenario=it.D1_2355)
    _, early = _run(paths, scenario=it.D1_1000, force=True)
    noon = 48
    assert _values(late, "p50")[noon] - _values(late, "p10")[noon] == pytest.approx(500.0)
    assert _values(early, "p50")[noon] - _values(early, "p10")[noon] == pytest.approx(900.0)


LATER = NOW + pd.Timedelta(minutes=10)


def test_rerun_keeps_a_primary_forecast_and_does_not_fetch(paths):
    summary, first = _run(paths)
    assert summary["action"] == "written"
    summary, again = _run(paths, fetch=_fail, now=LATER)
    assert summary["action"] == "kept" and summary["forecast_mode"] == "primary"
    assert summary["model_version"] == "pvlib-S01-2024.08.07" and "reason" in summary
    assert again == first


def test_rerun_upgrades_a_fallback(paths):
    _run(paths, fetch=_fail)
    summary, payload = _run(paths, now=LATER)
    assert summary["action"] == "replaced" and payload["forecast_mode"] == "primary"
    assert payload["issued_at"] == "2026-11-05T23:40:00+07:00"  # the actual issue time


def test_rerun_never_downgrades(paths):
    _run(paths)  # leaves a cache
    _run(paths, fetch=_fail, force=True)  # now cached_weather
    (paths.cache_dir / "S01.csv").unlink()
    summary, payload = _run(paths, fetch=_fail, now=LATER)
    assert summary["action"] == "kept" and "this run got climatology" in summary["reason"]
    assert payload["forecast_mode"] == "cached_weather"
    assert payload["issued_at"] == "2026-11-05T23:30:00+07:00"


def test_same_mode_rerun_keeps_the_first_file(paths):
    _run(paths, fetch=_fail)
    summary, payload = _run(paths, fetch=_fail, now=LATER)
    assert summary["action"] == "kept" and payload["issued_at"].endswith("23:30:00+07:00")


def test_force_replaces_a_primary_forecast(paths):
    _run(paths)
    summary, payload = _run(paths, fetch=_fail, now=LATER, force=True)
    assert summary["action"] == "replaced" and payload["forecast_mode"] == "cached_weather"


NIGHT_BEFORE = NOW - pd.Timedelta(days=1)


def test_night_writes_tomorrow_and_the_early_day_after():
    assert job.nightly_targets(NOW, SCENARIO) == [(DAY, SCENARIO),
                                                  (DAY + pd.Timedelta(days=1), it.D2_2355)]


def test_one_fetch_per_plant_serves_both_days(paths):
    calls = []

    def fetch(plant, day):
        calls.append(day)
        return _weather(day)

    shared = job.fetch_once_per_plant(fetch)
    for day, scenario in job.nightly_targets(NOW, SCENARIO):
        summary = job.run_plant("S01", day, scenario, paths, NOW, shared)
        assert summary["forecast_mode"] == "primary"
    assert calls == [DAY]


def test_final_forecast_replaces_the_early_version(paths):
    summary, early = _run(paths, scenario=it.D2_2355, now=NIGHT_BEFORE)
    assert summary["action"] == "written" and early["issue_scenario"] == "d2_2355"
    summary, final = _run(paths)
    assert summary["action"] == "replaced" and final["issue_scenario"] == "d1_2355"
    assert final["issued_at"] == "2026-11-05T23:30:00+07:00"


def test_early_version_never_replaces_the_final(paths):
    _, final = _run(paths)
    summary, again = _run(paths, scenario=it.D2_2355, now=LATER)
    assert summary["action"] == "kept" and again == final


def test_final_that_falls_back_keeps_the_early_primary(paths):
    _run(paths, scenario=it.D2_2355, now=NIGHT_BEFORE)
    (paths.cache_dir / "S01.csv").unlink()
    summary, payload = _run(paths, fetch=_fail)
    assert summary["action"] == "kept" and payload["issue_scenario"] == "d2_2355"


@pytest.mark.parametrize("content", ["{half a fi", "[1, 2]"])
def test_unreadable_file_is_replaced(paths, content):
    out = job.forecast_path(paths.forecast_dir, "S01", DAY)
    out.parent.mkdir(parents=True)
    out.write_text(content)
    summary, payload = _run(paths)
    assert summary["action"] == "written" and payload["forecast_mode"] == "primary"


def test_issue_time_without_a_band_fails_loudly(paths):
    with pytest.raises(ValueError, match="no band for d1_1000_morning"):
        job.load_model(paths.model_dir, "S01", it.D1_1000_MORNING)
    with pytest.raises(ValueError, match="unknown issue scenario"):
        job.get_scenario("d1_1200")


@pytest.mark.parametrize("scenario", [it.D1_2355, it.D1_1000])
def test_runs_published_after_the_cutoff_change_nothing(scenario):
    """Open-Meteo fills every offset for future days, so the late values are really there."""
    nf.check_nwp_no_future_runs(
        nf.load_plant_nwp(_weather(), PLANT.plant_id), scenario, [DAY], PLANT.lat, PLANT.lon,
        builder=lambda data, slots: job.usable_weather(data, slots, scenario, PLANT))


def test_payload_rejects_bad_values():
    good = np.zeros(96)
    bad = good.copy()
    bad[10] = np.nan
    with pytest.raises(ValueError, match="96 finite"):
        job.forecast_payload("S01", DAY, NOW, "v", "primary", {"p10": good, "p50": bad, "p90": good})

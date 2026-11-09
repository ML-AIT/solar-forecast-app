"""The replay's file check: what counts as a complete forecast (proposal §1.3)."""

import copy
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import replay_forecast_job as rp

DAY = date(2026, 10, 10)


def good_payload() -> dict:
    start = datetime(2026, 10, 10, tzinfo=rp.BANGKOK)
    return {"plant_id": "S01", "date": "2026-10-10", "issued_at": "2026-10-09T23:00:00+07:00",
            "model_version": "pvlib-S01-test", "forecast_mode": "primary",
            "points": [{"timestamp": (start + timedelta(minutes=15 * i)).isoformat(),
                        "p10": 1.0, "p50": 2.0, "p90": 3.0} for i in range(96)]}


def test_complete_file_has_no_problems():
    assert rp.check_forecast(good_payload(), "S01", DAY) == []


def test_each_broken_rule_is_named():
    bad = copy.deepcopy(good_payload())
    del bad["model_version"]
    bad["points"][7]["timestamp"] = bad["points"][8]["timestamp"]
    bad["points"][5]["p50"] = 9.0
    assert rp.check_forecast(bad, "S01", DAY) == [
        "missing model_version", "slot 7 out of 15-min order", "P10 <= P50 <= P90 broken"]


def test_non_finite_value():
    bad = good_payload()
    bad["points"][3]["p90"] = float("nan")
    assert rp.check_forecast(bad, "S01", DAY) == ["non-finite value"]


def test_short_day_and_wrong_plant():
    bad = good_payload()
    bad["points"] = bad["points"][:95]
    assert rp.check_forecast(bad, "S02", DAY) == ["wrong plant or date", "95 slots, not 96"]

import datetime as dt
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.providers import DemoForecastProvider

DATE = dt.date(2026, 10, 17)


def _write_forecast(root: Path, plant_id: str, date: dt.date, model_version: str) -> None:
    forecast = DemoForecastProvider().get_forecast(plant_id, date)
    forecast.model_version = model_version
    out = root / plant_id / f"{date.isoformat()}.json"
    out.parent.mkdir(parents=True)
    out.write_text(forecast.model_dump_json(), encoding="utf-8")


def test_health_reports_file_provider(file_client: TestClient) -> None:
    assert file_client.get("/health").json()["provider"] == "file"


def test_reads_forecast_json(file_client: TestClient, tmp_path: Path) -> None:
    _write_forecast(tmp_path, "S01", DATE, "lgbm-test-1")

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == "lgbm-test-1"
    assert len(body["points"]) == 96
    assert body["points"][0]["timestamp"] == "2026-10-17T00:00:00+07:00"


def test_missing_file_404(file_client: TestClient) -> None:
    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-18"})
    assert r.status_code == 404


def test_invalid_file_500(file_client: TestClient, tmp_path: Path) -> None:
    bad = tmp_path / "S01" / "2026-10-17.json"
    bad.parent.mkdir(parents=True)
    bad.write_text('{"plant_id": "S01", "points": []}', encoding="utf-8")

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 500


def test_mismatched_plant_in_file_500(file_client: TestClient, tmp_path: Path) -> None:
    # A file stored under S02/ that actually contains S01's forecast must not be served.
    forecast = DemoForecastProvider().get_forecast("S01", DATE)
    out = tmp_path / "S02" / "2026-10-17.json"
    out.parent.mkdir(parents=True)
    out.write_text(forecast.model_dump_json(), encoding="utf-8")

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S02", "date": "2026-10-17"})
    assert r.status_code == 500


def _write_payload(root: Path, payload: dict) -> None:
    out = root / payload["plant_id"] / f"{payload['date']}.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps(payload), encoding="utf-8")


def _demo_payload() -> dict:
    return json.loads(DemoForecastProvider().get_forecast("S01", DATE).model_dump_json())


def test_fallback_mode_is_served(file_client: TestClient, tmp_path: Path) -> None:
    _write_payload(tmp_path, {**_demo_payload(), "forecast_mode": "climatology"})

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 200
    assert r.json()["forecast_mode"] == "climatology"


def test_file_without_mode_defaults_to_primary(file_client: TestClient, tmp_path: Path) -> None:
    payload = _demo_payload()
    del payload["forecast_mode"]
    _write_payload(tmp_path, payload)

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 200
    assert r.json()["forecast_mode"] == "primary"


def test_unknown_mode_500(file_client: TestClient, tmp_path: Path) -> None:
    _write_payload(tmp_path, {**_demo_payload(), "forecast_mode": "failed"})

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 500


def test_issue_scenario_is_served(file_client: TestClient, tmp_path: Path) -> None:
    _write_payload(tmp_path, {**_demo_payload(), "issue_scenario": "d2_2355"})

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 200
    assert r.json()["issue_scenario"] == "d2_2355"


def test_file_without_issue_scenario_is_served(file_client: TestClient, tmp_path: Path) -> None:
    payload = _demo_payload()
    del payload["issue_scenario"]
    _write_payload(tmp_path, payload)

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 200
    assert r.json()["issue_scenario"] is None


def test_unknown_issue_scenario_500(file_client: TestClient, tmp_path: Path) -> None:
    _write_payload(tmp_path, {**_demo_payload(), "issue_scenario": "d0_1200"})

    r = file_client.get("/api/v1/forecast", params={"plant_id": "S01", "date": "2026-10-17"})
    assert r.status_code == 500

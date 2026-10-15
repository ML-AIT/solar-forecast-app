import datetime as dt
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

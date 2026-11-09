import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.plants import PLANTS


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "env": "test", "provider": "demo"}


def test_plants_match_contract(client: TestClient) -> None:
    r = client.get("/api/v1/plants")
    assert r.status_code == 200
    assert r.json() == [
        {"id": "S01", "name": "S01 Sa Kaeo", "capacity_kw": 6000, "lat": 13.867, "lon": 102.6434},
        {
            "id": "S02",
            "name": "S02 Prachuap Khiri Khan",
            "capacity_kw": 5950,
            "lat": 12.0017,
            "lon": 99.7959,
        },
        {"id": "S03", "name": "S03 Aranyaprathet", "capacity_kw": 8000, "lat": None, "lon": None},
        {"id": "S04", "name": "S04 Phichit", "capacity_kw": 8000, "lat": None, "lon": None},
    ]


@pytest.mark.parametrize("plant_id", sorted(PLANTS))
def test_forecast_shape_and_bounds(client: TestClient, plant_id: str) -> None:
    r = client.get("/api/v1/forecast", params={"plant_id": plant_id, "date": "2026-10-17"})
    assert r.status_code == 200
    body = r.json()

    assert body["plant_id"] == plant_id
    assert body["date"] == "2026-10-17"
    assert body["unit"] == "kW"
    assert body["resolution_minutes"] == 15
    assert body["timezone"] == "Asia/Bangkok"
    assert body["model_version"] == "demo-0.1"
    assert body["forecast_mode"] == "primary"
    assert body["issue_scenario"] == "d1_2355"
    assert body["issued_at"].endswith("+07:00")

    points = body["points"]
    assert len(points) == 96
    assert points[0]["timestamp"] == "2026-10-17T00:00:00+07:00"
    assert points[-1]["timestamp"] == "2026-10-17T23:45:00+07:00"

    cap = PLANTS[plant_id].capacity_kw
    for p in points:
        assert 0 <= p["p10"] <= p["p50"] <= p["p90"] <= cap
    # Night is zero, midday is producing.
    assert points[0]["p50"] == 0.0
    assert points[48]["p50"] > 0


def test_demo_forecast_is_deterministic(client: TestClient) -> None:
    params = {"plant_id": "S01", "date": "2026-10-17"}
    assert client.get("/api/v1/forecast", params=params).json() == (
        client.get("/api/v1/forecast", params=params).json()
    )


def test_unknown_plant_404(client: TestClient) -> None:
    r = client.get("/api/v1/forecast", params={"plant_id": "S99", "date": "2026-10-17"})
    assert r.status_code == 404


@pytest.mark.parametrize("bad_date", ["2026-13-01", "tomorrow", "17/10/2026"])
def test_bad_date_422(client: TestClient, bad_date: str) -> None:
    r = client.get("/api/v1/forecast", params={"plant_id": "S01", "date": bad_date})
    assert r.status_code == 422


def test_missing_params_422(client: TestClient) -> None:
    assert client.get("/api/v1/forecast").status_code == 422


def test_cors_allows_configured_origin(client: TestClient) -> None:
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_issued_before_target_day(client: TestClient) -> None:
    body = client.get("/api/v1/forecast", params={"plant_id": "S02", "date": "2026-10-17"}).json()
    issued = dt.datetime.fromisoformat(body["issued_at"])
    start = dt.datetime.fromisoformat(body["points"][0]["timestamp"])
    assert issued < start

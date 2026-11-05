"""Synthetic forecasts for development and demos. Uses NO real plant data.

The curve is a clear-sky-like shape from a simple solar-elevation model, scaled by a
pseudo-random "cloudiness" that is deterministic for each (plant_id, date).
"""

import datetime as dt
import hashlib
import math
import random

from app.plants import PLANTS
from app.providers.base import BANGKOK_TZ, ForecastNotFoundError
from app.schemas import INTERVALS_PER_DAY, Forecast, ForecastPoint

MODEL_VERSION = "demo-0.1"
# Used when a plant has no coordinates yet (roughly central Thailand).
DEFAULT_LAT, DEFAULT_LON = 13.75, 100.5
UTC_OFFSET_HOURS = 7.0
PEAK_FRACTION = 0.85  # peak clear-sky output as a fraction of capacity


def _seed(plant_id: str, date: dt.date) -> int:
    # hash() is randomised per process, so use a stable digest instead.
    digest = hashlib.sha256(f"{plant_id}:{date.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _solar_elevation_sin(lat: float, lon: float, date: dt.date, local_hour: float) -> float:
    """Approximate sine of the solar elevation angle (NOAA-style simplified formulas)."""
    doy = date.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (doy - 1 + (local_hour - 12) / 24)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )
    eqtime_min = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    solar_time_min = local_hour * 60 + eqtime_min + 4 * lon - 60 * UTC_OFFSET_HOURS
    hour_angle = math.radians(solar_time_min / 4 - 180)
    phi = math.radians(lat)
    return math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(hour_angle)


class DemoForecastProvider:
    name = "demo"

    def get_forecast(self, plant_id: str, date: dt.date) -> Forecast:
        plant = PLANTS.get(plant_id)
        if plant is None:
            raise ForecastNotFoundError(plant_id)

        cap = plant.capacity_kw
        lat = plant.lat if plant.lat is not None else DEFAULT_LAT
        lon = plant.lon if plant.lon is not None else DEFAULT_LON
        rng = random.Random(_seed(plant_id, date))
        day_clearness = rng.uniform(0.45, 1.0)  # 1.0 = perfectly clear day

        start = dt.datetime.combine(date, dt.time(0, 0), tzinfo=BANGKOK_TZ)
        points: list[ForecastPoint] = []
        for i in range(INTERVALS_PER_DAY):
            mid_hour = (i + 0.5) * 0.25  # evaluate the sun at the interval midpoint
            sin_elev = max(0.0, _solar_elevation_sin(lat, lon, date, mid_hour))
            clear_kw = cap * PEAK_FRACTION * sin_elev**1.2
            if clear_kw <= 0:
                p10 = p50 = p90 = 0.0
            else:
                cloud = day_clearness * rng.uniform(0.85, 1.05)
                p50 = min(cap, clear_kw * cloud)
                spread = 0.15 + 0.35 * (1 - day_clearness)  # cloudier -> wider band
                p10 = p50 * (1 - spread)
                p90 = min(cap, p50 * (1 + spread))
            points.append(
                ForecastPoint(
                    timestamp=start + dt.timedelta(minutes=15 * i),
                    p10=round(p10, 1),
                    p50=round(p50, 1),
                    p90=round(p90, 1),
                )
            )

        # Mirror the real pipeline: issued at 23:55 local on D-1.
        issued_at = dt.datetime.combine(date - dt.timedelta(days=1), dt.time(23, 55), BANGKOK_TZ)
        return Forecast(
            plant_id=plant_id,
            date=date,
            issued_at=issued_at,
            model_version=MODEL_VERSION,
            forecast_mode="primary",
            points=points,
        )

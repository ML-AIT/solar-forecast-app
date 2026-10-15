"""Reads forecasts written by the ML batch job: {FORECAST_DIR}/{plant_id}/{YYYY-MM-DD}.json"""

import datetime as dt
import logging
from pathlib import Path

from pydantic import ValidationError

from app.providers.base import ForecastDataError, ForecastNotFoundError
from app.schemas import Forecast

logger = logging.getLogger(__name__)


class FileForecastProvider:
    name = "file"

    def __init__(self, forecast_dir: Path) -> None:
        self.forecast_dir = Path(forecast_dir)

    def path_for(self, plant_id: str, date: dt.date) -> Path:
        # plant_id is validated against the registry by the router, so it is path-safe.
        return self.forecast_dir / plant_id / f"{date.isoformat()}.json"

    def get_forecast(self, plant_id: str, date: dt.date) -> Forecast:
        path = self.path_for(plant_id, date)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise ForecastNotFoundError(f"{plant_id} {date}") from exc

        try:
            forecast = Forecast.model_validate_json(raw)
        except ValidationError as exc:
            logger.error("Invalid forecast file %s: %s", path, exc)
            raise ForecastDataError(str(path)) from exc

        if forecast.plant_id != plant_id or forecast.date != date:
            logger.error("Forecast file %s does not match %s %s", path, plant_id, date)
            raise ForecastDataError(str(path))
        return forecast

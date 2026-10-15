"""Forecast provider interface and errors."""

import datetime as dt
from typing import Protocol

from app.schemas import Forecast

# Thailand has no DST, so a fixed offset is exact and needs no tz database.
BANGKOK_TZ = dt.timezone(dt.timedelta(hours=7))


class ForecastNotFoundError(Exception):
    """No forecast exists for the requested plant and date."""


class ForecastDataError(Exception):
    """A stored forecast exists but is invalid."""


class ForecastProvider(Protocol):
    name: str

    def get_forecast(self, plant_id: str, date: dt.date) -> Forecast:
        """Return the forecast for a known `plant_id` on local calendar day `date`.

        Raises ForecastNotFoundError if none is available.
        """
        ...

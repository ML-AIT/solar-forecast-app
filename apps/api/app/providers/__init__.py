"""Forecast providers: where forecasts come from (synthetic demo or ML job output files)."""

from app.config import Settings
from app.providers.base import ForecastDataError, ForecastNotFoundError, ForecastProvider
from app.providers.demo import DemoForecastProvider
from app.providers.file import FileForecastProvider

__all__ = [
    "DemoForecastProvider",
    "FileForecastProvider",
    "ForecastDataError",
    "ForecastNotFoundError",
    "ForecastProvider",
    "build_provider",
]


def build_provider(settings: Settings) -> ForecastProvider:
    if settings.forecast_provider == "file":
        return FileForecastProvider(settings.forecast_dir)
    return DemoForecastProvider()

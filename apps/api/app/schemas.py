"""API data contracts. The web app and the ML batch job both depend on these shapes."""

import datetime as dt
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

INTERVALS_PER_DAY = 96  # 24 h x 4 (15-min resolution)

ForecastMode = Literal["primary", "cached_weather", "climatology", "baseline"]


class Plant(BaseModel):
    id: str = Field(examples=["S01"])
    name: str = Field(examples=["S01 Sa Kaeo"])
    capacity_kw: int = Field(gt=0, examples=[6000], description="AC nameplate capacity (kW).")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class ForecastPoint(BaseModel):
    timestamp: dt.datetime = Field(description="Interval start, ISO 8601 with +07:00 offset.")
    p10: float = Field(ge=0)
    p50: float = Field(ge=0)
    p90: float = Field(ge=0)

    @model_validator(mode="after")
    def _quantiles_ordered(self) -> Self:
        if not (self.p10 <= self.p50 <= self.p90):
            raise ValueError("quantiles must satisfy p10 <= p50 <= p90")
        return self


class Forecast(BaseModel):
    plant_id: str
    date: dt.date
    issued_at: dt.datetime
    model_version: str
    forecast_mode: ForecastMode = Field(
        default="primary",
        description="primary = the model selected for this plant; anything else is a fallback.",
    )
    unit: Literal["kW"] = "kW"
    resolution_minutes: Literal[15] = 15
    timezone: Literal["Asia/Bangkok"] = "Asia/Bangkok"
    points: list[ForecastPoint] = Field(min_length=INTERVALS_PER_DAY, max_length=INTERVALS_PER_DAY)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    env: str
    provider: str

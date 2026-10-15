"""Plant and forecast endpoints (/api/v1)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.plants import PLANTS
from app.providers import ForecastDataError, ForecastNotFoundError, ForecastProvider
from app.schemas import Forecast, Plant

router = APIRouter(prefix="/api/v1", tags=["forecast"])


def get_provider(request: Request) -> ForecastProvider:
    return request.app.state.provider


@router.get("/plants", response_model=list[Plant])
def list_plants() -> list[Plant]:
    return list(PLANTS.values())


@router.get(
    "/forecast",
    response_model=Forecast,
    responses={404: {"description": "Unknown plant or no forecast for that date"}},
)
def get_forecast(
    provider: Annotated[ForecastProvider, Depends(get_provider)],
    plant_id: Annotated[str, Query(examples=["S01"])],
    date: Annotated[dt.date, Query(description="Local day (Asia/Bangkok), YYYY-MM-DD")],
) -> Forecast:
    if plant_id not in PLANTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown plant '{plant_id}'")
    try:
        return provider.get_forecast(plant_id, date)
    except ForecastNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No forecast for {plant_id} on {date.isoformat()}"
        ) from exc
    except ForecastDataError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Stored forecast is invalid"
        ) from exc

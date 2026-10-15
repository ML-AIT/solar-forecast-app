"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import Settings, get_settings
from app.providers import build_provider
from app.routers import forecast
from app.schemas import Health


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO)

    app = FastAPI(
        title="Solar Forecast API",
        version=__version__,
        description="Day-ahead 15-min PV power forecasts (P10/P50/P90) for PEA plants.",
    )
    app.state.settings = settings
    app.state.provider = build_provider(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=Health, tags=["ops"])
    def health() -> Health:
        return Health(env=settings.app_env, provider=app.state.provider.name)

    app.include_router(forecast.router)
    return app


app = create_app()

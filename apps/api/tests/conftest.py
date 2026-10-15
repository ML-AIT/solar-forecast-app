from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_env="test", forecast_provider="demo", _env_file=None)
    return TestClient(create_app(settings))


@pytest.fixture
def file_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        app_env="test", forecast_provider="file", forecast_dir=tmp_path, _env_file=None
    )
    return TestClient(create_app(settings))

"""Plant metadata (capacity, coordinates) from ml/configs/plants.yaml.

S03 and S04 coordinates are estimates (`coords_status == "approximate"`, decision 0003).
Code that depends on location should print or log `coords_status` so results based on an
estimate are never mistaken for exact ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "plants.yaml"
COORDS_STATUSES = ("exact", "approximate")


@dataclass(frozen=True)
class Plant:
    """One PEA plant. Coordinates in decimal degrees (WGS84), capacity in kW."""

    plant_id: str
    location: str
    capacity_kw: float
    lat: float
    lon: float
    coords_status: str
    coords_source: str


def load_plants(path: Path = CONFIG_PATH) -> dict[str, Plant]:
    """Read the plant config; returns {plant_id: Plant} in file order."""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)["plants"]
    plants = {pid: Plant(plant_id=pid, **fields) for pid, fields in raw.items()}
    for plant in plants.values():
        if plant.coords_status not in COORDS_STATUSES:
            raise ValueError(f"{plant.plant_id}: coords_status must be one of {COORDS_STATUSES}")
    return plants

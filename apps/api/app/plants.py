"""Static registry of the PEA plants served by this API."""

from app.schemas import Plant

PLANTS: dict[str, Plant] = {
    p.id: p
    for p in (
        Plant(id="S01", name="S01 Sa Kaeo", capacity_kw=6000, lat=13.867, lon=102.6434),
        Plant(id="S02", name="S02 Prachuap Khiri Khan", capacity_kw=5950, lat=12.0017, lon=99.7959),
        # TODO: exact coordinates for S03/S04 are still to be confirmed with PEA.
        Plant(id="S03", name="S03 Aranyaprathet", capacity_kw=8000),
        Plant(id="S04", name="S04 Phichit", capacity_kw=8000),
    )
}


def get_plant(plant_id: str) -> Plant | None:
    return PLANTS.get(plant_id)

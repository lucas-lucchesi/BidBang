"""Chargement du catalogue (lieux, cartes, épreuves de survie)."""
import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_location(location_id: str) -> dict | None:
    for loc in load_catalog()["locations"]:
        if loc["id"] == location_id:
            return loc
    return None


def get_items(location_id: str) -> list[dict]:
    return [i for i in load_catalog()["items"] if i["location_id"] == location_id]


def list_locations() -> list[dict]:
    return [{"id": l["id"], "name": l["name"], "description": l["description"]}
            for l in load_catalog()["locations"]]

from app import criteria
from app.catalog import get_items, get_location, list_locations, load_catalog
from app.items import is_valid_item

CRITERIA = set(criteria.registry())


def test_catalog_size():
    cat = load_catalog()
    assert len(cat["locations"]) == 7
    assert len(cat["items"]) == 84


def test_each_location_has_12_items_and_valid_criteria():
    for loc in list_locations():
        assert len(get_items(loc["id"])) == 12
        crit = get_location(loc["id"])["criteria"]
        assert criteria.clean_criteria(crit) == crit  # déjà normalisés, au moins un nécessaire
        assert get_location(loc["id"])["situation"]["title"]


def test_items_use_the_new_format():
    cat = load_catalog()
    ids = [i["id"] for i in cat["items"]]
    assert len(ids) == len(set(ids))
    for item in cat["items"]:
        assert is_valid_item(item), item["id"]
        assert item["description"] and item["category"] and "image" in item
        assert set(item["attributes"]) <= CRITERIA
        assert "stats" not in item and "tags" not in item  # ancien format non recréé
        assert all(v != 0 for v in item["attributes"].values())  # pas de « soins: 0 »


def test_old_ids_names_prices_and_rarities_are_kept():
    by_id = {i["id"]: i for i in load_catalog()["items"]}
    assert by_id["cabane_01"]["name"] == "Poêle à bois" and by_id["cabane_01"]["price"] == 220
    assert by_id["cabane_10"]["rarity"] == 3 and by_id["station_09"]["name"] == "Capsule d'évacuation"
    assert by_id["appartement_06"]["price"] == 380


def test_criteria_ids_are_ascii_and_registry_is_extensible():
    for cid in CRITERIA:
        assert cid.isascii() and cid == cid.lower()
    assert "decoration" in CRITERIA and "décoration" not in CRITERIA
    assert criteria.normalize_id("Décoration") == "decoration"
    assert all(criteria.label(c) for c in CRITERIA)
    for t in criteria.templates():
        assert criteria.clean_criteria(t["criteria"])  # les modèles sont valides

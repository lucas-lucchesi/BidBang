from app.catalog import get_items, get_location, list_locations, load_catalog


def test_catalog_size():
    cat = load_catalog()
    assert len(cat["locations"]) == 6
    assert len(cat["items"]) == 72


def test_each_location_has_12_items_and_3_trials():
    for loc in list_locations():
        assert len(get_items(loc["id"])) == 12
        assert len(get_location(loc["id"])["survival"]["trials"]) == 3


def test_items_are_valid():
    cat = load_catalog()
    ids = [i["id"] for i in cat["items"]]
    assert len(ids) == len(set(ids))
    for item in cat["items"]:
        assert item["price"] > 0
        assert item["rarity"] in (0, 1, 2, 3)
        assert set(item["stats"]) == set(cat["stats"])
        assert item["tags"]


def test_trials_use_known_stats():
    cat = load_catalog()
    for loc in cat["locations"]:
        for t in loc["survival"]["trials"]:
            assert t["stat"] in cat["stats"] and t["threshold"] > 0

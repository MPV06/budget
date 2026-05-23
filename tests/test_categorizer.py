from services.categorizer import categorize, DEFAULT_PFC_MAP


def test_groceries_maps_to_groceries():
    assert categorize("FOOD_AND_DRINK_GROCERIES", merchant="Trader Joe's") == "Groceries"


def test_restaurants_and_coffee_map_to_restaurants():
    assert categorize("FOOD_AND_DRINK_RESTAURANTS", merchant="Chipotle") == "Restaurants"
    assert categorize("FOOD_AND_DRINK_FAST_FOOD", merchant="McDonald's") == "Restaurants"
    assert categorize("FOOD_AND_DRINK_COFFEE", merchant="Starbucks") == "Restaurants"


def test_gas_maps_to_gas():
    assert categorize("TRANSPORTATION_GAS", merchant="Shell") == "Gas"


def test_unknown_returns_none():
    assert categorize("ENTERTAINMENT_MOVIES", merchant="AMC") is None


def test_merchant_override_takes_precedence():
    overrides = {"Costco Wholesale": "Groceries"}
    assert categorize("GENERAL_MERCHANDISE", merchant="Costco Wholesale",
                      merchant_overrides=overrides) == "Groceries"


def test_default_map_has_expected_keys():
    assert "FOOD_AND_DRINK_GROCERIES" in DEFAULT_PFC_MAP
    assert DEFAULT_PFC_MAP["FOOD_AND_DRINK_GROCERIES"] == "Groceries"

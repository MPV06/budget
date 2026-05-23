from typing import Dict, Optional

DEFAULT_PFC_MAP: Dict[str, str] = {
    "FOOD_AND_DRINK_GROCERIES": "Groceries",
    "FOOD_AND_DRINK_RESTAURANTS": "Restaurants",
    "FOOD_AND_DRINK_FAST_FOOD": "Restaurants",
    "FOOD_AND_DRINK_COFFEE": "Restaurants",
    "FOOD_AND_DRINK_BEER_WINE_AND_LIQUOR": "Restaurants",
    "TRANSPORTATION_GAS": "Gas",
}


def categorize(
    plaid_category: str,
    merchant: Optional[str] = None,
    merchant_overrides: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Return envelope name or None.

    Precedence:
        1. merchant_overrides exact match on merchant
        2. DEFAULT_PFC_MAP lookup
        3. None
    """
    if merchant and merchant_overrides and merchant in merchant_overrides:
        return merchant_overrides[merchant]
    return DEFAULT_PFC_MAP.get(plaid_category)

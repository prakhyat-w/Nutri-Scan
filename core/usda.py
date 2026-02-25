"""
USDA FoodData Central API client.

Docs: https://fdc.nal.usda.gov/api-guide.html
Free key signup: https://api.data.gov/signup  (1 000 req / hr / IP)
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.nal.usda.gov/fdc/v1"

# Map USDA nutrient IDs to human-readable names
_NUTRIENT_MAP = {
    1008: "calories",      # Energy (kcal)
    1003: "protein_g",     # Protein
    1005: "carbs_g",       # Carbohydrate, by difference
    1004: "fat_g",         # Total lipid (fat)
    1079: "fiber_g",       # Fiber, total dietary
}


def search_food(query: str, page_size: int = 5) -> list:
    """Search for foods by name.

    Returns a list of food dicts from the USDA API, or an empty list
    if the request fails.
    """
    try:
        resp = requests.get(
            f"{_BASE_URL}/foods/search",
            params={
                "query": query,
                "api_key": settings.FDC_API_KEY,
                "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
                "pageSize": page_size,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("foods", [])
    except requests.RequestException as exc:
        logger.warning("USDA search failed for '%s': %s", query, exc)
        return []


def get_nutrition(food_name: str) -> Optional[Dict]:
    """Return a normalised nutrition dict for the top-matching USDA food.

    Returns ``None`` if no food is found or the request fails.

    Example return value::

        {
            "food_name": "pizza",
            "fdc_id": 171921,
            "calories": 266.0,
            "protein_g": 11.0,
            "carbs_g": 33.0,
            "fat_g": 10.0,
            "fiber_g": 2.3,
            "raw": { ... },   # full USDA food object
        }
    """
    foods = search_food(food_name)
    if not foods:
        logger.info("No USDA results for '%s'", food_name)
        return None

    top = foods[0]
    fdc_id = top.get("fdcId")
    raw_nutrients = top.get("foodNutrients", [])

    # Build a lookup from nutrient id → value
    nutrient_values: Dict[int, float] = {}
    for n in raw_nutrients:
        nid = n.get("nutrientId") or n.get("nutrient", {}).get("id")
        val = n.get("value") or n.get("amount")
        if nid and val is not None:
            nutrient_values[int(nid)] = float(val)

    result: Dict = {
        "food_name": top.get("description", food_name),
        "fdc_id": fdc_id,
        "raw": top,
    }

    for nid, key in _NUTRIENT_MAP.items():
        result[key] = nutrient_values.get(nid)

    return result

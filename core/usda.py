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

# Map human-readable key → all USDA nutrient IDs that represent it.
# Different USDA databases use different IDs for the same nutrient:
#   Foundation foods  → 1008 (energy), 1003 (protein), 1005 (carbs), 1004 (fat), 1079 (fiber)
#   SR Legacy         →  208 (energy),  203 (protein),  205 (carbs),  204 (fat),  291 (fiber)
#   Survey (FNDDS)    → 2047 (energy), 2047 overlaps; protein=1003, carbs=1005
# We check all known IDs and take the first value found.
_NUTRIENT_MAP: dict[str, list[int]] = {
    "calories":  [1008, 208, 2047],
    "protein_g": [1003, 203],
    "carbs_g":   [1005, 205],
    "fat_g":     [1004, 204],
    "fiber_g":   [1079, 291],
}


def search_food(query: str, page_size: int = 5) -> list:
    """Search for foods by name.

    Returns a list of food dicts from the USDA API, or an empty list
    if the request fails.
    """
    try:
        # dataType must be passed as repeated tuple params — passing a Python
        # list causes requests to encode it as dataType%5B%5D=... which the
        # USDA API rejects with HTTP 400.
        params = [
            ("query", query),
            ("api_key", settings.FDC_API_KEY),
            ("dataType", "Foundation"),
            ("dataType", "SR Legacy"),
            ("dataType", "Survey (FNDDS)"),
            ("pageSize", page_size),
        ]
        resp = requests.get(
            f"{_BASE_URL}/foods/search",
            params=params,
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

    # Build a lookup from nutrient id → value covering all data-type variants
    nutrient_values: dict[int, float] = {}
    for n in raw_nutrients:
        nid = n.get("nutrientId") or n.get("nutrient", {}).get("id")
        val = n.get("value") if n.get("value") is not None else n.get("amount")
        if nid and val is not None:
            nutrient_values[int(nid)] = float(val)

    result: Dict = {
        "food_name": top.get("description", food_name),
        "fdc_id": fdc_id,
        "raw": top,
    }

    # Try each known nutrient ID in priority order; use the first hit
    for key, id_list in _NUTRIENT_MAP.items():
        for nid in id_list:
            if nid in nutrient_values:
                result[key] = nutrient_values[nid]
                break
        else:
            result[key] = None

    logger.info(
        "USDA result for '%s': cal=%s prot=%s carbs=%s fat=%s",
        food_name, result.get("calories"), result.get("protein_g"),
        result.get("carbs_g"), result.get("fat_g"),
    )
    return result

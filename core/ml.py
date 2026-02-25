"""
ML module — wraps the BLIP image captioning model.

Instead of classifying into a fixed set of 101 labels, BLIP generates
open-ended natural language captions such as:
  "grilled chicken breast with steamed broccoli and brown rice"

This caption is then parsed by tasks.py into individual food items,
each of which is looked up in the USDA FoodData Central API so that
mixed-plate meals are handled correctly.

The model is loaded ONCE at Django startup (via CoreConfig.ready())
and stored in the module-level ``_model`` variable so every gunicorn
worker reuses the same in-memory weights.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_model = None  # populated by load_model()

# ---------------------------------------------------------------------------
# Non-food words to block when extracting food items from BLIP captions.
# BLIP frequently describes the setting ("a fork on a table") alongside the
# actual food — these lists strip that noise before the USDA lookup.
# ---------------------------------------------------------------------------

NON_FOOD_WORDS: frozenset[str] = frozenset({
    # Utensils
    "fork", "knife", "spoon", "chopstick", "chopsticks", "tong", "tongs",
    "spatula", "ladle", "whisk", "grater", "peeler", "skewer",
    # Cookware
    "pan", "pot", "wok", "skillet", "oven", "microwave", "grill",
    # Tableware & vessels
    "plate", "bowl", "dish", "cup", "glass", "mug", "jar", "bottle",
    "container", "box", "bag", "wrapper", "tray", "basket", "rack",
    "napkin", "cloth", "towel",
    # Furniture & surfaces
    "table", "counter", "countertop", "board", "desk",
    "tablecloth", "mat", "placemat", "surface", "background",
    # Generic scene/photo words
    "food", "meal", "cuisine", "serving", "portion", "bite",
    "piece", "top", "view", "photo", "picture", "image",
    "restaurant", "kitchen", "cafe", "home",
    # Articles, prepositions, conjunctions that slip through splitting
    "a", "an", "the", "some", "with", "and", "of", "on", "in",
    "at", "by", "for", "to", "from",
    # Colors that appear as standalone tokens
    "white", "black", "red", "green", "yellow", "brown", "orange",
    "wooden", "ceramic", "metal", "plastic",
})

# Cooking-method / descriptor prefixes to strip from phrase starts so that
# "grilled chicken" → "chicken" (better USDA match)
STRIP_PREFIXES: frozenset[str] = frozenset({
    "grilled", "fried", "baked", "roasted", "steamed", "boiled",
    "sauteed", "sautéed", "stir", "smoked", "raw", "fresh", "frozen",
    "cooked", "crispy", "creamy", "spicy", "sweet", "savory",
    "homemade", "sliced", "chopped", "diced", "minced", "whole",
    "half", "small", "large", "big", "little", "hot", "cold", "warm",
})


def load_model() -> None:
    """Download (first run) and load the BLIP captioning model into memory.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _model
    if _model is not None:
        return

    from django.conf import settings
    from transformers import pipeline
    import torch

    model_id = getattr(settings, "ML_MODEL_ID", "Salesforce/blip-image-captioning-base")
    device = 0 if torch.cuda.is_available() else -1
    device_label = "GPU" if device == 0 else "CPU"

    logger.info("Loading BLIP captioning model '%s' on %s …", model_id, device_label)
    _model = pipeline(
        "image-to-text",
        model=model_id,
        device=device,
    )
    logger.info("BLIP model loaded successfully.")


# Backward-compat alias
load_classifier = load_model


def caption_image(image_path: str) -> str:
    """Generate a natural language caption for a meal photo.

    Args:
        image_path: Absolute path to the image file on disk.

    Returns:
        A caption string, e.g. ``"grilled salmon with asparagus and rice"``
    """
    if _model is None:
        load_model()

    results = _model(image_path, max_new_tokens=60)
    caption: str = results[0]["generated_text"].strip()
    logger.info("BLIP caption: %s", caption)
    return caption


def _clean_phrase(phrase: str) -> str:
    """Strip leading descriptor/article words from a phrase.

    Examples::
        "a bowl of grilled chicken" → "chicken"
        "grilled salmon fillet"     → "salmon fillet"
        "steamed white rice"        → "rice"
    """
    words = phrase.lower().split()
    while words and words[0] in STRIP_PREFIXES | NON_FOOD_WORDS:
        words.pop(0)
    return " ".join(words).strip()


def extract_food_items(caption: str) -> list[str]:
    """Parse a BLIP caption into clean, USDA-queryable food terms.

    Strategy:
    1. Split on conjunctions / prepositions that separate food items.
    2. Strip leading descriptor/article words from each candidate phrase.
    3. Remove any remaining tokens that are in the NON_FOOD_WORDS blocklist.
    4. Discard candidates where no real food word survives.
    5. Deduplicate while preserving order.
    6. Return up to ML_MAX_FOOD_ITEMS terms.

    Example::
        "a bowl of rice and a fork on a table"
        → split: ["a bowl of rice", "a fork on a table"]
        → clean: ["rice", ""]          (fork/table blocked)
        → result: ["rice"]             ✅
    """
    if not caption:
        return []

    from django.conf import settings

    max_items = getattr(settings, "ML_MAX_FOOD_ITEMS", 5)

    text = caption.lower()
    # Remove possessives and most punctuation (keep hyphens for "stir-fry" etc.)
    text = re.sub(r"'s\b", "", text)
    text = re.sub(r"[^\w\s\-]", " ", text)

    # Split on the words / patterns that separate food items in captions
    parts = re.split(
        r"\band\b|\bwith\b|\bon\b|\bover\b|\bserved\b|\btopped\b"
        r"|\bside\b|\bof\b|\balongside\b|\bplus\b|,",
        text,
    )

    seen: set[str] = set()
    foods: list[str] = []

    for part in parts:
        # 1. Strip leading descriptors / articles
        phrase = _clean_phrase(part.strip())
        if not phrase:
            continue

        # 2. Keep only food-word tokens (drop any trailing non-food words)
        food_tokens = [w for w in phrase.split() if w not in NON_FOOD_WORDS and len(w) > 2]
        if not food_tokens:
            continue

        clean = " ".join(food_tokens)

        if clean not in seen:
            seen.add(clean)
            foods.append(clean)

        if len(foods) >= max_items:
            break

    logger.info("Extracted food items from caption %r: %s", caption, foods)

    # Fallback: if nothing survived filtering, send the whole caption trimmed
    if not foods:
        foods = [caption[:80]]

    return foods

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
        A caption string, e.g.
        ``"grilled salmon with asparagus and lemon wedge"``
    """
    if _model is None:
        load_model()

    results = _model(image_path, max_new_tokens=60)
    caption: str = results[0]["generated_text"].strip()
    logger.info("BLIP caption: %s", caption)
    return caption


def extract_food_items(caption: str) -> list[str]:
    """Parse a BLIP caption into individual food search terms.

    Example::

        caption = "grilled chicken with steamed broccoli and brown rice"
        extract_food_items(caption)
        # → ["grilled chicken", "steamed broccoli", "brown rice"]

    Args:
        caption: Raw BLIP-generated caption string.

    Returns:
        A list of food name strings (max 5) suitable for USDA lookup.
    """
    from django.conf import settings

    max_items = getattr(settings, "ML_MAX_FOOD_ITEMS", 5)

    text = caption.lower().strip().rstrip(".")

    # Strip common photographic / container prefixes
    noise_prefixes = [
        r"^a (close[- ]up |top[- ]view |overhead |side[- ]view )?(photo|picture|image|shot) of (a |an )?",
        r"^there (is|are) ",
        r"^this is (a |an )?",
        r"^(a |an )?(plate|bowl|dish|tray|cup|serving|box|basket|pan) of ",
        r"^(a |an )?",
    ]
    for pattern in noise_prefixes:
        text = re.sub(pattern, "", text, count=1)

    # Split on common food connectors
    parts = re.split(
        r"\s*(?:,\s*| and | with | topped with | served with "
        r"| alongside | garnished with | on top of | over | plus )\s*",
        text,
    )

    # Generic words that aren't useful USDA search terms on their own
    _skip = {
        "food", "meal", "dish", "plate", "bowl", "some", "various",
        "assorted", "mixed", "cooked", "fresh", "homemade", "delicious",
        "tasty", "hot", "cold", "white", "table", "wooden",
    }

    foods: list[str] = []
    for part in parts:
        part = part.strip()
        if len(part) < 3:
            continue
        if part in _skip:
            continue
        # Skip if ALL words are generic noise
        if set(part.split()).issubset(_skip):
            continue
        foods.append(part)
        if len(foods) >= max_items:
            break

    # Fallback: use the whole (trimmed) caption if nothing useful was extracted
    if not foods:
        foods = [caption[:100]]

    return foods

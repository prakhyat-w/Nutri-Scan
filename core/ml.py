"""
ML module — wraps the Swin Transformer food classifier.

The classifier is loaded ONCE at Django startup (via CoreConfig.ready())
and stored in the module-level ``_classifier`` variable so every
gunicorn worker reuses the same in-memory model.
"""

from __future__ import annotations

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

_classifier = None  # populated by load_classifier()


def load_classifier():
    """Download (first run) and load the Swin food model into memory.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _classifier
    if _classifier is not None:
        return

    from django.conf import settings
    from transformers import pipeline
    import torch

    model_id = getattr(settings, "ML_MODEL_ID", "skylord/swin-finetuned-food101")
    device = 0 if torch.cuda.is_available() else -1  # CPU on HF Spaces free tier
    device_label = "GPU" if device == 0 else "CPU"

    logger.info("Loading ML model '%s' on %s …", model_id, device_label)
    _classifier = pipeline(
        "image-classification",
        model=model_id,
        device=device,
    )
    logger.info("ML model loaded successfully.")


def classify_image(image_path: str) -> List[Dict]:
    """Run image classification and return top-k results.

    Args:
        image_path: Absolute path to the image file on disk.

    Returns:
        A list of dicts like ``[{"label": "pizza", "score": 0.92}, …]``
        sorted by score descending.

    Raises:
        RuntimeError: If the model has not been loaded yet.
    """
    if _classifier is None:
        # Fallback: load on-demand if startup loading was skipped
        load_classifier()

    from django.conf import settings

    top_k = getattr(settings, "ML_TOP_K", 3)

    results = _classifier(image_path, top_k=top_k)
    # Normalise label format: "french_fries" → "french fries"
    for r in results:
        r["label"] = r["label"].replace("_", " ").lower().strip()
    return results

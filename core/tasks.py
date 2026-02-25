"""
Background tasks — run in a daemon thread so the upload HTTP response
returns immediately while ML inference + USDA lookup happen asynchronously.

Flow:
  1. View uploads image to Supabase Storage.
  2. View creates MealLog(status=PROCESSING) and saves to DB.
  3. View spawns a thread running ``analyse_meal(meal_id, tmp_image_path)``.
  4. Thread runs ML → USDA → updates MealLog(status=DONE) or (status=ERROR).
  5. Frontend polls /api/meal/<id>/status/ via HTMX every 2 seconds.
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)


def analyse_meal(meal_id: int, image_path: str) -> None:
    """Classify a meal photo and fetch nutrition data, then save to DB.

    Designed to run in a daemon thread.  All Django ORM calls use
    ``django.db.close_old_connections()`` to avoid "connection already
    closed" errors in threads that outlive the request.
    """
    import django
    from django.db import close_old_connections

    # Ensure Django setup is complete (important when called from a thread).
    if not django.conf.settings.configured:
        django.setup()

    close_old_connections()

    from core.models import MealLog
    from core import ml, usda

    try:
        meal = MealLog.objects.get(pk=meal_id)
        meal.status = MealLog.Status.PROCESSING
        meal.save(update_fields=["status"])

        # --- Step 1: ML classification ---
        predictions = ml.classify_image(image_path)
        if not predictions:
            raise ValueError("Model returned no predictions.")

        top = predictions[0]
        food_label = top["label"]
        confidence = float(top["score"])

        # --- Step 2: Nutrition lookup ---
        nutrition = usda.get_nutrition(food_label)

        # --- Step 3: Persist results ---
        meal.detected_food = food_label
        meal.confidence = confidence
        meal.status = MealLog.Status.DONE

        if nutrition:
            meal.calories = nutrition.get("calories")
            meal.protein_g = nutrition.get("protein_g")
            meal.carbs_g = nutrition.get("carbs_g")
            meal.fat_g = nutrition.get("fat_g")
            meal.fiber_g = nutrition.get("fiber_g")
            meal.raw_nutrition_data = nutrition.get("raw", {})

        meal.save()
        logger.info("analyse_meal(%d): done — %s (%.1f%%)", meal_id, food_label, confidence * 100)

    except MealLog.DoesNotExist:
        logger.error("analyse_meal: MealLog %d not found.", meal_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyse_meal(%d) failed: %s", meal_id, exc)
        try:
            meal = MealLog.objects.get(pk=meal_id)
            meal.status = MealLog.Status.ERROR
            meal.error_message = str(exc)
            meal.save(update_fields=["status", "error_message"])
        except Exception:
            pass
    finally:
        close_old_connections()
        # Clean up the temporary image file
        if os.path.exists(image_path):
            os.remove(image_path)


def dispatch_analyse_meal(meal_id: int, image_path: str) -> None:
    """Spawn a daemon thread to run ``analyse_meal`` in the background."""
    t = threading.Thread(
        target=analyse_meal,
        args=(meal_id, image_path),
        daemon=True,
        name=f"analyse-meal-{meal_id}",
    )
    t.start()
    logger.debug("Dispatched background thread %s", t.name)

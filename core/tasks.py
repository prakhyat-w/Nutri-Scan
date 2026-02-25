"""
Background tasks — run in a daemon thread so the upload HTTP response
returns immediately while ML inference + USDA lookup happen asynchronously.

Flow (BLIP 2-stage pipeline):
  1. View uploads image to Supabase Storage.
  2. View creates MealLog(status=PROCESSING) and saves to DB.
  3. View spawns a thread running ``analyse_meal(meal_id, tmp_image_path)``.
  4. Thread runs:
       a. BLIP caption  →  "grilled chicken with broccoli and rice"
       b. extract_food_items()  →  ["grilled chicken", "broccoli", "rice"]
       c. USDA lookup for each food item
       d. Sum all macros  →  save totals to MealLog(status=DONE)
  5. Frontend polls /api/meal/<id>/status/ via HTMX every 2 seconds.
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)


def analyse_meal(meal_id: int, image_path: str) -> None:
    """Caption a meal photo, extract foods, fetch nutrition, then save to DB.

    Designed to run in a daemon thread.  All Django ORM calls use
    ``django.db.close_old_connections()`` to avoid "connection already
    closed" errors in threads that outlive the request.
    """
    import django
    from django.db import close_old_connections

    if not django.conf.settings.configured:
        django.setup()

    close_old_connections()

    from core.models import MealLog
    from core import ml, usda

    try:
        meal = MealLog.objects.get(pk=meal_id)
        meal.status = MealLog.Status.PROCESSING
        meal.save(update_fields=["status"])

        # ── Step 1: BLIP captioning ───────────────────────────────────────
        caption = ml.caption_image(image_path)

        # ── Step 2: Parse caption → food item list ────────────────────────
        food_items = ml.extract_food_items(caption)
        logger.info("analyse_meal(%d): foods extracted → %s", meal_id, food_items)

        # ── Step 3: USDA lookup for each food item ────────────────────────
        nutrition_results: list[dict] = []
        for item in food_items:
            info = usda.get_nutrition(item)
            if info:
                info["queried_as"] = item
                nutrition_results.append(info)
                logger.info("  USDA hit: %s → %s kcal", item, info.get("calories"))
            else:
                logger.warning("  USDA miss: no result for '%s'", item)

        # ── Step 4: Sum macros across all identified foods ─────────────────
        def _sum(key: str) -> float | None:
            vals = [r[key] for r in nutrition_results if r.get(key) is not None]
            return round(sum(vals), 1) if vals else None

        # ── Step 5: Persist results ───────────────────────────────────────
        meal.detected_food = caption[:200]   # full BLIP caption (200 char field)
        meal.confidence = None               # BLIP has no classifier confidence
        meal.calories = _sum("calories")
        meal.protein_g = _sum("protein_g")
        meal.carbs_g = _sum("carbs_g")
        meal.fat_g = _sum("fat_g")
        meal.fiber_g = _sum("fiber_g")
        meal.raw_nutrition_data = {
            "caption": caption,
            "foods_detected": food_items,
            "usda_results": nutrition_results,
        }
        meal.status = MealLog.Status.DONE
        meal.save()

        logger.info(
            "analyse_meal(%d): done — caption=%r | items=%s | cal=%s",
            meal_id, caption, food_items, meal.calories,
        )

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

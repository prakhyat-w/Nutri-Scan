"""
Core app views.

URL map (see core/urls.py):
  /                  → landing page
  /register/         → user registration
  /dashboard/        → main dashboard (requires login)
  /upload/           → meal photo upload (HTMX POST)
  /api/meal/<id>/status/  → HTMX polling endpoint
  /api/meal/<id>/delete/  → delete a meal log entry
  /api/chart/daily/  → JSON data for the 7-day calorie chart
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import MealUploadForm, RegisterForm
from core.models import MealLog
from core import storage, tasks

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    features = [
        ("📸", "Photo upload", "Snap a photo of any meal and our AI identifies the food instantly."),
        ("🧠", "AI-powered", "Swin Transformer model trained on 101 food categories with 92% accuracy."),
        ("📊", "Macro tracking", "Calories, protein, carbs, and fat pulled from the USDA FoodData Central."),
    ]
    return render(request, "core/index.html", {"features": features})


# ---------------------------------------------------------------------------
# Auth — registration (login/logout handled by Django built-ins in config/urls.py)
# ---------------------------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to NutriScan! Upload your first meal.")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "auth/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    recent_logs = (
        MealLog.objects.filter(user=request.user)
        .order_by("-logged_at")[:20]
    )

    # Today's totals
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = MealLog.objects.filter(
        user=request.user,
        logged_at__gte=today_start,
        status=MealLog.Status.DONE,
    )
    today_totals = today_logs.aggregate(
        cal=Sum("calories"),
        pro=Sum("protein_g"),
        carb=Sum("carbs_g"),
        fat=Sum("fat_g"),
    )

    # 7-day calorie trend for Chart.js
    chart_labels, chart_data = _seven_day_calories(request.user)

    upload_form = MealUploadForm()

    # Pre-format stats for the template macro cards
    today_stats = [
        ("Calories", round(today_totals["cal"] or 0), "kcal", "text-yellow-400"),
        ("Protein",  round(today_totals["pro"] or 0, 1), "g",   "text-blue-400"),
        ("Carbs",    round(today_totals["carb"] or 0, 1), "g",  "text-orange-400"),
        ("Fat",      round(today_totals["fat"] or 0, 1), "g",   "text-pink-400"),
    ]

    return render(
        request,
        "core/dashboard.html",
        {
            "recent_logs": recent_logs,
            "today_totals": today_totals,
            "today_stats": today_stats,
            "today": timezone.now(),
            "chart_labels": json.dumps(chart_labels),
            "chart_data": json.dumps(chart_data),
            "upload_form": upload_form,
        },
    )


def _seven_day_calories(user) -> tuple[list, list]:
    """Return (labels, values) for the past 7 days' calorie totals."""
    now = timezone.now()
    labels, values = [], []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        total = (
            MealLog.objects.filter(
                user=user,
                logged_at__gte=day_start,
                logged_at__lt=day_end,
                status=MealLog.Status.DONE,
            ).aggregate(s=Sum("calories"))["s"]
            or 0
        )
        labels.append(day.strftime("%a %-d"))
        values.append(round(total, 1))
    return labels, values


# ---------------------------------------------------------------------------
# Meal upload
# ---------------------------------------------------------------------------

@login_required
@require_POST
def upload_meal(request):
    """Accept a multipart photo upload, store it, and kick off async analysis."""
    form = MealUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        # Return HTMX-friendly error fragment
        return render(request, "core/partials/upload_error.html", {"form": form}, status=422)

    photo = request.FILES["photo"]
    notes = form.cleaned_data.get("notes", "")

    # --- Save photo to a temp file for the ML pipeline ---
    suffix = os.path.splitext(photo.name)[1] or ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in photo.chunks():
        tmp.write(chunk)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    # --- Upload to Supabase Storage (returns a URL or None) ---
    photo.seek(0)
    image_url = storage.upload_meal_photo(
        file_bytes=photo.read(),
        original_filename=photo.name,
        user_id=request.user.id,
    ) or ""

    # --- Create MealLog record ---
    meal = MealLog.objects.create(
        user=request.user,
        image_url=image_url,
        user_notes=notes,
        status=MealLog.Status.PROCESSING,
    )

    # --- Dispatch background thread ---
    tasks.dispatch_analyse_meal(meal.id, tmp_path)

    # Return the "processing" partial that HTMX will swap into the page.
    return render(
        request,
        "core/partials/meal_processing.html",
        {"meal": meal},
    )


# ---------------------------------------------------------------------------
# Polling endpoint — called by HTMX every 2 seconds
# ---------------------------------------------------------------------------

@login_required
def meal_status(request, meal_id: int):
    """Return an HTMX partial fragment reflecting the current analysis status."""
    meal = get_object_or_404(MealLog, pk=meal_id, user=request.user)

    if meal.status == MealLog.Status.DONE:
        return render(request, "core/partials/meal_result.html", {"meal": meal})

    if meal.status == MealLog.Status.ERROR:
        return render(request, "core/partials/meal_error.html", {"meal": meal})

    # Still processing — return the same spinner partial so HTMX keeps polling
    return render(request, "core/partials/meal_processing.html", {"meal": meal})


# ---------------------------------------------------------------------------
# Delete a meal log entry
# ---------------------------------------------------------------------------

@login_required
@require_POST
def delete_meal(request, meal_id: int):
    meal = get_object_or_404(MealLog, pk=meal_id, user=request.user)
    meal.delete()
    # Return empty 200 — HTMX will remove the element via hx-swap="outerHTML"
    return render(request, "core/partials/empty.html")


# ---------------------------------------------------------------------------
# Chart data API (JSON)
# ---------------------------------------------------------------------------

@login_required
def chart_daily(request):
    """JSON endpoint for the 7-day calorie line chart (used by dashboard JS)."""
    labels, data = _seven_day_calories(request.user)
    return JsonResponse({"labels": labels, "data": data})

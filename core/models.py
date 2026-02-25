from django.db import models
from django.contrib.auth.models import User


class MealLog(models.Model):
    """Represents one meal photo uploaded by a user."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        ERROR = "error", "Error"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_logs")
    logged_at = models.DateTimeField(auto_now_add=True)

    # --- Image ---
    # We store the Supabase Storage public URL instead of a local file path.
    image_url = models.URLField(max_length=500, blank=True, default="")

    # --- ML classification result ---
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    detected_food = models.CharField(max_length=200, blank=True, default="")
    confidence = models.FloatField(null=True, blank=True)

    # --- Nutrition (extracted from raw USDA response) ---
    calories = models.FloatField(null=True, blank=True)      # kcal per 100 g
    protein_g = models.FloatField(null=True, blank=True)     # g per 100 g
    carbs_g = models.FloatField(null=True, blank=True)       # g per 100 g
    fat_g = models.FloatField(null=True, blank=True)         # g per 100 g
    fiber_g = models.FloatField(null=True, blank=True)       # g per 100 g

    # --- Raw API response stored for future reference / re-processing ---
    raw_nutrition_data = models.JSONField(default=dict, blank=True)

    # --- Optional user correction ---
    user_notes = models.TextField(blank=True, default="")

    # --- Error message if status == ERROR ---
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-logged_at"]
        indexes = [
            models.Index(fields=["user", "logged_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        food = self.detected_food or "unknown"
        return f"{self.user.username} – {food} ({self.logged_at:%Y-%m-%d %H:%M})"

    @property
    def macros_available(self):
        return self.calories is not None

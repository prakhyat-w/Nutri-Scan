from django.contrib import admin
from core.models import MealLog


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = ("user", "detected_food", "calories", "status", "logged_at")
    list_filter = ("status", "logged_at")
    search_fields = ("user__username", "detected_food")
    readonly_fields = ("logged_at", "raw_nutrition_data")
    date_hierarchy = "logged_at"

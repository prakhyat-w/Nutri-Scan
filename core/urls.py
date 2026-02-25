from django.urls import path
from core import views

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Meal management
    path("upload/", views.upload_meal, name="upload_meal"),
    path("api/meal/<int:meal_id>/status/", views.meal_status, name="meal_status"),
    path("api/meal/<int:meal_id>/delete/", views.delete_meal, name="delete_meal"),
    # Chart data
    path("api/chart/daily/", views.chart_daily, name="chart_daily"),
]

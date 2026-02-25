from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # Django built-in auth (login / logout / password change)
    path(
        "auth/login/",
        auth_views.LoginView.as_view(template_name="auth/login.html"),
        name="login",
    ),
    path(
        "auth/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    # Core app
    path("", include("core.urls")),
]

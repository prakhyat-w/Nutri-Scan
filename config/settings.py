"""
Django settings for NutriScan project.

Environment variables (set in HuggingFace Space secrets or a local .env file):
  SECRET_KEY           – Django secret key
  DEBUG                – "True" in dev, unset / "False" in prod
  ALLOWED_HOSTS        – comma-separated list of hostnames
  DATABASE_URL         – Neon PostgreSQL connection string
  SUPABASE_URL         – Supabase project URL
  SUPABASE_ANON_KEY    – Supabase anon/public API key
  SUPABASE_BUCKET      – name of the Supabase Storage bucket for meal photos
  FDC_API_KEY          – USDA FoodData Central API key (free at api.data.gov)
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-keep-long-random")
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

_raw_hosts = os.environ.get("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()] or ["*"]

# CSRF trusted origins for HuggingFace Spaces domain
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if not h.startswith("localhost")
]
CSRF_TRUSTED_ORIGINS += ["http://localhost:7860", "http://127.0.0.1:7860"]

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",  # must come BEFORE staticfiles
    "django.contrib.staticfiles",
    # Project apps
    "core.apps.CoreConfig",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — Neon PostgreSQL via DATABASE_URL
# Fallback to SQLite so the app works locally without any env vars.
# ---------------------------------------------------------------------------
_db_url = os.environ.get("DATABASE_URL", "")

if _db_url:
    # Parse postgres://user:pass@host:port/dbname
    import re

    _m = re.match(
        r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)", _db_url
    )
    if _m:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "USER": _m.group(1),
                "PASSWORD": _m.group(2),
                "HOST": _m.group(3),
                "PORT": _m.group(4) or "5432",
                "NAME": _m.group(5).split("?")[0],
                "OPTIONS": {"sslmode": "require"},
                "CONN_MAX_AGE": 60,
            }
        }
    else:
        raise ValueError(f"DATABASE_URL has unexpected format: {_db_url!r}")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files — WhiteNoise serves them from the container
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    # Media files are stored in Supabase Storage (not on local disk)
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# Allow HuggingFace Spaces to embed the app in its iframe
X_FRAME_OPTIONS = "ALLOWALL"

# ---------------------------------------------------------------------------
# Supabase Storage settings (accessed from core/storage.py)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "meal-photos")

# ---------------------------------------------------------------------------
# USDA FoodData Central
# ---------------------------------------------------------------------------
FDC_API_KEY = os.environ.get("FDC_API_KEY", "DEMO_KEY")

# ---------------------------------------------------------------------------
# ML model identifier loaded at worker startup (see core/apps.py)
# ---------------------------------------------------------------------------
ML_MODEL_ID = "skylord/swin-finetuned-food101"
ML_TOP_K = 3  # number of predictions returned per image

# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Pre-load the ML model when the Django process starts.

        This runs once per gunicorn worker. Loading the ~300 MB Swin model
        at startup (rather than on the first request) keeps per-request
        latency under 3 seconds on the HuggingFace Spaces CPU.
        """
        # Guard: only load in the main server process, not during management
        # commands like `migrate` or `collectstatic`.
        import sys

        _skip_commands = {"migrate", "collectstatic", "makemigrations", "shell"}
        if len(sys.argv) > 1 and sys.argv[1] in _skip_commands:
            return

        # Lazy import so the module is not evaluated before Django is ready.
        from core import ml  # noqa: F401  triggers ml._load_classifier()

        ml.load_classifier()

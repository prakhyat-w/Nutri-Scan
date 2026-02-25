from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Pre-load the BLIP captioning model when the Django process starts.

        Model loading runs in a background daemon thread so gunicorn workers
        start accepting requests immediately — avoiding the worker timeout that
        causes infinite "Restarting" on HuggingFace Spaces.
        """
        import sys

        _skip_commands = {"migrate", "collectstatic", "makemigrations", "shell"}
        if len(sys.argv) > 1 and sys.argv[1] in _skip_commands:
            return

        import threading
        from core import ml

        t = threading.Thread(target=ml.load_model, daemon=True, name="ml-preload")
        t.start()

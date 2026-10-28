from django.apps import AppConfig


class CreditsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "credits"

    def ready(self):
        import credits.signals  # noqa: F401

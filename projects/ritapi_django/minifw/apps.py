from django.apps import AppConfig


class MinifwConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'minifw'

    def ready(self):
        import minifw.signals  # noqa: F401

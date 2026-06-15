from django.apps import AppConfig

class AthenasappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "AthenasApp"
    verbose_name = "Athenas"

    def ready(self):
        from . import signals  # registra señales (grupos/permisos + sincronización usuarios)

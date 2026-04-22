from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        # Register django-background-tasks handlers when Django loads (web + process_tasks worker).
        import orders.background_tasks  # noqa: F401

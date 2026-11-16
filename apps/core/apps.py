from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _sqlite_pragmas(sender, connection, **kwargs):
    """WAL + a generous busy timeout, applied to every new SQLite connection.

    The web process and the print worker share one database file; without WAL a
    write in the worker blocks every page load.
    """
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=20000;")


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        connection_created.connect(_sqlite_pragmas, dispatch_uid="core.sqlite_pragmas")
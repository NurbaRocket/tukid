from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Сайт TUKID'

    def ready(self):
        from .site_cache import connect_site_cache_signals
        connect_site_cache_signals()

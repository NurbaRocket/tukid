"""DJANGO_SETTINGS_MODULE=config.production for the HTTPS deployment."""
from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403

if DEBUG:  # noqa: F405
    raise ImproperlyConfigured('Production requires DJANGO_DEBUG=False.')

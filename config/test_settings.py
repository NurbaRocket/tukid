import os

os.environ.setdefault('DB_PASSWORD', 'test-only')
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-only-key-for-isolated-tests')
os.environ.setdefault('DJANGO_DEBUG', 'True')

from .settings import *  # noqa: F403

DEBUG = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'test-default'},
    'site_content': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'test-site-content'},
}


# Tests run in an isolated in-memory database and do not modify PostgreSQL data.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

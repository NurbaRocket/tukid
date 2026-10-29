"""Cache raw site data; language and active menu state remain request-specific."""

from copy import deepcopy
import logging
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches
from django.db import connections, transaction
from django.db.models import Prefetch
from django.db.models.signals import post_delete, post_save, post_migrate

from .models import MenuItem, Page, SiteSettings

logger = logging.getLogger(__name__)


def _content_cache():
    return caches[getattr(settings, 'SITE_CONTENT_CACHE_ALIAS', 'default')]


def _shared_cache_allowed(using):
    # Never publish uncommitted data, including data later rolled back.
    return not connections[using].in_atomic_block


def _generation_key(using):
    return f'core:site-content:v1:{using}:generation'


def invalidate_site_content(using='default'):
    # A generation change makes a concurrent reader's old cache write harmless.
    try:
        _content_cache().set(_generation_key(using), uuid4().hex, timeout=None)
    except Exception:
        # Cache loss must not prevent saving content. Existing entries have a
        # bounded lifetime even when invalidation storage is temporarily down.
        logger.warning('Site content cache invalidation failed', exc_info=True)


def _cached_data(name, loader, using='default'):
    if not _shared_cache_allowed(using):
        return loader()
    try:
        cache = _content_cache()
        generation_key = _generation_key(using)
        generation = cache.get(generation_key)
        if generation is None:
            cache.add(generation_key, uuid4().hex, timeout=None)
            generation = cache.get(generation_key)
        key = f'core:site-content:v1:{using}:{generation}:{name}'
        value = cache.get(key)
    except Exception:
        logger.warning('Site content cache read failed; using database', exc_info=True)
        return loader()
    if value is None:
        value = loader()
        try:
            cache.set(key, value, timeout=getattr(settings, 'SITE_CONTENT_CACHE_TIMEOUT', 300))
        except Exception:
            logger.warning('Site content cache write failed', exc_info=True)
    # Request-specific active/visible attributes must never mutate cached models.
    return deepcopy(value)


def get_site_settings(request=None):
    if request is not None and hasattr(request, '_site_settings'):
        return request._site_settings
    value = _cached_data('settings', lambda: SiteSettings.objects.first() or SiteSettings())
    if request is not None:
        request._site_settings = value
    return value


def _load_navigation():
    return {
        'unpublished': set(Page.objects.filter(is_published=False).values_list('slug', flat=True)),
        'roots': list(MenuItem.objects.filter(parent__isnull=True, is_visible=True)
            .select_related('page').prefetch_related(Prefetch(
                'children', queryset=MenuItem.objects.filter(is_visible=True).select_related('page'),
                to_attr='visible_children',
            ))),
    }


def get_site_navigation(request):
    if not hasattr(request, '_site_navigation'):
        request._site_navigation = _cached_data('navigation', _load_navigation)
    return request._site_navigation


def _content_changed(sender, using, **kwargs):
    transaction.on_commit(lambda: invalidate_site_content(using), using=using)


def _migrations_finished(sender, using, **kwargs):
    invalidate_site_content(using)


def connect_site_cache_signals():
    for model in (SiteSettings, MenuItem, Page):
        for signal, action in ((post_save, 'save'), (post_delete, 'delete')):
            signal.connect(_content_changed, sender=model, weak=False,
                dispatch_uid=f'core.site-cache.{model._meta.label_lower}.{action}')
    post_migrate.connect(_migrations_finished, weak=False,
        dispatch_uid='core.site-cache.post-migrate')

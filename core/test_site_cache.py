from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import caches
from django.db import connection, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from django.utils.translation import override

from .admin_dashboard import dashboard
from .context_processors import site_content
from .models import HomeSection, MenuItem, News, Page, SiteSettings
from .site_cache import (
    _cached_data, _generation_key, _shared_cache_allowed, get_site_navigation,
    get_site_settings, invalidate_site_content,
)


@override_settings(
    SITE_CONTENT_CACHE_ALIAS='default',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'site-content-regression-tests'}},
)
class SiteContentCacheTests(TestCase):
    def setUp(self):
        caches['default'].clear()
        self.factory = RequestFactory()

    def tearDown(self):
        caches['default'].clear()

    def request(self, path='/'):
        request = self.factory.get(path)
        request.resolver_match = resolve(path)
        return request

    def test_request_reuses_navigation_without_duplicate_page_queries(self):
        request = self.request()
        with CaptureQueriesContext(connection) as queries:
            get_site_navigation(request)
            site_content(request)
        page_queries = [q for q in queries if 'FROM "core_page"' in q['sql']]
        self.assertEqual(len(page_queries), 1)

    @patch('core.site_cache._shared_cache_allowed', return_value=True)
    def test_warm_settings_and_menu_need_no_queries_and_do_not_share_active_state(self, _):
        item = MenuItem.objects.create(title='Cache test home', route='home')
        first = site_content(self.request('/'))
        self.assertTrue(next(root for root in first['site_menu'] if root.pk == item.pk).active)
        with self.assertNumQueries(0):
            second = site_content(self.request('/news/'))
        self.assertFalse(next(root for root in second['site_menu'] if root.pk == item.pk).active)
        self.assertTrue(next(root for root in first['site_menu'] if root.pk == item.pk).active)

    @patch('core.site_cache._shared_cache_allowed', return_value=True)
    def test_raw_cached_values_are_localized_for_each_request(self, _):
        item = MenuItem.objects.create(title='Russian menu title', route='news',
            translations={'tr': {'title': 'Turkish menu title'}})
        with override('ru'):
            russian = site_content(self.request('/news/'))
            root = next(root for root in russian['site_menu'] if root.pk == item.pk)
            self.assertEqual(root.localized('title'), 'Russian menu title')
            self.assertEqual(root.url, '/news/')
        with override('tr'), self.assertNumQueries(0):
            turkish = site_content(self.request('/tr/news/'))
            root = next(root for root in turkish['site_menu'] if root.pk == item.pk)
            self.assertEqual(root.localized('title'), 'Turkish menu title')
            self.assertEqual(root.url, '/tr/news/')
            self.assertTrue(root.active)

    @patch('core.site_cache._shared_cache_allowed', return_value=True)
    def test_settings_menu_and_page_edits_invalidate_after_commit(self, _):
        item = MenuItem.objects.create(title='Cached menu', route='about')
        original = site_content(self.request())
        self.assertIn(item.pk, [root.pk for root in original['site_menu']])
        with self.captureOnCommitCallbacks(execute=True):
            settings = SiteSettings.objects.get()
            settings.email = 'updated@example.com'
            settings.save()
            item.title = 'Updated cached menu'
            item.save()
        updated = site_content(self.request())
        self.assertEqual(updated['site_settings'].email, 'updated@example.com')
        self.assertEqual(next(root for root in updated['site_menu'] if root.pk == item.pk).title,
            'Updated cached menu')
        with self.captureOnCommitCallbacks(execute=True):
            page = Page.objects.get(slug='about')
            page.is_published = False
            page.save()
        hidden = site_content(self.request())
        self.assertNotIn('about', hidden['published_pages'])
        self.assertNotIn(item.pk, [root.pk for root in hidden['site_menu']])
        with self.captureOnCommitCallbacks(execute=True):
            deleted_pk = item.pk
            item.delete()
        self.assertNotIn(deleted_pk, [root.pk for root in get_site_navigation(self.request())['roots']])

    def test_atomic_reads_bypass_cache_and_rollback_does_not_publish_changes(self):
        with patch('core.site_cache._shared_cache_allowed', return_value=True):
            old_email = get_site_settings().email
        self.assertFalse(_shared_cache_allowed('default'))
        try:
            with transaction.atomic():
                settings = SiteSettings.objects.get()
                settings.email = 'rolled-back@example.com'
                settings.save()
                self.assertEqual(get_site_settings().email, 'rolled-back@example.com')
                raise ValueError('rollback test')
        except ValueError:
            pass
        with patch('core.site_cache._shared_cache_allowed', return_value=True), self.assertNumQueries(0):
            self.assertEqual(get_site_settings().email, old_email)

    @patch('core.site_cache._shared_cache_allowed', return_value=True)
    def test_generation_prevents_late_old_reader_from_restoring_stale_content(self, _):
        def old_reader():
            invalidate_site_content()
            return 'old value'
        self.assertEqual(_cached_data('race-test', old_reader), 'old value')
        self.assertEqual(_cached_data('race-test', lambda: 'new value'), 'new value')
        self.assertEqual(_cached_data('race-test', lambda: self.fail('must be cached')), 'new value')

    def test_invalidation_is_deferred_until_commit(self):
        invalidate_site_content()
        generation = caches['default'].get(_generation_key('default'))
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            settings = SiteSettings.objects.get()
            settings.email = 'pending@example.com'
            settings.save()
        self.assertEqual(caches['default'].get(_generation_key('default')), generation)
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertNotEqual(caches['default'].get(_generation_key('default')), generation)

    @patch('core.site_cache._shared_cache_allowed', return_value=True)
    def test_cache_read_and_write_failures_fall_back_to_database(self, _):
        broken = Mock()
        broken.get.side_effect = OSError('cache unavailable')
        with patch('core.site_cache._content_cache', return_value=broken), self.assertLogs('core.site_cache'):
            self.assertEqual(get_site_settings().pk, 1)
        broken = Mock()
        broken.get.side_effect = ['generation', None]
        broken.set.side_effect = OSError('cache full')
        with patch('core.site_cache._content_cache', return_value=broken), self.assertLogs('core.site_cache'):
            self.assertEqual(get_site_settings().pk, 1)

    def test_hidden_events_block_does_not_query_events(self):
        HomeSection.objects.filter(key='events').update(is_visible=False)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any('FROM "core_event"' in q['sql'] for q in queries))

    def test_dashboard_uses_single_aggregate_for_news_counts(self):
        News.objects.create(title='Visible news', slug='cache-count-visible', body='Text', is_published=True)
        News.objects.create(title='Draft news', slug='cache-count-draft', body='Text')
        request = self.request('/admin/')
        request.user = get_user_model().objects.create_user('cache-news-viewer', is_staff=True)
        request.user.user_permissions.add(Permission.objects.get(codename='view_news'))
        with CaptureQueriesContext(connection) as queries:
            context = dashboard(request, {})
        card = context['overview_cards'][0]
        self.assertEqual((card['total'], card['live']), (2, 1))
        # One aggregate for counts, plus the separate scheduled-publication count.
        news_queries = [q for q in queries if 'FROM "core_news"' in q['sql']]
        self.assertEqual(len(news_queries), 2)
        self.assertTrue(any(task['title'] == 'Новости: черновики' and task['count'] == 1
            for task in context['editorial_tasks']))

from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BoardMember, Event, GalleryPhoto, HomeSection, MenuItem, News, Page, SiteSettings


def picture(name='photo.svg'):
    return SimpleUploadedFile(name, b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h10v10z"/></svg>', content_type='image/svg+xml')


class PublicContentTests(TestCase):
    def test_settings_update_header_footer_contacts_and_metadata(self):
        settings = SiteSettings.objects.get()
        settings.email = 'new@example.com'
        settings.phone = '+996 (555) 12-34-56'
        settings.whatsapp = '+996 (555) 12-34-56'
        settings.address = 'Новый адрес офиса'
        settings.site_description = 'Описание для поиска'
        settings.footer_text = 'Текст об организации'
        settings.header_logo = picture('brand.svg')
        settings.footer_logo = picture('footer.svg')
        settings.save()
        response = self.client.get('/')
        for text in ['new@example.com', 'Новый адрес офиса', 'Описание для поиска',
                     'Текст об организации', 'https://wa.me/996555123456',
                     settings.header_logo.url, settings.footer_logo.url]:
            self.assertContains(response, text)
        contacts = self.client.get(reverse('core:contacts'))
        self.assertContains(contacts, 'tel:+996555123456')
        settings.show_contact_bar = False
        settings.save()
        self.assertNotContains(self.client.get('/'), 'aria-label="Контактные данные"')

    def test_home_sections_are_editable_reorderable_and_hideable(self):
        hero = HomeSection.objects.get(key='home')
        hero.title = 'Новый заголовок главной'
        hero.image = picture()
        hero.link_label = 'Открыть события'
        hero.link_route = 'events'
        hero.save()
        news = HomeSection.objects.get(key='news')
        news.sort_order = 0
        news.save()
        hero.sort_order = 100
        hero.save()
        response = self.client.get('/')
        self.assertContains(response, hero.title)
        self.assertContains(response, hero.image.url)
        self.assertContains(response, 'href="/events/">Открыть события')
        content = response.content.decode()
        self.assertLess(content.index('id="news"'), content.index('id="home"'))
        hero.is_visible = False
        hero.save()
        self.assertNotContains(self.client.get('/'), hero.title)

    def test_gallery_and_publication_photos_render_in_all_places(self):
        community = HomeSection.objects.get(key='community')
        community.is_visible = True
        community.save()
        gallery = GalleryPhoto.objects.first()
        gallery.image = picture('gallery.svg')
        gallery.save()
        news = News.objects.create(title='С фотографией', slug='with-photo', body='<p>Текст</p>',
            image=picture('news.svg'), is_published=True)
        event = Event.objects.create(title='Встреча с фотографией', slug='with-photo',
            image=picture('event.svg'), starts_at=timezone.now()+timedelta(days=1), is_published=True)
        for route, paths in [
            ('/', [gallery.image.url, news.image.url, event.image.url]),
            (reverse('core:news'), [news.image.url]),
            (news.get_absolute_url(), [news.image.url]),
            (reverse('core:events'), [event.image.url]),
            (event.get_absolute_url(), [event.image.url]),
        ]:
            response = self.client.get(route)
            for path in paths:
                self.assertContains(response, path)

    def test_custom_pages_and_menu_hide_drafts(self):
        page = Page.objects.create(title='Партнёры', slug='partners', body='<h2>Партнёрство</h2>', is_published=True)
        menu = MenuItem.objects.create(title='Новый раздел', page=page)
        self.assertContains(self.client.get(page.get_absolute_url()), '<h2>Партнёрство</h2>')
        self.assertContains(self.client.get('/'), menu.title)
        page.is_published = False
        page.save()
        self.assertEqual(self.client.get(page.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get('/'), menu.title)
        mission = Page.objects.get(slug='mission')
        mission.is_published = False
        mission.save()
        self.assertEqual(self.client.get(reverse('core:mission')).status_code, 404)
        self.assertNotContains(self.client.get('/'), 'href="/about/mission/"')

    def test_board_people_require_publication(self):
        public = BoardMember.objects.create(name='Имя председателя', position='Председатель',
            biography='<p>Биография</p>', photo=picture(), is_published=True)
        hidden = BoardMember.objects.create(name='Неопубликованный участник', position='Советник')
        response = self.client.get(reverse('core:board'))
        self.assertContains(response, public.name)
        self.assertContains(response, public.photo.url)
        self.assertNotContains(response, hidden.name)

    def test_rich_text_preserves_formatting_and_removes_active_content(self):
        page = Page.objects.get(slug='about')
        page.body = '<h2>Заголовок</h2><p>Наш <strong>текст</strong><script>alert(19)</script><img src=x onerror=alert(20)><a href="javascript:alert(21)">Ссылка</a></p>'
        page.save()
        response = self.client.get(page.get_absolute_url())
        self.assertContains(response, '<strong>текст</strong>')
        self.assertNotContains(response, 'alert(19)')
        self.assertNotContains(response, 'onerror')
        self.assertNotContains(response, 'javascript:')

    def test_menu_model_rejects_invalid_links_and_nested_submenus(self):
        parent = MenuItem.objects.create(title='Родитель', route='home')
        child = MenuItem.objects.create(title='Дочерний', parent=parent, route='about')
        for item in [
            MenuItem(title='Третий уровень', parent=child, route='about'),
            MenuItem(title='Два адреса', route='about', external_url='https://example.com'),
            MenuItem(title='Опасный адрес', external_url='javascript:alert(1)'),
            MenuItem(title='Нет адреса'),
        ]:
            with self.subTest(title=item.title), self.assertRaises(ValidationError):
                item.full_clean()
        parent.parent = child
        with self.assertRaises(ValidationError):
            parent.full_clean()


class AdminWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser('admin-cms', 'admin@example.com', 'test-password')

    def test_login_dashboard_and_all_cms_forms(self):
        response = self.client.get(reverse('admin:login'))
        self.assertContains(response, 'core/images/tukid_logo_text.svg')
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Ваш сайт под контролем')
        self.assertContains(response, 'core/css/admin.css')
        self.assertContains(response, 'core/images/tukid_logo_text.svg')
        for name in ['galleryphoto', 'boardmember', 'menuitem', 'homesection', 'homedirection', 'page', 'news', 'event', 'member', 'activitysector', 'newstag']:
            for suffix in ['changelist', 'add']:
                with self.subTest(model=name, view=suffix):
                    expected = 403 if name == 'homesection' and suffix == 'add' else 200
                    self.assertEqual(self.client.get(reverse(f'admin:core_{name}_{suffix}')).status_code, expected)
        settings = SiteSettings.objects.get()
        self.assertEqual(self.client.get(reverse('admin:core_sitesettings_changelist')).status_code, 302)
        self.assertContains(self.client.get(reverse('admin:core_sitesettings_change', args=[settings.pk])), 'Контакты')
        self.assertEqual(self.client.get(reverse('admin:core_sitesettings_add')).status_code, 403)
        for route in ['admin:auth_user_changelist', 'admin:auth_user_add', 'admin:auth_group_add']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_admin_logo_tracks_public_branding_and_editor_widget_is_local(self):
        settings = SiteSettings.objects.get()
        settings.header_logo = picture('admin-brand.svg')
        settings.save()
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(reverse('admin:index')), settings.header_logo.url)
        response = self.client.get(reverse('admin:core_news_add'))
        self.assertContains(response, '<trix-editor')
        self.assertContains(response, 'unfold/forms/js/trix/trix.js')

    def test_staff_dashboard_and_sidebar_respect_permissions(self):
        staff = get_user_model().objects.create_user('news-reader', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_news'))
        self.client.force_login(staff)
        News.objects.create(title='Черновик редактора', slug='draft-dashboard', body='Текст')
        response = self.client.get(reverse('admin:index'))
        self.assertEqual([card['title'] for card in response.context['overview_cards']], ['Новости'])
        self.assertEqual(response.context['quick_links'], [])
        self.assertNotContains(response, reverse('admin:auth_user_changelist'))
        self.assertNotContains(response, reverse('admin:core_sitesettings_changelist'))
        self.assertNotContains(response, reverse('admin:core_news_add'))
        self.assertEqual(self.client.get(reverse('admin:core_sitesettings_change', args=[1])).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:core_news_add')).status_code, 403)
        article = News.objects.get(slug='draft-dashboard')
        change_url = reverse('admin:core_news_change', args=[article.pk])
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.post(change_url, {'title': 'Изменён'}).status_code, 403)
        action_response = self.client.post(reverse('admin:core_news_changelist'), {
            'action': 'publish', '_selected_action': [article.pk],
        })
        self.assertIn(action_response.status_code, [200, 302])
        article.refresh_from_db()
        self.assertFalse(article.is_published)

    def test_publication_action_logs_changes(self):
        self.client.force_login(self.superuser)
        news = News.objects.create(title='Черновик', slug='action-draft', body='Текст')
        response = self.client.post(reverse('admin:core_news_changelist'), {
            'action': 'publish', '_selected_action': [news.pk],
        })
        self.assertEqual(response.status_code, 302)
        news.refresh_from_db()
        self.assertTrue(news.is_published)
        self.assertTrue(self.superuser.logentry_set.filter(object_id=str(news.pk)).exists())

    def test_admin_can_save_site_settings_and_edit_main_section(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin:core_sitesettings_change', args=[1]), {
            'name': 'TUKID', 'organization_name': 'Общественное объединение TUKID',
            'site_description': 'Новое описание сайта', 'email': 'cms@example.com',
            'phone': '+996555123456', 'whatsapp': '+996555123456', 'address': 'Адрес из админки',
            'header_logo': picture('new-logo.svg'), 'copyright_text': 'Все права защищены.',
            'show_contact_bar': 'on', '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        settings = SiteSettings.objects.get()
        response = self.client.get('/')
        self.assertContains(response, 'cms@example.com')
        self.assertContains(response, settings.header_logo.url)
        hero = HomeSection.objects.get(key='home')
        response = self.client.post(reverse('admin:core_homesection_change', args=[hero.pk]), {
            'eyebrow': 'TUKID', 'title': 'Заголовок через админку', 'description': 'Описание',
            'items_limit': 3, 'sort_order': 0, 'is_visible': 'on', '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get('/'), 'Заголовок через админку')

    def test_settings_can_be_viewed_without_editing_permission(self):
        reader = get_user_model().objects.create_user('settings-reader', is_staff=True)
        reader.user_permissions.add(Permission.objects.get(codename='view_sitesettings'))
        self.client.force_login(reader)
        url = reverse('admin:core_sitesettings_change', args=[1])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {'name': 'Недопустимо'}).status_code, 403)
        self.assertEqual(SiteSettings.objects.get().name, 'TUKID')

    def test_reserved_pages_and_singleton_are_protected(self):
        self.client.force_login(self.superuser)
        page = Page.objects.get(slug='about')
        self.assertFalse(admin.site._registry[Page].has_delete_permission(self.client.request().wsgi_request, page))
        self.assertEqual(self.client.post(reverse('admin:core_sitesettings_delete', args=[1]), {'post': 'yes'}).status_code, 403)
        self.assertEqual(SiteSettings.objects.count(), 1)
        with self.assertRaises(ValidationError):
            SiteSettings(id=2).full_clean()

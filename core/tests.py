from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ActivitySector, Event, Member, News, NewsTag, Page
from .validators import validate_logo


class HomePageTests(TestCase):
    def test_home_features_published_members_and_latest_tukid_news_only(self):
        members = [Member.objects.create(
            name=f'Company {i:02}', slug=f'company-{i}', is_published=True,
            logo=SimpleUploadedFile(f'logo-{i}.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
        ) for i in range(10)]
        hidden = Member.objects.create(name='Hidden company', slug='hidden-company')
        now = timezone.now()
        articles = [News.objects.create(
            title=f'Article {i}', slug=f'article-{i}', body='Content', is_published=True,
            published_at=now-timedelta(days=i+1),
        ) for i in range(5)]
        News.objects.create(title='Future', slug='future', body='Content', is_published=True, published_at=now+timedelta(days=1))
        News.objects.create(title='Draft', slug='draft', body='Content')
        News.objects.create(title='Industry', slug='industry', body='Content', is_published=True, is_tukid_news=False)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['home_member_logos']), members)
        self.assertEqual(list(response.context['home_news']), articles[:3])
        self.assertNotContains(response, hidden.name)

    def test_home_prefers_nearest_upcoming_and_ongoing_events(self):
        now = timezone.now()
        ongoing = Event.objects.create(title='Ongoing', slug='ongoing', starts_at=now-timedelta(hours=1), ends_at=now+timedelta(hours=1), is_published=True)
        future = [Event.objects.create(title=f'Future {i}', slug=f'future-{i}', starts_at=now+timedelta(days=i+1), is_published=True) for i in range(4)]
        Event.objects.create(title='Past', slug='past', starts_at=now-timedelta(days=1), is_published=True)
        Event.objects.create(title='Draft', slug='draft', starts_at=now)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['home_events'], [ongoing, *future[:2]])

    def test_home_keeps_upcoming_section_empty_when_only_past_events_exist(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['home_events'], [])
        now = timezone.now()
        older = Event.objects.create(title='Older', slug='older', starts_at=now-timedelta(days=5), is_published=True)
        recent = Event.objects.create(title='Recent', slug='recent', starts_at=now-timedelta(days=1), is_published=True)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['home_events'], [])
        self.assertNotContains(response, older.title)
        self.assertNotContains(response, recent.title)


class MenuPageTests(TestCase):
    def test_all_menu_destinations_render(self):
        for name in [
            'about', 'mission', 'board', 'members', 'news', 'tukid_news',
            'events', 'upcoming_events', 'past_events', 'career', 'contacts',
        ]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'core:{name}')).status_code, 200)

    def test_information_page_is_editable_and_escapes_html(self):
        page = Page.objects.get(slug='mission')
        page.body = 'Наша миссия\n<script>alert(1)</script>'
        page.save()
        response = self.client.get(reverse('core:mission'))
        self.assertContains(response, 'Наша миссия')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_membership_page_is_available_from_menu(self):
        response = self.client.get(reverse('core:members'))
        self.assertContains(response, 'href="/membership/">Стать членом объединения</a>')
        self.assertEqual(self.client.get(reverse('core:membership')).status_code, 200)

    def test_admin_forms_render_for_all_new_models(self):
        user = get_user_model().objects.create_superuser('editor', 'editor@example.com', 'test-password')
        self.client.force_login(user)
        for name in ['member', 'activitysector', 'newstag', 'news', 'event', 'page']:
            with self.subTest(model=name):
                response = self.client.get(reverse(f'admin:core_{name}_add'))
                self.assertEqual(response.status_code, 200)

    def test_admin_can_create_a_published_member_with_logo_and_tags(self):
        user = get_user_model().objects.create_superuser('manager', 'manager@example.com', 'test-password')
        self.client.force_login(user)
        sector = ActivitySector.objects.create(name='Услуги', slug='services')
        tag = NewsTag.objects.create(name='Компания', slug='company')
        logo = SimpleUploadedFile('logo.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>', content_type='image/svg+xml')
        response = self.client.post(reverse('admin:core_member_add'), {
            'name': 'Компания', 'slug': 'company', 'logo': logo, 'description': 'Описание компании',
            'city': 'Бишкек', 'address': 'Адрес', 'phone': '+996555123456', 'email': 'office@example.com',
            'website': 'https://example.com', 'director_name': 'Директор', 'sort_order': '0',
            'sectors': [sector.pk], 'news_tag': tag.pk, 'is_published': 'on', '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(slug='company')
        self.assertEqual(member.news_tag, tag)
        self.assertEqual(list(member.sectors.all()), [sector])
        self.assertContains(self.client.get(member.get_absolute_url()), member.logo.url)


class MemberDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sector = ActivitySector.objects.create(name='Строительство', slug='construction')
        other_sector = ActivitySector.objects.create(name='Строительные материалы', slug='materials')
        cls.tag = NewsTag.objects.create(name='Компания Альфа', slug='alpha')
        cls.member = Member.objects.create(
            name='Альфа', slug='alpha', city='Бишкек', is_published=True,
            director_name='Директор компании', news_tag=cls.tag,
            address='Адрес компании', phone='+996 (555) 12-34-56', email='office@example.com',
        )
        cls.member.sectors.set([cls.sector, other_sector])
        cls.hidden = Member.objects.create(name='Закрытый черновик', slug='hidden')
        cls.article = News.objects.create(title='Новость компании', slug='alpha-news', body='Текст', is_published=True)
        cls.article.tags.add(cls.tag)
        News.objects.create(title='Посторонняя новость', slug='other-news', body='Текст', is_published=True)
        future = News.objects.create(
            title='Будущая новость компании', slug='future-news', body='Текст',
            is_published=True, published_at=timezone.now() + timedelta(days=2),
        )
        future.tags.add(cls.tag)

    def test_drafts_are_hidden_from_list_and_detail(self):
        response = self.client.get(reverse('core:members'))
        self.assertContains(response, self.member.name)
        self.assertNotContains(response, self.hidden.name)
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)

    def test_search_across_multiple_matching_sectors_has_no_duplicates(self):
        response = self.client.get(reverse('core:members'), {'q': 'Строи'})
        self.assertEqual(list(response.context['page_obj']), [self.member])

    def test_sector_and_city_filters(self):
        response = self.client.get(reverse('core:members'), {'sector': self.sector.slug, 'q': 'Бишкек'})
        self.assertEqual(list(response.context['page_obj']), [self.member])
        response = self.client.get(reverse('core:members'), {'sector': 'unknown'})
        self.assertEqual(list(response.context['page_obj']), [])

    def test_detail_shows_contacts_and_only_related_published_news(self):
        response = self.client.get(self.member.get_absolute_url())
        self.assertContains(response, 'tel:+996555123456')
        self.assertContains(response, 'mailto:office@example.com')
        self.assertContains(response, self.member.director_name)
        self.assertContains(response, self.article.title)
        self.assertNotContains(response, 'Посторонняя новость')
        self.assertNotContains(response, 'Будущая новость компании')

    def test_pagination_preserves_filters(self):
        for number in range(13):
            member = Member.objects.create(name=f'Paged {number:02}', slug=f'paged-{number}', is_published=True)
            member.sectors.add(self.sector)
        response = self.client.get(reverse('core:members'), {'q': 'Paged', 'sector': self.sector.slug})
        self.assertEqual(response.context['page_obj'].paginator.count, 13)
        self.assertContains(response, 'q=Paged&amp;sector=construction&amp;page=2')
        response = self.client.get(reverse('core:members'), {'q': 'Paged', 'page': 2})
        self.assertEqual(len(response.context['page_obj']), 1)

    def test_svg_logo_can_be_saved_and_rendered(self):
        self.member.logo = SimpleUploadedFile(
            'company.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h10v10z"/></svg>',
            content_type='image/svg+xml',
        )
        self.member.full_clean()
        self.member.save()
        self.assertContains(self.client.get(self.member.get_absolute_url()), self.member.logo.url)
        self.assertTrue(self.member.logo.read().startswith(b'<svg'))


class PublicationTests(TestCase):
    def test_news_visibility_association_category_and_tags(self):
        tag = NewsTag.objects.create(name='Партнёр', slug='partner')
        public = News.objects.create(title='Публичная', slug='public', body='Текст', is_published=True)
        public.tags.add(tag)
        other = News.objects.create(title='Отраслевая', slug='industry', body='Текст', is_published=True, is_tukid_news=False)
        draft = News.objects.create(title='Черновик', slug='draft', body='Текст')
        future = News.objects.create(
            title='Запланированная', slug='scheduled', body='Текст', is_published=True,
            published_at=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('core:news'))
        self.assertEqual(set(response.context['page_obj']), {public, other})
        response = self.client.get(reverse('core:tukid_news'))
        self.assertEqual(list(response.context['page_obj']), [public])
        response = self.client.get(reverse('core:news'), {'tag': tag.slug})
        self.assertEqual(list(response.context['page_obj']), [public])
        for article in [draft, future]:
            self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse('core:news'), {'tag': 'unknown'}).status_code, 404)
        self.assertContains(self.client.get(public.get_absolute_url()), public.title)

    def test_events_partition_into_upcoming_ongoing_and_past(self):
        now = timezone.now()
        future = Event.objects.create(title='Будущее', slug='future', starts_at=now + timedelta(days=2), is_published=True)
        ongoing = Event.objects.create(
            title='Текущее', slug='ongoing', starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1), is_published=True,
        )
        past = Event.objects.create(title='Прошедшее', slug='past', starts_at=now - timedelta(days=2), is_published=True)
        ended = Event.objects.create(
            title='Завершённое', slug='ended', starts_at=now - timedelta(days=3),
            ends_at=now - timedelta(days=1), is_published=True,
        )
        draft = Event.objects.create(title='Черновик', slug='draft', starts_at=now)
        response = self.client.get(reverse('core:upcoming_events'))
        self.assertEqual(set(response.context['page_obj']), {future, ongoing})
        response = self.client.get(reverse('core:past_events'))
        self.assertEqual(set(response.context['page_obj']), {past, ended})
        response = self.client.get(reverse('core:events'))
        self.assertEqual(set(response.context['page_obj']), {future, ongoing, past, ended})
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.assertContains(self.client.get(past.get_absolute_url()), 'Мероприятие завершено.')

    def test_event_cannot_end_before_it_starts(self):
        now = timezone.now()
        event = Event(title='Ошибка дат', slug='invalid', starts_at=now, ends_at=now - timedelta(hours=1))
        with self.assertRaises(ValidationError):
            event.full_clean()


class LogoValidationTests(TestCase):
    def test_standard_svg_export_with_public_doctype_is_accepted(self):
        logo = SimpleUploadedFile('logo.svg', (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
            b'"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
            b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h10v10z"/></svg>'
        ))
        validate_logo(logo)
        self.assertEqual(logo.tell(), 0)

    def test_unsafe_or_invalid_uploads_are_rejected(self):
        for filename, content in [
            ('script.svg', b'<svg><script>alert(1)</script></svg>'),
            ('event.svg', b'<svg onload="alert(1)"/>'),
            ('external.svg', b'<svg><image href="https://example.com/image.png"/></svg>'),
            ('entity.svg', b'<!DOCTYPE svg [<!ENTITY test "value">]><svg/>'),
            ('stylesheet.svg', b'<?xml-stylesheet href="https://example.com/style.css"?><svg/>'),
            ('style.svg', b'<svg><style>@import "https://example.com/style.css";</style></svg>'),
            ('paint.svg', b'<svg><path fill="url(https://example.com/paint.svg)"/></svg>'),
            ('animation.svg', b'<svg><set attributeName="href" to="javascript:alert(1)"/></svg>'),
            ('invalid.svg', b'<svg>'),
            ('fake.png', b'<html>Not an image</html>'),
            ('large.svg', b'x' * (2 * 1024 * 1024 + 1)),
        ]:
            with self.subTest(filename=filename), self.assertRaises(ValidationError):
                validate_logo(SimpleUploadedFile(filename, content))

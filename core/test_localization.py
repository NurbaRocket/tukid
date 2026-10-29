from datetime import date
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils.translation import get_language, gettext, override

from .admin import MeetingPhotoInline
from .career_constants import CAREER_CONSENT
from .localization import CONTENT_FIELDS
from .membership_constants import MEMBERSHIP_DECLARATION
from .membership_pdf import build_membership_pdf
from .models import (
    ActivitySector, CareerApplication, MeetingPhoto, Member, MembershipApplication,
    News, OfficialMeeting, Page, SiteSettings, Vacancy,
)
from .test_career import applicant
from .test_membership import applicant_data, pdf_text


class PublicLocalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Member.objects.create(
            name='Компания на русском', slug='language-company', is_published=True,
            city='Бишкек', translations={'ky': {'name': 'Кыргыз компаниясы'}, 'tr': {'name': 'Türk şirketi'}},
        )
        cls.news = News.objects.create(
            title='Русская новость', slug='language-news', is_published=True,
            summary='Русское описание', body='<p>Русский текст.</p>',
            translations={'ky': {'title': 'Кыргызча жаңылык'}, 'tr': {
                'title': 'Türkçe haber', 'body': '<p>Haber metni</p><script>alert(1)</script>',
                'meta_description': 'Türkçe açıklama',
            }},
        )

    def test_urls_navigation_assets_and_document_language(self):
        for language, prefix in [('ru', ''), ('ky', '/ky'), ('tr', '/tr')]:
            with self.subTest(language=language), override(language):
                self.assertEqual(reverse('core:news'), prefix + '/news/')
                response = self.client.get(prefix + '/')
                self.assertContains(response, f'<html lang="{language}">')
                self.assertEqual(response['Content-Language'], language)
                self.assertContains(response, 'action="/i18n/setlang/"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(response, f'href="{prefix}/news/"')
                self.assertContains(response, 'href="/static/core/css/custom.css"')
                for code in ['ru', 'ky', 'tr']:
                    self.assertContains(response, f'name="language" value="{code}"')
                    self.assertContains(response, f'hreflang="{code}"')
                if language != 'ru':
                    self.assertNotEqual(gettext('Все новости'), 'Все новости')
                    self.assertContains(response, gettext('Все новости'))

    def test_language_switch_keeps_detail_and_query_and_rejects_external_next(self):
        response = self.client.post('/i18n/setlang/', {
            'language': 'tr', 'next': '/ky/news/posts/language-news/?source=menu&page=2',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/tr/news/posts/language-news/?source=menu&page=2')
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'tr')
        response = self.client.post('/i18n/setlang/', {'language': 'ru', 'next': '/tr/members/?page=2'})
        self.assertEqual(response['Location'], '/members/?page=2')
        response = self.client.post('/i18n/setlang/', {'language': 'tr', 'next': 'https://example.com/private'})
        self.assertEqual(response['Location'], '/tr/')
        response = self.client.post('/i18n/setlang/', {'language': 'en', 'next': '/news/'})
        self.assertEqual(response['Location'], '/news/')
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        self.assertEqual(Client(enforce_csrf_checks=True).post(
            '/i18n/setlang/', {'language': 'tr', 'next': '/'},
        ).status_code, 403)

    def test_content_fallback_seo_and_html_sanitization(self):
        response = self.client.get('/tr/news/posts/language-news/')
        self.assertContains(response, 'Türkçe haber')
        self.assertContains(response, 'Русское описание')
        self.assertContains(response, '<p>Haber metni</p>', html=True)
        self.assertContains(response, 'content="Türkçe açıklama"')
        self.assertNotContains(response, 'alert(1)')
        for language, expected in [('ru', 'Русская новость'), ('ky', 'Кыргызча жаңылык'), ('tr', 'Türkçe haber')]:
            with override(language):
                self.assertEqual(self.news.i18n['title'], expected)
                self.assertEqual(self.news.i18n['summary'], 'Русское описание')
        self.news.translations = {'ky': {'title': '   '}, 'tr': None}
        self.assertEqual(self.news.localized('title', 'ky'), self.news.title)
        self.assertEqual(self.news.localized('title', 'tr'), self.news.title)

    def test_translated_member_and_vacancy_search_including_related_fields(self):
        sector = ActivitySector.objects.create(
            name='Строительство', slug='language-sector', translations={'ky': {'name': 'Курулуш'}},
        )
        self.company.sectors.add(sector)
        vacancy = Vacancy.objects.create(
            title='Менеджер', slug='language-vacancy', company=self.company,
            description='Описание', is_published=True,
            translations={'tr': {'title': 'Satış uzmanı', 'location': 'Ankara'}},
        )
        for query in ['Кыргыз компаниясы', 'Курулуш', 'Компания на русском']:
            with self.subTest(query=query):
                response = self.client.get('/ky/members/', {'q': query})
                self.assertEqual(list(response.context['page_obj']), [self.company])
        for query in ['Satış', 'Türk şirketi', 'Ankara']:
            with self.subTest(query=query):
                response = self.client.get('/tr/career/', {'q': query})
                self.assertEqual(list(response.context['page_obj']), [vacancy])

    def test_forms_errors_and_career_submission_preserve_selected_language(self):
        for language in ['ky', 'tr']:
            with self.subTest(language=language), override(language):
                response = self.client.get(f'/{language}/career/')
                label = str(response.context['form'].fields['full_name'].label)
                self.assertEqual(label, gettext('Имя и фамилия'))
                self.assertNotEqual(label, 'Имя и фамилия')
                response = self.client.post(f'/{language}/career/', applicant(full_name='', consent_accepted=''))
                self.assertTrue(response.context['form'].errors)
                self.assertNotContains(response, 'Обязательное поле.')
                response = self.client.post(f'/{language}/membership/', {
                    **applicant_data(), 'declaration_accepted': '',
                })
                self.assertIn('declaration_accepted', response.context['form'].errors)
                self.assertNotIn('Подтвердите заявление о вступлении.', str(response.context['form'].errors))
                response = self.client.post(f'/{language}/career/', applicant())
                self.assertEqual(response['Location'], f'/{language}/career/sent/')
                application = CareerApplication.objects.get(language=language)
                self.assertEqual(application.consent_text, str(CAREER_CONSENT))
                with override('ru'):
                    self.assertNotEqual(application.consent_text, str(CAREER_CONSENT))

    def test_membership_language_pdf_and_russian_admin_rebuild(self):
        for language in ['ky', 'tr']:
            with self.subTest(language=language), override(language):
                response = self.client.post(f'/{language}/membership/', applicant_data())
                self.assertEqual(response['Location'], f'/{language}/membership/sent/')
                application = MembershipApplication.objects.get(language=language)
                original = bytes(application.submitted_pdf)
                self.assertEqual(application.declaration_text, str(MEMBERSHIP_DECLARATION))
                heading = gettext('ЗАЯВКА НА ЧЛЕНСТВО')
                self.assertNotEqual(heading, 'ЗАЯВКА НА ЧЛЕНСТВО')
                self.assertIn(heading, pdf_text(original))
                with override('ru'):
                    rebuilt = build_membership_pdf(application, SiteSettings.objects.get())
                    self.assertEqual(get_language(), 'ru')
                    self.assertIn(heading, pdf_text(rebuilt))
                application.refresh_from_db()
                self.assertEqual(bytes(application.submitted_pdf), original)

    def test_starter_translation_keeps_original_and_existing_editor_translation(self):
        page = Page.objects.get(slug='mission')
        original = page.body
        self.assertIn('членов Ассоциации', original)
        self.assertIn('Биздин миссиябыз', page.localized('body', 'ky'))
        self.assertIn('Misyonumuz', page.localized('body', 'tr'))
        page.translations['ky']['title'] = 'Редактордун өз аталышы'
        page.save(update_fields=['translations'])
        migration = import_module('core.migrations.0017_initial_content_translations')
        migration.seed_translations(apps, connection.schema_editor())
        page.refresh_from_db()
        self.assertEqual(page.body, original)
        self.assertEqual(page.translations['ky']['title'], 'Редактордун өз аталышы')


class AdminLocalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('language-admin', 'admin@example.com', 'test-password')

    def setUp(self):
        self.client.force_login(self.user)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'tr'

    def test_admin_stays_russian_with_foreign_cookie_and_browser_language(self):
        for path in ['/admin/', '/admin/core/page/', '/admin/core/page/add/']:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_ACCEPT_LANGUAGE='tr')
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<html lang="ru"')
                self.assertEqual(response['Content-Language'], 'ru')
        response = self.client.get('/admin/core/page/add/')
        self.assertContains(response, 'Перевод на кыргызский')
        self.assertContains(response, 'Перевод на турецкий')
        self.assertContains(response, 'name="title_ky"')
        self.assertContains(response, 'name="title_tr"')

    def test_all_content_models_expose_translation_fields_with_source_validation(self):
        request = RequestFactory().get('/admin/')
        request.user = self.user
        with override('ru'):
            for model_name, fields in CONTENT_FIELDS.items():
                with self.subTest(model=model_name):
                    model = apps.get_model('core', model_name)
                    handler = MeetingPhotoInline(OfficialMeeting, admin.site) if model is MeetingPhoto else admin.site._registry[model]
                    form = handler.get_formset(request).form if model is MeetingPhoto else handler.get_form(request)
                    visible = flatten_fieldsets(handler.get_fieldsets(request))
                    for name in fields:
                        for language in ['ky', 'tr']:
                            key = f'{name}_{language}'
                            self.assertIn(key, form.base_fields)
                            self.assertEqual(visible.count(key), 1)
                            self.assertFalse(form.base_fields[key].required)
                            source = model._meta.get_field(name)
                            self.assertEqual(form.base_fields[key].max_length, getattr(source, 'max_length', None))
                            if name in form.base_fields:
                                self.assertIs(type(form.base_fields[key].widget), type(form.base_fields[name].widget))

    def test_admin_save_preserves_russian_and_other_translations_and_can_clear_field(self):
        page = Page.objects.create(title='Русский заголовок', slug='language-page', body='<p>Русский текст.</p>',
            translations={'ky': {'title': 'Баштапкы аталыш', 'body': '<p>Кыргызча текст.</p>'}, 'tr': {'title': 'Başlık'}})
        url = reverse('admin:core_page_change', args=[page.pk])
        data = {'title': page.title, 'slug': page.slug, 'body': page.body, 'is_published': 'on', 'title_ky': 'Жаңы аталыш'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.title, data['title'])
        self.assertEqual(page.body, data['body'])
        self.assertEqual(page.translations['ky']['title'], 'Жаңы аталыш')
        self.assertEqual(page.translations['ky']['body'], '<p>Кыргызча текст.</p>')
        self.assertEqual(page.translations['tr']['title'], 'Başlık')
        response = self.client.post(url, {**data, 'title_ky': ''})
        self.assertEqual(response.status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.localized('title', 'ky'), page.title)
        response = self.client.post(url, {**data, 'title_ky': 'x'*201})
        self.assertEqual(response.status_code, 200)
        self.assertIn('title_ky', response.context['adminform'].form.errors)

    def test_meeting_photo_inline_saves_prefixed_translation_fields(self):
        meeting = OfficialMeeting.objects.create(title='Встреча', slug='language-meeting', date=date.today())
        photo = MeetingPhoto(meeting=meeting, caption='Русская подпись')
        photo.image.save('language.svg', ContentFile(b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'))
        request = RequestFactory().get('/admin/')
        request.user = self.user
        inline = MeetingPhotoInline(OfficialMeeting, admin.site)
        formset_class = inline.get_formset(request, meeting)
        prefix = formset_class.get_default_prefix()
        data = {
            f'{prefix}-TOTAL_FORMS': '1', f'{prefix}-INITIAL_FORMS': '1',
            f'{prefix}-0-id': str(photo.pk), f'{prefix}-0-meeting': str(meeting.pk),
            f'{prefix}-0-caption': photo.caption, f'{prefix}-0-sort_order': '0',
            f'{prefix}-0-caption_ky': 'Кыргызча сүрөт жазуусу', f'{prefix}-0-image_alt_tr': 'Toplantı fotoğrafı',
        }
        formset = formset_class(data=data, instance=meeting, prefix=prefix)
        self.assertTrue(formset.is_valid(), (formset.errors, formset.non_form_errors()))
        formset.save()
        photo.refresh_from_db()
        self.assertEqual(photo.caption, 'Русская подпись')
        self.assertEqual(photo.localized('caption', 'ky'), 'Кыргызча сүрөт жазуусу')
        self.assertEqual(photo.localized('image_alt', 'tr'), 'Toplantı fotoğrafı')

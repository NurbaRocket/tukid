from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from .models import MeetingPhoto, OfficialMeeting, Page


class ReadonlyTranslationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user('translation-viewer', is_staff=True)
        cls.viewer.user_permissions.set(Permission.objects.filter(
            content_type__app_label='core',
            codename__in=['view_page', 'view_officialmeeting', 'view_meetingphoto'],
        ))
        cls.page = Page.objects.create(
            title='Исходный заголовок', slug='readonly-translations', body='Исходный текст',
            translations={
                'ky': {'title': 'Кыргызча аталыш', 'body': 'Кыргызча текст'},
                'tr': {'title': 'Türkçe başlık', 'body': '<img src=x onerror=alert(71)>'},
            },
        )
        cls.meeting = OfficialMeeting.objects.create(
            title='Встреча', slug='readonly-meeting', date=date(2026, 1, 1),
        )
        cls.photo = MeetingPhoto(
            meeting=cls.meeting, caption='Русская подпись',
            translations={'ky': {'caption': 'Кыргызча сүрөт жазуусу'},
                          'tr': {'image_alt': 'Türkçe resim açıklaması'}},
        )
        cls.photo.image.save('readonly.svg', ContentFile(b'<svg xmlns="http://www.w3.org/2000/svg"/>'))

    def setUp(self):
        self.client.force_login(self.viewer)

    def test_viewer_sees_saved_translations_without_editable_inputs(self):
        response = self.client.get(reverse('admin:core_page_change', args=[self.page.pk]))
        self.assertEqual(response.status_code, 200)
        for text in ['Кыргызча аталыш', 'Кыргызча текст', 'Türkçe başlık',
                     'Перевод на кыргызский', 'Перевод на турецкий']:
            self.assertContains(response, text)
        self.assertNotContains(response, 'name="title_ky"')
        self.assertNotContains(response, 'name="title_tr"')

    def test_readonly_translation_escapes_stored_html(self):
        response = self.client.get(reverse('admin:core_page_change', args=[self.page.pk]))
        self.assertContains(response, '&lt;img src=x onerror=alert(71)&gt;')
        self.assertNotContains(response, '<img src=x onerror=alert(71)>')

    def test_viewer_sees_inline_translations(self):
        response = self.client.get(reverse('admin:core_officialmeeting_change', args=[self.meeting.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Кыргызча сүрөт жазуусу')
        self.assertContains(response, 'Türkçe resim açıklaması')
        self.assertNotContains(response, 'name="photos-0-caption_ky"')

    def test_view_permission_cannot_change_translation(self):
        response = self.client.post(reverse('admin:core_page_change', args=[self.page.pk]), {
            'title_tr': 'Attempted overwrite',
        })
        self.assertEqual(response.status_code, 403)
        self.page.refresh_from_db()
        self.assertEqual(self.page.translations['tr']['title'], 'Türkçe başlık')

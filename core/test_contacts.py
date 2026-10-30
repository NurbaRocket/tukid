from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import ContactMessage, Page, SiteSettings


class ContactMessageTests(TestCase):
    def submission(self, path='/contacts/', **changes):
        form = self.client.get(path).context['form']
        return {
            'submission_token': form.initial['submission_token'], 'website': '',
            'full_name': 'Тестовый посетитель', 'email': 'visitor@example.com',
            'phone': '+996 555 123 456', 'subject': 'Сотрудничество',
            'message': 'Хотим обсудить участие в мероприятиях.', **changes,
        }

    def test_valid_message_is_saved_once_and_refresh_does_not_resubmit(self):
        data = self.submission()
        response = self.client.post('/contacts/', data, follow=True)
        self.assertRedirects(response, '/contacts/')
        self.assertContains(response, 'Ваше сообщение отправлено.')
        message = ContactMessage.objects.get()
        for field in ['full_name', 'email', 'phone', 'subject', 'message']:
            self.assertEqual(getattr(message, field), data[field])
        self.assertEqual(message.status, ContactMessage.Status.NEW)
        self.client.post('/contacts/', {**data, 'message': 'Повторная отправка'}, follow=True)
        self.assertEqual(ContactMessage.objects.count(), 1)
        message.refresh_from_db()
        self.assertEqual(message.message, data['message'])
        self.assertNotContains(self.client.get('/contacts/'), 'Ваше сообщение отправлено.')

    def test_invalid_inputs_never_create_messages_and_keep_entered_values(self):
        for changes, field in [({'email': 'invalid'}, 'email'), ({'full_name': '  '}, 'full_name'),
                ({'message': 'x' * 5001}, 'message'), ({'subject': ''}, 'subject'),
                ({'phone': 'abcdefg'}, 'phone'), ({'message': 'bad\x01input'}, 'message')]:
            with self.subTest(field=field):
                response = self.client.post('/contacts/', self.submission(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertContains(response, 'aria-invalid="true"')
                self.assertEqual(response.context['form']['full_name'].value(), changes.get('full_name', 'Тестовый посетитель'))
                self.assertFalse(ContactMessage.objects.exists())

    def test_honeypot_and_invalid_tokens_are_rejected(self):
        for changes in [{'website': 'spam.example'}, {'submission_token': 'forged'},
                        {'submission_token': ''}]:
            response = self.client.post('/contacts/', self.submission(**changes))
            self.assertTrue(response.context['form'].errors)
            self.assertFalse(ContactMessage.objects.exists())

    def test_csrf_required_and_valid_form_works_without_javascript(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get('/contacts/')
        data = self.submission(phone='')
        self.assertEqual(client.post('/contacts/', data).status_code, 403)
        data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/contacts/', data).status_code, 302)
        self.assertEqual(ContactMessage.objects.get().phone, '')

    def test_localized_forms_map_and_confirmation(self):
        for prefix, language, label in [('/ky', 'ky', 'Бизге жазыңыз'), ('/tr', 'tr', 'Bize yazın')]:
            with self.subTest(language=language):
                response = self.client.get(prefix + '/contacts/')
                self.assertContains(response, label)
                self.assertContains(response, 'https://2gis.kg/bishkek/')
                self.assertIn('no-store', response['Cache-Control'])
                response = self.client.post(prefix + '/contacts/', self.submission(prefix + '/contacts/'))
                self.assertRedirects(response, prefix + '/contacts/')
                self.assertTrue(ContactMessage.objects.filter(language=language).exists())

    def test_draft_contact_page_is_unavailable_including_alias(self):
        Page.objects.filter(slug='contacts').update(is_published=False)
        for path in ['/contacts/', '/pages/contacts/']:
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.post(path, {}).status_code, 404)
        self.assertFalse(ContactMessage.objects.exists())

    @override_settings(APPLICATION_POST_LIMIT=1)
    def test_rate_limit_also_covers_page_alias(self):
        data = self.submission()
        self.assertEqual(self.client.post('/contacts/', data).status_code, 302)
        response = self.client.post('/pages/contacts/', data)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_oversized_request_is_not_saved(self):
        response = self.client.post('/contacts/', {'large': 'x' * (65 * 1024)})
        self.assertEqual(response.status_code, 413)
        self.assertFalse(ContactMessage.objects.exists())

    def test_map_center_is_editable_and_search_link_matches_address(self):
        settings = SiteSettings.objects.get()
        settings.map_latitude = 42.8
        settings.map_longitude = 74.6
        settings.map_zoom = 14
        settings.address = 'Бишкек, новый адрес 1'
        settings.maps_url = 'https://2gis.kg/bishkek/geo/15763234351102446'
        settings.dgis_api_key = 'test-public-map-key'
        settings.save()
        response = self.client.get('/contacts/')
        query = parse_qs(urlsplit(response.context['dgis_loader_url']).query)
        self.assertEqual(query, {'pkg': ['full'], 'key': ['test-public-map-key']})
        config = response.context['dgis_map_config']
        self.assertEqual((config['latitude'], config['longitude'], config['zoom']), (42.8, 74.6, 14))
        self.assertContains(response, 'https://maps.api.2gis.ru/2.0/loader.js?')
        self.assertContains(response, 'id="contact-map-config"')
        self.assertNotContains(response, 'firmsonmap')
        self.assertEqual(settings.dgis_url, settings.maps_url)
        settings.maps_url = 'https://evil.example/?2gis.kg'
        self.assertTrue(settings.dgis_url.startswith('https://2gis.kg/bishkek/search/'))
        settings.dgis_api_key = ''
        self.assertEqual(settings.dgis_loader_url, '')


class ContactMessageAdminTests(TestCase):
    def setUp(self):
        self.message = ContactMessage.objects.create(full_name='Посетитель', email='visitor@example.com',
            subject='Вопрос', message='<script>alert(1)</script>')
        self.staff = get_user_model().objects.create_user('contact-editor', is_staff=True)
        self.url = reverse('admin:core_contactmessage_change', args=[self.message.pk])

    def test_permission_required_and_readonly_original_message_is_escaped(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.staff.user_permissions.add(Permission.objects.get(codename='view_contactmessage'))
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'name="message"')
        self.assertEqual(self.client.post(self.url, {'status': 'closed'}).status_code, 403)

    def test_staff_can_change_status_and_notes_without_altering_submission(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='change_contactmessage'))
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {'status': 'closed', 'notes': 'Ответили по почте.',
                                              'message': 'Подменённый текст', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, 'closed')
        self.assertEqual(self.message.notes, 'Ответили по почте.')
        self.assertEqual(self.message.message, '<script>alert(1)</script>')

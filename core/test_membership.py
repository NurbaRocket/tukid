from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from pypdf import PdfReader

from .forms import new_submission_token
from .membership_constants import MEMBERSHIP_DECLARATION
from .membership_pdf import MembershipPDFError, build_membership_pdf
from .models import MembershipApplication, SiteSettings


def applicant_data():
    return {
        'company_name': 'ОсОО «Тестовая компания»',
        'activity_description': 'Торговля и логистика. Кыргызстан жана Türkiye.',
        'tax_id': '12345678901234', 'full_name': 'Тестовый Заявитель',
        'position': 'Генеральный директор', 'organization_address': 'Бишкек, тестовый адрес',
        'mobile_phone': '+996 (555) 12-34-56', 'work_phone': '+996312123456',
        'email': 'applicant@example.com', 'recommendations': 'Рекомендация участника',
        'information_source': 'Деловая встреча', 'declaration_accepted': 'on',
        'submission_token': new_submission_token(),
    }


def pdf_text(data):
    return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(bytes(data))).pages)


class MembershipFormTests(TestCase):
    def test_page_shows_document_fields_and_hides_board_fields(self):
        response = self.client.get(reverse('core:membership'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, MEMBERSHIP_DECLARATION)
        self.assertContains(response, 'name="tax_id"')
        self.assertContains(response, 'name="recommendations"')
        for name in ['membership_number', 'decision_number', 'decision_reason', 'status', 'chairperson_name']:
            self.assertNotContains(response, f'name="{name}"')
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_valid_submission_creates_private_pdf_and_success_receipt(self):
        data = applicant_data()
        response = self.client.post(reverse('core:membership'), data)
        self.assertRedirects(response, reverse('core:membership_success'))
        application = MembershipApplication.objects.get()
        self.assertEqual(application.status, MembershipApplication.Status.NEW)
        self.assertEqual(application.company_name, data['company_name'])
        self.assertEqual(application.declaration_text, MEMBERSHIP_DECLARATION)
        self.assertTrue(bytes(application.submitted_pdf).startswith(b'%PDF-'))
        self.assertEqual(bytes(application.submitted_pdf), bytes(application.current_pdf))
        text = pdf_text(application.submitted_pdf)
        self.assertIn('Общественное объединение', text)
        self.assertIn(data['full_name'], text)
        self.assertIn('Кыргызстан жана Türkiye.', text)
        self.assertIn(data['tax_id'], text)
        success = self.client.get(reverse('core:membership_success'))
        self.assertContains(success, application.reference)
        self.assertNotContains(success, application.email)
        self.assertNotContains(success, '/media/')
        self.assertNotContains(success, '/pdf/')
        self.assertNotIn(application.reference, Client().get(reverse('core:membership_success')).content.decode())

    def test_repeat_submission_does_not_duplicate_or_overwrite(self):
        data = applicant_data()
        self.client.post(reverse('core:membership'), data)
        first = MembershipApplication.objects.get()
        original = bytes(first.submitted_pdf)
        data['company_name'] = 'Изменённые данные повторного запроса'
        self.client.post(reverse('core:membership'), data)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        first.refresh_from_db()
        self.assertNotEqual(first.company_name, data['company_name'])
        self.assertEqual(bytes(first.submitted_pdf), original)

    def test_invalid_fields_do_not_create_records_and_preserve_input(self):
        for updates, expected in [
            ({'email': 'invalid'}, 'email'),
            ({'mobile_phone': 'не телефон'}, 'mobile_phone'),
            ({'declaration_accepted': ''}, 'declaration_accepted'),
            ({'activity_description': 'x'*2001}, 'activity_description'),
            ({'company_name': ''}, 'company_name'),
            ({'submission_token': 'tampered'}, 'submission_token'),
            ({'website': 'https://spam.example.com'}, 'website'),
        ]:
            with self.subTest(field=expected):
                data = {**applicant_data(), **updates}
                response = self.client.post(reverse('core:membership'), data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, response.context['form'].errors)
                self.assertEqual(response.context['form']['full_name'].value(), data['full_name'])
                self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_expired_form_token_is_rejected(self):
        data = applicant_data()
        with patch('django.core.signing.time.time', return_value=1):
            data['submission_token'] = new_submission_token()
        response = self.client.post(reverse('core:membership'), data)
        self.assertIn('submission_token', response.context['form'].errors)
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_public_post_cannot_set_board_decision(self):
        self.client.post(reverse('core:membership'), {
            **applicant_data(), 'status': 'approved', 'membership_number': 'HACK',
            'decision_number': 'HACK', 'chairperson_name': 'Не сотрудник',
        })
        application = MembershipApplication.objects.get()
        self.assertEqual(application.status, 'new')
        self.assertEqual(application.membership_number, '')
        self.assertEqual(application.decision_number, '')
        self.assertEqual(application.chairperson_name, '')

    def test_csrf_is_required(self):
        response = Client(enforce_csrf_checks=True).post(reverse('core:membership'), applicant_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_pdf_error_does_not_save_partial_application_and_allows_retry(self):
        data = applicant_data()
        with patch('core.membership_service.build_membership_pdf', side_effect=MembershipPDFError('Test failure')):
            with self.assertLogs('core.views', level='ERROR'):
                response = self.client.post(reverse('core:membership'), data)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertContains(response, 'Не удалось сформировать заявку', status_code=503)
        self.assertEqual(self.client.post(reverse('core:membership'), data).status_code, 302)
        self.assertEqual(MembershipApplication.objects.count(), 1)

    def test_pdf_escapes_markup_and_handles_maximum_text_lengths(self):
        application = MembershipApplication(
            company_name='Компания '*25, full_name='Тестовый Заявитель', tax_id='1234567890',
            position='Директор', organization_address='Адрес '*66, mobile_phone='+996555123456',
            email='applicant@example.com', declaration_accepted=True,
            declaration_text=MEMBERSHIP_DECLARATION,
            activity_description='<b>Текст</b><img src="https://example.com/photo.png">' + 'ӨҢҮ ŞĞİ '*243,
            recommendations='Рекомендация '*125, information_source='Источник '*55,
            status='rejected', decision_number='12/26', decision_date=date(2026, 10, 28),
            chairperson_name='Председатель', decision_reason='Причина решения '*200,
        )
        data = build_membership_pdf(application, SiteSettings())
        text = pdf_text(data)
        self.assertIn('<b>Текст</b>', text)
        self.assertIn('ӨҢҮ ŞĞİ', text)
        self.assertIn('Председатель', text)
        self.assertIn('Подписи проставляются на бумаге.', text)
        reader = PdfReader(BytesIO(data))
        self.assertGreater(len(reader.pages), 1)
        self.assertLessEqual(len(reader.pages), 6)


class MembershipAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser('membership-admin', 'admin@example.com', 'test-password')

    def setUp(self):
        self.client.post(reverse('core:membership'), applicant_data())
        self.application = MembershipApplication.objects.get()
        self.change_url = reverse('admin:core_membershipapplication_change', args=[self.application.pk])
        self.original_url = reverse('admin:core_membershipapplication_pdf', args=[self.application.pk, 'original'])
        self.current_url = reverse('admin:core_membershipapplication_pdf', args=[self.application.pk, 'current'])

    def test_admin_lists_applications_and_downloads_private_pdfs(self):
        self.client.force_login(self.admin_user)
        self.assertContains(self.client.get(reverse('admin:core_membershipapplication_changelist')), self.application.full_name)
        self.assertContains(self.client.get(self.change_url), self.original_url)
        self.assertContains(self.client.get(self.change_url), self.current_url)
        for url in [self.original_url, self.current_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertEqual(self.client.get(reverse('admin:core_membershipapplication_add')).status_code, 403)

    def test_pdf_download_requires_model_permission(self):
        self.assertEqual(self.client.get(self.original_url).status_code, 302)
        staff = get_user_model().objects.create_user('no-membership-permission', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.original_url).status_code, 403)
        self.assertNotContains(self.client.get(reverse('admin:index')), reverse('admin:core_membershipapplication_changelist'))
        staff.user_permissions.add(Permission.objects.get(codename='view_membershipapplication'))
        response = self.client.get(self.original_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertEqual(self.client.get(self.change_url).status_code, 200)
        self.assertContains(self.client.get(reverse('admin:index')), 'Новые заявки на членство')
        self.assertEqual(self.client.post(self.change_url, {'status': 'approved'}).status_code, 403)

    def test_board_decision_updates_current_pdf_and_keeps_original(self):
        original = bytes(self.application.submitted_pdf)
        self.client.force_login(self.admin_user)
        response = self.client.post(self.change_url, {
            'status': 'approved', 'membership_number': 'T-001', 'secretary_name': 'Секретарь',
            'proposed_on': '2026-10-28', 'decision_number': '12/26', 'decision_date': '2026-10-28',
            'chairperson_name': 'Председатель', 'decision_reason': 'Решение Совета',
            'company_name': 'Попытка изменить исходные сведения', '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(bytes(self.application.submitted_pdf), original)
        self.assertNotEqual(bytes(self.application.current_pdf), original)
        self.assertEqual(self.application.reviewed_by, self.admin_user)
        self.assertIsNotNone(self.application.reviewed_at)
        self.assertEqual(self.application.company_name, 'ОсОО «Тестовая компания»')
        text = pdf_text(self.application.current_pdf)
        self.assertIn('T-001', text)
        self.assertIn('12/26', text)
        self.assertIn('Председатель', text)
        self.assertIn('Заявитель принят в членство', text)
        self.assertTrue(self.admin_user.logentry_set.filter(object_id=str(self.application.pk)).exists())

    def test_incomplete_decision_is_not_saved(self):
        self.client.force_login(self.admin_user)
        for status, missing in [('approved', 'membership_number'), ('rejected', 'decision_reason')]:
            with self.subTest(status=status):
                response = self.client.post(self.change_url, {
                    'status': status, 'decision_number': '12/26',
                    'decision_date': '2026-10-28', 'chairperson_name': 'Председатель', '_save': 'Сохранить',
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(missing, response.context['adminform'].form.errors)
                self.application.refresh_from_db()
                self.assertEqual(self.application.status, 'new')

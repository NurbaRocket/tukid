from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from reportlab.pdfgen import canvas

from .career_constants import CAREER_CONSENT
from .career_service import submit_career_application
from .forms import new_career_submission_token, new_submission_token
from .models import CareerApplication, Member, Page, Vacancy


def pdf_bytes(text='Demonstration resume'):
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(50, 750, text)
    document.save()
    return output.getvalue()


def resume(content=None, name='resume.pdf'):
    return SimpleUploadedFile(name, pdf_bytes() if content is None else content, content_type='application/octet-stream')


def docx_bytes(extra=None, external_type=None):
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Test resume</w:t></w:r></w:p></w:body></w:document>')
        if extra:
            archive.writestr(*extra)
        if external_type:
            archive.writestr('word/_rels/document.xml.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{external_type}" Target="https://example.com/" TargetMode="External"/></Relationships>')
    return output.getvalue()


def applicant(**updates):
    return {
        'full_name': 'Тестовый Кандидат', 'email': 'candidate@example.com',
        'phone': '+996 (555) 12-34-56', 'city': 'Бишкек',
        'desired_position': 'Специалист', 'cover_letter': 'Описание опыта работы.',
        'consent_accepted': 'on', 'submission_token': new_career_submission_token(),
        'resume': resume(), **updates,
    }


class CareerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Member.objects.create(name='Компания Альфа', slug='career-alpha', is_published=True)
        cls.other_company = Member.objects.create(name='Компания Бета', slug='career-beta', is_published=True)
        cls.hidden_company = Member.objects.create(name='Неопубликованная компания', slug='career-hidden')

    def vacancy(self, **updates):
        return Vacancy.objects.create(**{
            'title': 'Менеджер по работе с клиентами', 'slug': 'client-manager',
            'company': self.company, 'description': '<p>Развитие отношений с клиентами.</p>',
            'requirements': '<p>Опыт работы и знание языков.</p>', 'location': 'Бишкек',
            'is_published': True, **updates,
        })

    def test_empty_career_has_general_application_form(self):
        response = self.client.get(reverse('core:career'))
        for text in ['Открытых вакансий пока нет', 'multipart/form-data', 'name="resume"', '.pdf,.docx', 'Общая заявка']:
            self.assertContains(response, text)
        self.assertNotContains(response, 'name="status"')
        self.assertNotContains(response, 'name="notes"')
        self.assertIn('no-store', response['Cache-Control'])

    def test_general_submission_stores_private_resume_and_session_receipt(self):
        data = applicant()
        expected = data['resume'].read()
        data['resume'].seek(0)
        response = self.client.post(reverse('core:career'), data)
        self.assertRedirects(response, reverse('core:career_success'))
        application = CareerApplication.objects.get()
        self.assertIsNone(application.vacancy)
        self.assertEqual(bytes(application.resume_data), expected)
        self.assertEqual(application.resume_size, len(expected))
        self.assertEqual(application.resume_content_type, 'application/pdf')
        self.assertEqual(application.resume_name, 'resume.pdf')
        self.assertEqual(application.consent_text, CAREER_CONSENT)
        self.assertEqual(application.status, 'new')
        success = self.client.get(reverse('core:career_success'))
        self.assertContains(success, application.reference)
        self.assertNotContains(success, application.email)
        self.assertNotContains(success, '/media/')
        self.assertRedirects(Client().get(reverse('core:career_success')), reverse('core:career'))

    def test_vacancy_selection_prefill_snapshot_and_public_fields(self):
        vacancy = self.vacancy()
        response = self.client.get(reverse('core:career'), {'vacancy': vacancy.slug})
        self.assertEqual(response.context['form']['vacancy'].value(), vacancy.pk)
        response = self.client.post(reverse('core:career'), applicant(
            vacancy=str(vacancy.pk), desired_position='', status='closed', notes='Injected notes',
            company_name='Wrong company', resume_data='Injected file',
        ))
        self.assertEqual(response.status_code, 302)
        application = CareerApplication.objects.get()
        self.assertEqual(application.vacancy, vacancy)
        self.assertEqual(application.vacancy_title, vacancy.title)
        self.assertEqual(application.desired_position, vacancy.title)
        self.assertEqual(application.company_name, self.company.name)
        self.assertEqual(application.status, 'new')
        self.assertEqual(application.notes, '')

    def test_repeat_post_does_not_duplicate_or_replace_resume(self):
        data = applicant()
        self.client.post(reverse('core:career'), data)
        original = CareerApplication.objects.get()
        original_bytes = bytes(original.resume_data)
        self.client.post(reverse('core:career'), {
            **data, 'resume': resume(pdf_bytes('Changed resume')), 'full_name': 'Другое имя',
        })
        self.assertEqual(CareerApplication.objects.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.full_name, 'Тестовый Кандидат')
        self.assertEqual(bytes(original.resume_data), original_bytes)

    def test_deleting_vacancy_preserves_original_application_and_resume(self):
        vacancy = self.vacancy()
        self.client.post(reverse('core:career'), applicant(vacancy=vacancy.pk))
        application = CareerApplication.objects.get()
        original = bytes(application.resume_data)
        vacancy.delete()
        application.refresh_from_db()
        self.assertIsNone(application.vacancy)
        self.assertEqual(application.vacancy_title, vacancy.title)
        self.assertEqual(application.company_name, self.company.name)
        self.assertEqual(bytes(application.resume_data), original)

    def test_docx_with_hyperlink_is_supported(self):
        response = self.client.post(reverse('core:career'), applicant(resume=resume(
            docx_bytes(external_type='hyperlink'), 'resume.docx')))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CareerApplication.objects.get().resume_content_type.endswith('wordprocessingml.document'))

    def test_invalid_files_are_rejected(self):
        files = [
            resume(b'<html>not a PDF</html>'), resume(b''),
            resume(b'MZ executable', 'resume.exe'), resume(b'not a ZIP', 'resume.docx'),
            resume(docx_bytes(('word/vbaProject.bin', b'macro')), 'macro.docx'),
            resume(docx_bytes(('word/embeddings/object.bin', b'embedded')), 'embedded.docx'),
            resume(docx_bytes(external_type='attachedTemplate'), 'external.docx'),
            resume(b'%PDF-' + b'0'*(5*1024*1024) + b'%%EOF'),
            resume(docx_bytes(('oversized.bin', b'0'*(26*1024*1024))), 'oversized.docx'),
        ]
        for file in files:
            with self.subTest(filename=file.name, size=file.size):
                response = self.client.post(reverse('core:career'), applicant(resume=file))
                if file.size > 5 * 1024 * 1024:
                    self.assertEqual(response.status_code, 413)
                else:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('resume', response.context['form'].errors)
                self.assertFalse(CareerApplication.objects.exists())

    def test_invalid_fields_keep_input_without_saving(self):
        for updates, field in [
            ({'full_name': ''}, 'full_name'), ({'email': 'invalid'}, 'email'),
            ({'phone': 'not a phone'}, 'phone'), ({'desired_position': ''}, 'desired_position'),
            ({'consent_accepted': ''}, 'consent_accepted'), ({'submission_token': 'tampered'}, 'submission_token'),
            ({'submission_token': new_submission_token()}, 'submission_token'),
            ({'website': 'https://spam.example.com'}, 'website'), ({'cover_letter': 'x'*6001}, 'cover_letter'),
        ]:
            with self.subTest(field=field):
                response = self.client.post(reverse('core:career'), applicant(**updates))
                self.assertIn(field, response.context['form'].errors)
                self.assertFalse(CareerApplication.objects.exists())
                self.assertEqual(response.context['form']['city'].value(), 'Бишкек')
        with patch('django.core.signing.time.time', return_value=1):
            token = new_career_submission_token()
        response = self.client.post(reverse('core:career'), applicant(submission_token=token))
        self.assertIn('submission_token', response.context['form'].errors)

    def test_csrf_is_required(self):
        response = Client(enforce_csrf_checks=True).post(reverse('core:career'), applicant())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CareerApplication.objects.exists())

    def test_only_open_published_company_vacancies_are_available(self):
        live = self.vacancy(closes_on=timezone.localdate())
        hidden = [
            self.vacancy(title='Черновик', slug='draft', is_published=False),
            self.vacancy(title='Закрытая позиция', slug='closed', is_closed=True),
            self.vacancy(title='Срок истёк', slug='expired', closes_on=timezone.localdate()-timedelta(days=1)),
            self.vacancy(title='Будущая публикация', slug='future', published_at=timezone.now()+timedelta(days=1)),
            self.vacancy(title='Скрытая компания', slug='hidden', company=self.hidden_company),
        ]
        response = self.client.get(reverse('core:career'))
        self.assertContains(response, live.title)
        self.assertEqual(list(response.context['form'].fields['vacancy'].queryset), [live])
        for vacancy in hidden:
            self.assertNotContains(response, vacancy.title)
            self.assertEqual(self.client.get(vacancy.get_absolute_url()).status_code, 404)
        response = self.client.post(reverse('core:career'), applicant(vacancy=hidden[0].pk))
        self.assertIn('vacancy', response.context['form'].errors)
        self.assertFalse(CareerApplication.objects.exists())

    def test_vacancy_closed_during_submission_does_not_accept_application(self):
        vacancy = self.vacancy()
        def close_then_submit(form):
            Vacancy.objects.filter(pk=vacancy.pk).update(is_closed=True)
            return submit_career_application(form)
        with patch('core.views.submit_career_application', side_effect=close_then_submit):
            response = self.client.post(reverse('core:career'), applicant(vacancy=vacancy.pk))
        self.assertContains(response, 'Вакансия уже закрыта')
        self.assertFalse(CareerApplication.objects.exists())

    def test_company_filter_member_badge_and_related_vacancies(self):
        first = self.vacancy()
        second = self.vacancy(title='Дизайнер', slug='designer', company=self.other_company)
        closed = self.vacancy(title='Архивная вакансия', slug='archive', is_closed=True)
        response = self.client.get(reverse('core:career'), {'company': self.other_company.slug})
        self.assertEqual(list(response.context['page_obj']), [second])
        response = self.client.get(reverse('core:career'), {'q': 'Дизайнер'})
        self.assertEqual(list(response.context['page_obj']), [second])
        response = self.client.get(self.company.get_absolute_url())
        self.assertContains(response, first.title)
        self.assertNotContains(response, closed.title)
        self.assertContains(self.client.get(reverse('core:members')), 'Открытых вакансий: 1')

    def test_job_detail_sanitizes_formatted_text(self):
        vacancy = self.vacancy(description='<p>Описание</p><script>alert(43)</script>',
            requirements='<strong>Опыт</strong><img src=x onerror=alert(44)>')
        response = self.client.get(vacancy.get_absolute_url())
        self.assertContains(response, '<strong>Опыт</strong>')
        self.assertContains(response, f'?vacancy={vacancy.slug}#apply')
        self.assertNotContains(response, 'alert(43)')
        self.assertNotContains(response, 'onerror')

    def test_hidden_career_page_disables_forms_and_vacancy_details(self):
        vacancy = self.vacancy()
        Page.objects.filter(slug='career').update(is_published=False)
        self.assertEqual(self.client.get(reverse('core:career')).status_code, 404)
        self.assertEqual(self.client.post(reverse('core:career'), applicant()).status_code, 404)
        self.assertEqual(self.client.get(vacancy.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse('core:members')), 'Открытых вакансий:')
        self.assertFalse(CareerApplication.objects.exists())


class CareerAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('career-admin', 'admin@example.com', 'test-password')
        cls.company = Member.objects.create(name='Работодатель', slug='employer', is_published=True)

    def submitted_application(self):
        self.client.post(reverse('core:career'), applicant())
        return CareerApplication.objects.get()

    def test_resume_requires_model_permission_and_downloads_as_private_attachment(self):
        application = self.submitted_application()
        url = reverse('admin:core_careerapplication_resume', args=[application.pk])
        self.assertEqual(Client().get(url).status_code, 302)
        staff = get_user_model().objects.create_user('career-staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='view_careerapplication'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), bytes(application.resume_data))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.client.get(reverse('admin:core_careerapplication_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:core_careerapplication_add')).status_code, 403)

    def test_admin_changes_status_but_preserves_applicant_and_resume(self):
        application = self.submitted_application()
        original = bytes(application.resume_data)
        self.client.force_login(self.user)
        url = reverse('admin:core_careerapplication_change', args=[application.pk])
        response = self.client.post(url, {'status': 'review', 'notes': 'Связаться с кандидатом',
            'full_name': 'Внедрённое имя', 'resume_data': 'Changed file', '_save': 'Сохранить'})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, 'review')
        self.assertEqual(application.notes, 'Связаться с кандидатом')
        self.assertEqual(application.full_name, 'Тестовый Кандидат')
        self.assertEqual(bytes(application.resume_data), original)
        self.assertEqual(application.reviewed_by, self.user)
        self.assertIsNotNone(application.reviewed_at)

    def test_admin_can_publish_company_vacancy(self):
        self.client.force_login(self.user)
        now = timezone.localtime()
        response = self.client.post(reverse('admin:core_vacancy_add'), {
            'title': 'Инженер', 'slug': 'engineer', 'company': self.company.pk,
            'description': '<p>Работа с проектами.</p>', 'requirements': 'Опыт', 'conditions': 'Условия',
            'location': 'Бишкек', 'employment': 'full_time', 'work_mode': 'hybrid',
            'published_at_0': now.strftime('%Y-%m-%d'), 'published_at_1': now.strftime('%H:%M:%S'),
            'is_published': 'on', '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        vacancy = Vacancy.objects.get(slug='engineer')
        self.assertContains(self.client.get(vacancy.get_absolute_url()), 'Инженер')
        self.assertContains(self.client.get(reverse('admin:index')), 'Вакансии')

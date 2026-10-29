from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, close_old_connections, connection, connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import ApplicationRequestLimit, CareerApplication, MembershipApplication
from .request_security import client_address, consume_request
from .test_career import applicant
from .test_membership import applicant_data


class ApplicationSecurityTests(TestCase):
    @override_settings(APPLICATION_POST_LIMIT=2)
    def test_repeated_valid_csrf_posts_are_limited_across_clients_and_languages(self):
        for path in ['/career/', '/tr/career/']:
            client = Client(enforce_csrf_checks=True)
            response = client.get(path)
            data = applicant(submission_token=response.context['form'].initial['submission_token'])
            data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
            self.assertEqual(client.post(path, data).status_code, 302)
        response = self.client.post('/ky/career/', applicant())
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(CareerApplication.objects.count(), 2)

    @override_settings(APPLICATION_POST_LIMIT=1)
    def test_invalid_posts_consume_budget_and_other_addresses_have_independent_budgets(self):
        first = self.client.post('/membership/', {})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.client.post('/membership/', applicant_data()).status_code, 429)
        self.assertEqual(self.client.post('/membership/', applicant_data(), REMOTE_ADDR='192.0.2.2').status_code, 302)
        self.assertEqual(MembershipApplication.objects.count(), 1)

    @override_settings(APPLICATION_GET_LIMIT=1)
    def test_form_get_limit_does_not_limit_success_pages_or_other_pages(self):
        self.assertEqual(self.client.get('/membership/').status_code, 200)
        self.assertEqual(self.client.get('/membership/').status_code, 429)
        self.assertEqual(self.client.get('/membership/sent/').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)

    @override_settings(APPLICATION_POST_LIMIT=1, APPLICATION_POST_WINDOW=60)
    def test_atomic_bucket_is_bounded_and_expires(self):
        self.assertEqual(consume_request('core:career', 'POST', '192.0.2.1', now=120), (True, 60))
        self.assertEqual(consume_request('core:career', 'POST', '192.0.2.1', now=130), (False, 50))
        self.assertEqual(consume_request('core:career', 'POST', '192.0.2.1', now=180), (True, 60))
        self.assertEqual(list(ApplicationRequestLimit.objects.values_list('count', flat=True)), [1, 1])
        self.assertTrue(all('192.0.2' not in key for key in ApplicationRequestLimit.objects.values_list('key', flat=True)))

    def test_oversized_body_rejected_before_validation(self):
        with patch('core.views.MembershipApplicationForm') as form:
            response = self.client.post('/membership/', {'large': 'x' * (65 * 1024)})
        self.assertEqual(response.status_code, 413)
        form.assert_not_called()
        self.assertFalse(MembershipApplication.objects.exists())

    def test_streaming_limit_rejects_file_before_saving(self):
        response = self.client.post('/career/', applicant(resume=SimpleUploadedFile(
            'large.pdf', b'%PDF-' + b'x' * (5 * 1024 * 1024) + b'%%EOF',
        )))
        self.assertEqual(response.status_code, 413)
        self.assertFalse(CareerApplication.objects.exists())

    def test_limiter_failure_does_not_allow_submission(self):
        with patch('core.request_security.consume_request', side_effect=DatabaseError('unavailable')):
            with self.assertLogs('core.request_security', level='ERROR'):
                response = self.client.post('/membership/', applicant_data())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Retry-After'], '60')
        self.assertFalse(MembershipApplication.objects.exists())

    def test_valid_resume_followed_by_oversized_extra_file_never_creates_application(self):
        data = applicant()
        data['extra'] = SimpleUploadedFile('ignored.bin', b'x' * (5 * 1024 * 1024))
        response = self.client.post('/career/', data)
        self.assertEqual(response.status_code, 413)
        self.assertFalse(CareerApplication.objects.exists())

    def test_expired_buckets_are_cleaned_without_deleting_active_buckets(self):
        ApplicationRequestLimit.objects.create(key='expired', expires_at=timezone.now() - timedelta(seconds=1))
        ApplicationRequestLimit.objects.create(key='active', expires_at=timezone.now() + timedelta(hours=1))
        self.client.get('/membership/')
        self.assertFalse(ApplicationRequestLimit.objects.filter(key='expired').exists())
        self.assertTrue(ApplicationRequestLimit.objects.filter(key='active').exists())

    @override_settings(APPLICATION_TRUSTED_PROXY_IPS=['127.0.0.1'])
    def test_forwarded_address_is_only_accepted_from_explicitly_trusted_peer(self):
        factory = RequestFactory()
        trusted = factory.get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='192.0.2.9')
        direct = factory.get('/', REMOTE_ADDR='192.0.2.1', HTTP_X_REAL_IP='192.0.2.9')
        malformed = factory.get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='invalid')
        self.assertEqual(client_address(trusted), '192.0.2.9')
        self.assertEqual(client_address(direct), '192.0.2.1')
        self.assertEqual(client_address(malformed), '127.0.0.1')


@skipUnless(connection.vendor == 'postgresql', 'Concurrency check requires PostgreSQL.')
@override_settings(APPLICATION_POST_LIMIT=3, APPLICATION_POST_WINDOW=60)
class ConcurrentApplicationLimitTests(TransactionTestCase):
    def test_parallel_workers_cannot_exceed_the_shared_budget(self):
        barrier = Barrier(8, timeout=10)

        def submit(_):
            close_old_connections()
            try:
                barrier.wait()
                return consume_request('core:career', 'POST', '192.0.2.50', now=120)[0]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as workers:
            accepted = list(workers.map(submit, range(8)))
        self.assertEqual(sum(accepted), 3)
        self.assertEqual(ApplicationRequestLimit.objects.get().count, 3)

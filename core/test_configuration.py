import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.environment import env_bool, env_int


class ConfigurationTests(SimpleTestCase):
    def test_malformed_configuration_is_rejected(self):
        with patch.dict(os.environ, {'AUDIT_BOOL': 'maybe', 'AUDIT_NUMBER': '-1'}):
            with self.assertRaises(ImproperlyConfigured):
                env_bool('AUDIT_BOOL')
            with self.assertRaises(ImproperlyConfigured):
                env_int('AUDIT_NUMBER', 1)

    def run_settings(self, **updates):
        environment = {**os.environ, 'DJANGO_DEBUG': 'False',
            'DJANGO_ALLOWED_HOSTS': 'example.com',
            'DJANGO_SECRET_KEY': 'test-production-' + '0123456789abcdef' * 5,
            'DB_PASSWORD': 'test-only', **updates}
        return subprocess.run([sys.executable, '-c',
            "import json; from config import production as s; "
            "print(json.dumps({'debug':s.DEBUG,'hosts':s.ALLOWED_HOSTS,"
            "'secure':s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT,"
            "'db':{k:s.DATABASES['default'][k] for k in ('NAME','USER','HOST','PORT')},"
            "'static':str(s.STATIC_ROOT)}))"],
            env=environment, cwd=Path(__file__).resolve().parent.parent,
            text=True, capture_output=True, timeout=15)

    def test_production_settings_and_database_environment(self):
        result = self.run_settings(DB_NAME='ci_db', DB_USER='ci_user', DB_HOST='db.internal', DB_PORT='5433')
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertFalse(values['debug'])
        self.assertTrue(values['secure'])
        self.assertEqual(values['hosts'], ['example.com'])
        self.assertEqual(values['db'], {'NAME':'ci_db', 'USER':'ci_user', 'HOST':'db.internal', 'PORT':'5433'})
        self.assertTrue(values['static'].endswith('staticfiles'))

    def test_production_refuses_debug_missing_hosts_and_weak_secret(self):
        for updates in ({'DJANGO_DEBUG':'True'}, {'DJANGO_ALLOWED_HOSTS':''},
                        {'DJANGO_SECRET_KEY':'short'}, {'DJANGO_ALLOWED_HOSTS':'*'},
                        {'DJANGO_SECRET_KEY':'GENERATE_A_NEW_RANDOM_SECRET_WITH_AT_LEAST_50_CHARACTERS'},
                        {'APPLICATION_TRUSTED_PROXY_IPS':'127.0.0.1/32'}):
            with self.subTest(updates=tuple(updates)):
                result = self.run_settings(**updates)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)

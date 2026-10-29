"""The same isolated tests on PostgreSQL, using Django's test_<DB_NAME> database."""
from .settings import DATABASES as POSTGRES_DATABASES
from .test_settings import *  # noqa: F403

DATABASES = POSTGRES_DATABASES

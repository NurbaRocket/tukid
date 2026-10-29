"""Strict, small helpers shared by settings and configuration checks."""
import os
from ipaddress import ip_address

from django.core.exceptions import ImproperlyConfigured


def env_bool(name, default=False):
    value = os.environ.get(name, str(default)).strip().lower()
    if value in {'1', 'true', 'yes', 'on'}:
        return True
    if value in {'0', 'false', 'no', 'off'}:
        return False
    raise ImproperlyConfigured(f'{name} must be true or false.')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


def env_ip_addresses(name):
    try:
        return [str(ip_address(value)) for value in env_list(name)]
    except ValueError as error:
        raise ImproperlyConfigured(f'{name} must contain individual IP addresses (no CIDR ranges).') from error


def env_int(name, default, minimum=0):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError) as error:
        raise ImproperlyConfigured(f'{name} must be an integer.') from error
    if value < minimum:
        raise ImproperlyConfigured(f'{name} must be at least {minimum}.')
    return value

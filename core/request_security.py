"""Bound public form traffic before parsing uploads or generating documents."""
import ipaddress
import logging
import math
import time
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.db import DatabaseError
from django.db.models import F
from django.http import HttpResponse
from django.urls import Resolver404, resolve
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext as _

from .models import ApplicationRequestLimit

logger = logging.getLogger(__name__)
APPLICATION_ROUTES = {'core:membership', 'core:career', 'core:contacts'}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def error_response(message, status):
    response = HttpResponse(message, status=status, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'private, no-store, max-age=0'
    return response


def client_address(request):
    peer = request.META.get('REMOTE_ADDR', '')
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return 'unknown'
    # Never trust client-supplied forwarded headers from an arbitrary peer.
    trusted = any(address == ipaddress.ip_address(value) for value in settings.APPLICATION_TRUSTED_PROXY_IPS)
    if trusted:
        try:
            return str(ipaddress.ip_address(request.META.get('HTTP_X_REAL_IP', '')))
        except ValueError:
            pass
    return str(address)


def consume_request(route, method, address, *, now=None):
    """Increment only below the limit, using one conditional atomic UPDATE."""
    now = time.time() if now is None else now
    prefix = 'APPLICATION_POST' if method == 'POST' else 'APPLICATION_GET'
    limit = getattr(settings, f'{prefix}_LIMIT')
    window = getattr(settings, f'{prefix}_WINDOW')
    bucket = int(now // window)
    expires = (bucket + 1) * window
    # Store neither raw addresses nor session identifiers in the database.
    key = salted_hmac('core.application-rate-limit.v1', f'{route}:{method}:{address}:{bucket}',
                      algorithm='sha256').hexdigest()
    ApplicationRequestLimit.objects.get_or_create(
        key=key, defaults={'expires_at': datetime.fromtimestamp(expires, datetime_timezone.utc)},
    )
    accepted = ApplicationRequestLimit.objects.filter(key=key, count__lt=limit).update(count=F('count') + 1)
    return bool(accepted), max(1, math.ceil(expires - now))


class BoundedResumeUploadHandler(FileUploadHandler):
    """Stop the multipart stream before disk/memory handlers exceed 5 MiB."""

    def __init__(self, request):
        super().__init__(request)
        self.received = 0

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > MAX_UPLOAD_BYTES:
            self.request._application_upload_too_large = True
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class ApplicationSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.next_cleanup = 0

    def __call__(self, request):
        try:
            match = resolve(request.path_info)
            route = match.view_name
            if route == 'core:page' and match.kwargs.get('slug') == 'contacts':
                route = 'core:contacts'
        except Resolver404:
            route = None
        if route not in APPLICATION_ROUTES or request.method not in {'GET', 'POST'}:
            return self.get_response(request)

        if request.method == 'POST':
            maximum = (settings.MEMBERSHIP_MAX_BODY_SIZE if route in {'core:membership', 'core:contacts'}
                       else settings.APPLICATION_MAX_BODY_SIZE)
            try:
                length = int(request.META.get('CONTENT_LENGTH') or 0)
            except (ValueError, TypeError):
                return error_response(_('Некорректный размер запроса.'), 400)
            if length < 0:
                return error_response(_('Некорректный размер запроса.'), 400)
            if length > maximum:
                return error_response(_('Размер запроса превышает допустимый предел.'), 413)
            request.upload_handlers.insert(0, BoundedResumeUploadHandler(request))

        try:
            accepted, retry_after = consume_request(route, request.method, client_address(request))
            self.cleanup_expired()
        except DatabaseError:
            logger.exception('Application request limiter unavailable')
            response = error_response(_('Отправка временно недоступна. Попробуйте позднее.'), 503)
            response['Retry-After'] = '60'
            return response
        if not accepted:
            response = error_response(_('Слишком много запросов. Попробуйте немного позднее.'), 429)
            response['Retry-After'] = str(retry_after)
            return response

        if request.method == 'POST':
            # Parse before dispatch: a valid first file must never be saved if
            # a later multipart part trips the aggregate upload limit.
            request.POST
            if getattr(request, '_application_upload_too_large', False):
                return error_response(_('Файл резюме должен быть не больше 5 МБ.'), 413)
        response = self.get_response(request)
        if getattr(request, '_application_upload_too_large', False):
            return error_response(_('Файл резюме должен быть не больше 5 МБ.'), 413)
        return response

    def cleanup_expired(self):
        current = time.monotonic()
        if current < self.next_cleanup:
            return
        self.next_cleanup = current + 300
        expired = list(ApplicationRequestLimit.objects.filter(
            expires_at__lte=datetime.now(datetime_timezone.utc),
        ).values_list('pk', flat=True)[:1000])
        if expired:
            ApplicationRequestLimit.objects.filter(pk__in=expired).delete()

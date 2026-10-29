from urllib.parse import urlsplit

from django.conf import settings
from django.utils.translation import get_language_from_path, override
from django.views.decorators.http import require_POST
from django.views.i18n import set_language


@require_POST
def site_set_language(request):
    # This endpoint has no language prefix. Resolve the current page in its
    # source language before Django translates its URL to the selected one.
    source = request.POST.get('next', '')
    try:
        source_language = get_language_from_path(urlsplit(source).path)
    except ValueError:
        source_language = None
    if request.POST.get('language') not in dict(settings.LANGUAGES):
        data = request.POST.copy()
        data.pop('language', None)
        request.POST = data
    with override(source_language or settings.LANGUAGE_CODE):
        # Django validates the destination host/scheme and sets its language
        # cookie with the configured security attributes.
        return set_language(request)

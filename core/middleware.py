from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class SiteLocaleMiddleware(LocaleMiddleware):
    def process_request(self, request):
        super().process_request(request)
        if request.path_info.startswith('/admin/'):
            translation.activate('ru')
            request.LANGUAGE_CODE = 'ru'

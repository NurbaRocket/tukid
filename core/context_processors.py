from django.conf import settings as django_settings
from django.urls import translate_url
from django.utils.translation import get_language

from .models import Page
from .site_cache import get_site_navigation, get_site_settings


def site_content(request):
    if request.resolver_match and request.resolver_match.app_name == 'admin':
        return {}
    settings = get_site_settings(request)
    navigation = get_site_navigation(request)
    unpublished, roots = navigation['unpublished'], navigation['roots']

    def visible(item):
        return not ((item.page_id and not item.page.is_published) or item.route in unpublished)

    def active(item):
        url = item.url
        detail_routes = {'members': 'member_detail', 'news': 'news_detail', 'events': 'event_detail', 'meetings': 'meeting_detail', 'career': 'vacancy_detail'}
        current = request.resolver_match.url_name if request.resolver_match else ''
        return bool(url and (request.path == url or current == detail_routes.get(item.route)))

    menu = []
    for root in roots:
        if not visible(root):
            continue
        root.visible_children = [child for child in root.visible_children if visible(child)]
        for child in root.visible_children:
            child.active = active(child)
        root.active = active(root) or any(child.active for child in root.visible_children)
        menu.append(root)
    return {
        'site_settings': settings, 'site_menu': menu,
        'published_pages': set(Page.Section.values) - unpublished,
        'language_options': [
            {'code': code, 'name': name, 'url': translate_url(request.path, code), 'active': code == get_language()}
            for code, name in django_settings.LANGUAGES
        ],
    }

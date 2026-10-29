from django.urls import reverse_lazy


def item(title, icon, model, app='core'):
    return {
        'title': title, 'icon': icon,
        'link': reverse_lazy(f'admin:{app}_{model}_changelist'),
        'permission': lambda request: request.user.has_perm(f'{app}.view_{model}') or request.user.has_perm(f'{app}.change_{model}'),
    }


UNFOLD = {
    'SITE_TITLE': 'TUKID · Управление сайтом',
    'SITE_HEADER': 'TUKID',
    'SITE_SUBHEADER': 'Управление сайтом',
    'SITE_URL': '/',
    'SITE_LOGO': 'core.admin_dashboard.site_logo',
    'SITE_FAVICONS': [{'rel': 'icon', 'type': 'image/x-icon', 'href': 'core.admin_dashboard.site_favicon'}],
    'STYLES': ['core.admin_dashboard.admin_styles'],
    'DASHBOARD_CALLBACK': 'core.admin_dashboard.dashboard',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': True,
    'COMMAND': {'search_models': True, 'show_history': True},
    'COLORS': {'primary': {
        '50': '#fff1f0', '100': '#ffe1df', '200': '#ffc7c3', '300': '#ffa09a',
        '400': '#ff6b63', '500': '#fe423d', '600': '#e4211b', '700': '#c01914',
        '800': '#9f1a16', '900': '#831c19', '950': '#480a08',
    }},
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': False,
        'navigation': [
            {'title': 'Сайт', 'separator': True, 'items': [
                item('Общие настройки', 'tune', 'sitesettings'),
                item('Блоки главной', 'dashboard_customize', 'homesection'),
                item('Направления', 'handshake', 'homedirection'),
                item('Фотогалерея', 'photo_library', 'galleryphoto'),
                item('Меню сайта', 'menu', 'menuitem'),
            ]},
            {'title': 'Контент', 'separator': True, 'items': [
                item('Страницы', 'article', 'page'),
                item('Новости', 'newspaper', 'news'),
                item('Мероприятия', 'event', 'event'),
                item('Официальные встречи', 'forum', 'officialmeeting'),
                item('Институциональное сотрудничество', 'handshake', 'institutionalcooperation'),
                item('Члены объединения', 'domain', 'member'),
                item('Заявки на членство', 'assignment', 'membershipapplication'),
                item('Совет правления', 'groups', 'boardmember'),
            ]},
            {'title': 'Карьера', 'separator': True, 'items': [
                item('Вакансии компаний', 'work', 'vacancy'),
                item('Отклики и резюме', 'contact_page', 'careerapplication'),
            ]},
            {'title': 'Справочники', 'separator': True, 'items': [
                item('Сферы деятельности', 'category', 'activitysector'),
                item('Теги новостей', 'sell', 'newstag'),
            ]},
            {'title': 'Доступ', 'separator': True, 'items': [
                item('Пользователи', 'manage_accounts', 'user', 'auth'),
                item('Группы и права', 'admin_panel_settings', 'group', 'auth'),
            ]},
        ],
    },
}

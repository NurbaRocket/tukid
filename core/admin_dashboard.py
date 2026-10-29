from django.contrib.admin.models import LogEntry
from django.db.models import Count, Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from .models import CareerApplication, Event, Member, MembershipApplication, News, Page, Vacancy
from .site_cache import get_site_settings


def site_logo(request):
    settings = get_site_settings(request)
    return settings.header_logo_url


def site_favicon(request):
    settings = get_site_settings(request)
    return settings.favicon_url


def admin_styles(request):
    return static('core/css/admin.css')


def dashboard(request, context):
    cards, quick_links, tasks = [], [], []
    now = timezone.now()
    definitions = [
        (Member, 'Члены объединения', 'domain', Q(is_published=True)),
        (News, 'Новости', 'newspaper', Q(is_published=True, published_at__lte=now)),
        (Event, 'Мероприятия', 'event', Q(is_published=True)),
        (Page, 'Страницы', 'article', Q(is_published=True)),
    ]
    for model, title, icon, published in definitions:
        name = model._meta.model_name
        can_view = request.user.has_perm(f'core.view_{name}') or request.user.has_perm(f'core.change_{name}')
        if not can_view:
            continue
        image_field = 'logo' if model is Member else 'image'
        counts = model.objects.aggregate(
            total=Count('pk'), live=Count('pk', filter=published),
            drafts=Count('pk', filter=Q(is_published=False)),
            missing=Count('pk', filter=Q(is_published=True, **{image_field: ''})),
        )
        total, live, drafts, missing = (counts[key] for key in ('total', 'live', 'drafts', 'missing'))
        url = reverse(f'admin:core_{name}_changelist')
        cards.append({'title': title, 'icon': icon, 'total': total, 'live': live, 'url': url})
        if request.user.has_perm(f'core.add_{name}'):
            quick_links.append({'title': f'Добавить: {title.lower()}', 'icon': icon, 'url': reverse(f'admin:core_{name}_add')})
        if drafts:
            tasks.append({'title': f'{title}: черновики', 'count': drafts, 'url': url + '?is_published__exact=0'})
        if missing:
            tasks.append({'title': f'{title}: без изображения', 'count': missing, 'url': url + f'?{image_field}__exact='})
    if request.user.has_perm('core.change_sitesettings'):
        quick_links.insert(0, {'title': 'Контакты и логотипы', 'icon': 'tune', 'url': reverse('admin:core_sitesettings_changelist')})
    if request.user.has_perm('core.view_vacancy') or request.user.has_perm('core.change_vacancy'):
        vacancies_url = reverse('admin:core_vacancy_changelist')
        cards.append({'title': 'Вакансии', 'icon': 'work', 'total': Vacancy.objects.count(),
            'live': Vacancy.objects.open().count(), 'url': vacancies_url})
        if request.user.has_perm('core.add_vacancy'):
            quick_links.append({'title': 'Добавить вакансию', 'icon': 'work', 'url': reverse('admin:core_vacancy_add')})
    if request.user.has_perm('core.view_careerapplication') or request.user.has_perm('core.change_careerapplication'):
        applications_url = reverse('admin:core_careerapplication_changelist')
        quick_links.append({'title': 'Отклики и резюме', 'icon': 'contact_page', 'url': applications_url})
        count = CareerApplication.objects.filter(status=CareerApplication.Status.NEW).count()
        if count:
            tasks.insert(0, {'title': 'Новые отклики на вакансии', 'count': count, 'url': applications_url + '?status__exact=new'})
    if request.user.has_perm('core.view_membershipapplication') or request.user.has_perm('core.change_membershipapplication'):
        applications_url = reverse('admin:core_membershipapplication_changelist')
        quick_links.append({'title': 'Рассмотреть заявки', 'icon': 'assignment', 'url': applications_url})
        membership_counts = MembershipApplication.objects.aggregate(
            new=Count('pk', filter=Q(status='new')), review=Count('pk', filter=Q(status='review')),
        )
        for status, title in [('new', 'Новые заявки на членство'), ('review', 'Заявки на рассмотрении')]:
            count = membership_counts[status]
            if count:
                tasks.insert(0, {'title': title, 'count': count, 'url': applications_url + f'?status__exact={status}'})
    context.update({
        'overview_cards': cards,
        'quick_links': quick_links,
        'editorial_tasks': tasks,
        'scheduled_news': News.objects.filter(is_published=True, published_at__gt=now).count()
            if request.user.has_perm('core.view_news') or request.user.has_perm('core.change_news') else None,
        'recent_actions': LogEntry.objects.filter(user=request.user).select_related('content_type')[:8],
    })
    return context

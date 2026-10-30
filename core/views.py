import logging

from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from .localization import content_search, normalize_search_query
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from .forms import ContactMessageForm, MembershipApplicationForm, new_contact_submission_token, new_submission_token
from .forms import CareerApplicationForm, new_career_submission_token
from .career_service import submit_career_application
from .membership_constants import MEMBERSHIP_DECLARATION
from .membership_pdf import MembershipPDFError
from .membership_service import submit_membership_application
from .site_cache import get_site_navigation, get_site_settings
from .search import search_site

from .models import (
    ActivitySector, BoardMember, ContactMessage, Event, GalleryPhoto, HomeDirection, HomeSection,
    InstitutionalCooperation, Member, News, NewsTag, OfficialMeeting, Page, Vacancy,
)

logger = logging.getLogger(__name__)


@require_GET
def search(request):
    query = normalize_search_query(request.GET.get('q', ''))
    return render(request, 'core/search.html', {
        'page_title': _('Поиск по сайту'), 'query': query,
        'page_obj': search_site(query, request.GET.get('page'),
            unpublished_pages=get_site_navigation(request)['unpublished']),
    })


@sensitive_post_parameters()
@never_cache
@require_http_methods(['GET', 'POST'])
def membership(request):
    form = MembershipApplicationForm(
        request.POST if request.method == 'POST' else None,
        initial={'submission_token': new_submission_token()},
    )
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            application = submit_membership_application(form)
        except MembershipPDFError:
            logger.exception('Membership PDF generation failed')
            form.add_error(None, _('Не удалось сформировать заявку. Попробуйте отправить её ещё раз позднее.'))
            status = 503
        else:
            request.session['membership_receipt'] = application.reference
            return redirect('core:membership_success')
    return render(request, 'core/membership/form.html', {
        'page_title': _('Стать членом объединения'), 'nav_section': 'members',
        'form': form, 'membership_declaration': MEMBERSHIP_DECLARATION,
    }, status=status)


@never_cache
@require_GET
def membership_success(request):
    return render(request, 'core/membership/success.html', {
        'page_title': _('Заявка на членство'), 'nav_section': 'members',
        'membership_reference': request.session.get('membership_receipt'),
    })

def home(request):
    sections = list(HomeSection.objects.filter(is_visible=True))
    unpublished = get_site_navigation(request)['unpublished']
    for section in sections:
        section.link_visible = section.link_route not in unpublished
        section.secondary_visible = section.secondary_route not in unpublished
    limits = {section.key: section.items_limit for section in sections}
    now = timezone.now()
    events = Event.objects.filter(is_published=True)
    upcoming = Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now)
    home_events = (list(events.filter(upcoming).order_by('starts_at', 'pk')[:limits['events']])
        if 'events' in limits else [])
    return render(request, 'core/home.html', {
        'home_sections': sections,
        'home_focus': HomeDirection.objects.filter(is_published=True)[:4],
        'home_directions': HomeDirection.objects.filter(is_published=True)[:limits.get('directions', 4)],
        'home_gallery': GalleryPhoto.objects.filter(is_published=True)[:limits.get('community', 4)],
        'home_member_logos': Member.objects.filter(is_published=True).exclude(logo='')[:limits.get('members', 24)],
        'home_news': News.objects.published().filter(is_tukid_news=True)[:limits.get('news', 3)],
        'home_events': home_events,
        'home_meetings': OfficialMeeting.objects.published()[:limits.get('meetings', 3)],
        'home_cooperation': InstitutionalCooperation.objects.filter(is_published=True)[:limits.get('cooperation', 3)],
    })


def information_page(request, slug):
    if slug == 'contacts':
        return contacts(request)
    if slug == 'career':
        return redirect('core:career')
    page = get_object_or_404(Page, slug=slug, is_published=True)
    section = 'about' if slug in {'about', 'mission', 'board'} else slug
    template = f'core/pages/{slug}.html' if slug in Page.Section.values else 'core/pages/information.html'
    return render(request, template, {
        'page': page, 'page_title': page.localized('title'), 'nav_section': section,
        'meta_description': page.localized('meta_description'),
        'board_members': BoardMember.objects.filter(is_published=True).select_related('company') if slug == 'board' else [],
    })


@sensitive_post_parameters()
@never_cache
@require_http_methods(['GET', 'POST'])
def contacts(request):
    page = get_object_or_404(Page, slug='contacts', is_published=True)
    form = ContactMessageForm(
        request.POST if request.method == 'POST' else None,
        initial={'submission_token': new_contact_submission_token()},
    )
    if request.method == 'POST' and form.is_valid():
        # A signed submission UUID keeps double clicks and retried POSTs idempotent.
        ContactMessage.objects.get_or_create(pk=form.submission_id, defaults={
            **{name: form.cleaned_data[name] for name in form.Meta.fields},
            'language': request.LANGUAGE_CODE.split('-')[0],
        })
        messages.success(request, _('Спасибо! Ваше сообщение отправлено. Мы свяжемся с вами по указанным контактам.'))
        return redirect('core:contacts')
    settings = get_site_settings(request)
    return render(request, 'core/pages/contacts.html', {
        'page': page, 'page_title': page.localized('title'), 'nav_section': 'contacts',
        'meta_description': page.localized('meta_description'), 'form': form,
        'dgis_loader_url': settings.dgis_loader_url, 'dgis_url': settings.dgis_url,
        'dgis_map_config': {'latitude': float(settings.map_latitude),
                            'longitude': float(settings.map_longitude), 'zoom': min(settings.map_zoom, 18),
                            'key': settings.dgis_api_key.strip(), 'name': settings.localized('name'),
                            'address': settings.localized('address')},
    })


def member_list(request):
    members = Member.objects.filter(is_published=True).prefetch_related('sectors',
        Prefetch('vacancies', queryset=Vacancy.objects.open().only('id', 'company_id'), to_attr='open_vacancies'))
    query = normalize_search_query(request.GET.get('q', ''))
    sector = request.GET.get('sector', '').strip()
    if query:
        members = members.filter(content_search(('name', 'description', 'city', 'sectors__name'), query)).distinct()
    if sector:
        members = members.filter(sectors__slug=sector)
    return render(request, 'core/members/list.html', {
        'page_title': _('Наши члены'), 'nav_section': 'members',
        'page_obj': Paginator(members, 12).get_page(request.GET.get('page')),
        'sectors': ActivitySector.objects.all(), 'query': query, 'selected_sector': sector,
    })


def member_detail(request, slug):
    member = get_object_or_404(
        Member.objects.filter(is_published=True).prefetch_related('sectors').select_related('news_tag'),
        slug=slug,
    )
    news = News.objects.published().filter(tags=member.news_tag) if member.news_tag_id else News.objects.none()
    return render(request, 'core/members/detail.html', {
        'member': member, 'page_title': member.localized('name'), 'nav_section': 'members', 'related_news': news[:6],
        'member_vacancies': Vacancy.objects.open().filter(company=member).select_related('company')[:6],
    })


@sensitive_post_parameters()
@never_cache
@require_http_methods(['GET', 'POST'])
def career(request):
    page = get_object_or_404(Page, slug='career', is_published=True)
    vacancies = Vacancy.objects.open().select_related('company')
    companies = Member.objects.filter(pk__in=vacancies.values('company_id')).order_by('name')
    query = normalize_search_query(request.GET.get('q', ''))
    selected_company = request.GET.get('company', '').strip()[:180]
    if query:
        vacancies = vacancies.filter(content_search((
            'title', 'company__name', 'location', 'description', 'requirements', 'conditions',
        ), query))
    if selected_company:
        vacancies = vacancies.filter(company__slug=selected_company)
    initial = {'submission_token': new_career_submission_token()}
    selected_vacancy = Vacancy.objects.open().filter(slug=request.GET.get('vacancy', '')[:180]).first()
    if selected_vacancy:
        initial['vacancy'] = selected_vacancy.pk
    form = CareerApplicationForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        initial=initial,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            application = submit_career_application(form)
        except ValidationError as error:
            form.add_error('vacancy', error)
        else:
            request.session['career_receipt'] = application.reference
            return redirect('core:career_success')
    return render(request, 'core/pages/career.html', {
        'page': page, 'page_title': page.localized('title'), 'meta_description': page.localized('meta_description'),
        'nav_section': 'career', 'form': form, 'companies': companies, 'query': query,
        'selected_company': selected_company,
        'page_obj': Paginator(vacancies, 9).get_page(request.GET.get('page')),
    })


@never_cache
@require_GET
def career_success(request):
    get_object_or_404(Page, slug='career', is_published=True)
    if not request.session.get('career_receipt'):
        return redirect('core:career')
    return render(request, 'core/career/success.html', {
        'page_title': _('Резюме отправлено'), 'nav_section': 'career',
        'career_reference': request.session['career_receipt'],
    })


@require_GET
def vacancy_detail(request, slug):
    get_object_or_404(Page, slug='career', is_published=True)
    vacancy = get_object_or_404(Vacancy.objects.open().select_related('company'), slug=slug)
    return render(request, 'core/career/vacancy_detail.html', {
        'vacancy': vacancy, 'page_title': vacancy.localized('title'), 'nav_section': 'career',
    })


def news_list(request, tukid_only=False):
    news = News.objects.published().prefetch_related('tags')
    if tukid_only:
        news = news.filter(is_tukid_news=True)
    tag = None
    if request.GET.get('tag'):
        tag = get_object_or_404(NewsTag, slug=request.GET['tag'])
        news = news.filter(tags=tag)
    return render(request, 'core/news/list.html', {
        'page_title': _('Новости TÜKİD') if tukid_only else _('Все новости'), 'nav_section': 'news',
        'page_obj': Paginator(news, 12).get_page(request.GET.get('page')), 'selected_tag': tag,
    })


def news_detail(request, slug):
    article = get_object_or_404(News.objects.published().prefetch_related('tags'), slug=slug)
    return render(request, 'core/news/detail.html', {
        'article': article, 'page_title': article.localized('title'), 'nav_section': 'news',
        'meta_description': article.localized('meta_description'),
    })


def event_list(request, period='all'):
    events = Event.objects.filter(is_published=True)
    now = timezone.now()
    upcoming = Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now)
    titles = {'all': _('Все мероприятия'), 'upcoming': _('Анонсы'), 'past': _('Прошедшие мероприятия')}
    if period == 'upcoming':
        events = events.filter(upcoming).order_by('starts_at', 'pk')
    elif period == 'past':
        events = events.exclude(upcoming)
    return render(request, 'core/events/list.html', {
        'page_title': titles[period], 'nav_section': 'events', 'event_period': period,
        'page_obj': Paginator(events, 12).get_page(request.GET.get('page')),
    })


def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug, is_published=True)
    return render(request, 'core/events/detail.html', {
        'event': event, 'page_title': event.localized('title'), 'nav_section': 'events',
    })


def meeting_list(request):
    meetings = OfficialMeeting.objects.published()
    return render(request, 'core/meetings/list.html', {
        'page_title': _('Официальные встречи'), 'nav_section': 'meetings',
        'page_obj': Paginator(meetings, 12).get_page(request.GET.get('page')),
    })


def meeting_detail(request, slug):
    meeting = get_object_or_404(OfficialMeeting.objects.published().prefetch_related('photos'), slug=slug)
    return render(request, 'core/meetings/detail.html', {
        'page_title': meeting.localized('title'), 'nav_section': 'meetings', 'meeting': meeting,
        'meta_description': meeting.localized('meta_description'),
    })

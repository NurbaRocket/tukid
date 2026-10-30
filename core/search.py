"""Search public content, paginating in the database before loading records."""

from django.core.paginator import Paginator
from django.db.models import Case, CharField, IntegerField, Value, When
from django.utils.translation import gettext as _

from .localization import content_search
from .models import Event, Member, News, OfficialMeeting, Page, Vacancy


def search_site(query, page_number, *, unpublished_pages):
    sections = {
        'member': (Member.objects.filter(is_published=True), _('Наши члены'),
            'name', ('name', 'description', 'city', 'address', 'sectors__name'), 'description'),
        'news': (News.objects.published(), _('Все новости'),
            'title', ('title', 'summary', 'body', 'tags__name'), 'summary'),
        'event': (Event.objects.filter(is_published=True), _('Все мероприятия'),
            'title', ('title', 'description', 'location'), 'description'),
        'meeting': (OfficialMeeting.objects.published(), _('Официальные встречи'),
            'title', ('title', 'participants', 'purpose', 'outcomes'), 'purpose'),
        'page': (Page.objects.filter(is_published=True), _('Информация'),
            'title', ('title', 'body', 'meta_description'), 'body'),
    }
    if 'career' not in unpublished_pages:
        sections['vacancy'] = (Vacancy.objects.open().select_related('company'), _('Карьера'),
            'title', ('title', 'company__name', 'location', 'description', 'requirements', 'conditions'),
            'description')

    if not query:
        return Paginator([], 12).get_page(page_number)

    queries = []
    for kind, (records, label, title, fields, summary) in sections.items():
        queries.append(records.filter(content_search(fields, query)).order_by().annotate(
            kind=Value(kind, output_field=CharField()),
            priority=Case(When(content_search((title,), query), then=Value(0)),
                default=Value(1), output_field=IntegerField()),
        ).values('pk', 'kind', 'priority').distinct())

    matches = queries[0].union(*queries[1:]).order_by('priority', 'kind', '-pk')
    page = Paginator(matches, 12).get_page(page_number)
    rows = list(page.object_list)
    objects = {
        kind: records.in_bulk([row['pk'] for row in rows if row['kind'] == kind])
        for kind, (records, *_) in sections.items()
    }
    results = []
    for row in rows:
        kind = row['kind']
        obj = objects[kind].get(row['pk'])
        if obj is None:  # A concurrent edit may unpublish a result.
            continue
        records, label, title, fields, summary = sections[kind]
        results.append({
            'title': obj.localized(title), 'summary': obj.localized(summary),
            'url': obj.get_absolute_url(), 'section': label,
        })
    page.object_list = results
    return page

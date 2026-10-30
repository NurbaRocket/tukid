from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import ActivitySector, Event, Member, News, NewsTag, OfficialMeeting, Page, Vacancy


class SiteSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Member.objects.create(
            name='Альфа', slug='search-company', city='Бишкек', is_published=True,
            translations={'ky': {'name': 'Өнүгүү кеңеши'}, 'tr': {'name': 'Güneş şirketi'}},
        )
        cls.news = News.objects.create(
            title='Альфа жаңылыктары', slug='search-news', body='<p>Экономика Кыргызстана</p>',
            is_published=True, translations={'ky': {'title': 'Өнүгүү жаңылыктары'}},
        )
        cls.event = Event.objects.create(
            title='Альфа форум', slug='search-event', starts_at=timezone.now(), is_published=True,
        )
        cls.meeting = OfficialMeeting.objects.create(
            title='Альфа диалог', slug='search-meeting', date=timezone.localdate(),
            purpose='Сотрудничество', is_published=True,
        )
        cls.page = Page.objects.create(title='Альфа информация', slug='search-page', body='О проекте')
        cls.vacancy = Vacancy.objects.create(
            title='Альфа менеджер', slug='search-vacancy', company=cls.company,
            description='Организация мероприятий', requirements='Кыргыз тили', is_published=True,
        )

    def results(self, query, language='', **params):
        return self.client.get(f'{language}/search/', {'q': query, **params})

    def urls(self, response):
        return {result['url'] for result in response.context['page_obj']}

    def test_header_search_and_all_public_content_types(self):
        response = self.results('аЛьФа')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 6)
        self.assertEqual(self.urls(response), {
            obj.get_absolute_url() for obj in (
                self.company, self.news, self.event, self.meeting, self.page, self.vacancy,
            )
        })
        self.assertContains(response, 'action="/search/"', count=2)
        self.assertContains(response, 'noto-sans-variable.woff2')

    def test_unicode_case_and_terms_in_different_fields(self):
        for query, language in [('ӨНҮГҮҮ КЕҢЕШИ', '/ky'), ('кеңеши өнүгүү', '/ky'),
                                ('gÜnEŞ ŞİRKETİ', '/tr'), ('GÜNEŞ ŞıRKETı', '/tr'), ('бишкек альфа', '')]:
            with self.subTest(query=query):
                response = self.client.get(f'{language}/members/', {'q': query})
                self.assertEqual(list(response.context['page_obj']), [self.company])
        response = self.results('ЖАҢЫЛЫКТАРЫ ӨНҮГҮҮ', '/ky')
        self.assertEqual(self.urls(response), {'/ky/news/posts/search-news/'})
        response = self.client.get('/career/', {'q': 'тили альфа кыргыз'})
        self.assertEqual(list(response.context['page_obj']), [self.vacancy])

    def test_query_normalization_literal_punctuation_and_escaping(self):
        response = self.results('  Бишкек\t\n  Альфа\u00a0 ')
        self.assertEqual(response.context['query'], 'Бишкек Альфа')
        self.assertIn(self.company.get_absolute_url(), self.urls(response))
        self.company.name = 'C++ [KG]'
        self.company.save()
        self.assertEqual(self.urls(self.results('C++ [KG]')), {
            self.company.get_absolute_url(), self.vacancy.get_absolute_url(),
        })
        self.assertEqual(self.urls(self.results('.*')), set())
        response = self.results('<script>alert(1)</script>')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        response = self.results('x' * 500)
        self.assertEqual(len(response.context['query']), 200)
        response = self.results(' '.join(['слово'] * 100))
        self.assertEqual(len(response.context['query'].split()), 12)
        response = self.client.get('/tr/members/', {'q': 'Gu\u0308nes\u0327'})
        self.assertEqual(list(response.context['page_obj']), [self.company])

    def test_drafts_future_publications_and_closed_jobs_are_hidden(self):
        future = timezone.now() + timedelta(days=2)
        Member.objects.create(name='Альфа hidden', slug='hidden-search')
        News.objects.create(title='Альфа draft', slug='draft-search')
        News.objects.create(title='Альфа future', slug='future-search', is_published=True, published_at=future)
        Event.objects.create(title='Альфа draft', slug='draft-search', starts_at=future)
        OfficialMeeting.objects.create(title='Альфа draft', slug='draft-search', date=timezone.localdate())
        OfficialMeeting.objects.create(title='Альфа future', slug='future-search', date=timezone.localdate(),
            is_published=True, published_at=future)
        Page.objects.create(title='Альфа draft', slug='draft-search', is_published=False)
        for index, extra in enumerate(({'is_closed': True}, {'published_at': future},
                {'closes_on': timezone.localdate() - timedelta(days=1)}, {'is_published': False})):
            Vacancy.objects.create(title='Альфа hidden', slug=f'hidden-search-{index}', company=self.company,
                **{'is_published': True, **extra})
        self.assertEqual(self.results('альфа').context['page_obj'].paginator.count, 6)
        Page.objects.filter(slug='career').update(is_published=False)
        self.assertNotIn(self.vacancy.get_absolute_url(), self.urls(self.results('альфа')))

    def test_related_matches_have_no_duplicates_and_title_matches_come_first(self):
        for index in range(2):
            sector = ActivitySector.objects.create(name=f'Экономика {index}', slug=f'search-sector-{index}')
            self.company.sectors.add(sector)
            tag = NewsTag.objects.create(name=f'Экономика {index}', slug=f'search-tag-{index}')
            self.news.tags.add(tag)
        response = self.results('экономика')
        self.assertEqual(response.context['page_obj'].paginator.count, 2)
        title_match = News.objects.create(title='Экономика', slug='title-match', is_published=True)
        self.assertEqual(list(self.results('экономика').context['page_obj'])[0]['url'], title_match.get_absolute_url())

    def test_pagination_localized_links_and_empty_search(self):
        for index in range(15):
            News.objects.create(title=f'Тест пагинации {index}', slug=f'paging-{index}', is_published=True)
        response = self.results('пагинации', '/ky')
        self.assertEqual(response.context['page_obj'].paginator.count, 15)
        self.assertEqual(len(response.context['page_obj']), 12)
        self.assertContains(response, 'page=2')
        self.assertTrue(all(url.startswith('/ky/') for url in self.urls(response)))
        response = self.results('пагинации', '/ky', page=2)
        self.assertEqual(len(response.context['page_obj']), 3)
        for page in ['invalid', -1, 999]:
            self.assertEqual(self.results('пагинации', page=page).status_code, 200)
        for query in ['', ' \t\u00a0\n ']:
            response = self.results(query)
            self.assertEqual(response.context['page_obj'].paginator.count, 0)
            self.assertContains(response, 'Введите слово или несколько слов для поиска.')
        self.assertEqual(self.client.post('/search/').status_code, 405)

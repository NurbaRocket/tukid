from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from .models import BoardMember, Event, Member, News, OfficialMeeting


class DemoContentTests(TestCase):
    models = (Member, BoardMember, News, OfficialMeeting, Event)

    def seed(self):
        call_command('seed_demo', stdout=StringIO())

    def test_seeds_ten_of_each_with_working_images_and_visible_demo_labels(self):
        self.seed()
        for model in self.models:
            self.assertEqual(model.objects.filter(is_demo=True, is_published=True).count(), 10)
        for model, field in [(Member, 'logo'), (BoardMember, 'photo'), (News, 'image'), (OfficialMeeting, 'image'), (Event, 'image')]:
            for obj in model.objects.filter(is_demo=True):
                asset = getattr(obj, field)
                self.assertTrue(asset.storage.exists(asset.name))
        for route in ['home', 'news', 'members', 'board', 'meetings', 'events']:
            response = self.client.get(reverse(f'core:{route}'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'demo-badge')
        for model in (Member, News, OfficialMeeting, Event):
            obj = model.objects.filter(is_demo=True).first()
            self.assertContains(self.client.get(obj.get_absolute_url()), 'Демонстрационный материал.')
        company = Member.objects.get(slug='demo-tukid-01')
        self.assertEqual(company.news_tag.news.count(), 1)
        self.assertEqual(company.sectors.count(), 1)
        self.assertContains(self.client.get(company.get_absolute_url()), company.news_tag.news.first().title)
        self.assertEqual(Event.objects.filter(is_demo=True, starts_at__gt=company.created_at).count(), 7)

    def test_repeat_run_preserves_edits_regular_records_and_file_names(self):
        real = Member.objects.create(name='Действительная компания', slug='real-member', description='Свой текст')
        self.seed()
        edited = News.objects.get(slug='demo-tukid-01')
        edited.title = 'Текст от редактора'
        edited.save()
        files_before = {model.__name__: list(model.objects.filter(is_demo=True).values_list('pk', 'photo' if model is BoardMember else 'logo' if model is Member else 'image')) for model in self.models}
        self.seed()
        edited.refresh_from_db()
        real.refresh_from_db()
        self.assertEqual(edited.title, 'Текст от редактора')
        self.assertEqual(real.description, 'Свой текст')
        self.assertFalse(real.is_demo)
        for model in self.models:
            self.assertEqual(model.objects.filter(is_demo=True).count(), 10)
            self.assertEqual(files_before[model.__name__], list(model.objects.filter(is_demo=True).values_list('pk', 'photo' if model is BoardMember else 'logo' if model is Member else 'image')))

    def test_slug_collision_preserves_regular_content_and_rolls_back_seed(self):
        real = News.objects.create(title='Оригинальная новость', slug='demo-tukid-01', body='Содержание редактора')
        with self.assertRaises(CommandError):
            self.seed()
        real.refresh_from_db()
        self.assertEqual(real.body, 'Содержание редактора')
        self.assertFalse(real.is_demo)
        for model in self.models:
            self.assertFalse(model.objects.filter(is_demo=True).exists())

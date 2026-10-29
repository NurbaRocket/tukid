from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.templatetags.static import static
from django.utils import timezone

from .models import (
    HomeSection, InstitutionalCooperation, MeetingPhoto, Member, OfficialMeeting,
)


def image(name='photo.svg'):
    return SimpleUploadedFile(name, b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h10v10z"/></svg>', content_type='image/svg+xml')


def meeting(**kwargs):
    values = {
        'title': 'Официальная встреча', 'slug': 'official-meeting',
        'date': timezone.localdate()-timedelta(days=1),
        'participants': 'Представители TÜKİD и делового сообщества',
        'purpose': 'Обсудить совместные инициативы.',
        'outcomes': 'Согласованы следующие шаги.',
        'is_published': True,
    }
    return OfficialMeeting.objects.create(**{**values, **kwargs})


class HomepageStructureTests(TestCase):
    def test_six_sections_and_membership_button(self):
        response = self.client.get('/')
        self.assertEqual([section.key for section in response.context['home_sections']], [
            'home', 'members', 'news', 'events', 'meetings', 'cooperation',
        ])
        text = response.content.decode()
        positions = [text.index(f'id="{key}"') for key in ('home', 'members', 'news', 'events', 'meetings', 'cooperation')]
        self.assertEqual(positions, sorted(positions))
        hero = text[text.index('<section id="home"'):text.index('</section>', text.index('<section id="home"'))]
        self.assertIn('href="/about/">О нас', hero)
        self.assertIn('href="/membership/">Стать членом', hero)
        self.assertNotContains(response, 'id="directions"')
        self.assertFalse(HomeSection.objects.get(key='directions').is_visible)
        self.assertFalse(HomeSection.objects.get(key='about').is_visible)
        self.assertFalse(HomeSection.objects.get(key='community').is_visible)

    def test_member_strip_uses_only_published_logos_and_obeys_limit(self):
        Member.objects.create(name='Без логотипа', slug='no-logo', is_published=True)
        Member.objects.create(name='Черновой логотип', slug='draft-logo', logo=image('draft.svg'))
        public = [Member.objects.create(name=f'Участник {i}', slug=f'member-{i}',
            logo=image(f'member-{i}.svg'), is_published=True) for i in range(3)]
        section = HomeSection.objects.get(key='members')
        section.items_limit = 2
        section.save()
        response = self.client.get('/')
        self.assertEqual(list(response.context['home_member_logos']), public[:2])
        self.assertContains(response, 'data-member-marquee')
        self.assertContains(response, 'view.members.js')
        self.assertContains(response, public[0].logo.url)
        self.assertContains(response, public[0].get_absolute_url())
        self.assertNotContains(response, 'Черновой логотип')
        self.assertNotContains(response, 'Без логотипа')

    def test_institutional_cards_are_editable_and_respect_visibility(self):
        cards = list(InstitutionalCooperation.objects.filter(is_published=True))
        self.assertEqual(len(cards), 3)
        response = self.client.get('/')
        for card in cards:
            self.assertContains(response, card.description)
        hidden = cards[0]
        hidden.is_published = False
        hidden.save()
        response = self.client.get('/')
        self.assertNotContains(response, hidden.title)
        custom = InstitutionalCooperation.objects.create(title='Новое взаимодействие',
            description='Текст из админки', icon='handshake', sort_order=0, is_published=True,
            website='https://example.com')
        response = self.client.get('/')
        self.assertContains(response, custom.title)
        self.assertContains(response, custom.description)
        self.assertContains(response, 'href="https://example.com"')

    def test_cooperation_logos_allow_upload_override_and_neutral_fallback(self):
        card = InstitutionalCooperation.objects.get(default_logo='president-kyrgyzstan')
        self.assertEqual(card.image_url, static('core/images/institutions/president-kyrgyzstan.png'))
        self.assertContains(self.client.get('/'), card.image_url)
        card.image = image('replacement-logo.svg')
        card.save()
        self.assertEqual(card.image_url, card.image.url)
        self.assertContains(self.client.get('/'), card.image.url)

        custom = InstitutionalCooperation.objects.create(title='Новый партнёр', description='Информация о партнёре')
        self.assertEqual(custom.image_url, static('core/images/placeholders/institution.svg'))

    def test_cooperation_copy_migration_preserves_editorial_changes(self):
        card = InstitutionalCooperation.objects.get(default_logo='president-kyrgyzstan')
        card.title = 'Противодействие коррупции'
        card.description = 'Описание от редактора'
        card.default_logo = ''
        card.image = image('editor-logo.svg')
        card.website = 'https://example.com/editor'
        card.is_published = False
        card.sort_order = 99
        card.save()
        before = (card.title, card.description, card.image.name, card.website, card.is_published, card.sort_order)
        section = HomeSection.objects.get(key='cooperation')
        section.eyebrow = 'Наше сотрудничество'
        section.description = 'Вступление от редактора'
        section.save()
        seed = InstitutionalCooperation.objects.get(default_logo='cabinet-kyrgyzstan')
        updated_title = seed.title
        seed.title = 'Инвестиционное взаимодействие'
        seed.description = f'{updated_title}.'
        seed.default_logo = ''
        seed.save()

        migration = import_module('core.migrations.0011_cooperation_design')
        migration.configure_cooperation(apps, connection.schema_editor())
        card.refresh_from_db()
        section.refresh_from_db()
        seed.refresh_from_db()
        self.assertEqual(before, (card.title, card.description, card.image.name, card.website, card.is_published, card.sort_order))
        self.assertEqual(section.eyebrow, 'Наше сотрудничество')
        self.assertEqual(section.description, 'Вступление от редактора')
        self.assertEqual(seed.title, updated_title)
        self.assertEqual(seed.default_logo, 'cabinet-kyrgyzstan')


class OfficialMeetingTests(TestCase):
    def test_home_card_detail_and_photo_gallery(self):
        entry = meeting(image=image())
        photo = MeetingPhoto.objects.create(meeting=entry, image=image('extra.svg'), caption='Фотография встречи')
        response = self.client.get('/')
        for value in (entry.title, entry.participants, entry.purpose, entry.outcomes, entry.image.url):
            self.assertContains(response, value)
        self.assertEqual(list(response.context['home_meetings']), [entry])
        self.assertContains(self.client.get(reverse('core:meetings')), entry.title)
        detail = self.client.get(entry.get_absolute_url())
        self.assertContains(detail, entry.date.strftime('%Y-%m-%d'))
        self.assertContains(detail, photo.image.url)
        self.assertContains(detail, photo.caption)
        self.assertContains(detail, 'data-plugin-lightbox')

    def test_meetings_hide_drafts_and_future_publications(self):
        public = meeting()
        hidden = meeting(title='Неопубликованная встреча', slug='draft', is_published=False)
        scheduled = meeting(title='Будущая публикация встречи', slug='scheduled',
            published_at=timezone.now()+timedelta(days=1))
        for url in ['/', reverse('core:meetings')]:
            response = self.client.get(url)
            self.assertContains(response, public.title)
            self.assertNotContains(response, hidden.title)
            self.assertNotContains(response, scheduled.title)
        for entry in [hidden, scheduled]:
            self.assertEqual(self.client.get(entry.get_absolute_url()).status_code, 404)

    def test_meeting_order_limit_and_pagination(self):
        now = timezone.localdate()
        entries = [meeting(title=f'Встреча {i:02}', slug=f'meeting-{i}', date=now-timedelta(days=i)) for i in range(14)]
        response = self.client.get('/')
        self.assertEqual(list(response.context['home_meetings']), entries[:3])
        response = self.client.get(reverse('core:meetings'))
        self.assertEqual(response.context['page_obj'].paginator.count, 14)
        second = self.client.get(reverse('core:meetings'), {'page': 2})
        self.assertEqual(len(second.context['page_obj']), 2)

    def test_meeting_text_is_escaped(self):
        entry = meeting(purpose='<script>alert(77)</script>', outcomes='<b>Обычный текст</b>')
        response = self.client.get(entry.get_absolute_url())
        self.assertNotContains(response, '<script>alert(77)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertContains(response, '&lt;b&gt;')


class HomepageAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('homepage-admin', 'admin@example.com', 'test-password')

    def test_admin_can_create_meeting_with_cover_and_multiple_photos(self):
        self.client.force_login(self.user)
        for name in ('officialmeeting', 'institutionalcooperation'):
            self.assertEqual(self.client.get(reverse(f'admin:core_{name}_add')).status_code, 200)
        response = self.client.post(reverse('admin:core_officialmeeting_add'), {
            'title': 'Встреча из админки', 'slug': 'from-admin',
            'date': '2026-10-28', 'participants': 'Участники', 'purpose': 'Цель', 'outcomes': 'Итоги',
            'image': image('cover.svg'), 'published_at_0': '2026-10-28',
            'published_at_1': '09:00:00', 'is_published': 'on',
            'photos-TOTAL_FORMS': '2', 'photos-INITIAL_FORMS': '0',
            'photos-MIN_NUM_FORMS': '0', 'photos-MAX_NUM_FORMS': '1000',
            'photos-0-image': image('photo-1.svg'), 'photos-0-caption': 'Первое фото', 'photos-0-sort_order': '0',
            'photos-1-image': image('photo-2.svg'), 'photos-1-caption': 'Второе фото', 'photos-1-sort_order': '1',
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        entry = OfficialMeeting.objects.get(slug='from-admin')
        self.assertEqual(entry.photos.count(), 2)
        self.assertTrue(entry.image)

    def test_staff_needs_permission_for_meetings(self):
        staff = get_user_model().objects.create_user('meeting-reader', is_staff=True)
        self.client.force_login(staff)
        listing = reverse('admin:core_officialmeeting_changelist')
        self.assertEqual(self.client.get(listing).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='view_officialmeeting'))
        self.assertEqual(self.client.get(listing).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:core_officialmeeting_add')).status_code, 403)

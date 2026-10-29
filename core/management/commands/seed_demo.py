from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.demo_content import (
    COMPANIES, EVENTS, MEETINGS, NEWS, POSITIONS, cover_art, logo_art, portrait_art,
)
from core.models import ActivitySector, BoardMember, Event, Member, News, NewsTag, OfficialMeeting


class Command(BaseCommand):
    help = 'Добавить по 10 явно отмеченных демозаписей. Повторный запуск сохраняет существующие записи и правки.'

    def handle(self, *args, **options):
        self.created_files = []
        self.created_counts = {model.__name__: 0 for model in (Member, BoardMember, News, OfficialMeeting, Event)}
        try:
            with transaction.atomic():
                self.seed()
        except Exception:
            # File storage is not transactional; remove only files from this failed run.
            for storage, name in self.created_files:
                storage.delete(name)
            raise
        for model, count in self.created_counts.items():
            self.stdout.write(f'{model}: +{count}')
        self.stdout.write(self.style.SUCCESS('Демоматериалы готовы. Фильтр в админке: «Демонстрационная запись».'))

    def create(self, model, lookup, values, artwork_field, artwork, number):
        obj, created = model.objects.get_or_create(**lookup, defaults={**values, 'is_demo': True, 'is_published': True})
        if not created:
            if not obj.is_demo:
                raise CommandError(f'Адрес демонстрационной записи занят обычной записью: {model.__name__}. Данные не изменены.')
            return obj, False
        field = getattr(obj, artwork_field)
        field.save(f'demo-{number:02}.svg', ContentFile(artwork.encode('utf-8')), save=False)
        self.created_files.append((field.storage, field.name))
        obj.full_clean()
        obj.save()
        self.created_counts[model.__name__] += 1
        return obj, True

    def seed(self):
        now = timezone.now().replace(microsecond=0)
        today = timezone.localdate(now)
        for i, (brand, initials, sector_name, director) in enumerate(COMPANIES):
            number = i + 1
            prefix = f'demo-tukid-{number:02}'
            sector, _ = ActivitySector.objects.get_or_create(name=sector_name, defaults={'slug': f'demo-sector-{number:02}'})
            tag, _ = NewsTag.objects.get_or_create(slug=prefix, defaults={'name': f'{brand} — демо'})
            company, created = self.create(Member, {'slug': prefix}, {
                'name': brand, 'city': ['Бишкек', 'Ош', 'Бишкек', 'Каракол'][i % 4],
                'address': f'Демонстрационный офис № {number}, адрес для примера',
                'email': f'hello@company-{number:02}.example', 'director_name': director,
                'description': f'<p>{brand} — вымышленная компания в сфере «{sector_name}».</p>'
                    '<p>Демонстрационная карточка показывает, как будут выглядеть описание, контакты, '
                    'направления деятельности и связанные новости действительного члена объединения.</p>',
                'news_tag': tag, 'member_since': today-timedelta(days=365+30*i), 'sort_order': 100+i,
            }, 'logo', logo_art(i, brand, initials), number)
            if created:
                company.sectors.add(sector)

            self.create(BoardMember, {'name': director, 'is_demo': True}, {
                'position': POSITIONS[i], 'company': company, 'sort_order': 100+i,
                'biography': '<p>Вымышленный участник совета для проверки оформления страницы. '
                    f'Пример профессиональной области: {sector_name.lower()}. Здесь можно разместить '
                    'краткую биографию и информацию о деятельности в объединении.</p>',
            }, 'photo', portrait_art(i, director), number)

            title, label, summary = NEWS[i]
            article, created = self.create(News, {'slug': prefix}, {
                'title': title, 'summary': summary, 'published_at': now-timedelta(days=i*3+1),
                'body': '<p>Демонстрационный материал для проверки сайта. Описанные события вымышлены.</p>'
                    f'<h2>{title}</h2><p>{summary}</p>'
                    '<p>Такая публикация может включать рассказ о событии, основные темы обсуждения, '
                    'мнения участников и информацию о следующих шагах.</p>'
                    '<h2>Пространство для сотрудничества</h2><p>Открытый обмен опытом, профессиональные '
                    'знакомства и взаимная поддержка помогают создавать связи между людьми и компаниями.</p>'
                    '<blockquote><p>Совместные идеи начинаются с открытого диалога.</p></blockquote>'
                    '<p>Замените этот текст реальным материалом и загрузите фотографии через админку.</p>',
                'image_alt': f'Демонстрационная иллюстрация: {label}',
            }, 'image', cover_art(i, label), number)
            if created:
                article.tags.add(tag)

            title, label, purpose, outcomes = MEETINGS[i]
            self.create(OfficialMeeting, {'slug': prefix}, {
                'title': title, 'date': today-timedelta(days=i*4+2),
                'participants': f'Представители демонстрационных компаний {brand} и {COMPANIES[(i+1) % 10][0]}.',
                'purpose': purpose, 'outcomes': outcomes,
                'published_at': now-timedelta(days=i*4+1),
                'meta_description': 'Демонстрационная встреча: событие и участники вымышлены.',
                'image_alt': f'Демонстрационная иллюстрация: {label}',
            }, 'image', cover_art(i+3, label), number)

            starts = (now+timedelta(days=7+i*5) if i < 7 else now-timedelta(days=7+(i-7)*10))
            starts = starts.astimezone(timezone.get_current_timezone()).replace(hour=10+i % 4, minute=0)
            self.create(Event, {'slug': prefix}, {
                'title': EVENTS[i], 'starts_at': starts, 'ends_at': starts+timedelta(hours=2),
                'location': 'Бишкек · демонстрационная площадка',
                'description': f'<p>{summary}</p><p>Демонстрационный анонс. Дата и место условные; '
                    'мероприятие не запланировано в действительности.</p>'
                    '<h2>Пример программы</h2><ul><li>Знакомство участников.</li>'
                    '<li>Обсуждение основной темы.</li><li>Обмен идеями и свободное общение.</li></ul>',
                'image_alt': f'Демонстрационная иллюстрация: {label}',
            }, 'image', cover_art(i+1, 'Встречи и события'), number)

import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .localization import TranslatedContent
from .validators import validate_favicon, validate_logo, validate_photo


def member_logo_path(instance, filename):
    return f'members/logos/{uuid4().hex}{Path(filename).suffix.lower()}'


def site_image_path(instance, filename):
    return f'site/{instance._meta.model_name}/{uuid4().hex}{Path(filename).suffix.lower()}'


def photo_field(label, **kwargs):
    return models.FileField(
        label, upload_to=site_image_path, blank=kwargs.pop('blank', True),
        validators=[FileExtensionValidator(['svg', 'png', 'jpg', 'jpeg', 'webp']), validate_photo],
        help_text='SVG, PNG, JPG или WebP, до 8 МБ.', **kwargs,
    )


PUBLIC_ROUTES = [
    ('home', 'Главная'), ('about', 'О нас'), ('mission', 'Миссия и видение'),
    ('board', 'Совет правления'), ('members', 'Наши члены'), ('news', 'Все новости'),
    ('tukid_news', 'Новости TUKID'), ('events', 'Все мероприятия'),
    ('upcoming_events', 'Анонсы'), ('past_events', 'Прошедшие мероприятия'),
    ('career', 'Карьера'), ('contacts', 'Контакты'),
    ('membership', 'Стать членом объединения'),
    ('meetings', 'Официальные встречи'),
]


class Page(TranslatedContent):
    class Section(models.TextChoices):
        ABOUT = 'about', 'О нас'
        MISSION = 'mission', 'Миссия и видение'
        BOARD = 'board', 'Совет правления'
        CAREER = 'career', 'Карьера'
        CONTACTS = 'contacts', 'Контакты'

    slug = models.SlugField('Адрес страницы', max_length=150, unique=True)
    title = models.CharField('Заголовок', max_length=200)
    body = models.TextField('Содержание', blank=True)
    image = photo_field('Обложка страницы')
    image_alt = models.CharField('Описание изображения', max_length=250, blank=True)
    meta_description = models.CharField('Описание для поисковых систем', max_length=300, blank=True)
    is_published = models.BooleanField('Опубликовано', default=True, db_index=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'информационная страница'
        verbose_name_plural = 'Информационные страницы'
        ordering = ['pk']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.slug in self.Section.values:
            return reverse(f'core:{self.slug}')
        return reverse('core:page', kwargs={'slug': self.slug})


class ActivitySector(TranslatedContent):
    name = models.CharField('Название', max_length=150, unique=True)
    slug = models.SlugField('Код для ссылки', max_length=150, unique=True)

    class Meta:
        verbose_name = 'сфера деятельности'
        verbose_name_plural = 'Сферы деятельности'
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name


class NewsTag(TranslatedContent):
    name = models.CharField('Название', max_length=150, unique=True)
    slug = models.SlugField('Код для ссылки', max_length=150, unique=True)

    class Meta:
        verbose_name = 'тег новостей'
        verbose_name_plural = 'Теги новостей'
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name


class DemoContent(TranslatedContent):
    is_demo = models.BooleanField(
        'Демонстрационная запись', default=False,
        help_text='Вымышленный материал для проверки оформления. На сайте показывается отметка «Демо».',
    )

    class Meta:
        abstract = True


class Member(DemoContent):
    name = models.CharField('Название компании', max_length=200)
    slug = models.SlugField('Адрес страницы', max_length=180, unique=True)
    logo = models.FileField(
        'Логотип', upload_to=member_logo_path, blank=True,
        validators=[FileExtensionValidator(['svg', 'png', 'jpg', 'jpeg', 'webp']), validate_logo],
        help_text='SVG, PNG, JPG или WebP. Максимум 2 МБ.',
    )
    address = models.CharField('Адрес', max_length=300, blank=True)
    city = models.CharField('Город', max_length=120, blank=True)
    phone = models.CharField('Телефон', max_length=60, blank=True)
    email = models.EmailField('Электронная почта', blank=True)
    website = models.URLField('Сайт компании', blank=True)
    description = models.TextField('Описание', blank=True)
    sectors = models.ManyToManyField(ActivitySector, verbose_name='Сферы деятельности', blank=True, related_name='members')
    news_tag = models.ForeignKey(
        NewsTag, verbose_name='Тег для новостей', blank=True, null=True,
        on_delete=models.SET_NULL, related_name='members',
        help_text='Новости с этим тегом появятся на странице компании.',
    )
    director_name = models.CharField('Генеральный директор', max_length=200, blank=True)
    member_since = models.DateField('Дата вступления', blank=True, null=True)
    is_published = models.BooleanField('Опубликовано на сайте', default=False, db_index=True)
    sort_order = models.PositiveIntegerField('Порядок отображения', default=0)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'член объединения'
        verbose_name_plural = 'Члены объединения'
        ordering = ['sort_order', 'name', 'pk']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('core:member_detail', kwargs={'slug': self.slug})

    @property
    def phone_link(self):
        return re.sub(r'[^\d+]', '', self.phone)


class NewsQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class News(DemoContent):
    title = models.CharField('Заголовок', max_length=250)
    slug = models.SlugField('Адрес страницы', max_length=180, unique=True)
    summary = models.TextField('Краткое описание', blank=True)
    body = models.TextField('Текст новости')
    image = photo_field('Изображение новости')
    image_alt = models.CharField('Описание изображения', max_length=250, blank=True)
    meta_description = models.CharField('Описание для поисковых систем', max_length=300, blank=True)
    tags = models.ManyToManyField(NewsTag, verbose_name='Теги', blank=True, related_name='news')
    is_tukid_news = models.BooleanField('Новость TÜKİD', default=True)
    is_published = models.BooleanField('Опубликовано', default=False, db_index=True)
    published_at = models.DateTimeField('Дата публикации', default=timezone.now, db_index=True)

    objects = NewsQuerySet.as_manager()

    class Meta:
        verbose_name = 'новость'
        verbose_name_plural = 'Новости'
        ordering = ['-published_at', '-pk']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('core:news_detail', kwargs={'slug': self.slug})

    @property
    def image_url(self):
        return self.image.url if self.image else ''


class Event(DemoContent):
    title = models.CharField('Название', max_length=250)
    slug = models.SlugField('Адрес страницы', max_length=180, unique=True)
    description = models.TextField('Описание', blank=True)
    image = photo_field('Изображение мероприятия')
    image_alt = models.CharField('Описание изображения', max_length=250, blank=True)
    starts_at = models.DateTimeField('Начало', db_index=True)
    ends_at = models.DateTimeField('Окончание', blank=True, null=True)
    location = models.CharField('Место проведения', max_length=300, blank=True)
    registration_url = models.URLField('Ссылка для регистрации', blank=True)
    is_published = models.BooleanField('Опубликовано', default=False, db_index=True)

    class Meta:
        verbose_name = 'мероприятие'
        verbose_name_plural = 'Мероприятия'
        ordering = ['-starts_at', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gte=F('starts_at')),
                name='event_end_not_before_start',
                violation_error_message='Окончание мероприятия не может быть раньше начала.',
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('core:event_detail', kwargs={'slug': self.slug})

    @property
    def image_url(self):
        return self.image.url if self.image else ''

    @property
    def is_past(self):
        return (self.ends_at or self.starts_at) < timezone.now()


class SiteSettings(TranslatedContent):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField('Короткое название', max_length=100, default='TUKID')
    organization_name = models.CharField('Полное название организации', max_length=300, default='Общественное объединение турецко-кыргызских предпринимателей, культуры, солидарности и дружбы')
    site_description = models.CharField('Описание сайта для поисковых систем', max_length=300, default='TUKID — Общественное объединение турецко-кыргызских предпринимателей, культуры, солидарности и дружбы.')
    email = models.EmailField('Почта', default='tukid.kg@gmail.com')
    phone = models.CharField('Телефон', max_length=60, default='+996502119983')
    whatsapp = models.CharField('Номер WhatsApp', max_length=60, default='+996502119983', help_text='Номер с кодом страны. Пробелы и скобки допустимы.')
    address = models.CharField('Адрес', max_length=300, default='г. Бишкек, улица Турусбекова, 82/1')
    facebook_url = models.URLField('Facebook', blank=True, default='https://www.facebook.com/tukid.kg')
    instagram_url = models.URLField('Instagram', blank=True, default='https://www.instagram.com/tukid_kg/')
    telegram_url = models.URLField('Telegram', blank=True)
    maps_url = models.URLField('Ссылка на карту', blank=True)
    dgis_api_key = models.CharField('API-ключ карты 2ГИС', max_length=200, blank=True,
        help_text='Ключ RasterJS API из Менеджера Платформы 2ГИС. Используется в браузере для карты с отметкой офиса.')
    map_latitude = models.DecimalField('Широта на карте 2ГИС', max_digits=9, decimal_places=6,
        default=Decimal('42.875314'), validators=[MinValueValidator(-90), MaxValueValidator(90)])
    map_longitude = models.DecimalField('Долгота на карте 2ГИС', max_digits=9, decimal_places=6,
        default=Decimal('74.584443'), validators=[MinValueValidator(-180), MaxValueValidator(180)])
    map_zoom = models.PositiveSmallIntegerField('Масштаб карты 2ГИС', default=16,
        validators=[MinValueValidator(1), MaxValueValidator(19)])
    header_logo = models.FileField('Логотип шапки и админки', upload_to=site_image_path, blank=True, validators=[FileExtensionValidator(['svg', 'png', 'jpg', 'jpeg', 'webp']), validate_logo], help_text='Если не загружен, используется текущий логотип из шапки. До 2 МБ.')
    footer_logo = models.FileField('Логотип футера', upload_to=site_image_path, blank=True, validators=[FileExtensionValidator(['svg', 'png', 'jpg', 'jpeg', 'webp']), validate_logo])
    favicon = models.FileField('Иконка сайта', upload_to=site_image_path, blank=True, validators=[FileExtensionValidator(['ico', 'svg', 'png']), validate_favicon])
    show_contact_bar = models.BooleanField('Показывать контакты над шапкой', default=True)
    footer_text = models.TextField('Текст футера', blank=True, help_text='Если пусто, выводится полное название организации.')
    copyright_text = models.CharField('Текст после названия в копирайте', max_length=200, default='Все права защищены.')
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'настройки сайта'
        verbose_name_plural = 'Настройки сайта'
        constraints = [models.CheckConstraint(condition=Q(id=1), name='one_site_settings_record')]

    def __str__(self):
        return 'Настройки сайта TUKID'

    @property
    def header_logo_url(self):
        return self.header_logo.url if self.header_logo else static('core/images/tukid_logo_text.svg')

    @property
    def footer_logo_url(self):
        return self.footer_logo.url if self.footer_logo else static('core/images/tukid_full_logo_white.svg')

    @property
    def favicon_url(self):
        return self.favicon.url if self.favicon else static('core/images/tukid_logo_icon_no_text.ico')

    @property
    def phone_link(self):
        return re.sub(r'[^\d+]', '', self.phone)

    @property
    def dgis_loader_url(self):
        if not self.dgis_api_key.strip():
            return ''
        return 'https://maps.api.2gis.ru/2.0/loader.js?' + urlencode({
            'pkg': 'full', 'key': self.dgis_api_key.strip(),
        })

    @property
    def dgis_url(self):
        parsed = urlsplit(self.maps_url)
        if parsed.scheme == 'https' and parsed.hostname in {'2gis.kg', '2gis.ru', '2gis.com'}:
            return self.maps_url
        return 'https://2gis.kg/bishkek/search/' + quote(self.address, safe='')

    @property
    def whatsapp_url(self):
        number = re.sub(r'\D', '', self.whatsapp)
        return f'https://wa.me/{number}' if number else ''


class HomeSection(TranslatedContent):
    class Key(models.TextChoices):
        HERO = 'home', 'Первый экран'
        DIRECTIONS = 'directions', 'Направления деятельности'
        ABOUT = 'about', 'Об объединении'
        MEMBERS = 'members', 'Члены объединения'
        EVENTS = 'events', 'Мероприятия'
        NEWS = 'news', 'Новости'
        COMMUNITY = 'community', 'Жизнь объединения'
        MEETINGS = 'meetings', 'Официальные встречи'
        COOPERATION = 'cooperation', 'Институциональное сотрудничество'

    key = models.CharField('Блок', max_length=30, choices=Key.choices, unique=True)
    eyebrow = models.CharField('Надзаголовок', max_length=180, blank=True)
    title = models.TextField('Заголовок', max_length=300, help_text='В первом экране переносы строк сохраняются.')
    description = models.TextField('Описание', blank=True)
    image = photo_field('Фотография блока')
    image_alt = models.CharField('Описание фотографии', max_length=250, blank=True)
    link_label = models.CharField('Текст основной кнопки', max_length=100, blank=True)
    link_route = models.CharField('Страница основной кнопки', max_length=40, choices=PUBLIC_ROUTES, blank=True)
    secondary_label = models.CharField('Текст второй кнопки', max_length=100, blank=True)
    secondary_route = models.CharField('Страница второй кнопки', max_length=40, choices=PUBLIC_ROUTES, blank=True)
    items_limit = models.PositiveSmallIntegerField('Количество карточек', default=3, validators=[MinValueValidator(1), MaxValueValidator(24)])
    is_visible = models.BooleanField('Показывать на главной', default=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'блок главной страницы'
        verbose_name_plural = 'Блоки главной страницы'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.get_key_display()

    @property
    def template_name(self):
        return f'core/home_sections/{self.key}.html'

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        name = {'home': 'hero', 'about': 'about', 'events': 'event', 'news': 'news'}.get(self.key)
        return static(f'core/images/placeholders/home-{name}.svg') if name else ''

    @property
    def link_url(self):
        return reverse(f'core:{self.link_route}') if self.link_route else ''

    @property
    def secondary_url(self):
        return reverse(f'core:{self.secondary_route}') if self.secondary_route else ''


class HomeDirection(TranslatedContent):
    ICONS = [('handshake', 'Рукопожатие'), ('landmark', 'Культура'), ('hands-holding-circle', 'Солидарность'), ('people-group', 'Сообщество'), ('globe', 'Международные связи'), ('briefcase', 'Бизнес'), ('heart', 'Поддержка')]
    title = models.CharField('Название', max_length=150)
    description = models.TextField('Описание')
    icon = models.CharField('Иконка', max_length=40, choices=ICONS, default='handshake')
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_published = models.BooleanField('Показывать', default=True)

    class Meta:
        verbose_name = 'направление деятельности'
        verbose_name_plural = 'Направления деятельности'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.title


class GalleryPhoto(TranslatedContent):
    title = models.CharField('Подпись', max_length=180)
    image = photo_field('Фотография')
    image_alt = models.CharField('Описание изображения', max_length=250, blank=True)
    placeholder = models.CharField('Заглушка', max_length=150, default='core/images/placeholders/home-gallery-1.svg', editable=False)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_published = models.BooleanField('Показывать', default=True)

    class Meta:
        verbose_name = 'фотография галереи'
        verbose_name_plural = 'Галерея'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.title

    @property
    def image_url(self):
        return self.image.url if self.image else static(self.placeholder)


class BoardMember(DemoContent):
    name = models.CharField('Имя и фамилия', max_length=200)
    position = models.CharField('Должность в объединении', max_length=200)
    photo = photo_field('Фотография')
    biography = models.TextField('Краткая биография', blank=True)
    company = models.ForeignKey(Member, verbose_name='Компания', null=True, blank=True, on_delete=models.SET_NULL)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_published = models.BooleanField('Опубликовано', default=False)

    class Meta:
        verbose_name = 'член совета правления'
        verbose_name_plural = 'Совет правления'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.name


class MenuItem(TranslatedContent):
    title = models.CharField('Название', max_length=150)
    parent = models.ForeignKey('self', verbose_name='Родительский пункт', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    route = models.CharField('Раздел сайта', max_length=40, choices=PUBLIC_ROUTES, blank=True)
    page = models.ForeignKey(Page, verbose_name='Информационная страница', null=True, blank=True, on_delete=models.SET_NULL)
    external_url = models.URLField('Внешняя ссылка', blank=True, validators=[URLValidator(schemes=['http', 'https'])])
    is_enabled = models.BooleanField('Ссылка активна', default=True)
    is_visible = models.BooleanField('Показывать', default=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'пункт меню'
        verbose_name_plural = 'Меню сайта'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return f'{self.parent.title} → {self.title}' if self.parent_id else self.title

    def clean(self):
        super().clean()
        parent = MenuItem.objects.filter(pk=self.parent_id).only('parent_id').first() if self.parent_id else None
        if self.parent_id and (self.parent_id == self.pk or (parent and parent.parent_id)):
            raise ValidationError({'parent': 'Допустим только один уровень выпадающего меню.'})
        if self.parent_id and self.pk and self.children.exists():
            raise ValidationError({'parent': 'Пункт с подпунктами нельзя вложить в другой пункт.'})
        if sum(bool(value) for value in (self.route, self.page_id, self.external_url)) > 1:
            raise ValidationError('Выберите один тип ссылки: раздел, страницу или внешний адрес.')
        if self.is_enabled and not any((self.route, self.page_id, self.external_url)):
            raise ValidationError('У активного пункта должен быть выбран адрес перехода.')

    @property
    def url(self):
        if not self.is_enabled:
            return ''
        if self.route:
            return reverse(f'core:{self.route}')
        if self.page_id and self.page.is_published:
            return self.page.get_absolute_url()
        return self.external_url


class MembershipApplication(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        REVIEW = 'review', 'На рассмотрении'
        APPROVED = 'approved', 'Принята'
        REJECTED = 'rejected', 'Отклонена'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    language = models.CharField('Язык заявки', max_length=2, choices=settings.LANGUAGES, default='ru', editable=False)
    company_name = models.CharField('Название фирмы', max_length=200)
    activity_description = models.TextField('Сфера деятельности и краткая информация', max_length=2000)
    tax_id = models.CharField('ИНН организации', max_length=30)
    full_name = models.CharField('ФИО заявителя', max_length=200)
    position = models.CharField('Должность', max_length=200)
    organization_address = models.CharField('Адрес организации', max_length=400)
    work_phone = models.CharField('Рабочий телефон', max_length=60, blank=True)
    mobile_phone = models.CharField('Мобильный телефон', max_length=60)
    email = models.EmailField('Электронная почта')
    recommendations = models.TextField('Рекомендации', max_length=1500, blank=True)
    information_source = models.CharField('Источник информации об объединении', max_length=500, blank=True)
    declaration_accepted = models.BooleanField('Заявление о вступлении подтверждено', default=False)
    declaration_text = models.TextField('Текст подтверждённого заявления', editable=False)
    status = models.CharField('Статус заявки', max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    membership_number = models.CharField('Членский номер', max_length=50, blank=True)
    secretary_name = models.CharField('Генеральный секретарь', max_length=200, blank=True)
    proposed_on = models.DateField('Дата предложения кандидатуры', null=True, blank=True)
    decision_number = models.CharField('Номер решения совета правления', max_length=60, blank=True)
    decision_date = models.DateField('Дата решения', null=True, blank=True)
    decision_reason = models.TextField('Причина / основание решения', max_length=3000, blank=True)
    chairperson_name = models.CharField('Председатель совета правления', max_length=200, blank=True)
    created_at = models.DateTimeField('Дата подачи', default=timezone.now, editable=False, db_index=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    reviewed_at = models.DateTimeField('Последнее рассмотрение', null=True, editable=False)
    reviewed_by = models.ForeignKey('auth.User', verbose_name='Рассмотрел сотрудник',
        on_delete=models.SET_NULL, null=True, editable=False, related_name='+')
    # Private documents live with the record, outside the public media directory.
    submitted_pdf = models.BinaryField('Исходный PDF', editable=False, default=bytes)
    current_pdf = models.BinaryField('PDF с результатами рассмотрения', editable=False, default=bytes)

    class Meta:
        verbose_name = 'заявка на членство'
        verbose_name_plural = 'Заявки на членство'
        ordering = ['-created_at', 'pk']

    def __str__(self):
        return f'{self.company_name} · {self.full_name}'

    @property
    def reference(self):
        return self.pk.hex.upper()

    def clean(self):
        super().clean()
        errors = {}
        if not self.declaration_accepted:
            errors['declaration_accepted'] = _('Подтвердите заявление о вступлении.')
        if self.status in {self.Status.APPROVED, self.Status.REJECTED}:
            for field in ('decision_number', 'decision_date', 'chairperson_name'):
                if not getattr(self, field):
                    errors[field] = 'Заполните поле для окончательного решения.'
        if self.status == self.Status.APPROVED and not self.membership_number:
            errors['membership_number'] = 'Укажите членский номер при принятии в объединение.'
        if self.status == self.Status.REJECTED and not self.decision_reason.strip():
            errors['decision_reason'] = 'Укажите причину отказа.'
        if errors:
            raise ValidationError(errors)


class OfficialMeetingQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class OfficialMeeting(DemoContent):
    title = models.CharField('Название встречи', max_length=250)
    slug = models.SlugField('Адрес публикации', max_length=180, unique=True)
    date = models.DateField('Дата встречи', db_index=True)
    participants = models.TextField('Участники встречи', max_length=2000)
    purpose = models.TextField('Цель встречи', max_length=2000)
    outcomes = models.TextField('Краткие итоги', max_length=5000)
    image = photo_field('Основная фотография')
    image_alt = models.CharField('Описание фотографии', max_length=250, blank=True)
    meta_description = models.CharField('Описание для поисковых систем', max_length=300, blank=True)
    is_published = models.BooleanField('Опубликовано', default=False, db_index=True)
    published_at = models.DateTimeField('Дата публикации', default=timezone.now, db_index=True)
    objects = OfficialMeetingQuerySet.as_manager()

    class Meta:
        verbose_name = 'официальная встреча'
        verbose_name_plural = 'Официальные встречи'
        ordering = ['-date', '-published_at', '-pk']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('core:meeting_detail', kwargs={'slug': self.slug})

    @property
    def image_url(self):
        return self.image.url if self.image else ''


class MeetingPhoto(TranslatedContent):
    meeting = models.ForeignKey(OfficialMeeting, verbose_name='Встреча', on_delete=models.CASCADE, related_name='photos')
    image = photo_field('Фотография', blank=False)
    caption = models.CharField('Подпись', max_length=250, blank=True)
    image_alt = models.CharField('Описание фотографии', max_length=250, blank=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'фотография встречи'
        verbose_name_plural = 'Фотографии встречи'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.caption or 'Фотография встречи'


class InstitutionalCooperation(TranslatedContent):
    DEFAULT_LOGOS = [
        ('president-kyrgyzstan', 'Президент Кыргызской Республики'),
        ('cabinet-kyrgyzstan', 'Кабинет Министров Кыргызской Республики'),
        ('turkiye-embassy', 'Посольство Турецкой Республики'),
    ]
    ICONS = [
        ('scale-balanced', 'Противодействие коррупции'),
        ('chart-line', 'Инвестиции'),
        ('landmark', 'Государственные и дипломатические связи'),
        ('handshake', 'Сотрудничество'),
        ('globe', 'Международные связи'),
    ]
    title = models.CharField('Название направления', max_length=250)
    description = models.TextField('Информация о сотрудничестве', max_length=2500)
    icon = models.CharField('Иконка', max_length=40, choices=ICONS, default='handshake')
    image = photo_field('Логотип или изображение')
    default_logo = models.CharField(
        'Стандартный логотип', max_length=40, choices=DEFAULT_LOGOS, blank=True,
        help_text='Используется, если собственное изображение не загружено.',
    )
    website = models.URLField('Ссылка на подробную информацию', blank=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_published = models.BooleanField('Опубликовано', default=False)

    class Meta:
        verbose_name = 'институциональное сотрудничество'
        verbose_name_plural = 'Институциональное сотрудничество'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.title

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        if self.default_logo in dict(self.DEFAULT_LOGOS):
            return static(f'core/images/institutions/{self.default_logo}.png')
        return static('core/images/placeholders/institution.svg')


class VacancyQuerySet(models.QuerySet):
    def open(self):
        return self.filter(
            is_published=True, is_closed=False, company__is_published=True,
            published_at__lte=timezone.now(),
        ).filter(Q(closes_on__isnull=True) | Q(closes_on__gte=timezone.localdate()))


class Vacancy(DemoContent):
    class Employment(models.TextChoices):
        FULL_TIME = 'full_time', _('Полная занятость')
        PART_TIME = 'part_time', _('Частичная занятость')
        PROJECT = 'project', _('Проектная работа')
        INTERNSHIP = 'internship', _('Стажировка')

    class WorkMode(models.TextChoices):
        OFFICE = 'office', _('В офисе')
        REMOTE = 'remote', _('Удалённо')
        HYBRID = 'hybrid', _('Гибридный формат')

    title = models.CharField('Название вакансии', max_length=200)
    slug = models.SlugField('Адрес страницы', max_length=180, unique=True)
    company = models.ForeignKey(Member, verbose_name='Компания — член объединения',
        on_delete=models.PROTECT, related_name='vacancies',
        help_text='Вакансии показываются только у опубликованных компаний.')
    location = models.CharField('Город или место работы', max_length=160, blank=True)
    employment = models.CharField('Занятость', max_length=20, choices=Employment.choices, default=Employment.FULL_TIME)
    work_mode = models.CharField('Формат работы', max_length=20, choices=WorkMode.choices, default=WorkMode.OFFICE)
    salary = models.CharField('Зарплата', max_length=140, blank=True, help_text='Например: от 50 000 сом. Можно оставить пустым.')
    description = models.TextField('Описание и задачи', max_length=12000)
    requirements = models.TextField('Требования', max_length=6000, blank=True)
    conditions = models.TextField('Условия', max_length=6000, blank=True)
    published_at = models.DateTimeField('Дата публикации', default=timezone.now, db_index=True)
    closes_on = models.DateField('Приём откликов до', null=True, blank=True, help_text='Включительно. Без даты — до ручного закрытия.')
    is_published = models.BooleanField('Опубликовано', default=False, db_index=True)
    is_closed = models.BooleanField('Вакансия закрыта', default=False)
    objects = VacancyQuerySet.as_manager()

    class Meta:
        verbose_name = 'вакансия'
        verbose_name_plural = 'Вакансии'
        ordering = ['-published_at', '-pk']

    def __str__(self):
        return f'{self.title} · {self.company.name}'

    def get_absolute_url(self):
        return reverse('core:vacancy_detail', kwargs={'slug': self.slug})


class CareerApplication(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        REVIEW = 'review', 'На рассмотрении'
        INTERVIEW = 'interview', 'Приглашён на собеседование'
        CLOSED = 'closed', 'Рассмотрение завершено'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    language = models.CharField('Язык заявки', max_length=2, choices=settings.LANGUAGES, default='ru', editable=False)
    vacancy = models.ForeignKey(Vacancy, verbose_name='Вакансия', on_delete=models.SET_NULL,
        related_name='applications', blank=True, null=True)
    vacancy_title = models.CharField('Вакансия на момент отправки', max_length=200, blank=True)
    company_name = models.CharField('Компания на момент отправки', max_length=200, blank=True)
    full_name = models.CharField('Имя и фамилия', max_length=200)
    email = models.EmailField('Электронная почта')
    phone = models.CharField('Телефон', max_length=60)
    city = models.CharField('Город проживания', max_length=120, blank=True)
    desired_position = models.CharField('Желаемая должность', max_length=200)
    cover_letter = models.TextField('О себе и своём опыте', max_length=6000, blank=True)
    resume_data = models.BinaryField('Резюме', editable=False)
    resume_name = models.CharField('Имя файла резюме', max_length=200)
    resume_content_type = models.CharField('Формат файла', max_length=100)
    resume_size = models.PositiveIntegerField('Размер файла в байтах')
    consent_accepted = models.BooleanField('Согласие на обработку данных', default=False)
    consent_text = models.TextField('Текст согласия при отправке')
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    notes = models.TextField('Внутренние заметки', blank=True, max_length=10000)
    created_at = models.DateTimeField('Отправлена', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    reviewed_at = models.DateTimeField('Последнее рассмотрение', null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Рассмотрел', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_career_applications')

    class Meta:
        verbose_name = 'отклик и резюме'
        verbose_name_plural = 'Отклики и резюме'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.full_name} · {self.desired_position}'

    @property
    def reference(self):
        return self.pk.hex.upper()


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новое'
        IN_PROGRESS = 'in_progress', 'В работе'
        CLOSED = 'closed', 'Обработано'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    full_name = models.CharField('Ваше имя', max_length=150)
    email = models.EmailField('Электронная почта')
    phone = models.CharField('Телефон', max_length=60, blank=True)
    subject = models.CharField('Тема сообщения', max_length=200)
    message = models.TextField('Сообщение', max_length=5000)
    language = models.CharField('Язык обращения', max_length=2, choices=settings.LANGUAGES, default='ru')
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    notes = models.TextField('Внутренние заметки', max_length=10000, blank=True)
    created_at = models.DateTimeField('Получено', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'сообщение с сайта'
        verbose_name_plural = 'Сообщения с сайта'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.full_name} · {self.subject}'


class ApplicationRequestLimit(models.Model):
    """Atomic rate-limit buckets shared by every application worker."""

    key = models.CharField(max_length=64, primary_key=True, editable=False)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        default_permissions = ()

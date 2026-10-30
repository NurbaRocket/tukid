from io import BytesIO

from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin, UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .membership_constants import APPLICANT_FIELDS, BOARD_FIELDS
from .membership_pdf import build_membership_pdf
from .career_constants import CAREER_APPLICANT_FIELDS
from .localization import TranslationAdminMixin

from .models import (
    ActivitySector, BoardMember, Event, GalleryPhoto, HomeDirection, HomeSection,
    InstitutionalCooperation, MeetingPhoto, Member, MembershipApplication, MenuItem,
    News, NewsTag, OfficialMeeting, Page, SiteSettings, Vacancy, CareerApplication, ContactMessage,
)

admin.site.site_title = 'TUKID · Управление сайтом'
admin.site.site_header = 'TUKID'
admin.site.index_title = 'Обзор сайта'


class ContentAdmin(TranslationAdminMixin, ModelAdmin):
    list_per_page = 25
    save_on_top = True
    warn_unsaved_form = True
    compressed_fields = True

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in {'body', 'biography'} or (
            db_field.name == 'description' and self.model in {Member, Event}
        ) or (
            self.model is Vacancy and db_field.name in {'description', 'requirements', 'conditions'}
        ):
            kwargs['widget'] = WysiwygWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description='Изображение')
    def image_preview(self, obj):
        for name in ('image', 'photo', 'logo'):
            field = getattr(obj, name, None)
            if field:
                return format_html('<img src="{}" alt="" style="max-width:240px;max-height:150px;object-fit:contain;border-radius:8px">', field.url)
        if getattr(obj, 'image_url', ''):
            return format_html('<img src="{}" alt="" style="max-width:240px;max-height:150px;object-fit:contain;border-radius:8px">', obj.image_url)
        return 'Изображение не загружено'


class PublicationAdmin(ContentAdmin):
    actions = ['publish', 'unpublish']

    def set_publication(self, request, queryset, value):
        # Use object checks and standard admin logging for every changed entry.
        changed = 0
        for obj in queryset:
            if self.has_change_permission(request, obj):
                obj.is_published = value
                obj.save(update_fields=['is_published'])
                self.log_change(request, obj, 'Опубликовано' if value else 'Снято с публикации')
                changed += 1
        self.message_user(request, f'Обновлено записей: {changed}', messages.SUCCESS)

    @admin.action(description='Опубликовать выбранные записи', permissions=['change'])
    def publish(self, request, queryset):
        self.set_publication(request, queryset, True)

    @admin.action(description='Снять выбранные записи с публикации', permissions=['change'])
    def unpublish(self, request, queryset):
        self.set_publication(request, queryset, False)


@admin.register(SiteSettings)
class SiteSettingsAdmin(ContentAdmin):
    readonly_fields = ['branding_preview', 'updated_at']
    fieldsets = [
        ('Организация', {'fields': ['name', 'organization_name', 'site_description']}),
        ('Логотипы', {'fields': ['branding_preview', 'header_logo', 'footer_logo', 'favicon'], 'classes': ['tab']}),
        ('Контакты', {'fields': ['email', 'phone', 'whatsapp', 'address', 'maps_url', 'show_contact_bar'], 'classes': ['tab']}),
        ('Карта 2ГИС', {'fields': ['dgis_api_key', 'map_latitude', 'map_longitude', 'map_zoom'],
                      'description': 'Карта с отметкой офиса без карточки организации. Для встраивания нужен ключ RasterJS API из Менеджера Платформы 2ГИС. При изменении адреса обновите координаты.', 'classes': ['tab']}),
        ('Социальные сети', {'fields': ['facebook_url', 'instagram_url', 'telegram_url'], 'classes': ['tab']}),
        ('Футер', {'fields': ['footer_text', 'copyright_text', 'updated_at'], 'classes': ['tab']}),
    ]

    @admin.display(description='Текущий логотип')
    def branding_preview(self, obj):
        return format_html('<img src="{}" alt="TUKID" style="max-width:180px;max-height:90px;object-fit:contain">', obj.header_logo_url)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            return super().changelist_view(request, extra_context)
        obj = SiteSettings.objects.first()
        if obj:
            return redirect(reverse('admin:core_sitesettings_change', args=[obj.pk]))
        return super().changelist_view(request, extra_context)


@admin.register(Page)
class PageAdmin(PublicationAdmin):
    list_display = ['title', 'slug', 'is_published', 'updated_at']
    list_filter = ['is_published']
    search_fields = ['title', 'body']
    readonly_fields = ['image_preview', 'updated_at']
    fieldsets = [
        ('Страница', {'fields': ['title', 'slug', 'body', 'is_published']}),
        ('Обложка и поиск', {'fields': ['image_preview', 'image', 'image_alt', 'meta_description', 'updated_at'], 'classes': ['tab']}),
    ]

    def get_prepopulated_fields(self, request, obj=None):
        return {'slug': ('title',)} if obj is None else {}

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.slug in Page.Section.values:
            fields.append('slug')
        return fields

    def has_delete_permission(self, request, obj=None):
        if obj and obj.slug in Page.Section.values:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Reserved pages have fixed routes, so prevent deleting them in bulk.
        actions.pop('delete_selected', None)
        return actions


@admin.register(ActivitySector, NewsTag)
class NamedDirectoryAdmin(ContentAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Member)
class MemberAdmin(PublicationAdmin):
    list_display = ['name', 'city', 'director_name', 'is_published', 'sort_order']
    list_editable = ['is_published', 'sort_order']
    list_filter = ['is_published', 'is_demo', 'sectors', 'city']
    search_fields = ['name', 'director_name', 'description', 'email']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['news_tag']
    filter_horizontal = ['sectors']
    readonly_fields = ['image_preview', 'created_at', 'updated_at']
    fieldsets = [
        ('Компания', {'fields': ['name', 'slug', 'image_preview', 'logo', 'description', 'sectors', 'director_name']}),
        ('Контакты', {'fields': ['city', 'address', 'phone', 'email', 'website'], 'classes': ['tab']}),
        ('Публикация', {'fields': ['member_since', 'news_tag', 'is_published', 'is_demo', 'sort_order', 'created_at', 'updated_at'], 'classes': ['tab']}),
    ]


@admin.register(News)
class NewsAdmin(PublicationAdmin):
    list_display = ['title', 'is_tukid_news', 'is_published', 'published_at']
    list_filter = ['is_published', 'is_demo', 'is_tukid_news', 'tags']
    search_fields = ['title', 'summary', 'body']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['tags']
    date_hierarchy = 'published_at'
    readonly_fields = ['image_preview']
    fieldsets = [
        ('Новость', {'fields': ['title', 'slug', 'summary', 'body']}),
        ('Обложка', {'fields': ['image_preview', 'image', 'image_alt'], 'classes': ['tab']}),
        ('Публикация и поиск', {'fields': ['is_tukid_news', 'tags', 'is_published', 'is_demo', 'published_at', 'meta_description'], 'classes': ['tab']}),
    ]


@admin.register(Event)
class EventAdmin(PublicationAdmin):
    list_display = ['title', 'starts_at', 'ends_at', 'location', 'is_published']
    list_filter = ['is_published', 'is_demo', 'starts_at']
    search_fields = ['title', 'description', 'location']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'starts_at'
    readonly_fields = ['image_preview']
    fieldsets = [
        ('Мероприятие', {'fields': ['title', 'slug', 'description', 'is_published', 'is_demo']}),
        ('Дата и место', {'fields': ['starts_at', 'ends_at', 'location', 'registration_url'], 'classes': ['tab']}),
        ('Обложка', {'fields': ['image_preview', 'image', 'image_alt'], 'classes': ['tab']}),
    ]


class MeetingPhotoInline(TranslationAdminMixin, TabularInline):
    model = MeetingPhoto
    fields = ['image', 'caption', 'image_alt', 'sort_order']
    extra = 0


@admin.register(OfficialMeeting)
class OfficialMeetingAdmin(PublicationAdmin):
    list_display = ['title', 'date', 'is_published', 'published_at']
    list_filter = ['is_published', 'is_demo', 'date']
    search_fields = ['title', 'participants', 'purpose', 'outcomes']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'date'
    readonly_fields = ['image_preview']
    inlines = [MeetingPhotoInline]
    fieldsets = [
        ('Встреча', {'fields': ['title', 'slug', 'date', 'participants', 'purpose', 'outcomes']}),
        ('Основная фотография', {'fields': ['image_preview', 'image', 'image_alt'], 'classes': ['tab']}),
        ('Публикация', {'fields': ['is_published', 'is_demo', 'published_at', 'meta_description'], 'classes': ['tab']}),
    ]


@admin.register(InstitutionalCooperation)
class InstitutionalCooperationAdmin(PublicationAdmin):
    list_display = ['title', 'is_published', 'sort_order']
    list_editable = ['is_published', 'sort_order']
    list_filter = ['is_published']
    search_fields = ['title', 'description']
    readonly_fields = ['image_preview']
    fields = ['title', 'description', 'icon', 'image_preview', 'default_logo', 'image', 'website', 'sort_order', 'is_published']


@admin.register(HomeSection)
class HomeSectionAdmin(ContentAdmin):
    list_display = ['title', 'key', 'is_visible', 'sort_order']
    list_editable = ['is_visible', 'sort_order']
    list_filter = ['is_visible']
    search_fields = ['title', 'description']
    readonly_fields = ['image_preview']
    fieldsets = [
        ('Содержимое блока', {'fields': ['key', 'eyebrow', 'title', 'description']}),
        ('Изображение', {'fields': ['image_preview', 'image', 'image_alt'], 'classes': ['tab']}),
        ('Кнопки', {'fields': ['link_label', 'link_route', 'secondary_label', 'secondary_route'], 'classes': ['tab']}),
        ('Отображение', {'fields': ['items_limit', 'is_visible', 'sort_order'], 'classes': ['tab']}),
    ]

    def get_readonly_fields(self, request, obj=None):
        return [*self.readonly_fields, *(['key'] if obj else [])]

    def has_add_permission(self, request):
        return HomeSection.objects.count() < len(HomeSection.Key.choices) and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(HomeDirection)
class HomeDirectionAdmin(PublicationAdmin):
    list_display = ['title', 'icon', 'is_published', 'sort_order']
    list_editable = ['is_published', 'sort_order']
    search_fields = ['title', 'description']
    list_filter = ['is_published']


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(PublicationAdmin):
    list_display = ['title', 'is_published', 'sort_order']
    list_editable = ['is_published', 'sort_order']
    search_fields = ['title']
    list_filter = ['is_published']
    readonly_fields = ['image_preview']
    fields = ['title', 'image_preview', 'image', 'image_alt', 'is_published', 'sort_order']


@admin.register(BoardMember)
class BoardMemberAdmin(PublicationAdmin):
    list_display = ['name', 'position', 'company', 'is_published', 'sort_order']
    list_editable = ['is_published', 'sort_order']
    list_filter = ['is_published', 'is_demo']
    search_fields = ['name', 'position']
    autocomplete_fields = ['company']
    readonly_fields = ['image_preview']
    fields = ['name', 'position', 'image_preview', 'photo', 'biography', 'company', 'is_published', 'is_demo', 'sort_order']


@admin.register(MenuItem)
class MenuItemAdmin(ContentAdmin):
    list_display = ['title', 'parent', 'route', 'page', 'is_enabled', 'is_visible', 'sort_order']
    list_editable = ['is_enabled', 'is_visible', 'sort_order']
    list_filter = ['parent', 'is_visible', 'is_enabled']
    list_select_related = ['parent', 'page']
    search_fields = ['title']
    autocomplete_fields = ['page']
    fieldsets = [
        ('Пункт меню', {'fields': ['title', 'parent', 'sort_order', 'is_visible', 'is_enabled']}),
        ('Куда ведёт ссылка', {
            'description': 'Выберите один вариант: раздел сайта, информационную страницу или внешний адрес. Для неактивного пункта адрес можно оставить пустым.',
            'fields': ['route', 'page', 'external_url'],
        }),
    ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'parent':
            kwargs['queryset'] = MenuItem.objects.filter(parent__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MembershipApplication)
class MembershipApplicationAdmin(ContentAdmin):
    list_display = ['company_name', 'full_name', 'status', 'created_at', 'pdf_links']
    list_filter = ['status', 'created_at']
    search_fields = ['company_name', 'full_name', 'tax_id', 'email', 'mobile_phone', 'membership_number']
    date_hierarchy = 'created_at'
    readonly_fields = [
        *APPLICANT_FIELDS, 'reference', 'declaration_text', 'created_at',
        'updated_at', 'reviewed_at', 'reviewed_by', 'pdf_links', 'language',
    ]
    fieldsets = [
        ('Заявка', {'fields': ['reference', 'created_at', 'language', 'pdf_links']}),
        ('Данные кандидата', {'fields': APPLICANT_FIELDS, 'classes': ['tab']}),
        ('Совет правления', {'fields': BOARD_FIELDS, 'classes': ['tab']}),
        ('История', {'fields': ['declaration_text', 'reviewed_by', 'reviewed_at', 'updated_at'], 'classes': ['tab']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('reviewed_by').defer('submitted_pdf', 'current_pdf')

    def has_add_permission(self, request):
        return False

    @admin.display(description='PDF заявки')
    def pdf_links(self, obj):
        original = reverse('admin:core_membershipapplication_pdf', args=[obj.pk, 'original'])
        current = reverse('admin:core_membershipapplication_pdf', args=[obj.pk, 'current'])
        return format_html('<a href="{}">Исходная заявка</a><br><a href="{}">PDF с решением</a>', original, current)

    def get_urls(self):
        return [
            path('<uuid:application_id>/pdf/<str:version>/', self.admin_site.admin_view(self.pdf_view),
                name='core_membershipapplication_pdf'),
            *super().get_urls(),
        ]

    def pdf_view(self, request, application_id, version):
        obj = self.get_object(request, str(application_id))
        if obj is None or version not in {'original', 'current'}:
            raise Http404
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        data = obj.submitted_pdf if version == 'original' else obj.current_pdf
        if not data:
            raise Http404
        response = FileResponse(BytesIO(bytes(data)), content_type='application/pdf',
            as_attachment=True, filename=f'membership-{obj.reference}-{version}.pdf')
        response['Cache-Control'] = 'private, no-store, max-age=0'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    def save_model(self, request, obj, form, change):
        if set(form.changed_data).intersection(BOARD_FIELDS):
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user
            settings = SiteSettings.objects.first() or SiteSettings()
            obj.current_pdf = build_membership_pdf(obj, settings)
        super().save_model(request, obj, form, change)


@admin.register(Vacancy)
class VacancyAdmin(PublicationAdmin):
    list_display = ['title', 'company', 'location', 'is_published', 'is_closed', 'closes_on']
    list_editable = ['is_published', 'is_closed']
    list_filter = ['is_published', 'is_closed', 'is_demo', 'company', 'employment', 'work_mode']
    search_fields = ['title', 'company__name', 'description', 'location']
    autocomplete_fields = ['company']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = [
        ('Вакансия', {'fields': ['title', 'slug', 'company', 'description', 'requirements', 'conditions']}),
        ('Условия работы', {'fields': ['location', 'employment', 'work_mode', 'salary'], 'classes': ['tab']}),
        ('Публикация', {'fields': ['is_published', 'is_closed', 'published_at', 'closes_on', 'is_demo'], 'classes': ['tab']}),
    ]


@admin.register(CareerApplication)
class CareerApplicationAdmin(ContentAdmin):
    list_display = ['full_name', 'desired_position', 'company_name', 'status', 'created_at', 'resume_link']
    list_filter = ['status', 'vacancy__company', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'desired_position', 'vacancy_title', 'company_name']
    date_hierarchy = 'created_at'
    readonly_fields = [
        *CAREER_APPLICANT_FIELDS, 'reference', 'vacancy_title', 'company_name', 'resume_link',
        'resume_name', 'resume_size', 'resume_content_type', 'consent_text',
        'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'language',
    ]
    fieldsets = [
        ('Отклик', {'fields': ['reference', 'created_at', 'language', 'status', 'resume_link', 'vacancy', 'vacancy_title', 'company_name']}),
        ('Кандидат', {'fields': ['full_name', 'email', 'phone', 'city', 'desired_position', 'cover_letter'], 'classes': ['tab']}),
        ('Рассмотрение', {'fields': ['notes', 'reviewed_by', 'reviewed_at', 'updated_at'], 'classes': ['tab']}),
        ('Файл и согласие', {'fields': ['resume_name', 'resume_size', 'resume_content_type', 'consent_accepted', 'consent_text'], 'classes': ['tab']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vacancy__company', 'reviewed_by').defer('resume_data')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Резюме')
    def resume_link(self, obj):
        return format_html('<a href="{}">Скачать резюме</a>', reverse('admin:core_careerapplication_resume', args=[obj.pk]))

    def get_urls(self):
        return [path('<uuid:application_id>/resume/', self.admin_site.admin_view(self.resume_view),
            name='core_careerapplication_resume'), *super().get_urls()]

    def resume_view(self, request, application_id):
        obj = self.get_object(request, str(application_id))
        if obj is None:
            raise Http404
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        if not obj.resume_data:
            raise Http404
        response = FileResponse(BytesIO(bytes(obj.resume_data)), content_type=obj.resume_content_type,
            as_attachment=True, filename=obj.resume_name)
        response['Cache-Control'] = 'private, no-store, max-age=0'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = "sandbox; default-src 'none'"
        return response

    def save_model(self, request, obj, form, change):
        if {'status', 'notes'}.intersection(form.changed_data):
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ['subject', 'full_name', 'email', 'status', 'created_at']
    list_filter = ['status', 'language', 'created_at']
    search_fields = ['subject', 'full_name', 'email', 'phone', 'message']
    date_hierarchy = 'created_at'
    list_per_page = 25
    readonly_fields = ['full_name', 'email', 'phone', 'subject', 'message', 'language', 'created_at', 'updated_at']
    fieldsets = [
        ('Обращение', {'fields': ['subject', 'message', 'created_at', 'language']}),
        ('Контакты отправителя', {'fields': ['full_name', 'email', 'phone']}),
        ('Обработка', {'fields': ['status', 'notes', 'updated_at']}),
    ]

    def has_add_permission(self, request):
        return False


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin, ModelAdmin):
    pass

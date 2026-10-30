from copy import deepcopy
import re
import unicodedata

from django.db import models
from django.db.models import Q
from django.utils.translation import get_language


CONTENT_FIELDS = {
    'page': ('title', 'body', 'image_alt', 'meta_description'),
    'activitysector': ('name',),
    'newstag': ('name',),
    'member': ('name', 'address', 'city', 'description', 'director_name'),
    'news': ('title', 'summary', 'body', 'image_alt', 'meta_description'),
    'event': ('title', 'description', 'image_alt', 'location'),
    'sitesettings': ('name', 'organization_name', 'site_description', 'address', 'footer_text', 'copyright_text'),
    'homesection': ('eyebrow', 'title', 'description', 'image_alt', 'link_label', 'secondary_label'),
    'homedirection': ('title', 'description'),
    'galleryphoto': ('title', 'image_alt'),
    'boardmember': ('name', 'position', 'biography'),
    'menuitem': ('title',),
    'officialmeeting': ('title', 'participants', 'purpose', 'outcomes', 'image_alt', 'meta_description'),
    'meetingphoto': ('caption', 'image_alt'),
    'institutionalcooperation': ('title', 'description'),
    'vacancy': ('title', 'location', 'salary', 'description', 'requirements', 'conditions'),
}
CONTENT_LANGUAGES = (('ky', 'Перевод на кыргызский'), ('tr', 'Перевод на турецкий'))


class TranslatedContent(models.Model):
    # Original fields remain Russian, preserving existing records and admin forms.
    translations = models.JSONField('Переводы', default=dict, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def i18n(self):
        return {field: self.localized(field) for field in CONTENT_FIELDS.get(self._meta.model_name, ())}

    def localized(self, field, language=None):
        language = (language or get_language() or 'ru').split('-')[0]
        if language in {'ky', 'tr'} and field in CONTENT_FIELDS.get(self._meta.model_name, ()):
            translated = self.translations if isinstance(self.translations, dict) else {}
            values = translated.get(language, {})
            value = values.get(field) if isinstance(values, dict) else None
            if isinstance(value, str) and value.strip():
                return value
        return getattr(self, field, '')


def localized(value, field, language=None):
    return value.localized(field, language) if isinstance(value, TranslatedContent) else getattr(value, field, '')


def normalize_search_query(query):
    # Bound both the displayed query and the number of database conditions.
    query = unicodedata.normalize('NFC', query)[:200]
    return ' '.join(query.split()[:12])


def content_search(fields, query):
    result = Q()
    language = (get_language() or 'ru').split('-')[0]
    for term in normalize_search_query(query).split():
        matches = Q()
        # Escape user input: punctuation is literal, never a regex operator.
        # iregex also handles Cyrillic case on SQLite, unlike its LIKE operator.
        # PostgreSQL's case mapping depends on its locale. Treat the Turkish
        # dotted and dotless I explicitly so all supported databases agree.
        pattern = ''.join('[iIıİ]' if char in 'iIıİ' else re.escape(char) for char in term)
        for field in fields:
            matches |= Q(**{f'{field}__iregex': pattern})
            if language in {'ky', 'tr'}:
                parts = field.split('__')
                path = '__'.join([*parts[:-1], 'translations', language, parts[-1], 'iregex'])
                matches |= Q(**{path: pattern})
        result &= matches
    return result


def translated_form(base_form, model, formfield_callback=None):
    fields = CONTENT_FIELDS.get(model._meta.model_name, ())
    if not fields:
        return base_form

    class TranslationForm(base_form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            data = self.instance.translations or {}
            for code, _ in CONTENT_LANGUAGES:
                for name in fields:
                    key = f'{name}_{code}'
                    if key in self.fields:
                        self.initial[key] = data.get(code, {}).get(name, '')

        def save(self, commit=True):
            obj = super().save(commit=False)
            data = deepcopy(obj.translations or {})
            for code, _ in CONTENT_LANGUAGES:
                values = data.setdefault(code, {})
                for name in fields:
                    key = f'{name}_{code}'
                    if key in self.cleaned_data and self.add_prefix(key) in self.data:
                        value = self.cleaned_data[key]
                        if value:
                            values[name] = value
                        else:
                            values.pop(name, None)
                if not values:
                    data.pop(code, None)
            obj.translations = data
            if commit:
                obj.save()
                self.save_m2m()
            return obj

    declared = {}
    for code, _ in CONTENT_LANGUAGES:
        for name in fields:
            source = model._meta.get_field(name)
            factory = formfield_callback or (lambda source, **options: source.formfield(**options))
            field = factory(source, required=False, label=str(source.verbose_name))
            field.help_text = 'Если перевод не заполнен, используется русский текст.'
            declared[f'{name}_{code}'] = field
    return type(f'{model.__name__}TranslationForm', (TranslationForm,), declared)


class TranslationAdminMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django renders view-only fields through ModelAdmin accessors rather
        # than form.initial. These fields live in JSON, not on the model.
        for code, _ in CONTENT_LANGUAGES:
            for name in CONTENT_FIELDS.get(self.model._meta.model_name, ()):
                key = f'{name}_{code}'
                if not hasattr(self, key):
                    setattr(self, key, self.translation_accessor(name, code))

    def translation_accessor(self, name, language):
        def value(obj):
            data = obj.translations if isinstance(obj.translations, dict) else {}
            translated = data.get(language, {})
            text = translated.get(name, '') if isinstance(translated, dict) else ''
            # Return ordinary text so admin escapes HTML in stored translations.
            return text if isinstance(text, str) else ''

        value.__name__ = f'{name}_{language}'
        value.short_description = self.model._meta.get_field(name).verbose_name
        return value

    def get_form(self, request, obj=None, **kwargs):
        callback = lambda field, **options: self.formfield_for_dbfield(field, request, **options)
        kwargs['form'] = translated_form(kwargs.get('form', self.form), self.model, callback)
        return super().get_form(request, obj, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        callback = lambda field, **options: self.formfield_for_dbfield(field, request, **options)
        kwargs['form'] = translated_form(kwargs.get('form', self.form), self.model, callback)
        return super().get_formset(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        fields = CONTENT_FIELDS.get(self.model._meta.model_name, ())
        if not fields:
            return fieldsets
        translated = {f'{name}_{code}' for code, _ in CONTENT_LANGUAGES for name in fields}

        def original(items):
            result = []
            for value in items:
                if isinstance(value, (list, tuple)):
                    nested = original(value)
                    if nested:
                        result.append(tuple(nested))
                elif value not in translated:
                    result.append(value)
            return result

        result = [(title, {**options, 'fields': original(options['fields'])}) for title, options in fieldsets]
        for code, title in CONTENT_LANGUAGES:
            result.append((title, {'fields': [f'{name}_{code}' for name in fields], 'classes': ['collapse']}))
        return result
